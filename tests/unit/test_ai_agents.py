"""Unit tests for scalable.ai.agents package — PydanticAI integration.

Tests cover:
* Agent base classes and dependency injection
* Model provider resolution
* Structured output models
* Tool registration
* Output validators
* Multi-agent coordination patterns
* Heuristic fallback behavior
"""

from __future__ import annotations

import pytest

from scalable.ai.agents.base import AgentConfig, AgentDeps, AgentResult, ScalableAgent
from scalable.ai.agents.coordination import (
    AgentChain,
    AgentPipeline,
    ChainStep,
    DelegatingAgent,
    PipelineStage,
)
from scalable.ai.agents.models import (
    ComposeOutput,
    DiagnosisOutput,
    ExplanationOutput,
    FailureDetail,
    MigrationOutput,
    OnboardingOutput,
    WorkflowComponent,
)
from scalable.ai.agents.providers import (
    ModelProvider,
    get_model_provider,
    list_providers,
    resolve_model_string,
)
from scalable.ai.agents.tools import ToolRegistry, get_default_registry, tool
from scalable.ai.agents.validators import (
    OutputValidator,
    confidence_validator,
    non_empty_list_validator,
    non_empty_string_validator,
    validate_output,
)


# ===========================================================================
# AgentDeps tests
# ===========================================================================


class TestAgentDeps:
    def test_default_construction(self):
        deps = AgentDeps()
        assert deps.run_context == {}
        assert deps.settings == {}
        assert deps.telemetry == {}
        assert deps.tools_enabled is True
        assert deps.max_retries == 3

    def test_custom_construction(self):
        deps = AgentDeps(
            run_context={"run_id": "abc123"},
            settings={"model": "gpt-4o"},
            telemetry={"failures": [{"type": "oom"}]},
            tools_enabled=False,
            max_retries=5,
        )
        assert deps.run_context["run_id"] == "abc123"
        assert deps.settings["model"] == "gpt-4o"
        assert deps.telemetry["failures"] == [{"type": "oom"}]
        assert deps.tools_enabled is False
        assert deps.max_retries == 5


# ===========================================================================
# AgentConfig tests
# ===========================================================================


class TestAgentConfig:
    def test_default_config(self):
        config = AgentConfig()
        assert config.model is None
        assert config.temperature == 0.0
        assert config.max_tokens == 4096
        assert config.max_retries == 3
        assert config.retry_delay == 1.0
        assert config.timeout == 120.0
        assert config.result_retries == 2
        assert config.system_prompt is None

    def test_custom_config(self):
        config = AgentConfig(
            model="openai:gpt-4o",
            temperature=0.7,
            max_tokens=8192,
            max_retries=5,
        )
        assert config.model == "openai:gpt-4o"
        assert config.temperature == 0.7
        assert config.max_tokens == 8192
        assert config.max_retries == 5


# ===========================================================================
# AgentResult tests
# ===========================================================================


class TestAgentResult:
    def test_basic_result(self):
        output = DiagnosisOutput(
            summary="Test diagnosis",
            root_cause="oom",
            severity="high",
        )
        result = AgentResult(
            data=output,
            model_name="openai:gpt-4o",
            usage={"request_tokens": 100, "response_tokens": 50, "total_tokens": 150},
            retries=0,
        )
        assert result.data.summary == "Test diagnosis"
        assert result.model_name == "openai:gpt-4o"
        assert result.usage["total_tokens"] == 150
        assert result.retries == 0

    def test_to_dict(self):
        output = DiagnosisOutput(
            summary="Test",
            root_cause="unknown",
            severity="low",
        )
        result = AgentResult(data=output, model_name="heuristic")
        d = result.to_dict()
        assert d["model_name"] == "heuristic"
        assert d["retries"] == 0
        assert "data" in d


# ===========================================================================
# ScalableAgent tests (heuristic fallback)
# ===========================================================================


class ConcreteTestAgent(ScalableAgent[DiagnosisOutput]):
    """Concrete agent for testing base class behavior."""

    def __init__(self):
        super().__init__(
            result_type=DiagnosisOutput,
            name="test-agent",
            system_prompt="You are a test agent.",
        )

    def _heuristic_fallback(self, prompt: str, deps: AgentDeps) -> DiagnosisOutput:
        return DiagnosisOutput(
            summary=f"Heuristic result for: {prompt}",
            root_cause="test",
            severity="low",
        )


