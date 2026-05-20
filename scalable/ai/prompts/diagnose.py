"""Prompt templates for failure diagnosis assistant."""

from __future__ import annotations

SYSTEM_PROMPT = """\
You are a failure diagnosis assistant for the Scalable scientific workflow framework.
Analyze run telemetry (task events, failures, resource usage) and provide:
1. Root cause classification
2. Supporting evidence from the telemetry
3. Suggested fixes in order of likelihood

Be specific and actionable. Reference Scalable manifest fields and CLI commands.
"""

DIAGNOSIS_PROMPT = """\
Diagnose this failed Scalable run:

Run metadata:
{run_metadata}

Failure events:
{failure_events}

Task events (final states):
{task_events}

Resource events:
{resource_events}

Provide:
1. Most likely failure cause (one of: oom, walltime, mount_missing, import_error,
   connection, credential, model_runtime, unknown)
2. Confidence level (high/medium/low)
3. Evidence supporting the diagnosis
4. Ordered list of suggested fixes
"""
