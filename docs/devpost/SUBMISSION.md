# Devpost submission — SIFTGuard

## Tagline (max 120 chars)

Court-defensible autonomous DFIR. Typed function boundaries make evidence
spoliation architecturally impossible.

## Inspired by

The SANS FIND EVIL! challenge and the Valhuntir reference submission. The
Valhuntir README contains a warning to analysts: *"do not use this
unsupervised."* We took that warning as a design constraint and built the
system that closes it.

## What it does

SIFTGuard takes a memory image, a disk image, and an investigation briefing,
and produces a court-defensible incident report. The agent runs entirely
inside the SANS SIFT Workstation and calls forensic tools — Volatility3, The
Sleuth Kit, registry parsers, MFT scanners — through a typed MCP server. The
analyst sees a live dashboard while the investigation runs, then reviews the
final report with full provenance from each finding back to the tool output
that produced it.

The system writes every action, every tool call, every confidence revision,
and every self-correction event into an append-only audit log. Reports are
stamped with a versioned methodology document so the scoring rules cannot be
changed retroactively without breaking the chain of evidence.

## How we built it

The architecture has four hard boundaries:

**Typed MCP server.** Every forensic tool is a Pydantic-validated function
with a frozen schema. The LLM cannot invoke arbitrary shell, cannot pass
unsanitised paths, cannot bypass the schema. We use the official MCP protocol
and the typed function pattern from the Anthropic SDK.

**Instrumented agent loop.** A v2 loop that writes structured snapshots on
every iteration: tokens in/out, dollar cost, confidence vector per finding,
hypothesis state, self-correction events when the agent revises a prior
conclusion. The original v1 loop is preserved, frozen, and remains the
baseline against which the v2 loop is ablated.

**Empirical evaluation framework.** Before shipping further agent features
we built an agent-agnostic evaluation subsystem: 30 seeded runs across 8
configurations, bootstrap confidence intervals, an automated hallucination
verifier that mechanically checks each finding's evidence excerpt against
raw tool output, and a SHA-pinned methodology document with a CI drift
checker. The headline number — 0.909 IOC F1, σ = 0.000 on TEST-001 across
6 seeds — is reproducible by any third party with the dataset and the
agent. The ablation produced the result we did not expect: self-correction
and the v2 prompt buy stability, not accuracy. A single-seed demo would
have credited those features with accuracy gains they do not provide. The
full decision record is in `docs/adr/ADR-001-empirical-evaluation-framework.md`.

**Append-only SQLite audit DB.** Insert-only access patterns enforced at the
data layer. Schema migrations are versioned, checksummed, and verified at
startup. Spoliation requires breaking the migration log, which is checked.

**Versioned methodology.** `docs/EVAL_FRAMEWORK.md` is the public methodology
contract — scoring rules, ground-truth normalization, panel definitions,
known limitations. The document's SHA-256 is pinned in the code; a CI step
fails if the doc and the code disagree. Every manifest and report header
embeds the methodology block.

The evaluation framework runs an 8-config experiment matrix: baseline, three
ablations (self-correction off, correlation off, v1 prompt), four iteration
caps. Each run produces a structured trace, scored against ground truth,
rendered into seven analytical panels.

## Stack

- **Agent:** Anthropic Claude (Sonnet primary; Opus and Haiku via the eval
  matrix)
- **Orchestration:** Custom MCP server, FastAPI, Server-Sent Events for the
  live dashboard
- **Forensics:** Volatility3, The Sleuth Kit (`fls`, `icat`), `analyzeMFT`,
  custom registry persistence-key tools
- **Storage:** SQLite (append-only audit), file-based Volatility cache for
  performance
- **Eval:** Pydantic Trace model, custom scorer framework, matplotlib panels,
  methodology-pinned manifests

## Challenges

**Volatility3 on emulated x86.** SIFT Workstation runs x86_64; the host is
an Apple Silicon M3. UTM emulation. A 5GB memory image scan takes minutes,
not seconds. We built a file-based plugin cache and pre-warmed it with
`nohup` jobs so the live dashboard does not stall.

**Live agent loop instrumentation without breaking the existing dashboard.**
The v1 loop powered the existing benchmark and the dashboard demo. We could
not edit it without invalidating the v1.0.0 baseline. The solution: a thin
dispatcher that routes by `prompt_version`, a frozen `loop_v1.py`, and a
fully instrumented `loop_v2.py` that runs in parallel. 68/68 existing tests
passed unchanged after the migration.

**Methodology drift.** Once you publish a benchmark, every later edit to the
scoring rules silently invalidates earlier numbers. We solved it with a
SHA-256 pin on `EVAL_FRAMEWORK.md`, embedded in the code, asserted in CI.
Every artifact carries the methodology version and the doc hash.

## Accomplishments we are proud of

- **Spoliation impossibility, proven.** 12/12 automated tests demonstrate
  that the agent cannot alter, delete, or fabricate evidence. Not a policy
  statement, an automated test suite.
- **Live self-correction event captured.** A real iteration where the agent
  revised its own conclusion after contradicting tool output. Visible in the
  audit log. Reproducible.
- **Versioned methodology.** The first DFIR-agent project we are aware of
  that pins its scoring rules to a SHA-256 and asserts the pin in CI.
- **Eight-config experiment matrix, zero parse failures.** Structured-output
  prompt + validator + retry loop produced clean traces across all 8
  configurations on the first full matrix run.

## What we learned

The most useful artifacts are not the dashboards or the demos. They are the
ones that make later regression impossible: the spoliation test suite, the
methodology hash, the append-only audit DB, the frozen v1 loop. These are
boring artifacts that quietly remove categories of failure.

A free-form-confidence prompt cannot produce calibrated probabilities. We
caught this in the v1-vs-v2 ablation and documented it as a methodological
finding rather than hiding the inconvenient number.

The agent's self-correction behaviour is real and reproducible, but rare.
Designing the audit schema to capture self-correction as a first-class event
made the difference between *"the agent self-corrects"* (a claim) and
*"here is the row in the audit log"* (an artifact).

## What's next

The 28-task roadmap is in [TASKS.md](../TASKS.md). The near-term items:

- Multi-model vendor-risk matrix: same case, same MCP server, run on Sonnet,
  Opus, Haiku, GPT-4o, Gemini 2.5 Pro. Output: accuracy, cost, latency,
  calibration. The single most decision-relevant artifact for an enterprise
  buyer evaluating agentic security tools.
- LangGraph and OpenAI orchestrator adapters. Same MCP server, different
  client. Proves the architecture is not vendor-locked.
- TEST-004 and TEST-005 generalization runs with multi-seed confidence
  intervals.
- Paired disk + memory dataset (NIST CFReDS or DFRWS 2008) for honest
  cross-source correlation.

## Try it

```bash
git clone https://github.com/Nafsgerman/siftguard.git
cd siftguard
make demo
```

The demo loads TEST-001 evidence, runs the v2 agent loop, opens the live
dashboard at http://localhost:8000, and produces a court-defensible report
in `experiments/results/baseline/TEST-001/`.