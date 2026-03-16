"""
Report generator: takes simulation results and produces comparison reports.
Outputs both JSON (for programmatic use) and markdown (for humans).
"""

import json
from datetime import datetime
from pathlib import Path


def generate_report(results: dict, output_dir: str = "output") -> dict:
    """generate full comparison report from experiment results"""
    Path(output_dir).mkdir(exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    # aggregate metrics across runs
    aggregated = {}
    for scenario_key, runs in results.items():
        metrics_list = [r["metrics"] for r in runs]
        agg = {}
        for key in metrics_list[0]:
            values = [m[key] for m in metrics_list if m[key] is not None]
            if values and isinstance(values[0], (int, float)):
                agg[key] = {
                    "mean": sum(values) / len(values),
                    "min": min(values),
                    "max": max(values)
                }
            else:
                agg[key] = values
        aggregated[scenario_key] = {
            "config": {
                "name": runs[0]["scenario"],
                "apy": runs[0]["apy"],
                "num_agents": runs[0]["num_agents"],
                "num_rounds": runs[0]["num_rounds"],
                "num_runs": len(runs)
            },
            "metrics": agg
        }

    # compute deltas (dyorx vs traditional)
    deltas = None
    if "traditional" in aggregated and "dyorx" in aggregated:
        trad = aggregated["traditional"]["metrics"]
        dyorx = aggregated["dyorx"]["metrics"]
        deltas = {}
        for key in trad:
            if isinstance(trad[key], dict) and "mean" in trad[key]:
                delta = dyorx[key]["mean"] - trad[key]["mean"]
                pct = (delta / trad[key]["mean"] * 100) if trad[key]["mean"] != 0 else 0
                deltas[key] = {"absolute": delta, "percentage": pct}

    report = {
        "timestamp": timestamp,
        "scenarios": aggregated,
        "deltas": deltas
    }

    # save JSON
    json_path = Path(output_dir) / f"report_{timestamp}.json"
    with open(json_path, "w") as f:
        json.dump(report, f, indent=2, default=str)

    # save markdown
    md_path = Path(output_dir) / f"report_{timestamp}.md"
    md_content = render_markdown(report)
    with open(md_path, "w") as f:
        f.write(md_content)

    return {
        "report": report,
        "json_path": str(json_path),
        "md_path": str(md_path),
        "markdown": md_content
    }


def render_markdown(report: dict) -> str:
    """render report as readable markdown"""
    lines = []
    lines.append("# DYORX Savings Circle Simulation Report")
    lines.append(f"\nGenerated: {report['timestamp']}\n")

    for key, data in report["scenarios"].items():
        cfg = data["config"]
        m = data["metrics"]

        lines.append(f"## {cfg['name']}")
        lines.append(f"APY: {cfg['apy']:.1%} | Agents: {cfg['num_agents']} | Rounds: {cfg['num_rounds']} | Runs: {cfg['num_runs']}\n")

        if isinstance(m.get("completion_rate"), dict):
            lines.append(f"→ Completion rate: {m['completion_rate']['mean']:.1%} (range: {m['completion_rate']['min']:.1%} to {m['completion_rate']['max']:.1%})")
            lines.append(f"→ Completed: {m['completed_count']['mean']:.1f} / {cfg['num_agents']}")
            lines.append(f"→ Dropouts: {m['dropout_count']['mean']:.1f}")
            lines.append(f"→ Total contributed: ${m['total_contributed']['mean']:.2f}")

            if m.get("total_yield_earned") and m["total_yield_earned"]["mean"] > 0:
                lines.append(f"→ Total yield earned: ${m['total_yield_earned']['mean']:.2f}")

            if m.get("avg_dropout_round") and isinstance(m["avg_dropout_round"], dict):
                lines.append(f"→ Avg dropout round: {m['avg_dropout_round']['mean']:.1f}")

            lines.append(f"→ Avg months contributed per agent: {m['avg_months_contributed']['mean']:.1f}")
            lines.append(f"→ Avg months skipped per agent: {m['avg_months_skipped']['mean']:.1f}")

        lines.append("")

    if report.get("deltas"):
        lines.append("## DYORX vs Traditional (Delta)")
        lines.append("")
        d = report["deltas"]

        if "completion_rate" in d:
            lines.append(f"→ Completion rate: {d['completion_rate']['absolute']:+.1%} ({d['completion_rate']['percentage']:+.1f}%)")
        if "total_contributed" in d:
            lines.append(f"→ Total contributed: ${d['total_contributed']['absolute']:+.2f} ({d['total_contributed']['percentage']:+.1f}%)")
        if "dropout_count" in d:
            lines.append(f"→ Dropouts: {d['dropout_count']['absolute']:+.1f}")
        if "total_yield_earned" in d:
            lines.append(f"→ Yield advantage: ${d['total_yield_earned']['absolute']:+.2f}")
        if "avg_dropout_round" in d and d["avg_dropout_round"]["absolute"] != 0:
            lines.append(f"→ Avg dropout timing: {d['avg_dropout_round']['absolute']:+.1f} rounds later")

        lines.append("")

    lines.append("## Thesis Validation")
    lines.append("")

    if report.get("deltas") and "completion_rate" in report["deltas"]:
        delta_cr = report["deltas"]["completion_rate"]["absolute"]
        if delta_cr > 0.05:
            lines.append("SUPPORTED: DeFi yields meaningfully improved circle completion rates.")
            lines.append(f"Adding yield increased completion by {delta_cr:.1%}, confirming the DYORX thesis")
            lines.append("that people save more when their money earns while sitting in the pool.")
        elif delta_cr > 0:
            lines.append("WEAKLY SUPPORTED: DeFi yields showed marginal improvement.")
            lines.append("Consider testing with higher APY or more agent runs for statistical significance.")
        else:
            lines.append("NOT SUPPORTED in this run: yields did not improve completion.")
            lines.append("Check agent configs, try more runs, or adjust yield parameters.")

    lines.append("")
    return "\n".join(lines)
