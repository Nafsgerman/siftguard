"""Tiered ablation runner — seed repeats + multi-case generalization.

Tier 1: TEST-001 × all configs × 3 seeds  (variance bands on headline matrix)
Tier 2: TEST-004 + TEST-005 × winning config × 3 seeds  (generalization claim)

Resumable: skips any run where result_seed{N}_*.json already exists in ablation_v2/.

Usage:
    python -m siftguard.eval.ablation_runner --dry-run
    python -m siftguard.eval.ablation_runner --tier 1
    python -m siftguard.eval.ablation_runner --tier 2 --winner baseline
    python -m siftguard.eval.ablation_runner --all
    python -m siftguard.eval.ablation_runner --variance-table
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))

from experiments.run import RESULTS_DIR, load_config, list_configs, run_single as _run_single
from siftguard.cases.loader import list_case_ids as available_datasets
from siftguard.eval.variance import compute_variance_stats

ABLATION_DIR = RESULTS_DIR / "ablation_v2"
SEEDS = [0, 1, 2]
TIER1_CASE = "TEST-001"
TIER2_CASES = ["TEST-004", "TEST-005"]


def _timestamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")


def _result_exists(config_name: str, case_id: str, seed: int) -> bool:
    return any((ABLATION_DIR / config_name / case_id).glob(f"result_seed{seed}_*.json"))


async def run_seeded(
    config: dict,
    case_id: str,
    seed: int,
    dry_run: bool = False,
    orchestrator: str | None = None,
) -> dict:
    config_name = config["name"]
    if _result_exists(config_name, case_id, seed):
        print(f"[SKIP] {config_name} × {case_id} × seed={seed} — already done")
        return {"status": "skipped_resume", "config": config_name, "case_id": case_id, "seed": seed}

    if orchestrator:
        config = {**config, "orchestrator": orchestrator}
    seeded = {**config, "seed": seed, "notes": f"{config.get('notes', '')} [seed={seed}]"}
    print(f"\n[RUN] {config_name} × {case_id} × seed={seed}")
    if dry_run:
        return {"status": "dry_run", "config": config_name, "case_id": case_id, "seed": seed}

    result = await _run_single(seeded, case_id, dry_run=False)
    result["seed"] = seed

    out_dir = ABLATION_DIR / config_name / case_id
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / f"result_seed{seed}_{_timestamp()}.json").write_text(json.dumps(result, indent=2))
    return result


async def run_tier1(
    dry_run: bool = False,
    seeds: list[int] = SEEDS,
    orchestrator: str | None = None,
) -> list[dict]:
    configs = [load_config(n) for n in list_configs()]
    results, total, done = [], len(configs) * len(seeds), 0
    for cfg in configs:
        for seed in seeds:
            done += 1
            print(f"\n[Tier1 {done}/{total}] {cfg['name']} × {TIER1_CASE} × seed={seed}")
            results.append(await run_seeded(cfg, TIER1_CASE, seed, dry_run=dry_run, orchestrator=orchestrator))
    return results


async def run_tier2(
    winner: str,
    dry_run: bool = False,
    seeds: list[int] = SEEDS,
    orchestrator: str | None = None,
) -> list[dict]:
    config = load_config(winner)
    cases = [c for c in TIER2_CASES if c in available_datasets()]
    if not cases:
        print(f"[WARN] No evidence available for {TIER2_CASES}. Skipping Tier 2.")
        return []
    results, total, done = [], len(cases) * len(seeds), 0
    for case_id in cases:
        for seed in seeds:
            done += 1
            print(f"\n[Tier2 {done}/{total}] {winner} × {case_id} × seed={seed}")
            results.append(await run_seeded(config, case_id, seed, dry_run=dry_run, orchestrator=orchestrator))
    return results


def load_seed_results(config_name: str, case_id: str) -> list[dict]:
    d = ABLATION_DIR / config_name / case_id
    if not d.exists():
        return []
    return [
        json.loads(f.read_text())
        for f in sorted(d.glob("result_seed*.json"))
        if json.loads(f.read_text()).get("status") == "ok"
    ]


def compute_variance_table(case_id: str = TIER1_CASE) -> dict[str, dict]:
    table = {}
    for name in list_configs():
        runs = load_seed_results(name, case_id)
        wall = [r["wall_time"] for r in runs if r.get("wall_time") is not None]
        halluc = [r["hallucination_rate"] for r in runs if r.get("hallucination_rate") is not None]
        table[name] = {
            "n_runs": len(runs),
            "wall_time": compute_variance_stats(wall).model_dump() if wall else None,
            "hallucination_rate": compute_variance_stats(halluc).model_dump() if halluc else None,
        }
    return table


def _print_summary(results: list[dict]) -> None:
    ok = sum(1 for r in results if r["status"] == "ok")
    skip = sum(1 for r in results if "skip" in r["status"])
    err = sum(1 for r in results if r["status"] == "error")
    dry = sum(1 for r in results if r["status"] == "dry_run")
    print(f"\n{'='*60}")
    print(f"  ABLATION SUMMARY  ok={ok} skipped={skip} errors={err} dry={dry}")
    for r in results:
        if r["status"] == "error":
            print(f"  ERR {r['config']} × {r.get('case_id')} × seed={r.get('seed')}: {r.get('error','')[:80]}")
    print(f"{'='*60}\n")


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--tier", choices=["1", "2", "all"], default="all")
    p.add_argument("--winner", default="baseline")
    p.add_argument("--seeds", nargs="+", type=int, default=SEEDS)
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--variance-table", action="store_true")
    p.add_argument("--orchestrator", default=None, help="Override orchestrator in config (native|langgraph)")
    args = p.parse_args()

    if args.variance_table:
        print(json.dumps(compute_variance_table(), indent=2))
        return 0

    results: list[dict] = []
    if args.tier in ("1", "all"):
        results += asyncio.run(run_tier1(dry_run=args.dry_run, seeds=args.seeds, orchestrator=args.orchestrator))
    if args.tier in ("2", "all"):
        results += asyncio.run(run_tier2(winner=args.winner, dry_run=args.dry_run, seeds=args.seeds, orchestrator=args.orchestrator))
    _print_summary(results)
    return 1 if any(r["status"] == "error" for r in results) else 0


if __name__ == "__main__":
    sys.exit(main())