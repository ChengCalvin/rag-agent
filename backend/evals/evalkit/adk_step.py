"""The `adk eval` commands for the generated evalsets (pure; the subprocess call is in the CLI).

One command per evalset file: the persona is in the file name, and `NOVAMART_USER` must be that
persona for the run (see `adk_evalset`). Authored, not run (ARCH-TEST-3). The detailed-results flag
is not used and the command output is never stored: it can hold replies and customer data (ERR-2).
"""

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class AdkCommand:
    """One `adk eval` invocation: the argv and the persona to put in `NOVAMART_USER`."""

    label: str
    persona: str
    argv: tuple[str, ...]


def adk_commands(evalsets_dir: Path, agent_dir: Path, only_set: str | None) -> list[AdkCommand]:
    """One `adk eval <agent dir> <evalset> --config_file_path <config>` command per evalset."""
    commands: list[AdkCommand] = []
    for evalset in sorted(evalsets_dir.glob("*/*.evalset.json")):
        set_name, persona = evalset.name.split(".")[:2]
        if only_set is not None and set_name != only_set:
            continue
        config = evalset.parent / "test_config.json"
        argv = (
            "adk",
            "eval",
            str(agent_dir),
            str(evalset),
            f"--config_file_path={config}",
        )
        commands.append(AdkCommand(f"{evalset.parent.name}/{evalset.name}", persona, argv))
    return commands


def adk_record(command: AdkCommand, exit_code: int) -> dict[str, object]:
    """What is kept of one `adk eval` run: the command label and its exit code, nothing else."""
    return {"command": command.label, "exit_code": exit_code}
