import asyncio
import time
from pathlib import Path

import click
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn
from rich.table import Table
from rich.live import Live
from rich.layout import Layout

from .config import settings
from .models.context import ReviewContext
from .models.report import ReviewReport
from .parser.diff_parser import (
    build_context_from_diff,
    build_context_from_directory,
    build_context_from_file,
)
from .agents.orchestrator import OrchestratorAgent
from .agents.security import SecurityAgent
from .agents.performance import PerformanceAgent
from .agents.standards import StandardsAgent
from .agents.logic import LogicAgent
from .agents.aggregator import AggregatorAgent
from .reporters.markdown import save_markdown
from .reporters.html import save_html

console = Console()


def _check_api_key():
    if not settings.anthropic_api_key or "sk-ant-" not in settings.anthropic_api_key:
        console.print(
            "[red]Error:[/red] Valid ANTHROPIC_API_KEY not set. "
            "Create a .env file or set the environment variable.",
        )
        raise click.Abort()


class ProgressDisplay:
    """Manages Rich progress display for multi-agent execution."""

    def __init__(self):
        self.status: dict[str, str] = {}

    def create_layout(self) -> Layout:
        layout = Layout()
        layout.split(
            Layout(name="header", size=3),
            Layout(name="body"),
        )
        layout["body"].split_row(
            Layout(name="agents", ratio=2),
            Layout(name="stats", ratio=1),
        )
        return layout

    def render(self) -> Panel:
        agent_lines = []
        for name, status in self.status.items():
            icon = {
                "pending": "⏳",
                "running": "[cyan]🔄[/cyan]",
                "completed": "[green]✅[/green]",
                "failed": "[red]❌[/red]",
            }.get(status, "⏳")
            agent_lines.append(f"{icon} {name}: {status}")

        return Panel(
            "\n".join(agent_lines) if agent_lines else "Initializing...",
            title="Agent Status",
            border_style="blue",
        )


async def run_review_pipeline(context: ReviewContext, verbose: bool = False) -> ReviewReport:
    """Execute the full multi-agent review pipeline."""
    start_time = time.time()
    progress = ProgressDisplay()

    # Phase 1: Orchestration
    progress.status = {
        "orchestrator": "running",
        "security": "pending",
        "performance": "pending",
        "standards": "pending",
        "logic": "pending",
        "aggregator": "pending",
    }

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
        console=console,
    ) as prog:
        orchestrate_task = prog.add_task(
            "[cyan]Orchestrator analyzing codebase...", total=1
        )

        orchestrator = OrchestratorAgent()
        if verbose:
            console.print("[cyan]Orchestrator:[/cyan] Analyzing code structure and planning review...")
        plan = await orchestrator.analyze(context)
        prog.update(orchestrate_task, completed=1)

        if verbose:
            console.print(f"[cyan]Orchestrator:[/cyan] Plan created — "
                          f"agents: {plan.agents_to_run}, "
                          f"focus areas: {len(plan.focus_areas)}")

        progress.status["orchestrator"] = "completed"

    # Phase 2: Parallel specialized agent execution
    agent_map = {
        "security": (SecurityAgent(), "security"),
        "performance": (PerformanceAgent(), "performance"),
        "standards": (StandardsAgent(), "standards"),
        "logic": (LogicAgent(), "logic"),
    }

    agent_tasks = {}
    for agent_name in plan.agents_to_run:
        if agent_name in agent_map:
            agent, _ = agent_map[agent_name]
            progress.status[agent_name] = "running"
            agent_tasks[agent_name] = agent.analyze(context, plan)

    if not agent_tasks:
        # Run all agents by default
        for agent_name, (agent, _) in agent_map.items():
            progress.status[agent_name] = "running"
            agent_tasks[agent_name] = agent.analyze(context, plan)

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as prog:
        agent_progress = {
            name: prog.add_task(f"[yellow]{name} agent analyzing...", total=1)
            for name in agent_tasks
        }

        if verbose:
            console.print("[yellow]Phase 2:[/yellow] Running specialized agents in parallel...")

        # Execute all agents concurrently
        results = await asyncio.gather(
            *agent_tasks.values(),
            return_exceptions=True,
        )

        agent_results: dict[str, list] = {}
        for (name, _), result in zip(agent_tasks.items(), results):
            if isinstance(result, Exception):
                console.print(f"[red]Agent {name} failed:[/red] {result}")
                progress.status[name] = "failed"
                agent_results[name] = []
            else:
                progress.status[name] = "completed"
                agent_results[name] = result
                prog.update(agent_progress[name], completed=1)
                if verbose:
                    console.print(f"[green]{name}:[/green] {len(result)} findings")

    # Phase 3: Aggregation
    progress.status["aggregator"] = "running"

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as prog:
        agg_task = prog.add_task("[magenta]Aggregator consolidating findings...", total=1)

        aggregator = AggregatorAgent()
        review_time = time.time() - start_time
        report = await aggregator.aggregate(context, agent_results, review_time)
        prog.update(agg_task, completed=1)

        progress.status["aggregator"] = "completed"

    if verbose:
        console.print(f"[magenta]Aggregator:[/magenta] {report.summary.total_findings} "
                      f"findings consolidated in {review_time:.1f}s")

    return report


