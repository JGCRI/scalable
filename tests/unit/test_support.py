"""Unit tests for :mod:`scalable.support` — Slurm command builders + parsers."""

from __future__ import annotations

import pytest

from scalable.support import (
    apptainer_module_command,
    core_command,
    jobcheck_command,
    jobid_command,
    memory_command,
    nodelist_command,
    parse_nodelist,
    salloc_command,
)

# ---------------------------------------------------------------------------
# salloc_command
# ---------------------------------------------------------------------------


def test_salloc_minimal():
    cmd = salloc_command(account="GCIMS")
    assert cmd[0] == "salloc"
    assert "-A" in cmd
    assert cmd[cmd.index("-A") + 1] == "GCIMS"
    # exclusive defaults to True
    assert "--exclusive" in cmd
    # always ends with --no-shell
    assert cmd[-1] == "--no-shell"


def test_salloc_full_options():
    cmd = salloc_command(
        account="A",
        chdir="/work",
        clusters="c1",
        exclusive=False,
        gpus="2",
        name="job",
        memory="8G",
        nodes=1,
        partition="general",
        time="01:00:00",
        extras=["--qos=high"],
    )
    assert "--exclusive" not in cmd
    assert "--qos=high" in cmd
    assert cmd[cmd.index("-N") + 1] == 1
    assert cmd[cmd.index("-p") + 1] == "general"
    assert cmd[cmd.index("-t") + 1] == "01:00:00"
    assert cmd[cmd.index("-D") + 1] == "/work"


# ---------------------------------------------------------------------------
# Apptainer / process commands
# ---------------------------------------------------------------------------


def test_apptainer_module_command_no_version():
    out = apptainer_module_command(None)
    assert out == ["module", "load", "apptainer"]


def test_apptainer_module_command_with_version():
    out = apptainer_module_command("1.3.2")
    # shlex tokenizes "module load apptainer/1.3.2" into 3 tokens
    assert out[-1] == "apptainer/1.3.2"


def test_memory_command_returns_shell_pipeline():
    out = memory_command()
    # Pipeline survives shlex tokenization
    assert "free" in out


def test_core_command():
    assert core_command() == ["nproc", "--all"]


def test_jobid_command():
    out = jobid_command("J1")
    assert any("--name=J1" in part for part in out)


def test_nodelist_command():
    out = nodelist_command("J1")
    assert any("%N" in part for part in out)


def test_jobcheck_command():
    out = jobcheck_command("12345")
    assert "12345" in " ".join(out)


# ---------------------------------------------------------------------------
# parse_nodelist
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "input_,expected",
    [
        ("node01", ["node01"]),
        ("node[01-03]", ["node01", "node02", "node03"]),
        ("node[01,03,05]", ["node01", "node03", "node05"]),
        ("node[01-02,05-06]", ["node01", "node02", "node05", "node06"]),
        ("compute[100-102]", ["compute100", "compute101", "compute102"]),
    ],
)
def test_parse_nodelist(input_, expected):
    assert parse_nodelist(input_) == expected
