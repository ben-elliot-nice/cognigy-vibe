# cognigy-mcp/cognigy_mcp/wizard_ui.py
from __future__ import annotations

import subprocess
import traceback
from dataclasses import dataclass

from rich.console import Console

console = Console()


@dataclass
class SubprocessResult:
    returncode: int
    stdout: str
    stderr: str


class StepFailure(Exception):
    def __init__(self, description: str, result: SubprocessResult) -> None:
        super().__init__(f"{description} failed with exit code {result.returncode}")
        self.description = description
        self.result = result


def run_subprocess(cmd: list[str], description: str, verbose: bool = False) -> SubprocessResult:
    if verbose:
        console.print(f"[dim]$ {' '.join(cmd)}[/dim]")
        proc = subprocess.run(cmd, capture_output=True, text=True)
        for stream in (proc.stdout, proc.stderr):
            for line in (stream or "").splitlines():
                console.print(f"  [dim]{line}[/dim]")
    else:
        with console.status(f"[bold cyan]{description}...[/bold cyan]"):
            proc = subprocess.run(cmd, capture_output=True, text=True)

    result = SubprocessResult(returncode=proc.returncode, stdout=proc.stdout, stderr=proc.stderr)
    if result.returncode != 0:
        raise StepFailure(description, result)
    console.print(f"[green]✓[/green] {description}")
    return result
