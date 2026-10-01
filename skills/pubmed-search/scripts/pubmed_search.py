#!/usr/bin/env python3
"""PubMed 候选检索、完整取回及断点恢复（仅使用 Python 标准库）。"""
import argparse
from datetime import date
import json
import os
from pathlib import Path
import re
import sys

sys.dont_write_bytecode = True

from pubmed_api import UID_LIMIT
from pubmed_checkpoint import atomic_json, require
from pubmed_runner import retrieve


class Parser(argparse.ArgumentParser):
    def error(self, message):
        raise ValueError(f"参数错误：{message}")


def date_bound(value, upper=False):
    if value is None:
        return None
    if re.fullmatch(r"[0-9]{4}", value):
        return date(int(value), 12 if upper else 1, 31 if upper else 1)
    if re.fullmatch(r"[0-9]{4}/[0-9]{2}/[0-9]{2}", value):
        return date(*map(int, value.split("/")))
    raise ValueError("日期使用 YYYY 或 YYYY/MM/DD")


def parse_args(argv):
    parser = Parser(description=__doc__)
    parser.add_argument("query", help="完整 PubMed 检索式")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--retmax", type=int, default=20, help="候选检索上限，默认 20")
    mode.add_argument("--all", action="store_true", help="请求完整取回；须指定检查点")
    parser.add_argument("--mindate")
    parser.add_argument("--maxdate")
    parser.add_argument("--datetype", default="pdat", choices=["pdat", "edat", "mdat"])
    parser.add_argument("--sort", default="relevance")
    parser.add_argument("--abstracts", action="store_true")
    parser.add_argument("--batch-size", type=int, default=200)
    parser.add_argument("--checkpoint", help="专用检查点目录，不存放其他文件")
    parser.add_argument("--resume", action="store_true", help="恢复相同参数下的检查点")
    parser.add_argument("--retries", type=int, default=3)
    parser.add_argument("--api-key", default=os.environ.get("NCBI_API_KEY"))
    parser.add_argument("--email", default=os.environ.get("NCBI_EMAIL"))
    parser.add_argument("--output", help="结果 JSON；不能位于检查点目录内")
    parser.add_argument("--overwrite-output", action="store_true", help="明确允许替换已有结果文件")
    args = parser.parse_args(argv)
    require(args.query.strip() and args.sort.strip(), "检索式和排序不能为空")
    require(1 <= args.retmax <= UID_LIMIT, f"retmax 必须为 1–{UID_LIMIT}")
    require(1 <= args.batch_size <= 200, "batch-size 必须为 1–200")
    require(1 <= args.retries <= 5, "retries 必须为 1–5")
    require(not args.all or args.checkpoint, "--all 必须提供 --checkpoint")
    require(not args.resume or args.checkpoint, "--resume 必须提供 --checkpoint")
    lower, upper = date_bound(args.mindate), date_bound(args.maxdate, upper=True)
    require(not (lower and upper and lower > upper), "日期范围起点不能晚于终点")
    if args.output:
        output = Path(args.output)
        require(not output.is_symlink(), "输出文件不能是符号链接")
        require(not output.exists() or (args.overwrite_output and output.is_file()), "输出已存在；确认后使用 --overwrite-output，或选择新路径")
        if args.checkpoint:
            resolved, root = output.resolve(), Path(args.checkpoint).resolve()
            require(resolved != root and root not in resolved.parents, "输出文件不能位于检查点目录内")
    return args


def main(argv=None):
    try:
        args = parse_args(argv)
        payload, code = retrieve(args)
        if args.output:
            output = Path(args.output)
            output.parent.mkdir(parents=True, exist_ok=True)
            atomic_json(output, payload, overwrite=args.overwrite_output)
            print(f"已写入 {payload['returned']} 条记录；状态 {payload['status']}", file=sys.stderr)
        else:
            print(json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False))
        return code
    except (ValueError, OSError) as error:
        print(json.dumps({"status": "error", "error": str(error)}, ensure_ascii=False), file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
