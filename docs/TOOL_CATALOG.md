# SIFTGuard Tool Catalog

Auto-generated from `src/siftguard/mcp_server/server.py`. Do not edit manually.
Run `python scripts/generate_tool_catalog.py` to regenerate.

| Tool | Description | Required Parameters | Optional Parameters |
|------|-------------|---------------------|---------------------|
| `analyze_mft` | Parse Windows $MFT. Returns typed entries with timestomp flags. READ-ONLY. | `memory_image` (string) | `timestomp_only` (boolean) |
| `vol_pslist` | List processes from memory image. Flags suspicious names and parent-child combos. READ-ONLY. | `memory_image` (string) | — |
| `vol_netscan` | Scan memory image for network connections. READ-ONLY. | `memory_image` (string) | — |
| `vol_malfind` | Find injected code and suspicious memory regions. READ-ONLY. | `memory_image` (string) | — |
| `create_supertimeline` | Run log2timeline to build a plaso supertimeline from evidence. READ-ONLY. | `evidence_path` (string) | `output_plaso` (string) |
| `sort_timeline` | Run psort to produce a sorted CSV timeline from a plaso file. READ-ONLY. | `plaso_file` (string) | `output_csv` (string), `filter_date_start` (string) |
| `run_regripper` | Run a regripper plugin against a registry hive. Approved plugins: autoruns, services, run, userassist, shellbags, recentdocs, networklist, timezone, samparse. READ-ONLY. | `hive_path` (string) | `plugin` (string) |
| `list_files` | List files in a disk image using fls (TSK). Recovers deleted files. READ-ONLY. | `image_path` (string) | `offset` (string), `recursive` (boolean) |
| `extract_file` | Extract a file from a disk image by inode using icat. READ-ONLY. | `image_path` (string), `inode` (string), `output_path` (string) | `offset` (string) |
