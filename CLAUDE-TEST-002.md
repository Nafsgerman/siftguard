# SIFTGuard — TEST-002 Investigation Context

## Case
NIST CFReDS Hacking Case — disk image at /cases/TEST-002/SCHARDT.img
Case manifest: experiments/cases/TEST-002/manifest.json

## Evidence shape
Disk-only. No memory image present.
Available tools: filesystem_walk, mft_parse, registry_hive_parse, timeline_build, file_content_read, hash_lookup
DO NOT call volatility_pslist, volatility_netscan, volatility_malfind — no_memory_image.

## Investigation objective
Find evidence of hacking activity. Suspect: Greg Schardt / "Mr. Evil".
Look for: hacking tools installed, wireless sniffing artifacts, credential harvesting tools, IRC communication logs, registry owner confirmation.

## MCP server
Same as TEST-001. Single-line start:
uvicorn siftguard.mcp_server:app --host 0.0.0.0 --port 8090

## Run experiment
python -m siftguard.eval.run_experiment --orchestrator siftguard-claudecode --case TEST-002
