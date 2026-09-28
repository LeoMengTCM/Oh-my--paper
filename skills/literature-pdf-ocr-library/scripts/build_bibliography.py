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

Chinese papers get pinyin keys (``张三 2023 基于深度学习的…`` → ``zhang2023shendu``):
the surname comes from a built-in table, the title word needs the optional
``pypinyin`` package and falls back to ``paper`` without it.

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


CJK_RE = re.compile(r"[㐀-䶿一-鿿]")

# Chinese compound surnames, checked before falling back to the first character.
COMPOUND_SURNAMES = {
    "欧阳": "ouyang", "司马": "sima", "诸葛": "zhuge", "上官": "shangguan",
    "东方": "dongfang", "皇甫": "huangfu", "尉迟": "yuchi", "公孙": "gongsun",
    "慕容": "murong", "令狐": "linghu", "长孙": "zhangsun", "宇文": "yuwen",
    "司徒": "situ", "夏侯": "xiahou", "轩辕": "xuanyuan", "端木": "duanmu",
    "独孤": "dugu", "南宫": "nangong", "西门": "ximen", "闻人": "wenren",
    "申屠": "shentu", "澹台": "tantai", "万俟": "moqi", "钟离": "zhongli",
    "呼延": "huyan", "太史": "taishi", "公冶": "gongye", "赫连": "helian",
    "拓跋": "tuoba",
}

# Surname readings for common single-character surnames. Checked before
# pypinyin, because polyphonic surnames (曾 zeng, 单 shan, 仇 qiu, 解 xie,
# 区 ou, 朴 piao, 查 zha, 覃 qin ...) read differently from the everyday word.
SURNAME_PINYIN = {
    "王": "wang", "李": "li", "张": "zhang", "刘": "liu", "陈": "chen", "杨": "yang",
    "黄": "huang", "赵": "zhao", "吴": "wu", "周": "zhou", "徐": "xu", "孙": "sun",
    "马": "ma", "朱": "zhu", "胡": "hu", "郭": "guo", "何": "he", "高": "gao",
    "林": "lin", "罗": "luo", "郑": "zheng", "梁": "liang", "谢": "xie", "宋": "song",
    "唐": "tang", "许": "xu", "韩": "han", "冯": "feng", "邓": "deng", "曹": "cao",
    "彭": "peng", "曾": "zeng", "肖": "xiao", "萧": "xiao", "田": "tian", "董": "dong",
    "袁": "yuan", "潘": "pan", "于": "yu", "蒋": "jiang", "蔡": "cai", "余": "yu",
    "杜": "du", "叶": "ye", "程": "cheng", "苏": "su", "魏": "wei", "吕": "lv",
    "丁": "ding", "任": "ren", "沈": "shen", "姚": "yao", "卢": "lu", "姜": "jiang",
    "崔": "cui", "钟": "zhong", "谭": "tan", "陆": "lu", "汪": "wang", "范": "fan",
    "金": "jin", "石": "shi", "廖": "liao", "贾": "jia", "夏": "xia", "韦": "wei",
    "付": "fu", "傅": "fu", "方": "fang", "白": "bai", "邹": "zou", "孟": "meng",
    "熊": "xiong", "秦": "qin", "邱": "qiu", "江": "jiang", "尹": "yin", "薛": "xue",
    "闫": "yan", "阎": "yan", "段": "duan", "雷": "lei", "侯": "hou", "龙": "long",
    "史": "shi", "陶": "tao", "黎": "li", "贺": "he", "顾": "gu", "毛": "mao",
    "郝": "hao", "龚": "gong", "邵": "shao", "万": "wan", "钱": "qian", "严": "yan",
    "覃": "qin", "武": "wu", "戴": "dai", "莫": "mo", "孔": "kong", "向": "xiang",
    "汤": "tang", "常": "chang", "温": "wen", "康": "kang", "施": "shi", "文": "wen",
    "牛": "niu", "樊": "fan", "葛": "ge", "邢": "xing", "安": "an", "齐": "qi",
    "易": "yi", "乔": "qiao", "伍": "wu", "庞": "pang", "颜": "yan", "倪": "ni",
    "庄": "zhuang", "聂": "nie", "章": "zhang", "鲁": "lu", "岳": "yue", "翟": "zhai",
    "殷": "yin", "詹": "zhan", "申": "shen", "欧": "ou", "耿": "geng", "关": "guan",
    "兰": "lan", "焦": "jiao", "俞": "yu", "左": "zuo", "柳": "liu", "甘": "gan",
    "祝": "zhu", "包": "bao", "宁": "ning", "尚": "shang", "符": "fu", "舒": "shu",
    "阮": "ruan", "柯": "ke", "纪": "ji", "梅": "mei", "童": "tong", "凌": "ling",
    "毕": "bi", "单": "shan", "季": "ji", "裴": "pei", "霍": "huo", "涂": "tu",
    "成": "cheng", "苗": "miao", "谷": "gu", "盛": "sheng", "曲": "qu", "翁": "weng",
    "冉": "ran", "骆": "luo", "蓝": "lan", "路": "lu", "游": "you", "辛": "xin",
    "靳": "jin", "管": "guan", "柴": "chai", "蒙": "meng", "鲍": "bao", "华": "hua",
    "喻": "yu", "祁": "qi", "蒲": "pu", "房": "fang", "滕": "teng", "屈": "qu",
    "饶": "rao", "解": "xie", "牟": "mou", "艾": "ai", "尤": "you", "阳": "yang",
    "时": "shi", "穆": "mu", "农": "nong", "司": "si", "卓": "zhuo", "古": "gu",
    "吉": "ji", "缪": "miao", "简": "jian", "车": "che", "项": "xiang", "连": "lian",
    "芦": "lu", "麦": "mai", "褚": "chu", "娄": "lou", "窦": "dou", "戚": "qi",
    "岑": "cen", "景": "jing", "党": "dang", "宫": "gong", "费": "fei", "卜": "bu",
    "冷": "leng", "晏": "yan", "席": "xi", "卫": "wei", "米": "mi", "柏": "bai",
    "宗": "zong", "瞿": "qu", "桂": "gui", "全": "quan", "佟": "tong", "应": "ying",
    "臧": "zang", "闵": "min", "苟": "gou", "邬": "wu", "边": "bian", "卞": "bian",
    "姬": "ji", "师": "shi", "和": "he", "仇": "qiu", "栾": "luan", "隋": "sui",
    "商": "shang", "刁": "diao", "沙": "sha", "荣": "rong", "巫": "wu", "寇": "kou",
    "桑": "sang", "郎": "lang", "甄": "zhen", "丛": "cong", "仲": "zhong", "虞": "yu",
    "敖": "ao", "巩": "gong", "明": "ming", "佘": "she", "池": "chi", "查": "zha",
    "麻": "ma", "苑": "yuan", "迟": "chi", "邝": "kuang", "区": "ou", "朴": "piao",
    "乐": "yue", "盖": "ge", "员": "yun", "郁": "yu", "封": "feng", "储": "chu",
    "宿": "su", "薄": "bo", "燕": "yan", "蔺": "lin", "井": "jing", "鞠": "ju",
    "冀": "ji", "惠": "hui", "荆": "jing", "雍": "yong", "巴": "ba", "楼": "lou",
    "权": "quan", "鄢": "yan", "戈": "ge", "那": "na", "贝": "bei", "秋": "qiu",
    "蔚": "yu", "逯": "lu", "厉": "li", "茅": "mao", "伏": "fu", "竺": "zhu",
    "晋": "jin", "束": "shu", "裘": "qiu", "奚": "xi", "仝": "tong", "种": "chong",
    "召": "shao", "繁": "po", "秘": "bi",
}

