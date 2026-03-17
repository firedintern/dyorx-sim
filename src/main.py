"""
DYORX Savings Circle Simulator
Entry point: runs the full experiment and prints results.
"""

import os
import sys
from pathlib import Path
from dotenv import load_dotenv
from anthropic import Anthropic
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table

from .simulation import run_full_experiment
from .report import generate_report

console = Console()


def main():
    load_dotenv()

    # validate env
    api_key = os.getenv("ANTHROPIC_API_KEY")
    model = os.getenv("LLM_MODEL_NAME", "claude-haiku-4-5-20251001")

    if not api_key:
        console.print("[red]ERROR: ANTHROPIC_API_KEY not set in .env[/red]")
        console.print("Copy .env.example to .env and add your Anthropic API key")
        sys.exit(1)

    # init Anthropic client
    client = Anthropic(api_key=api_key)

    console.print(Panel(
        "[bold]DYORX Savings Circle Simulator[/bold]\n"
        f"LLM: {model} (Anthropic)\n"
        "Comparing: Traditional (0% APY) vs DYORX (7% gross APY, 85% to members)",
        title="dyorx-sim",
        border_style="cyan"
    ))

    # find config dir (handle running from project root or src/)
    config_dir = "config"
    if not Path(config_dir).exists():
        config_dir = Path(__file__).parent.parent / "config"

    def on_round(scenario_name, run_idx, composition_label, round_data):
        active = round_data["active_count"]
        rd = round_data["round"]
        contribs = round_data["contributions"]
        drops = round_data["dropouts"]
        console.print(
            f"  [dim]{scenario_name}[/dim] circle {run_idx} [{composition_label}] | "
            f"round {rd:2d} | "
            f"active: {active:2d} | "
            f"contributed: {contribs:2d} | "
            f"dropouts: {drops}"
        )

    console.print("\n[bold cyan]running simulations...[/bold cyan]\n")

    results = run_full_experiment(
        llm_client=client,
        model=model,
        config_dir=str(config_dir),
        on_round_complete=on_round
    )

    console.print("\n[bold cyan]generating report...[/bold cyan]\n")

    output_dir = "output"
    if not Path(output_dir).exists():
        output_dir = str(Path(__file__).parent.parent / "output")

    report_data = generate_report(results, output_dir=output_dir)

    # print markdown report
    console.print(Panel(
        report_data["markdown"],
        title="SIMULATION RESULTS",
        border_style="green"
    ))

    console.print(f"\n[dim]Full report saved to:[/dim]")
    console.print(f"  JSON: {report_data['json_path']}")
    console.print(f"  Markdown: {report_data['md_path']}")
    console.print()


if __name__ == "__main__":
    main()
