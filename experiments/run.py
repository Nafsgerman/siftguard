"""SIFTGuard experiment runner.

Usage:
    python -m experiments.run --config baseline
    python -m experiments.run --config baseline --case TEST-001
    python -m experiments.run --all
    python -m experiments.run --all --dry-run

ADR: docs/adr/ADR-001-empirical-evaluation-framework.md
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import time
from datetime import UTC, datetime, timezone
from pathlib import Path

from siftguard.eval.methodology import current_block

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from siftguard.agent.loop import run_case

CONFIGS_DIR = Path(__file__).parent / "configs"
RESULTS_DIR = Path(__file__).parent / "results"
CASES_ROOT = Path(os.environ.get("SIFTGUARD_CASES_ROOT", "/cases"))

CASE_EVIDENCE = {
    "TEST-001": {
        "memory": str(CASES_ROOT / "TEST-001" / "base-hunt-memory.img"),
    },
    "TEST-002": {
        "disk": str(CASES_ROOT / "TEST-002" / "SCHARDT.img"),
    },
    "TEST-004": {
        "memory": str(CASES_ROOT / "TEST-004" / "base-hunt-memory.img"),
    },
    "TEST-005": {
        "memory": str(CASES_ROOT / "TEST-005" / "base-hunt-memory.img"),
    },
}

CASE_BRIEFINGS = {
    "TEST-001": (
        "Windows 10 x64 memory image from SRL-2018 APT hunt scenario. "
        "Suspected compromise with C2 activity. Find evil."
    ),
    "TEST-002": (
        "Windows XP disk image. Suspect Greg Schardt aka Mr. Evil. "
        "Find hacking tools, wireless sniffing artifacts, credential "
        "harvesting software, and evidence of war-driving activity."
    ),
    "TEST-004": (
        "Windows 10 x64 memory image. Focus: registry persistence " "and truncated process names."
    ),
    "TEST-005": (
        "Windows 10 x64 memory image. Focus: full C2 infrastructure "
        "mapping and network correlation."
    ),
}

GROUND_TRUTH_DIR = REPO_ROOT / "tests" / "benchmark" / "ground_truth"


def load_config(name: str) -> dict:
    path = CONFIGS_DIR / f"{name}.json"
    if not path.exists():
        raise FileNotFoundError(f"Config not found: {path}")
    return json.loads(path.read_text())  # type: ignore[no-any-return]


def list_configs() -> list[str]:
    return sorted(p.stem for p in CONFIGS_DIR.glob("*.json"))


def evidence_available(case_id: str) -> bool:
    evidence = CASE_EVIDENCE.get(case_id, {})
    return all(Path(p).exists() for p in evidence.values())


def audit_db_for_case(case_id: str) -> str:
    db_dir = CASES_ROOT / case_id / "siftguard" / "audit"
    db_dir.mkdir(parents=True, exist_ok=True)
    return str(db_dir / "CASE-001.db") if case_id == "TEST-001" else str(db_dir / f"{case_id}.db")


async def run_single(
    config: dict,
    case_id: str,
    dry_run: bool = False,
) -> dict:
    """Run one experiment config against one case. Returns result summary."""

    if not evidence_available(case_id):
        return {
            "status": "skipped",
            "reason": f"Evidence not available for {case_id}",
            "config": config["name"],
            "case_id": case_id,
        }

    evidence_files = CASE_EVIDENCE[case_id]
    briefing = CASE_BRIEFINGS[case_id]
    audit_db = audit_db_for_case(case_id)
    ground_truth = str(GROUND_TRUTH_DIR / f"{case_id}.json")

    result_dir = RESULTS_DIR / config["name"] / case_id
    result_dir.mkdir(parents=True, exist_ok=True)

    print(f"\n{'='*60}")
    print(f"  Config:  {config['name']}")
    print(f"  Case:    {case_id}")
    print(f"  Model:   {config['model']}")
    print(f"  MaxIter: {config['max_iterations']}")
    print(f"  DryRun:  {dry_run}")
    print(f"{'='*60}\n")

    if dry_run:
        return {
            "status": "dry_run",
            "config": config["name"],
            "case_id": case_id,
        }

    start = time.time()
    try:
        report = await run_case(
            case_id=case_id,
            evidence_files=evidence_files,
            briefing=briefing,
            audit_db=audit_db,
            training_mode=config.get("training_mode", False),
            model=config["model"],
            prompt_version=config.get("prompt_version", "v2"),
            config_override={
                k: config[k]
                for k in [
                    "self_correction",
                    "correlation",
                    "max_iterations",
                    "seed",
                    "notes",
                    "orchestrator",
                    "agent_id",
                ]
                if k in config
            },
            ground_truth_path=ground_truth,
        )

        wall_time = time.time() - start

        # Save report
        report_path = result_dir / f"report_{_timestamp()}.md"
        report_path.write_text(report)

        result = {
            "status": "ok",
            "config": config["name"],
            "case_id": case_id,
            "wall_time": round(wall_time, 1),
            "hallucination_rate": None,
            "verified_rate": None,
            "unverifiable_rate": None,
            "report": str(report_path),
            "timestamp": _timestamp(),
            "methodology": current_block().to_dict(),
        }

    except Exception as exc:
        wall_time = time.time() - start
        result = {
            "status": "error",
            "config": config["name"],
            "case_id": case_id,
            "error": str(exc),
            "wall_time": round(wall_time, 1),
            "timestamp": _timestamp(),
        }
        print(f"[ERROR] {exc}")

    # Save result summary
    summary_path = result_dir / f"result_{_timestamp()}.json"
    summary_path.write_text(json.dumps(result, indent=2))
    print(f"\n[result] {result['status']} — saved to {summary_path}")

    return result


def _timestamp() -> str:
    return datetime.now(UTC).strftime("%Y%m%d_%H%M%S")


async def run_all(configs: list[dict], dry_run: bool = False) -> list[dict]:
    results = []
    total = sum(len(c.get("cases", ["TEST-001"])) for c in configs)
    done = 0
    for config in configs:
        for case_id in config.get("cases", ["TEST-001"]):
            done += 1
            print(f"\n[{done}/{total}] {config['name']} × {case_id}")
            result = await run_single(config, case_id, dry_run=dry_run)
            results.append(result)
    return results


def print_summary(results: list[dict]) -> None:
    print(f"\n{'='*60}")
    print("  EXPERIMENT MATRIX SUMMARY")
    print(f"{'='*60}")
    ok = [r for r in results if r["status"] == "ok"]
    skipped = [r for r in results if r["status"] == "skipped"]
    errors = [r for r in results if r["status"] == "error"]
    print(f"  Total:   {len(results)}")
    print(f"  OK:      {len(ok)}")
    print(f"  Skipped: {len(skipped)}")
    print(f"  Errors:  {len(errors)}")
    if errors:
        print("\n  Errors:")
        for r in errors:
            print(f"    {r['config']} × {r['case_id']}: {r.get('error','')[:80]}")
    if skipped:
        print("\n  Skipped:")
        for r in skipped:
            print(f"    {r['config']} × {r['case_id']}: {r.get('reason','')}")
    print(f"{'='*60}\n")


def main() -> int:
    parser = argparse.ArgumentParser(description="SIFTGuard experiment runner")
    parser.add_argument("--config", help="Config name (without .json)")
    parser.add_argument("--case", help="Override case ID")
    parser.add_argument("--all", action="store_true", help="Run all configs")
    parser.add_argument("--list", action="store_true", help="List available configs")
    parser.add_argument("--dry-run", action="store_true", help="Print plan, no API calls")
    args = parser.parse_args()

    if args.list:
        print("Available configs:")
        for name in list_configs():
            cfg = load_config(name)
            print(f"  {name:40s} {cfg.get('description','')[:60]}")
        return 0

    if args.all:
        configs = [load_config(name) for name in list_configs()]
    elif args.config:
        configs = [load_config(args.config)]
    else:
        parser.print_help()
        return 1

    # Override cases if --case specified
    if args.case:
        for cfg in configs:
            cfg["cases"] = [args.case]

    results = asyncio.run(run_all(configs, dry_run=args.dry_run))
    print_summary(results)

    errors = [r for r in results if r["status"] == "error"]
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