class TestScalableAgent:
    def test_heuristic_fallback_when_no_model(self, monkeypatch):
        monkeypatch.setattr("scalable.common.settings.ai_backend", "none")
        agent = ConcreteTestAgent()
        result = agent.run_sync("test prompt")
        assert result.data.summary == "Heuristic result for: test prompt"
        assert result.model_name == "heuristic"
        assert result.retries == 0

    def test_model_string_resolution_openai(self, monkeypatch):
        monkeypatch.setattr("scalable.common.settings.ai_backend", "openai")
        monkeypatch.setattr("scalable.common.settings.ai_model", "gpt-4o-mini")
        agent = ConcreteTestAgent()
        assert agent._get_model_string() == "openai:gpt-4o-mini"

    def test_model_string_resolution_anthropic(self, monkeypatch):
        monkeypatch.setattr("scalable.common.settings.ai_backend", "anthropic")
        monkeypatch.setattr("scalable.common.settings.ai_model", None)
        agent = ConcreteTestAgent()
        assert agent._get_model_string() == "anthropic:claude-sonnet-4-20250514"

    def test_model_string_resolution_google(self, monkeypatch):
        monkeypatch.setattr("scalable.common.settings.ai_backend", "google")
        monkeypatch.setattr("scalable.common.settings.ai_model", "gemini-1.5-flash")
        agent = ConcreteTestAgent()
        assert agent._get_model_string() == "google-gla:gemini-1.5-flash"

    def test_model_string_resolution_ollama(self, monkeypatch):
        monkeypatch.setattr("scalable.common.settings.ai_backend", "ollama")
        monkeypatch.setattr("scalable.common.settings.ai_model", "mistral")
        agent = ConcreteTestAgent()
        assert agent._get_model_string() == "ollama:mistral"

    def test_model_string_resolution_none(self, monkeypatch):
        monkeypatch.setattr("scalable.common.settings.ai_backend", "none")
        agent = ConcreteTestAgent()
        assert agent._get_model_string() is None

    def test_model_string_from_config(self):
        config = AgentConfig(model="groq:llama-3.1-70b-versatile")
        agent = ConcreteTestAgent()
        agent.config = config
        assert agent._get_model_string() == "groq:llama-3.1-70b-versatile"

    def test_missing_heuristic_raises(self):
        agent = ScalableAgent(
            result_type=DiagnosisOutput,
            name="no-fallback",
            system_prompt="test",
        )
        with pytest.raises(NotImplementedError, match="must implement _heuristic_fallback"):
            agent._heuristic_fallback("test", AgentDeps())


# ===========================================================================
# ModelProvider tests
# ===========================================================================


class TestModelProvider:
    def test_construction(self):
        provider = ModelProvider(
            name="openai",
            model="gpt-4o",
            model_string="openai:gpt-4o",
        )
        assert provider.name == "openai"
        assert provider.model == "gpt-4o"
        assert provider.model_string == "openai:gpt-4o"

    def test_custom_endpoint(self):
        provider = ModelProvider(
            name="openai",
            model="local-model",
            model_string="openai:local-model",
            endpoint="http://localhost:8080/v1",
            api_key="test-key",
        )
        assert provider.endpoint == "http://localhost:8080/v1"
        assert provider.api_key == "test-key"


class TestResolveModelString:
    def test_none_backend(self):
        assert resolve_model_string(None) is None
        assert resolve_model_string("none") is None

    def test_openai_default(self):
        assert resolve_model_string("openai") == "openai:gpt-4o"

    def test_openai_custom_model(self):
        assert resolve_model_string("openai", "gpt-4o-mini") == "openai:gpt-4o-mini"

    def test_anthropic_default(self):
        assert resolve_model_string("anthropic") == "anthropic:claude-sonnet-4-20250514"

    def test_google_default(self):
        assert resolve_model_string("google") == "google:gemini-1.5-pro"

    def test_full_model_string_passthrough(self):
        assert resolve_model_string("openai:custom-model") == "openai:custom-model"

    def test_ollama_default(self):
        assert resolve_model_string("ollama") == "ollama:llama3"


