# Case Manifest Schema v1.0.0

Per-case file at `experiments/cases/<CASE_ID>/manifest.json`. MCP server reads this at case-load time to determine which tools to expose.

## Schema
```json
{
  "case_id": "TEST-002",
  "case_name": "NIST CFReDS Hacking Case (Schardt / Mr. Evil)",
  "evidence_files": [
    {
      "path": "/cases/TEST-002/SCHARDT.img",
      "type": "disk_image",
      "format": "raw_dd",
      "filesystem": "ntfs",
      "sha256": "<computed>"
    }
  ],
  "available_tools": [
    "filesystem_walk",
    "mft_parse",
    "registry_hive_parse",
    "timeline_build",
    "file_content_read",
    "hash_lookup"
  ],
  "unavailable_tools": [
    {"tool": "volatility_pslist", "reason": "no_memory_image"},
    {"tool": "volatility_netscan", "reason": "no_memory_image"},
    {"tool": "volatility_malfind", "reason": "no_memory_image"},
    {"tool": "volatility_handles", "reason": "no_memory_image"}
  ],
  "ground_truth_path": "experiments/ground_truth/TEST-002-v1.1.0.json"
}
```

## Contract
- MCP server registers ONLY tools in `available_tools` for this case-load
- Calls to `unavailable_tools` return typed `ToolUnavailable(reason)` error — never silently no-op, never hallucinate output
- Orchestrators discover availability via REGISTRY; no per-case adapter changes anywhere
- Manifest hash committed alongside ground truth — manifest drift = audit failure
