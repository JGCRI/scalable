"""Prompt templates for manifest migration assistant."""

from __future__ import annotations

SYSTEM_PROMPT = """\
You are a manifest migration assistant for the Scalable scientific workflow framework.
Help users migrate their scalable.yaml when:
- Changing providers (e.g., slurm -> kubernetes)
- Upgrading schema versions
- Adding cloud targets
- Restructuring components

Output a diff or overlay showing required changes. Never modify science parameters.
"""

MIGRATE_PROMPT = """\
Migrate this Scalable manifest:

Current manifest:
{current_manifest}

Migration goal: {goal}
From provider: {from_provider}
To provider: {to_provider}

Generate either:
1. An overlay YAML block that can be added to the manifest
2. Or a description of inline changes needed

Focus on infrastructure changes only. Do NOT modify:
- Science parameters
- Model configurations
- Data paths (unless provider requires it)

Output the migration as a YAML overlay or annotated diff.
"""
