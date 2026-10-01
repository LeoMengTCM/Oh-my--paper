"""PubMed 检查点：独占锁、原子写入和请求绑定。"""
from datetime import datetime
import json
import os
from pathlib import Path
import tempfile
import uuid

from pubmed_api import now, valid_pmid


def require(condition, message):
    if not condition:
        raise ValueError(message)


def validate_time(value):
    require(isinstance(value, str) and bool(value), "检查点日期时间无效")
    require(datetime.fromisoformat(value.replace("Z", "+00:00")).tzinfo is not None, "检查点日期时间缺少时区")


def read_json(path):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            require(key not in result, "检查点存在重复 JSON 字段")
            result[key] = value
        return result
    def reject(value):
        raise ValueError("检查点包含非标准 JSON 数值")
    require(not path.is_symlink(), "检查点文件不能是符号链接")
    return json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=unique, parse_constant=reject)


def atomic_json(path, payload, overwrite=True):
    require(not path.is_symlink(), "不能覆盖符号链接输出")
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent, prefix=".pubmed-", delete=False) as handle:
            temporary = Path(handle.name)
            json.dump(payload, handle, ensure_ascii=False, indent=2, allow_nan=False)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        if overwrite:
            os.replace(temporary, path)
        else:
            # 独占发布，避免取回期间出现的同名文件被覆盖。
            os.link(temporary, path)
    finally:
        if temporary is not None and temporary.exists():
            temporary.unlink()


class Checkpoint:
    def __init__(self, directory, request, resume=False):
        self.directory = Path(directory) if directory else None
        self.request = request
        self.resume = resume
        self.locked = False
        self.state = None
        self.memory = {}

    def __enter__(self):
        try:
            if self.directory:
                require(not self.directory.is_symlink(), "检查点目录不能是符号链接")
                if self.resume:
                    require(self.directory.is_dir(), "找不到要恢复的检查点目录")
                self.directory.mkdir(parents=True, exist_ok=True)
                try:
                    with (self.directory / ".lock").open("x", encoding="utf-8") as handle:
                        self.locked = True
                        json.dump({"pid": os.getpid(), "created_at": now()}, handle)
                except FileExistsError as error:
                    raise ValueError("检查点正在使用或遗留 .lock；确认原进程停止后再由用户处理，不自动删除锁") from error
                if self.resume:
                    self.state = read_json(self.directory / "checkpoint.json")
                    require(isinstance(self.state, dict) and type(self.state.get("schema_version")) is int and self.state["schema_version"] == 1,
                            "不支持的检查点格式")
                    require(self.state.get("request") == self.request, "恢复参数与原查询、日期、模式或批大小不一致")
                    require(isinstance(self.state.get("run_id"), str) and self.state["run_id"], "检查点缺少 run_id")
                    require("search" in self.state, "检查点缺少搜索快照字段")
                    validate_time(self.state.get("started_at"))
                    require(isinstance(self.state.get("search_attempts"), list), "检查点搜索尝试记录无效")
                    for attempt in self.state["search_attempts"]:
                        require(isinstance(attempt, dict), "检查点搜索尝试条目无效")
                        validate_time(attempt.get("executed_at"))
                        require(type(attempt.get("total_count")) is int and type(attempt.get("selected")) is int and
                                0 <= attempt["selected"] <= attempt["total_count"], "检查点搜索尝试计数无效")
                else:
                    require(not any(p.name != ".lock" for p in self.directory.iterdir()), "检查点目录非空；使用 --resume 或选择新目录")
                batch_dir = self.directory / "batches"
                require(not batch_dir.is_symlink(), "批次目录不能是符号链接")
                batch_dir.mkdir(exist_ok=True)
            if self.state is None:
                self.state = {"schema_version": 1, "run_id": str(uuid.uuid4()), "request": self.request,
                              "started_at": now(), "search": None, "search_attempts": []}
                self.save_state()
            return self
        except BaseException:
            self.release()
            raise

    def release(self):
        if self.locked:
            (self.directory / ".lock").unlink()
            self.locked = False

    def __exit__(self, *exc):
        self.release()

    def save_state(self):
        if self.directory:
            atomic_json(self.directory / "checkpoint.json", self.state)

    def load_batch(self, offset, pmids):
        path = self.directory / "batches" / f"{offset:05d}.json" if self.directory else None
        if path is not None and path.exists():
            batch = read_json(path)
        else:
            batch = self.memory.get(offset)
        if batch is None:
            batch = {"schema_version": 1, "run_id": self.state["run_id"], "pmids": pmids,
                     "summaries": {}, "abstracts": {}, "responses": []}
        require(isinstance(batch, dict) and type(batch.get("schema_version")) is int and batch["schema_version"] == 1,
                "批次格式无效")
        require(batch.get("run_id") == self.state["run_id"] and batch.get("pmids") == pmids, "批次不属于当前运行或 PMID 清单")
        for key in ("summaries", "abstracts"):
            values = batch.get(key)
            require(isinstance(values, dict) and set(values).issubset(pmids), "批次缓存存在非请求的 PMID")
            for pmid, item in values.items():
                require(valid_pmid(pmid) and isinstance(item, dict), "批次缓存条目无效")
                if key == "summaries":
                    require(item.get("pmid") == pmid and isinstance(item.get("title"), str) and item["title"].strip(),
                            "缓存元数据 PMID 或标题无效")
                    require(all(isinstance(item.get(field), str) for field in ("journal", "pubdate", "doi", "url")) and
                            isinstance(item.get("authors"), list) and all(isinstance(author, str) for author in item["authors"]),
                            "缓存元数据字段无效")
                else:
                    require(isinstance(item.get("abstract"), str) and isinstance(item.get("mesh_terms"), list) and
                            all(isinstance(term, str) for term in item["mesh_terms"]) and
                            item.get("abstract_status") in ("available", "not_reported"), "缓存摘要无效")
                    require(bool(item["abstract"].strip()) == (item["abstract_status"] == "available"), "缓存摘要状态与正文不符")
        require(isinstance(batch.get("responses"), list), "缓存缺少响应记录")
        return batch

    def save_batch(self, offset, batch):
        if self.directory:
            atomic_json(self.directory / "batches" / f"{offset:05d}.json", batch)
        self.memory[offset] = batch
