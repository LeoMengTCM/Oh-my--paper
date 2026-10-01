"""题录标识的保守归一化；不按标题推断身份。"""
import re


def optional_text(value, field):
    if value is None:
        return ""
    if not isinstance(value, str):
        raise ValueError(f"{field} 必须是字符串或 null")
    return value.strip()


def normalize_doi(value):
    value = optional_text(value, "doi").lower()
    if not value:
        return ""
    value = re.sub(r"^https?://(?:dx\.)?doi\.org/", "", value)
    value = re.sub(r"^doi:\s*", "", value)
    if not re.fullmatch(r"10\.\d{4,9}/\S+", value):
        raise ValueError(f"DOI 格式无效：{value}")
    return value


def normalize_pmid(value):
    value = optional_text(value, "pmid")
    if not value:
        return ""
    value = re.sub(r"^pmid:\s*", "", value, flags=re.I)
    value = re.sub(r"^https?://pubmed\.ncbi\.nlm\.nih\.gov/", "", value, flags=re.I).rstrip("/")
    if not re.fullmatch(r"[0-9]+", value) or int(value) <= 0:
        raise ValueError(f"PMID 格式无效：{value}")
    return str(int(value))


def identifiers(record):
    return {key: value for key, value in (("doi", normalize_doi(record.get("doi"))),
                                         ("pmid", normalize_pmid(record.get("pmid")))) if value}
