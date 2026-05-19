"""AI-assisted workflow composition for Scalable.

Generates workflow skeletons from natural-language descriptions or
structured specifications. Outputs reviewable files (workflow.py,
component YAML, README).
"""

from __future__ import annotations

import ast
import re
import textwrap
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from .backend import AIBackend, get_ai_backend
from .prompts.compose import COMPOSE_PROMPT, SYSTEM_PROMPT

__all__ = ["ComposeResult", "compose_workflow"]


#: Known model patterns for heuristic composition
_KNOWN_MODELS: dict[str, dict[str, Any]] = {
    "gcam": {
        "full_name": "GCAM",
        "language": "c++",
        "cpus": 6,
        "memory": "20G",
        "runtime": "apptainer",
        "tags": ["iam", "climate", "compiled"],
        "description": "Global Change Assessment Model",
    },
    "stitches": {
        "full_name": "Stitches",
        "language": "python",
        "cpus": 1,
        "memory": "50G",
        "runtime": "docker",
        "tags": ["climate", "python"],
        "description": "Climate pattern scaling",
    },
    "demeter": {
        "full_name": "Demeter",
        "language": "python",
        "cpus": 2,
        "memory": "8G",
        "runtime": "docker",
        "tags": ["land-use", "python"],
        "description": "Land use spatial downscaling",
    },
    "tethys": {
        "full_name": "Tethys",
        "language": "python",
        "cpus": 2,
        "memory": "8G",
        "runtime": "docker",
        "tags": ["water", "python"],
        "description": "Water demand model",
    },
    "xanthos": {
        "full_name": "Xanthos",
        "language": "python",
        "cpus": 2,
        "memory": "16G",
        "runtime": "docker",
        "tags": ["hydrology", "python"],
        "description": "Global hydrology model",
    },
    "hector": {
        "full_name": "Hector",
        "language": "c++",
        "cpus": 1,
        "memory": "4G",
        "runtime": "docker",
        "tags": ["climate", "compiled"],
        "description": "Simple climate model",
    },
}


@dataclass
class ComposeResult:
    """Result of workflow composition."""

    description: str
    workflow_py: str
    components_yaml: str
    readme: str
    detected_models: list[str] = field(default_factory=list)
    method: str = "heuristic"
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "description": self.description,
            "detected_models": self.detected_models,
            "method": self.method,
            "warnings": self.warnings,
            "files": {
                "workflow.py": self.workflow_py,
                "components.yaml": self.components_yaml,
                "README.generated.md": self.readme,
            },
        }

    def write_to_directory(self, output_dir: str | Path) -> list[str]:
        """Write generated files to a directory.

        Returns list of written file paths.
        """
        out = Path(output_dir)
        out.mkdir(parents=True, exist_ok=True)

        written: list[str] = []

        workflow_path = out / "workflow.py"
        workflow_path.write_text(self.workflow_py, encoding="utf-8")
        written.append(str(workflow_path))

        components_path = out / "components.yaml"
        components_path.write_text(self.components_yaml, encoding="utf-8")
        written.append(str(components_path))

        readme_path = out / "README.generated.md"
        readme_path.write_text(self.readme, encoding="utf-8")
        written.append(str(readme_path))

        return written


def compose_workflow(
    description: str,
    *,
    output_dir: str | Path | None = None,
    backend: AIBackend | None = None,
    no_ai: bool = False,
) -> ComposeResult:
    """Generate a workflow from a natural-language description.

    Parameters
    ----------
    description : str
        Natural-language description of the workflow to generate.
    output_dir : str | Path | None
        If provided, write generated files to this directory.
    backend : AIBackend | None
        AI backend for enhanced composition.
    no_ai : bool
        If True, skip LLM enhancement.

    Returns
    -------
    ComposeResult
        Generated workflow files and metadata.
    """
    if not description.strip():
        raise ValueError("Description cannot be empty")

    # Detect known models in the description
    detected = _detect_models(description)

    # Try AI enhancement
    if not no_ai:
        ai_backend = backend or get_ai_backend()
        if ai_backend.available():
            try:
                result = _compose_with_ai(description, detected, ai_backend)
                if output_dir:
                    result.write_to_directory(output_dir)
                return result
            except Exception:
                pass  # Fall through to heuristic

    # Heuristic composition
    result = _compose_heuristic(description, detected)
    if output_dir:
        result.write_to_directory(output_dir)
    return result


