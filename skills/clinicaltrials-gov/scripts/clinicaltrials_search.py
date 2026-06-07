#!/usr/bin/env python3
"""
clinicaltrials_search.py — Search ClinicalTrials.gov via the public API v2 (stdlib only).

No third-party dependencies and no API key required.

Examples:
  python3 clinicaltrials_search.py --condition "heart failure" --status RECRUITING --max 50
  python3 clinicaltrials_search.py --term "semaglutide obesity" --max 100 --output trials.json
  python3 clinicaltrials_search.py --condition stroke --intervention thrombectomy
"""
import argparse
import json
import sys
import time
import urllib.parse
import urllib.request

API = "https://clinicaltrials.gov/api/v2/studies"
TOOL = "oh-my-paper"


def _get(params, *, retries=3, timeout=30):
    full = f"{API}?{urllib.parse.urlencode(params)}"
    last_err = None
    for attempt in range(retries):
        try:
            req = urllib.request.Request(full, headers={"User-Agent": TOOL})
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return json.loads(resp.read())
        except Exception as err:  # noqa: BLE001 - surface after retries
            last_err = err
            time.sleep(1.5 * (attempt + 1))
    raise RuntimeError(f"request failed after {retries} tries: {last_err}\nURL: {full}")


def flatten(study):
    ps = study.get("protocolSection", {})
    ident = ps.get("identificationModule", {})
    status = ps.get("statusModule", {})
    design = ps.get("designModule", {})
    conditions = ps.get("conditionsModule", {})
    arms = ps.get("armsInterventionsModule", {})
    sponsor = ps.get("sponsorCollaboratorsModule", {})
    nct = ident.get("nctId", "")
    return {
        "nct_id": nct,
        "title": ident.get("briefTitle", ""),
        "status": status.get("overallStatus", ""),
        "study_type": design.get("studyType", ""),
        "phases": design.get("phases", []),
        "enrollment": (design.get("enrollmentInfo", {}) or {}).get("count"),
        "conditions": conditions.get("conditions", []),
        "interventions": [
            f"{i.get('type', '')}: {i.get('name', '')}".strip(": ")
            for i in arms.get("interventions", [])
        ],
        "lead_sponsor": (sponsor.get("leadSponsor", {}) or {}).get("name", ""),
        "start_date": (status.get("startDateStruct", {}) or {}).get("date", ""),
        "url": f"https://clinicaltrials.gov/study/{nct}" if nct else "",
    }


def main():
    parser = argparse.ArgumentParser(description="Search ClinicalTrials.gov via API v2.")
    parser.add_argument("--term", help="free-text query (query.term)")
    parser.add_argument("--condition", help="condition/disease (query.cond)")
    parser.add_argument("--intervention", help="intervention/treatment (query.intr)")
    parser.add_argument("--status", help="filter by overall status, e.g. RECRUITING, COMPLETED")
    parser.add_argument("--max", type=int, default=50, help="max studies to return across pages (default 50)")
    parser.add_argument("--page-size", type=int, default=100, help="results per page, max 1000 (default 100)")
    parser.add_argument("--output", help="write JSON here instead of stdout")
    args = parser.parse_args()

    if not (args.term or args.condition or args.intervention):
        parser.error("provide at least one of --term, --condition, --intervention")

    base = {
        "format": "json",
        "countTotal": "true",
        "pageSize": str(max(1, min(args.page_size, args.max, 1000))),
    }
    if args.term:
        base["query.term"] = args.term
    if args.condition:
        base["query.cond"] = args.condition
    if args.intervention:
        base["query.intr"] = args.intervention
    if args.status:
        base["filter.overallStatus"] = args.status

    studies = []
    total = None
    page_token = None
    while len(studies) < args.max:
        params = dict(base)
        if page_token:
            params["pageToken"] = page_token
        data = _get(params)
        if total is None:
            total = data.get("totalCount")
        for study in data.get("studies", []):
            studies.append(flatten(study))
            if len(studies) >= args.max:
                break
        page_token = data.get("nextPageToken")
        if not page_token:
            break
        time.sleep(0.2)

    payload = {
        "query": {k: v for k, v in base.items() if k.startswith(("query.", "filter."))},
        "total_count": total,
        "returned": len(studies),
        "results": studies,
    }
    text = json.dumps(payload, indent=2, ensure_ascii=False)
    if args.output:
        with open(args.output, "w", encoding="utf-8") as fh:
            fh.write(text + "\n")
        print(f"Wrote {len(studies)} of {total} matching studies to {args.output}", file=sys.stderr)
    else:
        print(text)


if __name__ == "__main__":
    main()
