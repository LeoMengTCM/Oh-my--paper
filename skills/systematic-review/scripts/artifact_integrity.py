"""检测运行后产物变动；文件摘要不是研究或人员真实性认证。"""
import hashlib
from pathlib import Path

from review_model import require


def file_digest(path):
    path = Path(path)
    require(path.is_file() and not path.is_symlink(), f"产物不存在或是符号链接：{path}")
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def artifact_digests(directory, names):
    directory = Path(directory)
    require(isinstance(names, list) and all(isinstance(name, str) and name and Path(name).name == name and name not in (".", "..") for name in names),
            "产物清单必须只包含当前目录下的文件名")
    require(len(names) == len(set(names)), "产物清单重复")
    return {name: file_digest(directory / name) for name in names if name != "run_manifest.json"}


def verify_artifacts(directory, manifest):
    expected = manifest.get("artifact_sha256")
    require(isinstance(expected, dict) and expected, "运行没有产物摘要，须复核或重新执行，不能自动补造历史摘要")
    actual = artifact_digests(directory, manifest.get("artifacts"))
    require(set(actual) == set(expected), "产物摘要清单不完整")
    modified = [name for name, digest in actual.items() if expected[name] != digest]
    require(not modified, "运行产物已改变：" + ", ".join(modified))