def _detect_models(description: str) -> list[str]:
    """Detect known model names in the description."""
    desc_lower = description.lower()
    detected: list[str] = []
    for model_key, info in _KNOWN_MODELS.items():
        if model_key in desc_lower or info["full_name"].lower() in desc_lower:
            detected.append(model_key)
    return detected


def _compose_heuristic(description: str, detected_models: list[str]) -> ComposeResult:
    """Generate workflow using template-based heuristics."""
    if not detected_models:
        # Generic workflow template
        return _compose_generic(description)

    # Generate workflow for detected models
    workflow_py = _generate_workflow_code(detected_models)
    components_yaml = _generate_components_yaml(detected_models)
    readme = _generate_readme(description, detected_models)

    warnings: list[str] = []
    if len(detected_models) == 1:
        warnings.append("Only one model detected - workflow may be simpler than intended")

    # Validate generated Python
    try:
        ast.parse(workflow_py)
    except SyntaxError as e:
        warnings.append(f"Generated workflow has syntax issues: {e}")

    return ComposeResult(
        description=description,
        workflow_py=workflow_py,
        components_yaml=components_yaml,
        readme=readme,
        detected_models=detected_models,
        method="heuristic",
        warnings=warnings,
    )


def _compose_generic(description: str) -> ComposeResult:
    """Generate a generic workflow template."""
    workflow_py = textwrap.dedent('''\
        """Generated workflow skeleton.

        Description: {description}

        This is a template - fill in task functions with your model logic.
        """

        from scalable import ScalableSession


        def run_task(input_data):
            """TODO: Implement your task logic here."""
            # Your model code goes here
            return {{"status": "completed", "input": input_data}}


        def main():
            """Execute the workflow."""
            session = ScalableSession.from_yaml("scalable.yaml", target="local")

            with session as client:
                future = client.submit(run_task, "example_input", tag="default")
                result = future.result()
                print(f"Result: {{result}}")


        if __name__ == "__main__":
            main()
    ''').format(description=description[:100])

    components_yaml = textwrap.dedent("""\
        # Generated component template
        # Customize for your model
        default:
          cpus: 2
          memory: 8G
          tags: [generic]
    """)

    readme = textwrap.dedent(f"""\
        # Generated Workflow

        ## Description

        {description}

        ## Files

        - `workflow.py` — Main workflow script (template)
        - `components.yaml` — Component definitions to merge into scalable.yaml

        ## Usage

        1. Review and customize `workflow.py` with your model logic
        2. Merge `components.yaml` into your `scalable.yaml`
        3. Run: `scalable run scalable.yaml --workflow workflow.py`

        ## Notes

        - This workflow was generated from a description with no known models detected
        - All task functions need implementation
        - Review resource allocations before running
    """)

    return ComposeResult(
        description=description,
        workflow_py=workflow_py,
        components_yaml=components_yaml,
        readme=readme,
        detected_models=[],
        method="heuristic",
        warnings=["No known models detected - generated generic template"],
    )


def _generate_workflow_code(models: list[str]) -> str:
    """Generate workflow.py for detected models."""
    imports = [
        '"""Generated Scalable workflow.',
        "",
        f"Models: {', '.join(m.upper() for m in models)}",
        "",
        "Review this file before execution. All task functions are stubs",
        "that need implementation with your specific model logic.",
        '"""',
        "",
        "from scalable import ScalableSession",
        "",
    ]

    functions: list[str] = []
    for model in models:
        info = _KNOWN_MODELS[model]
        func_name = f"run_{model}"
        functions.append(textwrap.dedent(f'''\

            def {func_name}(scenario, **kwargs):
                """Run {info["full_name"]} for a given scenario.

                TODO: Implement {info["full_name"]} execution logic.
                """
                # Your {info["full_name"]} code here
                print(f"Running {info['full_name']} for scenario: {{scenario}}")
                return {{"model": "{model}", "scenario": scenario, "status": "completed"}}
        '''))

    # Generate main function
    main_lines = [
        "",
        "",
        "def main():",
        '    """Execute the multi-model workflow."""',
        '    session = ScalableSession.from_yaml("scalable.yaml")',
        "",
        "    with session as client:",
    ]

    # Submit tasks in order
    for i, model in enumerate(models):
        info = _KNOWN_MODELS[model]
        func_name = f"run_{model}"
        var_name = f"future_{model}"
        main_lines.append(f'        # Stage {i+1}: {info["full_name"]}')
        main_lines.append(
            f'        {var_name} = client.submit({func_name}, "reference", tag="{model}")'
        )
        main_lines.append(f"        result_{model} = {var_name}.result()")
        main_lines.append(f'        print(f"{info["full_name"]} complete: {{result_{model}}}")')
        main_lines.append("")

    main_lines.append('    print("Workflow complete!")')
    main_lines.append("")
    main_lines.append("")
    main_lines.append('if __name__ == "__main__":')
    main_lines.append("    main()")
    main_lines.append("")

    return "\n".join(imports) + "\n".join(functions) + "\n".join(main_lines)


