"""
SIFTGuard Benchmark Runner
Runs the agent against all ground truth cases and outputs accuracy scores.

Usage:
    python -m tests.benchmark.runner --case TEST-001 --evidence-dir /cases
    python -m tests.benchmark.runner --all --evidence-dir /cases
    python -m tests.benchmark.runner --dry-run   # score saved reports without running agent
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

# Add project root to path
sys.path.insert(0, str(Path(__file__).parents[3] / "src"))

from siftguard.agent.loop import run_case
from tests.benchmark.scorer import BenchmarkScore, load_ground_truth, score_report

console = Console()

REPORTS_DIR = Path(__file__).parent / "reports"
SCORES_DIR = Path(__file__).parent / "scores"


def _get_evidence_files(case_id: str, evidence_dir: str) -> dict[str, str]:
    base = Path(evidence_dir) / case_id
    evidence = {}
    candidates = {
        "memory_image": [
            "memory.mem",
            "memory.raw",
            "memory.vmem",
            "mem.dmp",
            "base-hunt-memory.img",
            "*.img",
            "*.mem",
            "*.raw",
            "*.vmem",
        ],
        "disk_image": ["disk.dd", "disk.img", "disk.e01", "disk.raw", "*.dd", "*.E01"],
        "mft": ["$MFT", "MFT", "mft.bin"],
        "system_hive": ["SYSTEM", "system.hiv"],
        "software_hive": ["SOFTWARE", "software.hiv"],
        "ntuser_hive": ["NTUSER.DAT", "ntuser.dat"],
    }
    for label, filenames in candidates.items():
        for fn in filenames:
            if "*" in fn:
                matches = list(base.glob(fn))
                if matches:
                    evidence[label] = str(matches[0])
                    break
            else:
                candidate = base / fn
                if candidate.exists():
                    evidence[label] = str(candidate)
                    break
    return evidence


async def run_benchmark_case(
    case_id: str,
    evidence_dir: str,
    dry_run: bool = False,
) -> BenchmarkScore:
    gt = load_ground_truth(case_id)
    report_text = ""

    if dry_run:
        report_file = REPORTS_DIR / f"{case_id}_report.txt"
        if not report_file.exists():
            console.print(f"[red]No saved report for {case_id}. Run without --dry-run first.[/red]")
            sys.exit(1)
        report_text = report_file.read_text()
        console.print(f"[dim]Scoring saved report: {report_file}[/dim]")
    else:
        evidence = _get_evidence_files(case_id, evidence_dir)
        if not evidence:
            console.print(f"[red]No evidence files found for {case_id}.[/red]")
            console.print(f"[dim]Expected files in {evidence_dir}/{case_id}/[/dim]")
            console.print("[yellow]Use --dry-run to score a saved report instead.[/yellow]")
            sys.exit(1)

        console.print(
            Panel(
                (
                    f"Case: [yellow]{case_id}[/yellow]\n"
                    f"Threat: [cyan]{gt['threat_type']}[/cyan]\n"
                    f"Evidence: {list(evidence.keys())}"
                ),
                title="Running Benchmark Case",
            )
        )

        report_text = await run_case(
            case_id=case_id,
            evidence_files=evidence,
            briefing=gt["description"],
        )

        REPORTS_DIR.mkdir(exist_ok=True)
        ts = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
        report_file = REPORTS_DIR / f"{case_id}_{ts}_report.txt"
        report_file.write_text(report_text)
        (REPORTS_DIR / f"{case_id}_report.txt").write_text(report_text)
        console.print(f"[dim]Report saved: {report_file}[/dim]")

    score = score_report(report_text, gt)
    SCORES_DIR.mkdir(exist_ok=True)
    ts = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
    score_file = SCORES_DIR / f"{case_id}_{ts}_score.json"
    score_file.write_text(json.dumps(score.to_dict(), indent=2))
    return score


def _print_score_table(scores: list[BenchmarkScore]) -> None:
    table = Table(title="SIFTGuard Benchmark Results", show_lines=True)
    table.add_column("Case ID", style="cyan")
    table.add_column("Threat Type", style="dim")
    table.add_column("IOC Precision", justify="right")
    table.add_column("IOC Recall", justify="right")
    table.add_column("IOC F1", justify="right", style="yellow")
    table.add_column("Sections", justify="right")
    table.add_column("Verdict", justify="right")
    table.add_column("OVERALL", justify="right", style="bold green")

    for s in scores:
        d = s.to_dict()["scores"]
        table.add_row(
            s.case_id,
            s.threat_type,
            f"{d['ioc_precision']:.1%}",
            f"{d['ioc_recall']:.1%}",
            f"{d['ioc_f1']:.1%}",
            f"{d['section_completeness']:.1%}",
            f"{d['verdict_accuracy']:.1%}",
            f"{d['overall']:.1%}",
        )

    if len(scores) > 1:
        avg_overall = sum(s.overall_score for s in scores) / len(scores)
        avg_f1 = sum(s.ioc_f1 for s in scores) / len(scores)
        table.add_section()
        table.add_row(
            "[bold]AVERAGE[/bold]",
            "",
            "",
            "",
            f"[bold]{avg_f1:.1%}[/bold]",
            "",
            "",
            f"[bold]{avg_overall:.1%}[/bold]",
        )

    console.print(table)

    for s in scores:
        missed = [i for i in s.ioc_scores if not i.found and i.expected_confidence == "high"]
        if missed:
            console.print(f"\n[red]High-confidence IOCs missed in {s.case_id}:[/red]")
            for m in missed:
                console.print(f"  ✗ [{m.ioc_type}] {m.ioc_value}")


async def main() -> None:
    parser = argparse.ArgumentParser(description="SIFTGuard Benchmark Runner")
    parser.add_argument("--case", help="Run a single case by ID (e.g. TEST-001)")
    parser.add_argument("--all", action="store_true", help="Run all available ground truth cases")
    parser.add_argument(
        "--dry-run", action="store_true", help="Score saved reports without running agent"
    )
    parser.add_argument(
        "--evidence-dir", default="/cases", help="Root directory containing case evidence folders"
    )
    args = parser.parse_args()

    if not args.case and not args.all:
        parser.print_help()
        sys.exit(1)

    gt_dir = Path(__file__).parent / "ground_truth"
    if args.all:
        case_ids = [f.stem for f in gt_dir.glob("*.json")]
    else:
        case_ids = [args.case]

    scores = []
    for case_id in case_ids:
        score = await run_benchmark_case(
            case_id=case_id,
            evidence_dir=args.evidence_dir,
            dry_run=args.dry_run,
        )
        scores.append(score)

    _print_score_table(scores)

    avg = sum(s.overall_score for s in scores) / len(scores) if scores else 0
    sys.exit(0 if avg >= 0.6 else 1)


if __name__ == "__main__":
    asyncio.run(main())
