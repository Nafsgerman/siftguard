# SIFTGuard Tool Catalog

> Auto-generated from `src/siftguard/mcp_server/server.py`.
> Do **not** edit manually — run `make tool-catalog` to regenerate.

**9 forensic tools registered.** All tools are READ-ONLY.
Evidence integrity is enforced architecturally — destructive operations do not exist.

## Index

- [`analyze_mft`](#analyze-mft)
- [`vol_pslist`](#vol-pslist)
- [`vol_netscan`](#vol-netscan)
- [`vol_malfind`](#vol-malfind)
- [`create_supertimeline`](#create-supertimeline)
- [`sort_timeline`](#sort-timeline)
- [`run_regripper`](#run-regripper)
- [`list_files`](#list-files)
- [`extract_file`](#extract-file)

---

## analyze_mft

**Description:** Parse Windows $MFT. Returns typed entries with timestomp flags. READ-ONLY.

### Input Schema

| Parameter | Type | Required | Default | Notes |
|-----------|------|:--------:|---------|-------|
| `memory_image` | `string` | ✓ |  |  |
| `timestomp_only` | `boolean` |  | `False` |  |


### Output

Returns [`ForensicResult`](../src/siftguard/models/forensic.py) serialized as JSON.
Key fields: `tool` · `findings` · `evidence_refs` · `duration_ms` · `outcome` (`ok` | `partial` | `fail`)

### Example Invocation

```json
{
  "tool": "analyze_mft",
  "arguments": {
    "memory_image": "/cases/TEST-001/base-hunt-memory.img"
  }
}
```

---

## vol_pslist

**Description:** List processes from memory image. Flags suspicious names and parent-child combos. READ-ONLY.

### Input Schema

| Parameter | Type | Required | Default | Notes |
|-----------|------|:--------:|---------|-------|
| `memory_image` | `string` | ✓ |  |  |


### Output

Returns [`ForensicResult`](../src/siftguard/models/forensic.py) serialized as JSON.
Key fields: `tool` · `findings` · `evidence_refs` · `duration_ms` · `outcome` (`ok` | `partial` | `fail`)

### Example Invocation

```json
{
  "tool": "vol_pslist",
  "arguments": {
    "memory_image": "/cases/TEST-001/base-hunt-memory.img"
  }
}
```

---

## vol_netscan

**Description:** Scan memory image for network connections. READ-ONLY.

### Input Schema

| Parameter | Type | Required | Default | Notes |
|-----------|------|:--------:|---------|-------|
| `memory_image` | `string` | ✓ |  |  |


### Output

Returns [`ForensicResult`](../src/siftguard/models/forensic.py) serialized as JSON.
Key fields: `tool` · `findings` · `evidence_refs` · `duration_ms` · `outcome` (`ok` | `partial` | `fail`)

### Example Invocation

```json
{
  "tool": "vol_netscan",
  "arguments": {
    "memory_image": "/cases/TEST-001/base-hunt-memory.img"
  }
}
```

---

## vol_malfind

**Description:** Find injected code and suspicious memory regions. READ-ONLY.

### Input Schema

| Parameter | Type | Required | Default | Notes |
|-----------|------|:--------:|---------|-------|
| `memory_image` | `string` | ✓ |  |  |


### Output

Returns [`ForensicResult`](../src/siftguard/models/forensic.py) serialized as JSON.
Key fields: `tool` · `findings` · `evidence_refs` · `duration_ms` · `outcome` (`ok` | `partial` | `fail`)

### Example Invocation

```json
{
  "tool": "vol_malfind",
  "arguments": {
    "memory_image": "/cases/TEST-001/base-hunt-memory.img"
  }
}
```

---

## create_supertimeline

**Description:** Run log2timeline to build a plaso supertimeline from evidence. READ-ONLY.

### Input Schema

| Parameter | Type | Required | Default | Notes |
|-----------|------|:--------:|---------|-------|
| `evidence_path` | `string` | ✓ |  |  |
| `output_plaso` | `string` |  | `/tmp/siftguard_timeline.plaso` |  |


### Output

Returns [`ForensicResult`](../src/siftguard/models/forensic.py) serialized as JSON.
Key fields: `tool` · `findings` · `evidence_refs` · `duration_ms` · `outcome` (`ok` | `partial` | `fail`)

### Example Invocation

```json
{
  "tool": "create_supertimeline",
  "arguments": {
    "evidence_path": "/cases/TEST-001/base-hunt-memory.img"
  }
}
```

---

## sort_timeline

**Description:** Run psort to produce a sorted CSV timeline from a plaso file. READ-ONLY.

### Input Schema

| Parameter | Type | Required | Default | Notes |
|-----------|------|:--------:|---------|-------|
| `plaso_file` | `string` | ✓ |  |  |
| `output_csv` | `string` |  | `/tmp/siftguard_sorted.csv` |  |
| `filter_date_start` | `string` |  |  |  |


### Output

Returns [`ForensicResult`](../src/siftguard/models/forensic.py) serialized as JSON.
Key fields: `tool` · `findings` · `evidence_refs` · `duration_ms` · `outcome` (`ok` | `partial` | `fail`)

### Example Invocation

```json
{
  "tool": "sort_timeline",
  "arguments": {
    "plaso_file": "/tmp/siftguard_timeline.plaso"
  }
}
```

---

## run_regripper

**Description:** Run a regripper plugin against a registry hive. Approved plugins: autoruns, services, run, userassist, shellbags, recentdocs, networklist, timezone, samparse. READ-ONLY.

### Input Schema

| Parameter | Type | Required | Default | Notes |
|-----------|------|:--------:|---------|-------|
| `hive_path` | `string` | ✓ |  |  |
| `plugin` | `string` |  | `autoruns` |  |


### Output

Returns [`ForensicResult`](../src/siftguard/models/forensic.py) serialized as JSON.
Key fields: `tool` · `findings` · `evidence_refs` · `duration_ms` · `outcome` (`ok` | `partial` | `fail`)

### Example Invocation

```json
{
  "tool": "run_regripper",
  "arguments": {
    "hive_path": "/cases/TEST-001/hives/SYSTEM"
  }
}
```

---

## list_files

**Description:** List files in a disk image using fls (TSK). Recovers deleted files. READ-ONLY.

### Input Schema

| Parameter | Type | Required | Default | Notes |
|-----------|------|:--------:|---------|-------|
| `image_path` | `string` | ✓ |  |  |
| `offset` | `string` |  |  |  |
| `recursive` | `boolean` |  | `True` |  |


### Output

Returns [`ForensicResult`](../src/siftguard/models/forensic.py) serialized as JSON.
Key fields: `tool` · `findings` · `evidence_refs` · `duration_ms` · `outcome` (`ok` | `partial` | `fail`)

### Example Invocation

```json
{
  "tool": "list_files",
  "arguments": {
    "image_path": "/cases/TEST-001/disk.img"
  }
}
```

---

## extract_file

**Description:** Extract a file from a disk image by inode using icat. READ-ONLY.

### Input Schema

| Parameter | Type | Required | Default | Notes |
|-----------|------|:--------:|---------|-------|
| `image_path` | `string` | ✓ |  |  |
| `inode` | `string` | ✓ |  |  |
| `output_path` | `string` | ✓ |  |  |
| `offset` | `string` |  |  |  |


### Output

Returns [`ForensicResult`](../src/siftguard/models/forensic.py) serialized as JSON.
Key fields: `tool` · `findings` · `evidence_refs` · `duration_ms` · `outcome` (`ok` | `partial` | `fail`)

### Example Invocation

```json
{
  "tool": "extract_file",
  "arguments": {
    "output_path": "/tmp/extracted_file",
    "image_path": "/cases/TEST-001/disk.img",
    "inode": "12345-128-1"
  }
}
```

---
