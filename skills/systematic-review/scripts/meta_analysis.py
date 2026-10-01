#!/usr/bin/env python3
"""校验提取证据与分析计划；统计执行只写入独立结果目录。"""
import argparse
import json
import os
import sys

sys.dont_write_bytecode = True

from analysis_records import AnalysisBlocked, prepare_analysis
from analysis_runner import run_analysis
from review_model import require


class Parser(argparse.ArgumentParser):
    def error(self, message):
        raise ValueError(message)


def main(argv=None):
    try:
        parser = Parser(description=__doc__)
        parser.add_argument("command", choices=["validate", "run"])
        parser.add_argument("directory")
        parser.add_argument("--plan", required=True)
        parser.add_argument("--out")
        parser.add_argument("--rscript", default=os.environ.get("RSCRIPT", "Rscript"))
        parser.add_argument("--reason", default="prespecified_analysis", help="本次运行的原因，如预设分析、复现或错误修复")
        args = parser.parse_args(argv)
        require(bool(args.reason.strip()), "运行原因不能为空")
        require(args.command != "run" or args.out, "run 必须指定新的 --out 目录")
        prepared = prepare_analysis(args.directory, args.plan)
        if args.command == "run":
            result = run_analysis(prepared, args.directory, args.out, args.rscript, args.reason)
            print(json.dumps(result, ensure_ascii=False))
            return 0 if result["status"] == "completed" else 2
        print(json.dumps({"status": "ready", "analysis_id": prepared["analysis_id"],
                          "selected_studies": len(prepared["rows"]), "effect_measure": prepared["plan"]["effect_measure"]}, ensure_ascii=False))
        return 0
    except AnalysisBlocked as error:
        print(json.dumps({"status": "blocked", "reason": error.reason, "details": error.details}, ensure_ascii=False))
        return 2
    except (ValueError, OSError) as error:
        print(json.dumps({"status": "error", "error": str(error)}, ensure_ascii=False), file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
