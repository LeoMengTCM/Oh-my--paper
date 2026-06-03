#!/usr/bin/env python3
"""Convert local PDFs or images to Markdown via the PaddleOCR-VL async OCR API.

Uses the official AI Studio async job API:
  1. POST the file to create a job        -> data.jobId
  2. Poll GET {api}/{jobId} until state    -> done | failed
  3. Download data.resultUrl.jsonUrl        -> JSONL of layout-parsing results
  4. Write doc_<n>.md (+ images) per page

Falls back to pdfminer-based text extraction when --fallback-pdfminer is set
and the API is unavailable or returns an error (e.g. no token, quota, timeout).
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path
from typing import Dict, List

import requests

from literature_lib import discover_input_files, ensure_dir, slugify, write_json

# Official async PaddleOCR-VL endpoint (job-based). Override with --api-url / PADDLEOCR_API_URL.
DEFAULT_API_URL = "https://paddleocr.aistudio-app.com/api/v2/ocr/jobs"
DEFAULT_MODEL = "PaddleOCR-VL-1.6"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("inputs", nargs="+", help="Input files or directories.")
    parser.add_argument("--output-dir", required=True, help="Output directory for Markdown and images.")
    parser.add_argument("--recursive", action="store_true", help="Recurse into input directories.")
    parser.add_argument("--api-url", default=os.environ.get("PADDLEOCR_API_URL", DEFAULT_API_URL))
    parser.add_argument("--token", default=os.environ.get("PADDLEOCR_TOKEN"))
    parser.add_argument("--model", default=os.environ.get("PADDLEOCR_MODEL", DEFAULT_MODEL))
    parser.add_argument("--skip-existing", action="store_true", help="Skip files whose manifest already exists.")
    parser.add_argument("--poll-interval", type=float, default=5.0, help="Seconds between job-status polls.")
    parser.add_argument("--max-wait", type=float, default=1800.0, help="Max seconds to wait for one job.")
    parser.add_argument(
        "--fallback-pdfminer",
        action="store_true",
        help="Fall back to pdfminer text extraction when the API call fails or no token is set.",
    )
    return parser.parse_args()


def convert_pdf_pdfminer(path: Path, output_dir: Path) -> Dict:
    """Extract text from a PDF with pdfminer and write a single doc_0.md."""
    try:
        from pdfminer.high_level import extract_text  # type: ignore
    except ImportError as exc:
        raise RuntimeError("pdfminer not installed; run: pip install pdfminer.six") from exc

    text = extract_text(str(path))
    md_path = output_dir / "doc_0.md"
    md_path.write_text(text or "", encoding="utf-8")
    manifest = {
        "input_path": str(path),
        "output_dir": str(output_dir),
        "backend": "pdfminer",
        "documents": [{"markdown_path": str(md_path), "markdown_image_paths": [], "output_image_paths": []}],
    }
    write_json(output_dir / "manifest.json", manifest)
    return manifest


def submit_job(path: Path, api_url: str, token: str, model: str) -> str:
    """Upload a local file as an OCR job and return its jobId."""
    headers = {"Authorization": f"bearer {token}"}
    data = {
        "model": model,
        "optionalPayload": json.dumps(
            {
                "useDocOrientationClassify": False,
                "useDocUnwarping": False,
                "useChartRecognition": False,
            }
        ),
    }
    with path.open("rb") as handle:
        files = {"file": (path.name, handle)}
        response = requests.post(api_url, headers=headers, data=data, files=files, timeout=180)
    response.raise_for_status()
    return response.json()["data"]["jobId"]


def wait_for_result(api_url: str, job_id: str, token: str, poll_interval: float, max_wait: float) -> str:
    """Poll a job until it is done and return the result JSONL URL."""
    headers = {"Authorization": f"bearer {token}"}
    status_url = f"{api_url.rstrip('/')}/{job_id}"
    deadline = time.monotonic() + max_wait
    while True:
        response = requests.get(status_url, headers=headers, timeout=60)
        response.raise_for_status()
        data = response.json()["data"]
        state = data.get("state")
        if state == "done":
            return data["resultUrl"]["jsonUrl"]
        if state == "failed":
            raise RuntimeError(data.get("errorMsg") or f"PaddleOCR job {job_id} failed")
        progress = data.get("extractProgress") or {}
        print(
            json.dumps(
                {
                    "job": job_id,
                    "state": state,
                    "extractedPages": progress.get("extractedPages"),
                    "totalPages": progress.get("totalPages"),
                },
                ensure_ascii=False,
            ),
            file=sys.stderr,
        )
        if time.monotonic() > deadline:
            raise RuntimeError(f"PaddleOCR job {job_id} timed out after {max_wait}s (last state: {state})")
        time.sleep(poll_interval)


def convert_one(path: Path, output_dir: Path, api_url: str, token: str, model: str,
                poll_interval: float, max_wait: float) -> Dict:
    job_id = submit_job(path, api_url, token, model)
    jsonl_url = wait_for_result(api_url, job_id, token, poll_interval, max_wait)

    jsonl_response = requests.get(jsonl_url, timeout=120)
    jsonl_response.raise_for_status()

    doc_rows: List[Dict] = []
    page_num = 0
    for line in jsonl_response.text.strip().split("\n"):
        line = line.strip()
        if not line:
            continue
        result = json.loads(line)["result"]
        for parsed in result.get("layoutParsingResults", []):
            md_path = output_dir / f"doc_{page_num}.md"
            md_path.write_text(parsed["markdown"]["text"], encoding="utf-8")

            downloaded_images = []
            for image_rel_path, image_url in (parsed["markdown"].get("images") or {}).items():
                local_image_path = output_dir / image_rel_path
                ensure_dir(local_image_path.parent)
                local_image_path.write_bytes(requests.get(image_url, timeout=60).content)
                downloaded_images.append(str(local_image_path))

            output_images = []
            for image_name, image_url in (parsed.get("outputImages") or {}).items():
                local_image_path = output_dir / f"{image_name}_{page_num}.jpg"
                ensure_dir(local_image_path.parent)
                image_response = requests.get(image_url, timeout=60)
                image_response.raise_for_status()
                local_image_path.write_bytes(image_response.content)
                output_images.append(str(local_image_path))

            doc_rows.append(
                {
                    "markdown_path": str(md_path),
                    "markdown_image_paths": downloaded_images,
                    "output_image_paths": output_images,
                }
            )
            page_num += 1

    manifest = {
        "input_path": str(path),
        "output_dir": str(output_dir),
        "backend": "paddleocr-vl",
        "model": model,
        "job_id": job_id,
        "documents": doc_rows,
    }
    write_json(output_dir / "manifest.json", manifest)
    return manifest


def main() -> int:
    args = parse_args()
    use_api = bool(args.token)
    if not use_api and not args.fallback_pdfminer:
        raise SystemExit(
            "PADDLEOCR_TOKEN is required via --token or environment variable. "
            "Pass --fallback-pdfminer to use local pdfminer extraction instead."
        )

    inputs = [Path(item).expanduser().resolve() for item in args.inputs]
    files = discover_input_files(inputs, recursive=args.recursive)
    output_root = Path(args.output_dir).expanduser().resolve()
    ensure_dir(output_root)

    manifests = []
    for path in files:
        file_output_dir = output_root / slugify(path.stem)
        manifest_path = file_output_dir / "manifest.json"
        if args.skip_existing and manifest_path.exists():
            manifests.append(json.loads(manifest_path.read_text(encoding="utf-8")))
            continue
        ensure_dir(file_output_dir)

        if use_api:
            try:
                manifests.append(
                    convert_one(
                        path, file_output_dir, args.api_url, args.token, args.model,
                        args.poll_interval, args.max_wait,
                    )
                )
                continue
            except Exception as exc:  # noqa: BLE001
                if args.fallback_pdfminer:
                    print(json.dumps({"warning": f"API failed for {path.name}: {exc}; falling back to pdfminer"}))
                else:
                    raise

        # pdfminer fallback
        if path.suffix.lower() == ".pdf":
            manifests.append(convert_pdf_pdfminer(path, file_output_dir))
        else:
            print(json.dumps({"warning": f"Skipping non-PDF {path.name} (pdfminer only supports PDFs)"}))

    write_json(output_root / "batch_manifest.json", {"converted_files": len(manifests), "items": manifests})
    print(json.dumps({"converted_files": len(manifests), "output_dir": str(output_root)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
