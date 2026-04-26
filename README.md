# SIFTGuard

> Autonomous DFIR agent for the SANS SIFT Workstation.
> Typed MCP server makes evidence spoliation architecturally impossible.
> Self-correcting loop. Full audit trail. Senior-analyst reasoning at machine speed.

**SANS FIND EVIL! Hackathon 2026** — submission in progress.

## Why SIFTGuard

Most LLM-driven forensic agents pipe raw shell output into a prompt and hope. That's how you get
hallucinated MFT entries, missed timestomps, and — worst — accidental spoliation.

SIFTGuard takes a different path:

1. **Typed MCP tools.** Every SIFT tool is wrapped as a Pydantic-validated function. The agent
   never sees raw shell. It sees structured findings with provenance.
2. **Architectural read-only.** Destructive commands physically don't exist in our MCP server.
   We prove this with a spoliation test suite that tries to make the agent destroy evidence
   and shows it cannot.
3. **Self-correcting agent.** The loop tracks hypotheses, replans on failure, caps iterations,
   and persists every decision to an append-only SQLite audit log.
4. **Reproducible accuracy.** Ships with a benchmark suite and ground-truth cases so you can
   measure performance — not just demo it.

## Quickstart

```bash
git clone https://github.com/Nafsgerman/siftguard
cd siftguard
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env  # add your ANTHROPIC_API_KEY
siftguard --help
```

## Architecture

See `docs/architecture/` — diagram coming in W1.

## Roadmap

- [x] Repo scaffold, directory structure, config files
- [ ] W1: MCP server skeleton, first 5 typed SIFT tool wrappers
- [ ] W2: 20 tools wrapped, agent loop v1
- [ ] W3: Self-correction loop, hypothesis tracker, audit log
- [ ] W4: Multi-source correlation, accuracy benchmark
- [ ] W5: Spoliation test suite, ground-truth cases
- [ ] W6: Docker image, web UI for traces
- [ ] W7: Demo video, submission

## License

MIT (effective at public release, June 10 2026)