def _generate_components_yaml(models: list[str]) -> str:
    """Generate components YAML fragment."""
    components: dict[str, dict[str, Any]] = {}
    for model in models:
        info = _KNOWN_MODELS[model]
        component: dict[str, Any] = {
            "image": f"# TODO: set image for {info['full_name']}",
            "runtime": info["runtime"],
            "cpus": info["cpus"],
            "memory": info["memory"],
            "tags": info["tags"],
        }
        if info["cpus"] > 1:
            component["env"] = {"OMP_NUM_THREADS": str(info["cpus"])}
        components[model] = component

    header = "# Generated component definitions\n# Merge into your scalable.yaml under 'components:'\n\n"
    return header + yaml.dump(components, default_flow_style=False, sort_keys=False)


def _generate_readme(description: str, models: list[str]) -> str:
    """Generate README for the workflow."""
    model_list = "\n".join(
        f"- **{_KNOWN_MODELS[m]['full_name']}** ({m}): {_KNOWN_MODELS[m]['description']}"
        for m in models
    )

    return textwrap.dedent(f"""\
        # Generated Workflow

        ## Description

        {description}

        ## Models

        {model_list}

        ## Files

        - `workflow.py` — Main workflow script with task stubs
        - `components.yaml` — Component definitions to merge into scalable.yaml

        ## Usage

        1. Review `workflow.py` and implement task function bodies
        2. Merge `components.yaml` into your `scalable.yaml` under `components:`
        3. Configure target-specific settings in `scalable.yaml`
        4. Run: `scalable run scalable.yaml --workflow workflow.py`

        ## Notes

        - All task functions are stubs that need implementation
        - Container images need to be specified in components.yaml
        - Resource estimates are defaults and may need tuning
        - Review mount paths for your data layout
    """)


def _compose_with_ai(
    description: str,
    detected_models: list[str],
    backend: AIBackend,
) -> ComposeResult:
    """Generate workflow with AI enhancement."""
    prompt = COMPOSE_PROMPT.format(description=description)
    response = backend.complete(prompt, system=SYSTEM_PROMPT)

    # Parse response into files
    workflow_py = _extract_file_section(response, "workflow.py") or ""
    components_yaml = _extract_file_section(response, "components.yaml") or ""
    readme = _extract_file_section(response, "README.generated.md") or ""

    warnings: list[str] = ["AI-generated - review all files before use"]

    # Validate Python
    if workflow_py:
        try:
            ast.parse(workflow_py)
        except SyntaxError as e:
            warnings.append(f"Generated Python has syntax issues: {e}")

    return ComposeResult(
        description=description,
        workflow_py=workflow_py or "# AI generation failed - use heuristic template",
        components_yaml=components_yaml or "# AI generation failed",
        readme=readme or f"# Generated from: {description}",
        detected_models=detected_models,
        method="ai-enhanced",
        warnings=warnings,
    )


def _extract_file_section(response: str, filename: str) -> str | None:
    """Extract a file section from AI response delimited by --- filename ---."""
    pattern = rf"---\s*{re.escape(filename)}\s*---\s*\n(.*?)(?=---\s*\w|$)"
    match = re.search(pattern, response, re.DOTALL)
    if match:
        return match.group(1).strip()
    return None
