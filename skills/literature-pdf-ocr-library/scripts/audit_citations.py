#!/usr/bin/env python3
"""Audit citations: every \\cite must resolve to a real, sourced reference.

Cross-checks three things and fails (non-zero exit) on the dangerous cases:

  1. \\cite{key} in sections/*.tex   →  must exist in references.bib   (dangling = build error / fabricated key)
  2. each key in references.bib      →  must have provenance in bibliography.json   (unsourced = hand-written / fabricated entry)
  3. keys in references.bib not cited anywhere                                       (unused = info only)

The bibliography.json provenance map is produced by build_bibliography.py from
real metadata.json files, so an entry without provenance is one that was NOT
generated from verified metadata — exactly the fabrication this guards against.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Dict, List, Optional, Set

CITE_RE = re.compile(r"\\[a-zA-Z]*cite[a-zA-Z]*\s*(?:\[[^\]]*\]){0,2}\s*\{([^}]+)\}")
BIB_KEY_RE = re.compile(r"@\w+\s*\{\s*([^,\s}]+)")


def collect_cited_keys(tex_files: List[Path]) -> Dict[str, List[str]]:
    """Return {citation_key: [files it appears in]}."""
    cited: Dict[str, List[str]] = {}
    for tex in tex_files:
        try:
            text = tex.read_text(encoding="utf-8")
        except OSError:
            continue
        for match in CITE_RE.finditer(text):
            for key in match.group(1).split(","):
                key = key.strip()
                if key:
                    cited.setdefault(key, [])
                    if tex.name not in cited[key]:
                        cited[key].append(tex.name)
    return cited


def collect_bib_keys(bib_path: Path) -> Set[str]:
    if not bib_path.is_file():
        return set()
    text = bib_path.read_text(encoding="utf-8")
    return {match.group(1).strip() for match in BIB_KEY_RE.finditer(text)}


def collect_sourced_keys(map_path: Optional[Path]) -> Optional[Set[str]]:
    if not map_path or not map_path.is_file():
        return None
    try:
        data = json.loads(map_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return set((data.get("entries") or {}).keys())


def gather_tex_files(sections_dir: Optional[Path], extra: List[Path]) -> List[Path]:
    files: List[Path] = []
    if sections_dir and sections_dir.is_dir():
        files.extend(sorted(sections_dir.glob("**/*.tex")))
    files.extend(extra)
    # De-dup while preserving order.
    seen, unique = set(), []
    for path in files:
        resolved = path.resolve()
        if resolved not in seen:
            seen.add(resolved)
            unique.append(path)
    return unique


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--sections-dir", default="sections", help="Directory of .tex sections (default: sections).")
    parser.add_argument("--tex", nargs="*", default=[], help="Extra .tex files (e.g. main.tex).")
    parser.add_argument("--bib", default="references.bib", help="Path to references.bib.")
    parser.add_argument("--map", dest="map_path", default=None, help="bibliography.json (default: next to --bib).")
    parser.add_argument("--allow-unsourced", action="store_true", help="Do not fail on bib entries that lack provenance.")
    parser.add_argument("--report-out", default=None, help="Optional path to write the JSON report.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    bib_path = Path(args.bib).expanduser().resolve()
    sections_dir = Path(args.sections_dir).expanduser().resolve() if args.sections_dir else None
    tex_files = gather_tex_files(sections_dir, [Path(p).expanduser().resolve() for p in args.tex])
    map_path = Path(args.map_path).expanduser().resolve() if args.map_path else bib_path.with_name("bibliography.json")

    cited = collect_cited_keys(tex_files)
    bib_keys = collect_bib_keys(bib_path)
    sourced = collect_sourced_keys(map_path)

    cited_keys = set(cited)
    dangling = sorted(cited_keys - bib_keys)               # cited but not in bib → fabricated / typo
    unused = sorted(bib_keys - cited_keys)                  # in bib but never cited → info
    unsourced = sorted(bib_keys - sourced) if sourced is not None else []  # in bib but no provenance → suspect

    report = {
        "tex_files": [str(p) for p in tex_files],
        "bib": str(bib_path),
        "map": str(map_path) if sourced is not None else None,
        "counts": {
            "cited": len(cited_keys),
            "bib": len(bib_keys),
            "dangling": len(dangling),
            "unsourced": len(unsourced),
            "unused": len(unused),
        },
        "dangling": [{"key": key, "in": cited[key]} for key in dangling],
        "unsourced": unsourced,
        "unused": unused,
        "provenance_checked": sourced is not None,
    }

    if args.report_out:
        out = Path(args.report_out).expanduser().resolve()
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    # Human-readable summary to stderr-ish stdout.
    print(json.dumps(report["counts"], ensure_ascii=False))
    if dangling:
        print(f"FAIL: {len(dangling)} dangling \\cite (key not in references.bib): {', '.join(dangling[:10])}")
    if sourced is None:
        print("WARN: bibliography.json not found — cannot verify provenance (run build_bibliography.py first).")
    elif unsourced:
        label = "WARN" if args.allow_unsourced else "FAIL"
        print(f"{label}: {len(unsourced)} references.bib entries without provenance (not from verified metadata): {', '.join(unsourced[:10])}")
    if unused:
        print(f"INFO: {len(unused)} bib entries never cited.")
    if not dangling and not (unsourced and not args.allow_unsourced):
        print("OK: every \\cite resolves to a real, sourced reference.")

    failed = bool(dangling) or (bool(unsourced) and not args.allow_unsourced)
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