class TestGetModelProvider:
    def test_returns_none_for_no_backend(self, monkeypatch):
        monkeypatch.setattr("scalable.common.settings.ai_backend", "none")
        monkeypatch.setattr("scalable.common.settings.ai_model", None)
        monkeypatch.setattr("scalable.common.settings.ai_endpoint", None)
        result = get_model_provider()
        assert result is None

    def test_returns_provider_for_openai(self, monkeypatch):
        monkeypatch.setattr("scalable.common.settings.ai_backend", "openai")
        monkeypatch.setattr("scalable.common.settings.ai_model", "gpt-4o")
        monkeypatch.setattr("scalable.common.settings.ai_endpoint", None)
        provider = get_model_provider()
        assert provider is not None
        assert provider.name == "openai"
        assert provider.model == "gpt-4o"
        assert provider.model_string == "openai:gpt-4o"

    def test_explicit_params_override_settings(self, monkeypatch):
        monkeypatch.setattr("scalable.common.settings.ai_backend", "openai")
        monkeypatch.setattr("scalable.common.settings.ai_model", "gpt-4o")
        monkeypatch.setattr("scalable.common.settings.ai_endpoint", None)
        provider = get_model_provider(backend="anthropic", model="claude-sonnet-4-20250514")
        assert provider is not None
        assert provider.name == "anthropic"
        assert provider.model == "claude-sonnet-4-20250514"


class TestListProviders:
    def test_lists_all_providers(self):
        providers = list_providers()
        names = [p["name"] for p in providers]
        assert "openai" in names
        assert "anthropic" in names
        assert "google" in names
        assert "ollama" in names
        assert "groq" in names

    def test_provider_info_structure(self):
        providers = list_providers()
        for p in providers:
            assert "name" in p
            assert "default_model" in p
            assert "model_string" in p
            assert "available" in p
            assert isinstance(p["available"], bool)


# ===========================================================================
# Structured Output Models tests
# ===========================================================================


class TestDiagnosisOutput:
    def test_minimal_construction(self):
        output = DiagnosisOutput(summary="No issues", root_cause="none", severity="low")
        assert output.summary == "No issues"
        assert output.classifications == []
        assert output.requires_manual_intervention is False

    def test_with_classifications(self):
        detail = FailureDetail(
            failure_class="oom",
            confidence="high",
            evidence=["Container killed with signal 9", "Memory usage peaked at 32G"],
            suggested_fixes=["Increase memory to 64G", "Reduce batch size"],
        )
        output = DiagnosisOutput(
            summary="OOM failure detected",
            classifications=[detail],
            root_cause="oom",
            severity="high",
            requires_manual_intervention=True,
        )
        assert len(output.classifications) == 1
        assert output.classifications[0].failure_class == "oom"
        assert len(output.classifications[0].evidence) == 2


class TestExplanationOutput:
    def test_construction(self):
        output = ExplanationOutput(
            overview="Plan deploys 3 components on Kubernetes",
            resource_narrative="8 CPUs, 32G memory total",
            recommendations=["Consider scaling workers"],
        )
        assert "Kubernetes" in output.overview
        assert len(output.recommendations) == 1


class TestComposeOutput:
    def test_with_components(self):
        comp = WorkflowComponent(
            name="gcam",
            runtime="apptainer",
            cpus=6,
            memory="20G",
            tags=["iam", "climate"],
        )
        output = ComposeOutput(
            description="GCAM workflow",
            components=[comp],
            execution_order=["gcam"],
            parallelism_groups=[["gcam"]],
        )
        assert len(output.components) == 1
        assert output.components[0].name == "gcam"
        assert output.components[0].cpus == 6

    def test_workflow_component_defaults(self):
        comp = WorkflowComponent(name="test")
        assert comp.runtime == "docker"
        assert comp.cpus == 1
        assert comp.memory == "4G"
        assert comp.dependencies == []


class TestMigrationOutput:
    def test_construction(self):
        output = MigrationOutput(
            goal="Migrate to Kubernetes",
            changes=["Add kubernetes target", "Configure namespace"],
            overlay_yaml="targets:\n  kubernetes:\n    provider: kubernetes",
        )
        assert "Kubernetes" in output.goal
        assert len(output.changes) == 2
        assert output.breaking_changes == []
        assert output.rollback_steps == []


