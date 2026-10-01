"""PubMed E-utilities 传输和解析；错误消息不包含凭证或完整请求 URL。"""
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

EUTILS = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
UID_LIMIT = 10000  # 本实现保守支持的 UID 清单上限，不承诺自动拆分更大查询。


def now():
    return datetime.now(timezone.utc).isoformat()


class RetrievalError(Exception):
    def __init__(self, code, message):
        super().__init__(message)
        self.code = code


def valid_pmid(value):
    return isinstance(value, str) and re.fullmatch(r"[1-9][0-9]*", value) is not None


class EutilsClient:
    def __init__(self, args):
        self.args = args
        self.interval = 0.11 if args.api_key else 0.34
        self.last_request = None

    def request(self, endpoint, params, post=False):
        params = {"tool": "oh-my-paper", **params}
        if self.args.email:
            params["email"] = self.args.email
        if self.args.api_key:
            params["api_key"] = self.args.api_key
        encoded = urllib.parse.urlencode(params)
        url = f"{EUTILS}/{endpoint}"
        last_code = "network_error"
        for attempt in range(self.args.retries):
            backoff = min(2 ** attempt, 8)
            if self.last_request is not None:
                wait = self.interval - (time.monotonic() - self.last_request)
                if wait > 0:
                    time.sleep(wait)
            self.last_request = time.monotonic()
            request = urllib.request.Request(url if post else f"{url}?{encoded}",
                                             data=encoded.encode() if post else None,
                                             headers={"User-Agent": "oh-my-paper"})
            try:
                with urllib.request.urlopen(request, timeout=30) as response:
                    return response.read()
            except urllib.error.HTTPError as error:
                last_code = f"http_{error.code}"
                retry_after = error.headers.get("Retry-After") if error.headers else None
                # HTTPError 也持有响应流；重试或退出前关闭，避免回收警告打印错误中的请求信息。
                error.close()
                if error.code != 429 and error.code < 500:
                    break
                if retry_after:
                    try:
                        if retry_after.isascii() and retry_after.isdigit():
                            seconds = int(retry_after) if len(retry_after) <= 10 else 61
                        else:
                            when = parsedate_to_datetime(retry_after)
                            seconds = (when - datetime.now(timezone.utc)).total_seconds()
                        backoff = max(backoff, seconds)
                    except (ValueError, TypeError, OverflowError):
                        pass
                if backoff > 60:
                    break  # 保留检查点，让用户稍后恢复，而不是忽略服务端等待时间。
            except (urllib.error.URLError, TimeoutError, OSError):
                last_code = "network_error"
            if attempt + 1 < self.args.retries:
                time.sleep(backoff)
        raise RetrievalError(last_code, f"NCBI 请求未成功（{last_code}），已保留可恢复的进度")

    def json_request(self, endpoint, params, post=False):
        try:
            result = json.loads(self.request(endpoint, params, post=post))
        except (ValueError, UnicodeError) as error:
            raise RetrievalError("invalid_json", "NCBI 返回的 JSON 无法解析") from error
        if not isinstance(result, dict) or result.get("error") or result.get("ERROR"):
            raise RetrievalError("api_error", "NCBI 返回错误对象，不能当作成功结果")
        return result

    def search(self, limit):
        params = {"db": "pubmed", "term": self.args.query, "retmax": str(limit), "retmode": "json",
                  "datetype": self.args.datetype, "sort": self.args.sort}
        for key in ("mindate", "maxdate"):
            if getattr(self.args, key):
                params[key] = getattr(self.args, key)
        raw = self.json_request("esearch.fcgi", params)
        result = raw.get("esearchresult")
        if not isinstance(result, dict) or result.get("errorlist") or result.get("ERROR") or result.get("error"):
            raise RetrievalError("search_error", "ESearch 未返回有效检索结果，请核查检索式")
        count = result.get("count")
        if not ((type(count) is int and count >= 0) or (isinstance(count, str) and count.isascii() and count.isdigit())):
            raise RetrievalError("invalid_count", "ESearch 缺少有效总命中数")
        ids = result.get("idlist")
        if not isinstance(ids, list) or not all(valid_pmid(value) for value in ids) or len(set(ids)) != len(ids):
            raise RetrievalError("invalid_uid_snapshot", "ESearch PMID 清单无效或存在重复")
        count = int(count)
        if len(ids) > min(count, limit):
            raise RetrievalError("invalid_uid_snapshot", "ESearch PMID 数量与请求或命中数不符")
        translation = result.get("querytranslation", "")
        if not isinstance(translation, str):
            raise RetrievalError("invalid_translation", "ESearch 查询转换字段无效")
        return {"total_count": count, "pmids": ids, "executed_at": now(), "query_translation": translation,
                "uid_snapshot_complete": len(ids) == min(count, limit), "raw_response": raw}

    def summaries(self, pmids):
        raw = self.json_request("esummary.fcgi", {"db": "pubmed", "id": ",".join(pmids), "retmode": "json"}, post=True)
        result = raw.get("result")
        if not isinstance(result, dict):
            raise RetrievalError("summary_error", "ESummary 缺少结果对象")
        uids = result.get("uids", [])
        if not isinstance(uids, list) or not all(isinstance(uid, str) and uid in pmids for uid in uids):
            raise RetrievalError("unexpected_pmid", "ESummary 返回非请求的 PMID")
        records = {}
        originals = {}
        for pmid in pmids:
            item = result.get(pmid)
            if not isinstance(item, dict) or item.get("error"):
                continue
            if str(item.get("uid", pmid)) != pmid:
                raise RetrievalError("unexpected_pmid", "ESummary 条目与 PMID 不一致")
            title = item.get("title")
            authors = item.get("authors", [])
            articleids = item.get("articleids", [])
            if not isinstance(title, str) or not title.strip() or not isinstance(authors, list) or not isinstance(articleids, list):
                continue
            if not all(isinstance(author, dict) and isinstance(author.get("name", ""), str) for author in authors):
                continue
            if not all(isinstance(identifier, dict) for identifier in articleids):
                continue
            doi = next((a.get("value", "") for a in articleids if a.get("idtype") == "doi"), "")
            if not isinstance(doi, str):
                continue
            record = {"pmid": pmid, "title": title, "journal": item.get("fulljournalname") or item.get("source", ""),
                      "pubdate": item.get("sortpubdate") or item.get("pubdate", ""),
                      "authors": [a["name"] for a in authors if a.get("name")], "doi": doi,
                      "url": f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/"}
            if not isinstance(record["journal"], str) or not isinstance(record["pubdate"], str):
                continue
            records[pmid] = record
            originals[pmid] = item
        return records, originals

    def abstracts(self, pmids):
        raw = self.request("efetch.fcgi", {"db": "pubmed", "id": ",".join(pmids), "rettype": "abstract", "retmode": "xml"}, post=True)
        try:
            root = ET.fromstring(raw)
        except ET.ParseError as error:
            raise RetrievalError("invalid_xml", "EFetch XML 无法解析") from error
        if root.tag == "ERROR" or root.find(".//ERROR") is not None:
            raise RetrievalError("fetch_error", "EFetch 返回错误，未取得摘要记录")
        nodes = root.findall(".//PubmedArticle") + root.findall(".//PubmedBookArticle")
        if root.tag in ("PubmedArticle", "PubmedBookArticle"):
            nodes.insert(0, root)
        records = {}
        for article in nodes:
            identifier = article.find("./MedlineCitation/PMID")
            if identifier is None:
                identifier = article.find("./BookDocument/PMID")
            if identifier is None or not identifier.text:
                raise RetrievalError("invalid_pmid", "EFetch 条目缺少 PMID")
            pmid = identifier.text.strip()
            if pmid not in pmids or pmid in records:
                raise RetrievalError("unexpected_pmid", "EFetch 返回非请求或重复 PMID")
            if article.tag == "PubmedArticle" and article.find("./MedlineCitation/Article") is None:
                continue  # 缺少文章主体不是“文章没有摘要”。
            parts = []
            for abstract in article.findall(".//Abstract/AbstractText"):
                value = "".join(abstract.itertext()).strip()
                if value:
                    parts.append(f"{abstract.get('Label')}: {value}" if abstract.get("Label") else value)
            mesh = [node.text.strip() for node in article.findall(".//MeshHeading/DescriptorName") if node.text]
            records[pmid] = {"abstract": "\n".join(parts), "mesh_terms": mesh,
                             "abstract_status": "available" if parts else "not_reported"}
        try:
            original = raw.decode("utf-8")
        except UnicodeError as error:
            raise RetrievalError("unexpected_xml_encoding", "EFetch 返回非预期的 XML 编码，不能标记完整取回") from error
        return records, original
