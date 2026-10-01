"""核对本地书目、原始元数据与保存的核验记录；不联网、不改写引用键。"""
from datetime import datetime
from html import unescape
from html.parser import HTMLParser
from pathlib import Path
import re
import unicodedata
from urllib.parse import unquote, urlsplit

from identifiers import normalize_doi, normalize_pmid
from review_model import parse_json


_KEY = re.compile(r"[A-Za-z0-9:_\.\-]+", re.ASCII)


def _require(condition, message):
    if not condition:
        raise ValueError(message)


def _string(value, label):
    _require(isinstance(value, str) and bool(value.strip()), f"{label} 必须是非空字符串")
    return value


class _PlainText(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts = []

    def handle_data(self, data):
        self.parts.append(data)


def _text(value):
    parser = _PlainText()
    parser.feed(_string(value, "文字字段"))
    return " ".join(unicodedata.normalize("NFC", unescape("".join(parser.parts))).casefold().split()).rstrip(".。")


def _authors(value):
    _require(isinstance(value, list) and bool(value), "authors 必须是非空姓名数组")
    # 保留姓名顺序及拼写，不扩展缩写、不猜测姓与名的顺序。
    return [_text(name) for name in value]


def _year(value):
    _require(type(value) in (int, str) and re.fullmatch(r"[0-9]{4}", str(value)), "year 必须为四位年份")
    return str(value)


def _arxiv(value):
    if value is None or value == "":
        return ""
    value = _string(value, "arxiv_id").strip().casefold()
    value = re.sub(r"^https?://(?:www\.)?arxiv\.org/(?:abs|pdf)/", "", value)
    value = re.sub(r"^arxiv:\s*", "", value)
    return value.removesuffix(".pdf")


def _identity(record):
    _require(isinstance(record, dict), "元数据必须是对象")
    return {
        "title": _text(record.get("title")),
        "authors": _authors(record.get("authors")),
        "year": _year(record.get("year")),
        "doi": normalize_doi(record.get("doi")),
        "arxiv_id": _arxiv(record.get("arxiv_id")),
    }


def _same(left, right, fields):
    for field in fields:
        _require(left[field] == right[field], f"{field} 与原始元数据不一致")


def _path(base, value, label):
    path = Path(_string(value, label)).expanduser()
    return path if path.is_absolute() else base / path


def _json_file(path):
    try:
        return parse_json(path.read_text(encoding="utf-8-sig"), str(path))
    except (OSError, UnicodeError) as error:
        raise ValueError(f"JSON 文件不存在或不可读：{path}") from error


def _newline(value):
    return value.replace("\r\n", "\n").replace("\r", "\n")


def _bib_fields(value, key):
    """读取生成器使用的字面量字段；拒绝宏、拼接表达式及额外条目。"""
    value = _string(value, "bibtex")
    header = re.match(r"\s*@([A-Za-z]+)\s*\{([^,\s]+)\s*,", value)
    _require(header is not None and header[1].lower() not in ("comment", "preamble", "string"), "BibTeX 条目不可解析")
    _require(header[2] == key, "BibTeX 引用键与 entries 键不一致")
    position, fields = header.end(), {}
    while True:
        while position < len(value) and value[position].isspace():
            position += 1
        if position < len(value) and value[position] == "}":
            _require(not value[position + 1:].strip(), "BibTeX 含额外条目或尾随内容")
            return fields
        match = re.match(r"([A-Za-z][A-Za-z0-9_-]*)\s*=\s*", value[position:])
        _require(match is not None, "BibTeX 字段不可解析")
        field = match[1].lower()
        _require(field not in fields, f"BibTeX 重复字段：{field}")
        position += match.end()
        _require(position < len(value), "BibTeX 字段值缺失")
        start = position
        opening = value[position]
        if opening in ('{', '"'):
            position += 1
            start = position
            depth = 1 if opening == "{" else 0
            while position < len(value):
                char = value[position]
                if char == "\\":
                    position += 2
                    continue
                if char == "{":
                    depth += 1
                elif char == "}":
                    depth -= 1
                    if opening == "{" and depth == 0:
                        break
                    _require(depth >= 0, "BibTeX 字段括号不成对")
                elif char == '"' and opening == '"' and depth == 0:
                    break
                position += 1
            _require(position < len(value), "BibTeX 字段未闭合")
            raw = value[start:position]
            position += 1
        else:
            number = re.match(r"[0-9]+", value[position:])
            _require(number is not None, "BibTeX 字段须为字面量，不解析宏")
            raw = number[0]
            position += number.end()
        fields[field] = re.sub(r"\\([&%#_{}])", r"\1", raw)
        while position < len(value) and value[position].isspace():
            position += 1
        _require(position < len(value) and value[position] in ",}", "BibTeX 字段分隔符缺失")
        if value[position] == ",":
            position += 1


def _validate_entry(key, entry):
    _require(_KEY.fullmatch(key) is not None, "引用键仅允许安全 ASCII 字母数字及 :_-. ")
    _require(isinstance(entry, dict) and entry.get("citation_key") == key, "entry.citation_key 与 entries 键不一致")
    fields = _bib_fields(entry.get("bibtex"), key)
    identity = _identity(entry)
    bib_identity = _identity({
        "title": fields.get("title"),
        "authors": re.split(r"\s+and\s+", fields.get("author", "")),
        "year": fields.get("year"), "doi": fields.get("doi"),
        "arxiv_id": fields.get("eprint"),
    })
    _same(bib_identity, identity, ("title", "authors", "year", "doi"))
    if "eprint" in fields:
        _same(bib_identity, identity, ("arxiv_id",))
    provenance = entry.get("provenance")
    _require(isinstance(provenance, dict), "缺少 provenance 对象")
    _string(provenance.get("origin"), "provenance.origin")
    _string(provenance.get("metadata_path"), "provenance.metadata_path")
    _platforms(provenance.get("source_platforms"))


def _platforms(value):
    _require(isinstance(value, list), "source_platforms/merged_sources 必须为数组")
    names = [_string(name, "来源平台") for name in value]
    _require(len(names) == len(set(names)), "来源平台重复")
    return set(names)


def _metadata(base, entry, key):
    provenance = entry["provenance"]
    metadata = _json_file(_path(base, provenance["metadata_path"], "metadata_path"))
    _require(isinstance(metadata, dict) and metadata.get("citation_key") == key, "metadata.citation_key 不一致")
    _same(_identity(entry), _identity(metadata), ("title", "authors", "year", "doi", "arxiv_id"))
    merged = metadata.get("merged_sources")
    source = metadata.get("source")
    if source is not None:
        _string(source, "metadata.source")
    sources = _platforms(merged) if merged is not None else set()
    if sources and source:
        _require(source in sources, "metadata.source 不在 merged_sources 中")
    expected = sources or ({source} if source else set())
    _require(_platforms(provenance["source_platforms"]) == expected, "source_platforms 与原始来源声明不一致")
    return metadata


def _url(value):
    value = _string(value, "source_url")
    parsed = urlsplit(value)
    _require(parsed.scheme in ("http", "https") and parsed.hostname and not parsed.username and not parsed.password,
             "source_url 必须是无账号信息的 HTTP(S) URL")
    _require(not any(char.isspace() for char in value), "source_url 含空白字符")
    return parsed


def _verification(base, record, metadata, reviewers):
    _require(type(record.get("schema_version")) is int and record["schema_version"] == 1,
             "核验记录仅支持 schema_version=1")
    _string(record.get("verification_id"), "verification_id")
    checked_by = _string(record.get("checked_by"), "checked_by")
    _require(checked_by in reviewers, "checked_by 未登记")
    checked_at = _string(record.get("checked_at"), "checked_at")
    try:
        date = datetime.fromisoformat(checked_at.replace("Z", "+00:00"))
    except ValueError as error:
        raise ValueError("checked_at 必须是含时区的 ISO 日期时间") from error
    _require(date.tzinfo is not None and date.utcoffset() is not None, "checked_at 必须包含时区")
    source_url = record.get("source_url")
    url = _url(source_url)
    evidence = _json_file(_path(base, record.get("evidence_path"), "evidence_path"))
    _require(isinstance(evidence, dict), "核验证据必须是 JSON 对象")
    identity = _identity(metadata)
    source_type = record.get("source_type")
    if source_type == "crossref":
        _require(url.scheme == "https" and url.netloc.lower() == "api.crossref.org" and
                 url.path.startswith("/works/") and not url.query and not url.fragment,
                 "Crossref source_url 必须指向 api.crossref.org/works/对应DOI")
        _require(bool(identity["doi"]) and normalize_doi(unquote(url.path[len("/works/"):])) == identity["doi"],
                 "Crossref URL 中的 DOI 与元数据不一致")
        message = evidence.get("message")
        _require(isinstance(message, dict), "缺少 Crossref message 对象")
        titles, authors = message.get("title"), message.get("author")
        _require(isinstance(titles, list) and len(titles) == 1, "Crossref title 必须含唯一标题")
        _require(isinstance(authors, list) and bool(authors), "Crossref author 缺失")
        names = []
        for author in authors:
            _require(isinstance(author, dict), "Crossref author 必须为对象")
            given = author.get("given", "")
            family = author.get("family", "")
            _require(isinstance(given, str) and isinstance(family, str), "Crossref 作者姓名字段无效")
            names.append(_string(f"{given} {family}".strip(), "Crossref 作者姓名"))
        issued = message.get("issued")
        parts = issued.get("date-parts") if isinstance(issued, dict) else None
        _require(isinstance(parts, list) and len(parts) == 1 and isinstance(parts[0], list) and bool(parts[0]),
                 "Crossref issued.date-parts 缺失")
        actual = _identity({"title": titles[0], "authors": names, "year": parts[0][0], "doi": message.get("DOI")})
        compared = ["title", "authors", "year", "doi"]
        _same(actual, identity, compared)
        level = "crossref_snapshot_checked"
    elif source_type == "manual":
        _require(reviewers[checked_by]["kind"] == "human", "人工核验必须由登记的人类研究者完成")
        _require(evidence.get("source_url") == source_url, "人工证据 source_url 与核验记录不一致")
        actual = _identity(evidence)
        compared = ["title", "authors", "year", "doi", "arxiv_id"]
        _same(actual, identity, compared)
        level = "manual_record_checked"
    else:
        raise ValueError("source_type 仅支持 crossref 或 manual")
    # 只返回匹配摘要，不复制证据响应、作者附加信息或私密字段。
    return {"verification_level": level, "verification_id": record["verification_id"],
            "source_type": source_type, "source_url": source_url, "checked_at": checked_at,
            "matched_fields": compared}


def check_citations(review_directory, config, included_reports, reviewers):
    """返回引用检查与可预览的原条目；整体格式错误抛 ValueError，引用问题记为 blocker。

    配置及 evidence_path 相对 review_directory；provenance.metadata_path 相对
    bibliography.json 所在目录。bib_out 必须为生成器记录的绝对路径。
    """
    base = Path(review_directory)
    _require(isinstance(config, dict), "引用配置必须是对象")
    report_map = config.get("report_citations")
    methods = config.get("method_citations")
    _require(isinstance(report_map, dict), "report_citations 必须是对象")
    _require(isinstance(methods, list), "method_citations 必须是数组")
    for report_id, key in report_map.items():
        _string(report_id, "report_id")
        _string(key, "citation_key")
    for key in methods:
        _string(key, "method_citations 引用键")
    _require(isinstance(included_reports, list), "included_reports 必须是数组")
    reports = {}
    for report in included_reports:
        _require(isinstance(report, dict), "纳入报告必须是对象")
        report_id = _string(report.get("report_id"), "report_id")
        _require(report_id not in reports, "included_reports 含重复 report_id")
        reports[report_id] = report
    _require(isinstance(reviewers, dict), "reviewers 必须是对象")
    for reviewer_id, reviewer in reviewers.items():
        _string(reviewer_id, "reviewer_id")
        _require(isinstance(reviewer, dict) and reviewer.get("kind") in ("human", "ai"), "reviewer.kind 无效")

    bibliography_path = _path(base, config.get("bibliography"), "bibliography")
    bibliography = _json_file(bibliography_path)
    _require(isinstance(bibliography, dict) and isinstance(bibliography.get("entries"), dict), "bibliography.entries 必须是对象")
    all_entries = bibliography["entries"]
    skipped = bibliography.get("skipped")
    _require(isinstance(skipped, list), "bibliography.skipped 必须是数组")
    for field, expected in (("count", len(all_entries)), ("skipped_count", len(skipped))):
        _require(type(bibliography.get(field)) is int and bibliography[field] == expected, f"bibliography.{field} 与实际条目数不一致")
    _require(isinstance(bibliography.get("generated_from"), list) and
             all(isinstance(path, str) for path in bibliography["generated_from"]), "generated_from 必须是路径数组")
    bib_path = Path(_string(bibliography.get("bib_out"), "bib_out"))
    _require(bib_path.is_absolute(), "bib_out 必须是绝对路径")

    blockers, entries, metadata, checks = [], {}, {}, []
    invalid_keys = set()

    def block(code, message, key=None, report_id=None):
        item = {"code": code, "message": message}
        if key is not None:
            item["citation_key"] = key
            invalid_keys.add(key)
        if report_id is not None:
            item["report_id"] = report_id
        blockers.append(item)

    selected = {report_id: report_map[report_id] for report_id in reports if report_id in report_map}
    used_keys = sorted(set(selected.values()) | set(methods))
    for report_id in reports:
        if report_id not in selected:
            block("citation_report_missing", "纳入报告缺少引用键映射", report_id=report_id)
    for report_id, key in report_map.items():
        if report_id not in reports:
            block("citation_report_not_included", "引用映射指向非当前纳入报告", key, report_id)
    first_report = {}
    for report_id, key in selected.items():
        if key in first_report:
            block("citation_report_duplicate", f"不同报告共用引用键，请核查重复报告：{first_report[key]}", key, report_id)
        first_report[key] = report_id
    for key, entry in all_entries.items():
        try:
            _validate_entry(key, entry)
        except ValueError as error:
            block("citation_entry_invalid", str(error), key)
        else:
            if key in used_keys:
                entries[key] = entry

    try:
        full_bib = bib_path.read_text(encoding="utf-8")
        _require(all(isinstance(entry, dict) and isinstance(entry.get("bibtex"), str) for entry in all_entries.values()),
                 "entries 缺少可拼接的 BibTeX 文本")
        expected_bib = "".join(all_entries[key]["bibtex"] for key in sorted(all_entries))
        _require(_newline(full_bib) == _newline(expected_bib), "bib_out 与全部 entries 的原始 BibTeX 拼接不一致")
    except (OSError, UnicodeError, ValueError) as error:
        block("citation_bibtex_mismatch", str(error))
        invalid_keys.update(used_keys)

    records = {}
    verification_path = config.get("verification_records")
    if verification_path not in (None, ""):
        path = _path(base, verification_path, "verification_records")
        try:
            lines = path.read_text(encoding="utf-8-sig").splitlines()
        except (OSError, UnicodeError) as error:
            raise ValueError(f"核验记录文件不存在或不可读：{path}") from error
        for number, line in enumerate(lines, 1):
            if not line.strip():
                continue
            record = parse_json(line, f"{path}:{number}")
            _require(isinstance(record, dict), "核验记录每行必须为对象")
            key = _string(record.get("citation_key"), "verification.citation_key")
            records.setdefault(key, []).append(record)

    for key in used_keys:
        check = {"citation_key": key, "status": "invalid", "verification_level": "none"}
        checks.append(check)
        if not _KEY.fullmatch(key):
            block("citation_key_invalid", "引用键仅允许安全 ASCII 字母数字及 :_-.", key)
            continue
        if key not in all_entries:
            block("citation_entry_missing", "bibliography.entries 缺少引用键", key)
            continue
        if key not in entries:
            continue
        try:
            metadata[key] = _metadata(bibliography_path.parent, entries[key], key)
        except ValueError as error:
            block("citation_metadata_invalid", str(error), key)
            continue
        for report_id, mapped_key in selected.items():
            if mapped_key != key:
                continue
            report = reports[report_id]
            try:
                _require(_text(report.get("title")) == _text(metadata[key].get("title")), "报告 title 与引用元数据不一致")
                for field, normalize in (("doi", normalize_doi), ("pmid", normalize_pmid)):
                    identifier = normalize(report.get(field))
                    if identifier:
                        _require(identifier == normalize(metadata[key].get(field)), f"报告 {field} 与引用元数据不一致")
            except ValueError as error:
                block("citation_report_mismatch", str(error), key, report_id)
        candidates = records.get(key, [])
        if not candidates:
            # source/merged_sources 仅为来源声明，绝不能充当外部核验记录。
            if key not in invalid_keys:
                check["status"] = "unverified"
            blockers.append({"code": "citation_unverified", "message": "缺少可核对的外部核验记录", "citation_key": key})
        elif len(candidates) > 1:
            block("citation_verification_ambiguous", "同一引用键有多个核验记录；请去除重复并消除冲突，不能自动选最新记录", key)
        else:
            try:
                check.update(_verification(base, candidates[0], metadata[key], reviewers))
                if key not in invalid_keys:
                    check["status"] = "matched"
            except ValueError as error:
                block("citation_verification_invalid", str(error), key)
    return {"entries": entries, "metadata": metadata, "checks": checks, "used_keys": used_keys,
            "report_citations": selected, "blockers": blockers,
            "bibtex": "".join(entries[key]["bibtex"] for key in sorted(entries))}