class TestOnboardingOutput:
    def test_construction(self):
        output = OnboardingOutput(
            name="my-model",
            language="python",
            runtime="docker",
            cpus=2,
            memory="8G",
            confidence="medium",
        )
        assert output.name == "my-model"
        assert output.language == "python"
        assert output.confidence == "medium"


# ===========================================================================
# ToolRegistry tests
# ===========================================================================


class TestToolRegistry:
    def test_register_decorator_without_args(self):
        registry = ToolRegistry()

        @registry.register
        def my_tool(x: int) -> str:
            """My tool description."""
            return str(x)

        assert "my_tool" in registry
        assert registry.get("my_tool") is my_tool
        assert len(registry) == 1

    def test_register_decorator_with_args(self):
        registry = ToolRegistry()

        @registry.register(name="custom_name", retries=3)
        def my_tool(x: int) -> str:
            """Tool desc."""
            return str(x)

        assert "custom_name" in registry
        assert "my_tool" not in registry
        meta = registry.get_metadata("custom_name")
        assert meta is not None
        assert meta["retries"] == 3

    def test_unregister(self):
        registry = ToolRegistry()

        @registry.register
        def temp_tool() -> str:
            """Temp."""
            return "temp"

        assert "temp_tool" in registry
        registry.unregister("temp_tool")
        assert "temp_tool" not in registry

    def test_list_tools(self):
        registry = ToolRegistry()

        @registry.register
        def tool_a() -> str:
            """A."""
            return "a"

        @registry.register
        def tool_b() -> str:
            """B."""
            return "b"

        tools = registry.list_tools()
        assert "tool_a" in tools
        assert "tool_b" in tools

    def test_module_level_decorator(self):
        # Ensure the @tool decorator registers in default registry
        default_reg = get_default_registry()
        initial_count = len(default_reg)

        @tool
        def test_global_tool(name: str) -> str:
            """A test tool."""
            return f"hello {name}"

        assert len(default_reg) == initial_count + 1
        assert "test_global_tool" in default_reg

        # Cleanup
        default_reg.unregister("test_global_tool")


# ===========================================================================
# OutputValidator tests
# ===========================================================================


class TestOutputValidator:
    def test_passing_validation(self):
        validator = OutputValidator()
        validator.add_rule(
            lambda r: r.summary != "",
            "Summary must not be empty",
        )
        output = DiagnosisOutput(summary="Has content", root_cause="x", severity="low")
        errors = validator.validate(output)
        assert errors == []
        assert validator.is_valid(output)

    def test_failing_validation(self):
        validator = OutputValidator()
        validator.add_rule(
            lambda r: len(r.classifications) > 0,
            "At least one classification required",
        )
        output = DiagnosisOutput(summary="Empty", root_cause="x", severity="low")
        errors = validator.validate(output)
        assert len(errors) == 1
        assert "classification" in errors[0]

    def test_field_rule(self):
        validator = OutputValidator()
        validator.add_field_rule(
            "summary",
            lambda val: len(val) >= 10,
            "must be at least 10 characters",
        )
        output = DiagnosisOutput(summary="Short", root_cause="x", severity="low")
        errors = validator.validate(output)
        assert len(errors) == 1
        assert "summary" in errors[0]

    def test_multiple_rules(self):
        validator = OutputValidator()
        validator.add_rule(lambda r: r.summary != "", "Summary required")
        validator.add_rule(lambda r: r.severity in ("low", "medium", "high", "critical"), "Invalid severity")
        validator.add_field_rule("root_cause", lambda v: v != "unknown", "Root cause must be identified")

        output = DiagnosisOutput(summary="", root_cause="unknown", severity="invalid")
        errors = validator.validate(output)
        assert len(errors) == 3


class TestValidateOutput:
    def test_valid_output(self):
        output = DiagnosisOutput(summary="Test", root_cause="oom", severity="high")
        is_valid, errors = validate_output(output)
        assert is_valid is True
        assert errors == []

    def test_with_custom_validators(self):
        validator = non_empty_string_validator("summary")
        output = DiagnosisOutput(summary="", root_cause="x", severity="low")
        is_valid, errors = validate_output(output, validators=[validator])
        assert is_valid is False
        assert len(errors) > 0


