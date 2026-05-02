# SIFTGuard 🛡️

> Autonomous DFIR agent for the SANS SIFT Workstation.  
> Typed MCP server makes evidence spoliation architecturally impossible.  
> Self-correcting loop. Full audit trail. Senior-analyst reasoning at machine speed.

**SANS FIND EVIL! Hackathon 2026** · [Devpost](https://devpost.com/software/siftguard) · Private until June 10

---

## Why SIFTGuard

Most LLM-driven forensic agents pipe raw shell output into a prompt and hope. That's how you get hallucinated MFT entries, missed timestomps, and — worst — accidental spoliation.

SIFTGuard takes a different path:

1. **Typed MCP tools.** Every SIFT tool is wrapped as a Pydantic-validated function. The agent never sees raw shell. It sees structured findings with provenance.
2. **Architectural read-only.** Destructive commands physically don't exist in our MCP server. Proven by a spoliation test suite that tries to make the agent destroy evidence — and shows it cannot.
3. **Self-correcting agent.** The loop tracks hypotheses, replans on failure, caps iterations, and persists every decision to an append-only SQLite audit log.
4. **Reproducible accuracy.** Ships with a benchmark suite and ground-truth cases so you can measure performance — not just demo it.

---

## Benchmark Results

| Case | Threat Type | IOC F1 | Sections | Verdict | **Overall** |
|------|------------|--------|----------|---------|-------------|
| TEST-001 | APT C2 | 70.6% | 100% | 100% | **85.3%** |

Scoring: IOC F1 (50%) + Section completeness (25%) + Verdict accuracy (25%)

---

## Architecture

┌─────────────────────────────────────────────────┐
│                  SIFTGuard Agent                 │
│                                                  │
│  Case Briefing → Hypothesis → Tool Loop → Report │
└──────────────────┬──────────────────────────────┘
│ MCP Protocol
┌──────────────────▼──────────────────────────────┐
│              SIFTGuard MCP Server                │
│                                                  │
│  vol_pslist │ vol_netscan │ vol_malfind          │
│  analyze_mft │ run_regripper │ create_timeline   │
│  list_files │ extract_file │ sort_timeline       │
└──────────────────┬──────────────────────────────┘
│
┌──────────────────▼──────────────────────────────┐
│           SANS SIFT Workstation (x86_64)         │
│                                                  │
│  Volatility 3 │ log2timeline │ analyzeMFT        │
│  RegRipper │ The Sleuth Kit (fls/icat)           │
└─────────────────────────────────────────────────┘


---

## Quickstart

```bash
git clone https://github.com/Nafsgerman/siftguard
cd siftguard
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env  # add your ANTHROPIC_API_KEY
siftguard --help
```

### Run an Investigation

```bash
siftguard investigate CASE-001 \
  --briefing "Suspected ransomware. Victim executed invoice.exe." \
  --memory /cases/CASE-001/memory.img
```

### Run the Benchmark

```bash
python -m tests.benchmark.runner --case TEST-001 --evidence-dir /cases
python -m tests.benchmark.runner --all --evidence-dir /cases
```

### Start the Dashboard

```bash
uvicorn siftguard.dashboard.app:app --host 0.0.0.0 --port 8000
```

---

## Forensic Tools (MCP Server)

| Tool | Underlying Binary | Purpose |
|------|------------------|---------|
| `vol_pslist` | Volatility 3 `psscan` | Process enumeration, orphan detection |
| `vol_netscan` | Volatility 3 `netscan` | Network connections, C2 identification |
| `vol_malfind` | Volatility 3 `malfind` | Code injection, shellcode detection |
| `analyze_mft` | analyzeMFT.py | MFT parsing, timestomp detection |
| `run_regripper` | RegRipper `rip.pl` | Registry hive analysis (9 approved plugins) |
| `create_supertimeline` | log2timeline | Plaso supertimeline generation |
| `sort_timeline` | psort | Sorted CSV timeline output |
| `list_files` | TSK `fls` | Disk image file listing, deleted file recovery |
| `extract_file` | TSK `icat` | File extraction by inode |

All tools are **READ-ONLY by architecture**. Destructive commands do not exist in the MCP server.

---

## Agent Loop

Receive case briefing + evidence paths
Form initial hypothesis
Call forensic tools via MCP
Parse typed ForensicResult objects
Update hypothesis based on findings
Repeat until confident or max iterations (15)
Output structured incident report

Report sections: Executive Summary · Timeline of Events · Indicators of Compromise · Persistence Mechanisms · Recommendations · Evidence References

---

## Project Structure
src/siftguard/
├── agent/loop.py          # Main agent loop (Claude + tool dispatch)
├── mcp_server/
│   ├── server.py          # MCP server (stdio transport)
│   └── tools/             # Forensic tool wrappers
│       ├── volatility.py  # Volatility 3 (pslist, netscan, malfind)
│       ├── mft.py         # MFT analysis
│       ├── registry.py    # RegRipper
│       ├── timeline.py    # log2timeline / psort
│       └── filesystem.py  # TSK fls/icat
├── models/forensic.py     # Pydantic models (ForensicResult, MFTEntry, etc.)
├── parsers/               # Output parsers for each tool
├── audit/log.py           # SQLite audit trail
├── dashboard/app.py       # FastAPI + SSE live dashboard
└── cli/main.py            # CLI entry point
tests/
├── benchmark/
│   ├── ground_truth/      # JSON ground truth per case
│   ├── scorer.py          # Precision/recall/F1 scoring
│   ├── runner.py          # Benchmark runner
│   ├── reports/           # Saved agent reports
│   └── scores/            # Saved score JSON
├── spoliation/            # Proves agent cannot destroy evidence
└── unit/


---

## Security

- Tool allowlist enforced at MCP server level — no arbitrary command execution
- RegRipper limited to 9 approved plugins
- All evidence access is read-only at the OS level
- Full SQLite audit trail of every tool invocation (args, outcome, duration, iteration)

---

## Roadmap

- [x] Repo scaffold, MCP server, 9 typed SIFT tool wrappers
- [x] Self-correcting agent loop with hypothesis tracker
- [x] Append-only SQLite audit trail
- [x] Benchmark suite with precision/recall/F1 scoring
- [x] Spoliation test suite
- [x] Live SSE dashboard
- [ ] PDF/markdown report export
- [ ] IOC visualization panel
- [ ] Demo video (Loom)
- [ ] Public release (June 10, 2026)

---

## License

MIT — effective at public release, June 10 2026
