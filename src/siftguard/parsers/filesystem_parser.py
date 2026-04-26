from __future__ import annotations


def parse_fls_output(raw: str) -> list[dict]:
    """Parse fls output into structured entries. Flags deleted files."""
    entries = []
    for line in raw.splitlines():
        line = line.strip()
        if not line:
            continue
        # fls format: TYPE/TYPE  INODE:  NAME
        # deleted entries start with '*'
        deleted = line.startswith("*")
        if deleted:
            line = line[1:].strip()
        parts = line.split("\t")
        if len(parts) < 2:
            continue
        type_inode = parts[0].strip()
        name = parts[1].strip() if len(parts) > 1 else ""
        type_parts = type_inode.split(" ")
        ftype = type_parts[0] if type_parts else ""
        inode = type_parts[-1].rstrip(":") if len(type_parts) > 1 else ""
        entries.append({
            "type": ftype,
            "inode": inode,
            "name": name,
            "deleted": deleted,
        })
    return entries