class TestPrebuiltValidators:
    def test_non_empty_string(self):
        v = non_empty_string_validator("summary")
        output = DiagnosisOutput(summary="Hello", root_cause="x", severity="low")
        assert v.is_valid(output)

        output2 = DiagnosisOutput(summary="", root_cause="x", severity="low")
        assert not v.is_valid(output2)

    def test_non_empty_list(self):
        v = non_empty_list_validator("classifications", min_items=1)
        output = DiagnosisOutput(summary="X", root_cause="x", severity="low", classifications=[])
        assert not v.is_valid(output)

        detail = FailureDetail(failure_class="oom", confidence="high")
        output2 = DiagnosisOutput(summary="X", root_cause="oom", severity="high", classifications=[detail])
        assert v.is_valid(output2)

    def test_confidence_validator(self):
        v = confidence_validator()
        output = OnboardingOutput(name="test", confidence="high")
        assert v.is_valid(output)

        output2 = OnboardingOutput(name="test", confidence="invalid")
        assert not v.is_valid(output2)


# ===========================================================================
# Multi-agent coordination tests
# ===========================================================================


class MockAgent(ScalableAgent[DiagnosisOutput]):
    """Mock agent that returns predictable heuristic results."""

    def __init__(self, name: str = "mock"):
        super().__init__(
            result_type=DiagnosisOutput,
            name=name,
            system_prompt="Mock agent",
        )

    def _heuristic_fallback(self, prompt: str, deps: AgentDeps) -> DiagnosisOutput:
        return DiagnosisOutput(
            summary=f"[{self.name}] processed: {prompt[:50]}",
            root_cause="mock",
            severity="low",
        )


class TestAgentChain:
    def test_chain_sync(self, monkeypatch):
        monkeypatch.setattr("scalable.common.settings.ai_backend", "none")

        agent1 = MockAgent("step1")
        agent2 = MockAgent("step2")

        chain = AgentChain(steps=[
            ChainStep(agent=agent1, name="first"),
            ChainStep(agent=agent2, name="second", prompt_template="Continue: {previous_result}"),
        ])

        results = chain.run_sync("initial prompt")
        assert len(results) == 2
        assert "[step1]" in results[0].data.summary
        assert "[step2]" in results[1].data.summary

    def test_single_step_chain(self, monkeypatch):
        monkeypatch.setattr("scalable.common.settings.ai_backend", "none")

        agent = MockAgent("solo")
        chain = AgentChain(steps=[ChainStep(agent=agent, name="only")])

        results = chain.run_sync("test")
        assert len(results) == 1
        assert "[solo]" in results[0].data.summary


class TestAgentPipeline:
    def test_pipeline_all_stages(self, monkeypatch):
        monkeypatch.setattr("scalable.common.settings.ai_backend", "none")

        agent1 = MockAgent("stage1")
        agent2 = MockAgent("stage2")

        pipeline = AgentPipeline(stages=[
            PipelineStage(agent=agent1, name="first"),
            PipelineStage(agent=agent2, name="second"),
        ])

        result = pipeline.run_sync("test input")
        assert "[stage2]" in result.data.summary

    def test_pipeline_with_condition_skip(self, monkeypatch):
        monkeypatch.setattr("scalable.common.settings.ai_backend", "none")

        agent1 = MockAgent("triage")
        agent2 = MockAgent("deep")

        # Second stage only runs if severity is "critical"
        pipeline = AgentPipeline(stages=[
            PipelineStage(agent=agent1, name="triage"),
            PipelineStage(
                agent=agent2,
                name="deep",
                condition=lambda r: r.data.severity == "critical",
            ),
        ])

        result = pipeline.run_sync("non-critical issue")
        # Since mock returns "low" severity, stage2 is skipped
        assert "[triage]" in result.data.summary

    def test_pipeline_empty_raises(self):
        pipeline = AgentPipeline(stages=[])
        with pytest.raises(RuntimeError, match="no results"):
            pipeline.run_sync("test")


