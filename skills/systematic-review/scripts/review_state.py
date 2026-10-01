#!/usr/bin/env python3
"""离线校验综述记录并生成筛选进度。"""
import argparse
import json
import sys

sys.dont_write_bytecode = True

from review_model import load_review
from screening import summarize
from prisma import markdown_summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["validate", "prisma"])
    parser.add_argument("directory", help="包含 review.json 与 JSONL 记录的目录")
    parser.add_argument("--format", choices=["json", "markdown"], default="json", help="prisma 输出格式")
    args = parser.parse_args()
    try:
        if args.command != "prisma" and args.format != "json":
            raise ValueError("validate 仅输出 JSON；Markdown 计数请用 prisma")
        result = summarize(load_review(args.directory))
        print(markdown_summary(result) if args.format == "markdown" else json.dumps(result, ensure_ascii=False, indent=2))
        return 0 if result["screening_complete"] else 2
    except (ValueError, OSError) as error:
        print(json.dumps({"status": "error", "error": str(error)}, ensure_ascii=False), file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
