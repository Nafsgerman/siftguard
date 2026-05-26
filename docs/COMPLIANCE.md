# SIFTGuard — Submission Compliance Map

SANS FIND EVIL! Hackathon 2026. Every required submission artifact, mapped to its exact location in this repository.

Last verified: 2026-06-10 · Tag: `v1.0.0-hackathon`

| # | Requirement | Location |
|---|---|---|
| 1 | Public code repository | https://github.com/Nafsgerman/siftguard |
| 2 | Open-source license (MIT) | [`LICENSE`](../LICENSE) |
| 3 | README with setup instructions | [`README.md` § Quick Start](../README.md#quick-start) |
| 4 | Deployment / step-by-step run | [`Dockerfile`](../Dockerfile), [`Makefile`](../Makefile) (`make demo`), [`scripts/cold_clone_test.sh`](../scripts/cold_clone_test.sh) |
| 5 | Project description (features & functionality) | [`README.md`](../README.md), [`docs/devpost/SUBMISSION.md`](./devpost/SUBMISSION.md) |
| 6 | Demonstration video | [`docs/devpost/loom_script.md`](./devpost/loom_script.md) → Loom URL: *added at submission* |
| 7 | Architecture diagram | [`docs/architecture/architecture-v3.svg`](./architecture/architecture-v3.svg) |
| 8 | Evidence dataset documentation | [`README.md` § Datasets](../README.md#datasets), [`tests/benchmark/ground_truth/`](../tests/benchmark/ground_truth/) |
| 9 | Accuracy report | [`docs/devpost/SUBMISSION.md` § Accuracy](./devpost/SUBMISSION.md#accuracy), Panel 7 cross-dataset F1, [`docs/adr/ADR-007-spoliation-moat.md`](./adr/ADR-007-spoliation-moat.md), [`tests/spoliation/`](../tests/spoliation/) |
| 10 | Agent execution logs | SQLite `auditentry` table (19 columns: timestamps, tokens, cost, args/output SHA256), [`docs/audit_logs/sample_run.json`](./audit_logs/sample_run.json), Dashboard Panel 3 (live SSE) |

## How to verify each item

```bash
# Items 1, 2, 3
git ls-remote https://github.com/Nafsgerman/siftguard
head -1 LICENSE
head -50 README.md

# Item 4 — reproducible cold-clone
git clone https://github.com/Nafsgerman/siftguard && cd siftguard && make demo

# Item 6 — Loom URL is added to README hero and Devpost form at submission
# Item 10 — sample audit log exported from a real run, see file header for run_id
```

## Compliance checks in CI

CI fails the build if any item above is missing. See `.github/workflows/ci.yml` job `compliance-check`.