class TestDelegatingAgent:
    def test_delegation_routing(self, monkeypatch):
        monkeypatch.setattr("scalable.common.settings.ai_backend", "none")

        diag_agent = MockAgent("diagnose")
        explain_agent = MockAgent("explain")

        delegator = DelegatingAgent(
            name="orchestrator",
            agents={
                "diagnose": diag_agent,
                "explain": explain_agent,
            },
            router=lambda prompt, deps: "diagnose" if "error" in prompt.lower() else "explain",
        )

        results = delegator.run_sync("Error: OOM killed")
        assert "diagnose" in results
        assert "[diagnose]" in results["diagnose"].data.summary

    def test_delegation_to_explain(self, monkeypatch):
        monkeypatch.setattr("scalable.common.settings.ai_backend", "none")

        diag_agent = MockAgent("diagnose")
        explain_agent = MockAgent("explain")

        delegator = DelegatingAgent(
            name="orchestrator",
            agents={
                "diagnose": diag_agent,
                "explain": explain_agent,
            },
            router=lambda prompt, deps: "diagnose" if "error" in prompt.lower() else "explain",
        )

        results = delegator.run_sync("Explain this plan")
        assert "explain" in results

    def test_no_router_raises(self):
        delegator = DelegatingAgent(name="test")
        with pytest.raises(RuntimeError, match="No router configured"):
            delegator.run_sync("test")

    def test_multi_target_routing(self, monkeypatch):
        monkeypatch.setattr("scalable.common.settings.ai_backend", "none")

        agent1 = MockAgent("a1")
        agent2 = MockAgent("a2")

        delegator = DelegatingAgent(
            name="multi",
            agents={"a1": agent1, "a2": agent2},
            router=lambda prompt, deps: ["a1", "a2"],
        )

        results = delegator.run_sync("process both")
        assert "a1" in results
        assert "a2" in results


# ===========================================================================
# Concrete Agent tests (heuristic fallback)
# ===========================================================================


class TestDiagnosisAgent:
    def test_heuristic_with_failures(self, monkeypatch):
        monkeypatch.setattr("scalable.common.settings.ai_backend", "none")

        from scalable.ai.agents.diagnosis_agent import DiagnosisAgent

        agent = DiagnosisAgent()
        deps = AgentDeps(
            telemetry={
                "failures": [
                    {
                        "task_id": "t1",
                        "failure_class": "oom",
                        "message": "Container killed: OOM",
                        "details": {},
                    }
                ],
                "tasks": [
                    {"task_id": "t1", "state": "failed"},
                ],
                "resources": [],
            }
        )
        result = agent.run_sync("Diagnose run", deps=deps)
        assert result.data.root_cause != "none"
        assert len(result.data.classifications) > 0

    def test_heuristic_no_failures(self, monkeypatch):
        monkeypatch.setattr("scalable.common.settings.ai_backend", "none")

        from scalable.ai.agents.diagnosis_agent import DiagnosisAgent

        agent = DiagnosisAgent()
        deps = AgentDeps(
            telemetry={"failures": [], "tasks": [], "resources": []}
        )
        result = agent.run_sync("Diagnose run", deps=deps)
        assert result.data.root_cause == "none"
        assert result.data.severity == "low"


class TestExplanationAgent:
    def test_heuristic_plan_explanation(self, monkeypatch):
        monkeypatch.setattr("scalable.common.settings.ai_backend", "none")

        from scalable.ai.agents.explanation_agent import ExplanationAgent

        agent = ExplanationAgent()
        deps = AgentDeps(
            run_context={
                "plan": {
                    "target": "production",
                    "provider": "kubernetes",
                    "task_to_component": {"task1": "comp1"},
                    "scale_plan": {
                        "workers_by_tag": {"comp1": 3},
                        "resources_by_tag": {"comp1": {"cpus": 4, "memory": "16G"}},
                    },
                }
            }
        )
        result = agent.run_sync("Explain the plan", deps=deps)
        assert "kubernetes" in result.data.overview.lower() or "production" in result.data.overview.lower()
        assert result.data.resource_narrative != ""