# Leading words of Chinese titles that say nothing about the topic.
CHINESE_TITLE_PREFIXES = ("基于", "关于", "浅谈", "浅析", "试论", "试析", "略论", "一种", "一例")


def _pinyin(text: str) -> Optional[str]:
    """Toneless pinyin via the optional pypinyin package; None if it is not installed."""
    try:
        from pypinyin import lazy_pinyin  # type: ignore
    except ImportError:
        return None
    return "".join(lazy_pinyin(text))


def chinese_surname(name: str) -> Optional[str]:
    han = "".join(CJK_RE.findall(name or ""))
    if not han:
        return None
    if han[:2] in COMPOUND_SURNAMES:
        return COMPOUND_SURNAMES[han[:2]]
    return SURNAME_PINYIN.get(han[0]) or _pinyin(han[0])


def derive_lastname(name: str) -> str:
    # Keep latin + accented letters; drop all-caps initials like "JA" in "Smith JA".
    tokens = re.findall(r"[A-Za-zÀ-ɏ]+", name or "")
    candidates = [token for token in tokens if not (len(token) <= 2 and token.isupper())]
    if not candidates:
        candidates = tokens
    if candidates:
        return candidates[-1]
    return chinese_surname(name) or "anon"


def chinese_title_word(title: str) -> Optional[str]:
    """Pinyin of the first two characters after a filler prefix (needs pypinyin)."""
    han = "".join(CJK_RE.findall(title or ""))
    for prefix in CHINESE_TITLE_PREFIXES:
        if han.startswith(prefix) and len(han) >= len(prefix) + 2:
            han = han[len(prefix):]
            break
    if len(han) < 2:
        return None
    word = _pinyin(han[:2])
    return word.lower() if word else None


def first_title_word(title: str) -> str:
    latin_words = re.findall(r"[A-Za-z]+", title or "")
    # A mostly-Chinese title ("…的Meta分析") keys on its Chinese words, not the stray English one.
    if len(CJK_RE.findall(title or "")) > sum(len(word) for word in latin_words):
        word = chinese_title_word(title)
        if word:
            return word
    for word in latin_words:
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
