#!/usr/bin/env python3
"""Build an authoritative BibTeX file from real paper metadata.

This is the bridge between the survey stage and the write stage: it turns the
verified metadata under ``papers/*/metadata.json`` into

  - ``references.bib``   — real BibTeX entries with stable citation keys
  - ``bibliography.json`` — key → metadata + provenance (where each entry came
                            from), so an audit can prove every entry is real.

Citation keys are deterministic (``lastname + year + first-title-word``) and
written back into each ``metadata.json`` (the ``citation_key`` field), so the
survey and the write stage always refer to the same key. Existing keys are
reused, not recomputed, so adding new papers never renumbers old ones.

Entries with insufficient metadata (no title/year, and no author/doi/arxiv) are
skipped and listed under ``skipped`` rather than guessed — never fabricate a
reference.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from literature_lib import ensure_dir, write_json

# Title stop-words skipped when picking the key's title word.
STOPWORDS = {
    "a", "an", "the", "on", "of", "for", "and", "to", "in", "with", "via",
    "using", "toward", "towards", "is", "are", "be", "study", "analysis",
    "approach", "method", "methods", "learning", "deep", "neural", "networks",
    "network", "model", "models", "survey", "review", "from", "by",
}


def derive_lastname(name: str) -> str:
    # Keep latin + accented letters; drop all-caps initials like "JA" in "Smith JA".
    tokens = re.findall(r"[A-Za-zÀ-ɏ]+", name or "")
    candidates = [token for token in tokens if not (len(token) <= 2 and token.isupper())]
    if not candidates:
        candidates = tokens
    return candidates[-1] if candidates else "anon"


def first_title_word(title: str) -> str:
    for word in re.findall(r"[A-Za-z]+", title or ""):
        if len(word) > 1 and word.lower() not in STOPWORDS:
            return word.lower()
    return "paper"


def base_cite_key(record: Dict) -> str:
    authors = record.get("authors") or []
    lastname = derive_lastname(authors[0]) if authors else "anon"
    year = record.get("year")
    year_str = str(year) if isinstance(year, int) else "nd"
    key = f"{lastname}{year_str}{first_title_word(record.get('title'))}".lower()
    return re.sub(r"[^a-z0-9]", "", key) or "ref"


def is_sufficient(record: Dict) -> Tuple[bool, Optional[str]]:
    """A reference is citable only if it carries enough real metadata."""
    if not record.get("title"):
        return False, "missing title"
    if not record.get("year"):
        return False, "missing year"
    if not (record.get("authors") or record.get("doi") or record.get("arxiv_id")):
        return False, "missing author/doi/arxiv_id"
    return True, None


def _esc(value: Optional[str]) -> str:
    if not value:
        return ""
    out = str(value)
    for char, repl in (("&", r"\&"), ("%", r"\%"), ("#", r"\#"), ("_", r"\_")):
        out = out.replace(char, repl)
    return out.replace("\n", " ").strip()


def entry_type(record: Dict) -> str:
    publication_type = (record.get("publication_type") or "").lower()
    venue = (record.get("venue") or "").lower()
    if record.get("arxiv_id") and not record.get("doi") and ("arxiv" in venue or not venue):
        return "misc"
    if any(token in publication_type for token in ("conf", "proceed", "inproceedings")):
        return "inproceedings"
    if "book" in publication_type or "chapter" in publication_type:
        return "incollection"
    return "article"


def format_bibtex(record: Dict, key: str) -> str:
    kind = entry_type(record)
    authors = " and ".join(_esc(author) for author in (record.get("authors") or []) if author)
    fields: List[Tuple[str, str]] = [("title", f"{{{_esc(record.get('title'))}}}")]
    if authors:
        fields.append(("author", authors))
    venue = _esc(record.get("venue"))
    if kind == "inproceedings" and venue:
        fields.append(("booktitle", venue))
    elif kind == "incollection" and venue:
        fields.append(("booktitle", venue))
    elif kind == "article" and venue:
        fields.append(("journal", venue))
    if record.get("year"):
        fields.append(("year", str(record["year"])))
    if kind == "misc" and record.get("arxiv_id"):
        fields.append(("eprint", _esc(record["arxiv_id"])))
        fields.append(("archivePrefix", "arXiv"))
    if record.get("doi"):
        fields.append(("doi", _esc(record["doi"])))
    url = record.get("landing_page") or record.get("pdf_url")
    if url:
        fields.append(("url", _esc(url)))
    body = ",\n".join(f"  {name} = {{{value}}}" if name != "title" else f"  {name} = {value}" for name, value in fields)
    return f"@{kind}{{{key},\n{body}\n}}\n"


def collect_metadata(library_roots: List[Path]) -> List[Tuple[Path, Dict]]:
    found: List[Tuple[Path, Dict]] = []
    for root in library_roots:
        papers_dir = root / "papers"
        search_dir = papers_dir if papers_dir.is_dir() else root
        for metadata_path in sorted(search_dir.glob("*/metadata.json")):
            try:
                record = json.loads(metadata_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError) as exc:
                print(f"[warn] skipping unreadable {metadata_path}: {exc}")
                continue
            found.append((metadata_path, record))
    return found


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--library-root", nargs="+", required=True, help="One or more corpus roots containing papers/*/metadata.json.")
    parser.add_argument("--bib-out", default=None, help="Output references.bib (default: <first library-root>/references.bib).")
    parser.add_argument("--map-out", default=None, help="Output bibliography.json (default: next to --bib-out).")
    parser.add_argument("--origin", default="survey", help="Provenance origin tag for these entries (e.g. survey, write).")
    parser.add_argument("--recompute-keys", action="store_true", help="Recompute citation keys even if metadata already has one.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    library_roots = [Path(root).expanduser().resolve() for root in args.library_root]
    bib_out = Path(args.bib_out).expanduser().resolve() if args.bib_out else library_roots[0] / "references.bib"
    map_out = Path(args.map_out).expanduser().resolve() if args.map_out else bib_out.with_name("bibliography.json")

    records = collect_metadata(library_roots)

    # First pass: reserve existing keys so new papers never collide with or
    # renumber already-cited ones.
    used_keys = set()
    if not args.recompute_keys:
        for _, record in records:
            existing = record.get("citation_key")
            if existing:
                used_keys.add(existing)

    entries: Dict[str, Dict] = {}
    skipped: List[Dict] = []

    for metadata_path, record in records:
        ok, reason = is_sufficient(record)
        if not ok:
            skipped.append({"metadata_path": str(metadata_path), "reason": reason, "title": record.get("title")})
            continue

        key = None if args.recompute_keys else record.get("citation_key")
        if not key:
            key = base_cite_key(record)
            if key in used_keys:
                for suffix in "abcdefghijklmnopqrstuvwxyz":
                    if f"{key}{suffix}" not in used_keys:
                        key = f"{key}{suffix}"
                        break
            used_keys.add(key)
            # Persist the key back so survey and write share the same one.
            if record.get("citation_key") != key:
                record["citation_key"] = key
                try:
                    metadata_path.write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
                except OSError as exc:
                    print(f"[warn] could not write citation_key into {metadata_path}: {exc}")

        entries[key] = {
            "citation_key": key,
            "title": record.get("title"),
            "authors": record.get("authors") or [],
            "year": record.get("year"),
            "venue": record.get("venue"),
            "doi": record.get("doi"),
            "arxiv_id": record.get("arxiv_id"),
            "citation_count": record.get("citation_count"),
            "full_text_status": record.get("full_text_status"),
            "bibtex": format_bibtex(record, key),
            "provenance": {
                "origin": args.origin,
                "source_platforms": record.get("merged_sources") or ([record.get("source")] if record.get("source") else []),
                "metadata_path": str(metadata_path),
            },
        }

    # Write references.bib sorted by key for stable diffs.
    ensure_dir(bib_out.parent)
    bib_text = "".join(entries[key]["bibtex"] for key in sorted(entries))
    bib_out.write_text(bib_text, encoding="utf-8")

    write_json(
        map_out,
        {
            "generated_from": [str(root) for root in library_roots],
            "bib_out": str(bib_out),
            "count": len(entries),
            "skipped_count": len(skipped),
            "entries": entries,
            "skipped": skipped,
        },
    )

    print(json.dumps({"bib_entries": len(entries), "skipped": len(skipped), "bib_out": str(bib_out), "map_out": str(map_out)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
