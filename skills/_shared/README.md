# 共享参考（vendored from CCFA-Skills）

本目录不是 skill（没有 SKILL.md，不会进 `research-catalog.json`）。这里放的是被
多个论文类 skill 引用的共享规则，来自 CCFA-Skills 的 `_shared/`。

来源：https://github.com/mikubaka88/CCFA-Skills @ `fd5c7e3afcc097d874d296a0e1e8118ae597f847`（MIT）

引用方式：从 skill 目录用 `../_shared/<file>` 引用。

未吸收的上游文件：`routing.md`、`skill-trigger-registry.yaml`（CCFA 家族内部路由，
本仓库用 `research-stage-map.json` + conductor agent 代替）、`ccfa-yaml-contract.md`
（与本仓库的 `.pipeline/` 状态模型冲突）。