class TestComposeAgent:
    def test_heuristic_known_model(self, monkeypatch):
        monkeypatch.setattr("scalable.common.settings.ai_backend", "none")

        from scalable.ai.agents.compose_agent import ComposeAgent

        agent = ComposeAgent()
        result = agent.run_sync("Create a workflow with GCAM and Demeter")
        assert len(result.data.components) >= 2
        names = [c.name for c in result.data.components]
        assert "gcam" in names
        assert "demeter" in names

    def test_heuristic_generic(self, monkeypatch):
        monkeypatch.setattr("scalable.common.settings.ai_backend", "none")

        from scalable.ai.agents.compose_agent import ComposeAgent

        agent = ComposeAgent()
        result = agent.run_sync("Create a generic data processing pipeline")
        assert len(result.data.components) >= 1
        assert len(result.data.warnings) > 0


class TestMigrationAgent:
    def test_heuristic_provider_migration(self, monkeypatch):
        monkeypatch.setattr("scalable.common.settings.ai_backend", "none")

        from scalable.ai.agents.migration_agent import MigrationAgent

        agent = MigrationAgent()
        deps = AgentDeps(
            run_context={
                "to_provider": "kubernetes",
                "goal": "Migrate to Kubernetes",
                "manifest": {},
            }
        )
        result = agent.run_sync("Migrate to kubernetes", deps=deps)
        assert "kubernetes" in result.data.goal.lower() or "Kubernetes" in result.data.goal
        assert result.data.overlay_yaml != ""
        assert len(result.data.changes) > 0

    def test_heuristic_unknown_provider(self, monkeypatch):
        monkeypatch.setattr("scalable.common.settings.ai_backend", "none")

        from scalable.ai.agents.migration_agent import MigrationAgent

        agent = MigrationAgent()
        deps = AgentDeps(
            run_context={
                "to_provider": "unknown_provider",
                "goal": "Migrate to unknown",
                "manifest": {},
            }
        )
        result = agent.run_sync("Migrate", deps=deps)
        assert len(result.data.warnings) > 0


class TestOnboardingAgent:
    def test_heuristic_with_scan(self, monkeypatch):
        monkeypatch.setattr("scalable.common.settings.ai_backend", "none")

        from scalable.ai.agents.onboarding_agent import OnboardingAgent
        from scalable.ai.heuristics import DirectoryScanResult

        scan = DirectoryScanResult(
            path="/tmp/test-model",
            languages=["python"],
            build_systems=["pyproject.toml"],
            container_files=["Dockerfile"],
            estimated_cpus=2,
            estimated_memory="8G",
            suggested_runtime="docker",
            suggested_tags=["python", "ml"],
            confidence="medium",
        )

        agent = OnboardingAgent()
        deps = AgentDeps(run_context={"scan": scan, "name": "test-model"})
        result = agent.run_sync("Analyze model", deps=deps)
        assert result.data.name == "test-model"
        assert result.data.language == "python"
        assert result.data.cpus == 2
        assert result.data.confidence == "medium"

    def test_heuristic_no_scan(self, monkeypatch):
        monkeypatch.setattr("scalable.common.settings.ai_backend", "none")

        from scalable.ai.agents.onboarding_agent import OnboardingAgent

        agent = OnboardingAgent()
        deps = AgentDeps(run_context={"name": "empty-model"})
        result = agent.run_sync("Analyze model", deps=deps)
        assert result.data.name == "empty-model"
        assert result.data.confidence == "low"


# ===========================================================================
# Backend integration tests (new providers)
# ===========================================================================


class TestBackendAnthropicGoogle:
    def test_anthropic_backend_registered(self):
        from scalable.ai.backend import _BACKEND_REGISTRY
        assert "anthropic" in _BACKEND_REGISTRY

    def test_google_backend_registered(self):
        from scalable.ai.backend import _BACKEND_REGISTRY
        assert "google" in _BACKEND_REGISTRY

    def test_anthropic_backend_name(self):
        from scalable.ai.backend import AnthropicBackend
        b = AnthropicBackend()
        assert b.name == "anthropic"

    def test_google_backend_name(self):
        from scalable.ai.backend import GoogleBackend
        b = GoogleBackend()
        assert b.name == "google"

    def test_anthropic_default_model(self):
        from scalable.ai.backend import AnthropicBackend
        b = AnthropicBackend()
        assert b._model == "claude-sonnet-4-20250514"

    def test_google_default_model(self):
        from scalable.ai.backend import GoogleBackend
        b = GoogleBackend()
        assert b._model == "gemini-1.5-pro"