def _print_summary(report: ReviewReport):
    """Print a formatted summary to the console."""
    s = report.summary

    # Risk score panel
    risk_color = "red" if s.risk_score >= 76 else "yellow" if s.risk_score >= 51 else "green"
    risk_level = "CRITICAL" if s.risk_score >= 76 else "HIGH" if s.risk_score >= 51 else "MEDIUM" if s.risk_score >= 26 else "LOW"

    console.print(Panel(
        f"[bold {risk_color}]Risk Score: {s.risk_score}/100 — {risk_level}[/bold {risk_color}]",
        title="Risk Assessment",
        border_style=risk_color,
    ))

    # Findings table
    table = Table(title="Review Summary")
    table.add_column("Category", style="cyan")
    table.add_column("Critical", style="red")
    table.add_column("High", style="yellow")
    table.add_column("Medium", style="yellow")
    table.add_column("Low", style="blue")
    table.add_column("Info", style="dim")
    table.add_column("Total", style="bold")

    table.add_row(
        "Security", str(s.security_count), "-", "-", "-", "-",
        str(s.security_count),
    )
    table.add_row(
        "Performance", str(s.performance_count), "-", "-", "-", "-",
        str(s.performance_count),
    )
    table.add_row(
        "Standards", str(s.standards_count), "-", "-", "-", "-",
        str(s.standards_count),
    )
    table.add_row(
        "Logic", str(s.logic_count), "-", "-", "-", "-",
        str(s.logic_count),
    )
    table.add_row(
        "[bold]Total[/bold]",
        f"[bold red]{s.critical}[/bold red]",
        f"[bold yellow]{s.high}[/bold yellow]",
        str(s.medium),
        str(s.low),
        str(s.info),
        f"[bold]{s.total_findings}[/bold]",
    )

    console.print(table)

    # Top recommendations
    if report.recommendations:
        console.print("\n[bold]Top Recommendations:[/bold]")
        for i, rec in enumerate(report.recommendations[:5], 1):
            console.print(f"  {i}. {rec}")


@click.group()
@click.version_option(version="1.0.0")
def cli():
    """AI-Driven Full-Chain Code Review & Security Audit System.

    Uses multiple specialized AI agents to review code for security vulnerabilities,
    performance issues, standards violations, and logic errors.
    """


@cli.command()
@click.argument("path", type=click.Path(exists=True))
@click.option("--output-dir", "-o", default=None, help="Output directory for reports")
@click.option("--format", "-f", "fmt", default="both",
              type=click.Choice(["md", "html", "both"]),
              help="Report format")
@click.option("--verbose", "-v", is_flag=True, help="Show detailed agent output")
def file(path: str, output_dir: str | None, fmt: str, verbose: bool):
    """Review a single file."""
    _check_api_key()

    filepath = Path(path).resolve()
    console.print(f"[bold]Reviewing file:[/bold] {filepath.name}")

    context = build_context_from_file(filepath)
    report = asyncio.run(run_review_pipeline(context, verbose=verbose))

    _save_and_display(report, output_dir, fmt, filepath.name)


@cli.command()
@click.argument("path", type=click.Path(exists=True))
@click.option("--output-dir", "-o", default=None, help="Output directory for reports")
@click.option("--format", "-f", "fmt", default="both",
              type=click.Choice(["md", "html", "both"]),
              help="Report format")
@click.option("--max-files", "-m", default=None, type=int, help="Max files to review")
@click.option("--verbose", "-v", is_flag=True, help="Show detailed agent output")
def dir(path: str, output_dir: str | None, fmt: str, max_files: int | None, verbose: bool):
    """Review all source files in a directory."""
    _check_api_key()

    dirpath = Path(path).resolve()
    max_f = max_files or settings.max_files_per_review

    console.print(f"[bold]Reviewing directory:[/bold] {dirpath} (max {max_f} files)")

    context = build_context_from_directory(dirpath, max_f)
    if not context.files:
        console.print("[yellow]No source files found in directory.[/yellow]")
        return

    console.print(f"Found {len(context.files)} files across {len(context.languages)} languages")
    report = asyncio.run(run_review_pipeline(context, verbose=verbose))

    _save_and_display(report, output_dir, fmt, dirpath.name)


@cli.command()
@click.argument("diff_file", type=click.Path(exists=True))
@click.option("--output-dir", "-o", default=None, help="Output directory for reports")
@click.option("--format", "-f", "fmt", default="both",
              type=click.Choice(["md", "html", "both"]),
              help="Report format")
@click.option("--verbose", "-v", is_flag=True, help="Show detailed agent output")
def diff(diff_file: str, output_dir: str | None, fmt: str, verbose: bool):
    """Review a git diff file."""
    _check_api_key()

    diff_path = Path(diff_file).resolve()
    console.print(f"[bold]Reviewing diff:[/bold] {diff_path.name}")

    diff_text = diff_path.read_text(encoding="utf-8", errors="ignore")
    context = build_context_from_diff(diff_text)

    if not context.diffs:
        console.print("[yellow]No changes found in diff file.[/yellow]")
        return

    console.print(f"Found {len(context.diffs)} changed files")
    report = asyncio.run(run_review_pipeline(context, verbose=verbose))

    _save_and_display(report, output_dir, fmt, diff_path.stem)


def _save_and_display(report: ReviewReport, output_dir: str | None, fmt: str, source_name: str):
    """Save reports to files and display summary."""
    out_dir = Path(output_dir) if output_dir else settings.output_path
    out_dir = out_dir.resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    report_id = report.id

    if fmt in ("md", "both"):
        md_path = save_markdown(report, out_dir / f"review-{report_id}.md")
        console.print(f"[green]Markdown report:[/green] {md_path}")

    if fmt in ("html", "both"):
        html_path = save_html(report, out_dir / f"review-{report_id}.html")
        console.print(f"[green]HTML report:[/green] {html_path}")

    console.print("")
    _print_summary(report)


if __name__ == "__main__":
    cli()
