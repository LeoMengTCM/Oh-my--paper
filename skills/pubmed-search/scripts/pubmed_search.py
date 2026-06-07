#!/usr/bin/env python3
"""
pubmed_search.py — Search PubMed/MEDLINE via NCBI E-utilities (standard library only).

Pipeline: esearch -> PMIDs, esummary -> metadata, efetch -> abstract + MeSH terms.
No third-party dependencies (urllib + xml.etree from the stdlib).

Examples:
  python3 pubmed_search.py "metformin AND cardiovascular outcomes" --retmax 50
  python3 pubmed_search.py '"heart failure"[MeSH] AND randomized[tiab]' \
      --mindate 2020/01/01 --maxdate 2024/12/31 --abstracts --output hf.json
  python3 pubmed_search.py "sepsis bundle" --api-key "$NCBI_API_KEY" --abstracts

NCBI asks every caller to identify itself; pass --email so they can reach you if a
query misbehaves. A free --api-key raises the rate limit from 3 to 10 requests/sec.
"""
import argparse
import json
import sys
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

EUTILS = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
TOOL = "oh-my-paper"


def _get(url, params, *, retries=3, timeout=30):
    full = f"{url}?{urllib.parse.urlencode(params)}"
    last_err = None
    for attempt in range(retries):
        try:
            req = urllib.request.Request(full, headers={"User-Agent": TOOL})
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return resp.read()
        except Exception as err:  # noqa: BLE001 - surface after retries
            last_err = err
            time.sleep(1.5 * (attempt + 1))
    raise RuntimeError(f"request failed after {retries} tries: {last_err}\nURL: {full}")


def _common(params, args):
    params.setdefault("tool", TOOL)
    if args.email:
        params["email"] = args.email
    if args.api_key:
        params["api_key"] = args.api_key
    return params


def esearch(args):
    params = _common({
        "db": "pubmed",
        "term": args.query,
        "retmax": str(args.retmax),
        "retmode": "json",
        "datetype": args.datetype,
        "sort": args.sort,
    }, args)
    if args.mindate:
        params["mindate"] = args.mindate
    if args.maxdate:
        params["maxdate"] = args.maxdate
    data = json.loads(_get(f"{EUTILS}/esearch.fcgi", params))
    result = data.get("esearchresult", {})
    return result.get("idlist", []), int(result.get("count", 0))


def esummary(pmids, args):
    if not pmids:
        return {}
    params = _common({"db": "pubmed", "id": ",".join(pmids), "retmode": "json"}, args)
    data = json.loads(_get(f"{EUTILS}/esummary.fcgi", params))
    return data.get("result", {})


def efetch_abstracts(pmids, args):
    """Return {pmid: {"abstract": str, "mesh": [str]}} parsed from efetch XML."""
    if not pmids:
        return {}
    params = _common({
        "db": "pubmed",
        "id": ",".join(pmids),
        "rettype": "abstract",
        "retmode": "xml",
    }, args)
    out = {}
    root = ET.fromstring(_get(f"{EUTILS}/efetch.fcgi", params))
    for article in root.findall(".//PubmedArticle"):
        pmid_el = article.find(".//MedlineCitation/PMID")
        if pmid_el is None or not pmid_el.text:
            continue
        pmid = pmid_el.text.strip()
        chunks = []
        for ab in article.findall(".//Abstract/AbstractText"):
            text = "".join(ab.itertext()).strip()
            if not text:
                continue
            label = ab.get("Label")
            chunks.append(f"{label}: {text}" if label else text)
        mesh = [
            d.text.strip()
            for d in article.findall(".//MeshHeadingList/MeshHeading/DescriptorName")
            if d.text
        ]
        out[pmid] = {"abstract": "\n".join(chunks), "mesh": mesh}
    return out


def build_records(pmids, summary, abstracts):
    records = []
    for pmid in pmids:
        item = summary.get(pmid)
        if not isinstance(item, dict):
            continue
        authors = [a.get("name", "") for a in item.get("authors", []) if a.get("name")]
        doi = next(
            (aid.get("value", "") for aid in item.get("articleids", []) if aid.get("idtype") == "doi"),
            "",
        )
        record = {
            "pmid": pmid,
            "title": item.get("title", "").rstrip("."),
            "journal": item.get("fulljournalname") or item.get("source", ""),
            "pubdate": item.get("sortpubdate") or item.get("pubdate", ""),
            "authors": authors,
            "doi": doi,
            "url": f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/",
        }
        if pmid in abstracts:
            record["abstract"] = abstracts[pmid]["abstract"]
            record["mesh_terms"] = abstracts[pmid]["mesh"]
        records.append(record)
    return records


def main():
    parser = argparse.ArgumentParser(description="Search PubMed/MEDLINE via NCBI E-utilities.")
    parser.add_argument("query", help='PubMed query; supports field tags e.g. "diabetes[MeSH] AND 2023[pdat]"')
    parser.add_argument("--retmax", type=int, default=20, help="max records to return (default 20)")
    parser.add_argument("--mindate", help="earliest date, YYYY/MM/DD or YYYY")
    parser.add_argument("--maxdate", help="latest date, YYYY/MM/DD or YYYY")
    parser.add_argument("--datetype", default="pdat", help="date type: pdat (publication), edat (entrez), mdat")
    parser.add_argument("--sort", default="relevance", help="relevance | pub_date | first_author | journal")
    parser.add_argument("--abstracts", action="store_true", help="also fetch abstracts and MeSH terms (one extra request)")
    parser.add_argument("--api-key", dest="api_key", help="NCBI API key (raises rate limit to 10/s)")
    parser.add_argument("--email", help="contact email NCBI can reach you at")
    parser.add_argument("--output", help="write JSON here instead of stdout")
    args = parser.parse_args()

    pmids, total = esearch(args)
    delay = 0.11 if args.api_key else 0.34
    time.sleep(delay)
    summary = esummary(pmids, args)
    abstracts = {}
    if args.abstracts and pmids:
        time.sleep(delay)
        abstracts = efetch_abstracts(pmids, args)
    records = build_records(pmids, summary, abstracts)

    payload = {
        "query": args.query,
        "total_count": total,
        "returned": len(records),
        "results": records,
    }
    text = json.dumps(payload, indent=2, ensure_ascii=False)
    if args.output:
        with open(args.output, "w", encoding="utf-8") as fh:
            fh.write(text + "\n")
        print(f"Wrote {len(records)} of {total} matching records to {args.output}", file=sys.stderr)
    else:
        print(text)


if __name__ == "__main__":
    main()
