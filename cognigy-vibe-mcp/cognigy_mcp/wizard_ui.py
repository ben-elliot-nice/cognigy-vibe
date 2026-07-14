# cognigy-vibe-mcp/cognigy_mcp/wizard_ui.py
from __future__ import annotations

import subprocess
import traceback
from dataclasses import dataclass

from rich.console import Console
from rich.panel import Panel
from rich.rule import Rule
from rich.table import Table

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


def print_header(text: str) -> None:
    console.print()
    console.print(Panel(text, style="bold cyan"))


def print_section(number: int, title: str) -> None:
    console.print()
    console.print(Rule(f"[bold]{number}. {title}[/bold]", style="cyan"))


def print_summary(rows: list[tuple[str, str]]) -> None:
    table = Table(show_header=False, box=None)
    table.add_column(style="bold")
    table.add_column()
    for label, value in rows:
        table.add_row(label, value)
    console.print()
    console.print(Panel(table, title="Summary", border_style="green"))


def print_drift_table(rows: list[tuple[str, str, str, str]]) -> None:
    table = Table()
    table.add_column("surface")
    table.add_column("current")
    table.add_column("expected")
    table.add_column("status")
    style = {"ok": "green", "drift": "yellow", "missing": "dim"}
    for surface, current, expected, status in rows:
        s = style[status]
        table.add_row(surface, current, expected, f"[{s}]{status}[/{s}]")
    console.print()
    console.print(table)


def print_step(text: str) -> None:
    console.print(f"[cyan]›[/cyan] {text}")


def print_error_panel(message: str, exc: Exception, debug: bool = False, title: str = "Setup failed") -> None:
    body = message
    if isinstance(exc, StepFailure):
        captured = "\n".join(filter(None, [exc.result.stdout.strip(), exc.result.stderr.strip()]))
        if captured:
            body = f"{body}\n\n{captured}"
    if debug:
        tb = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))
        body = f"{body}\n\n{tb}"
    console.print()
    console.print(Panel(body, title=title, border_style="red"))
