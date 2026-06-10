---
id: remote-experiment
name: Remote Experiment Execution
version: 2.0.0
stages: []
tools: [bash, read_file, write_file]
description: 通过 compute-helper CLI 在远程服务器上自主执行、调试、迭代
summary: Autonomous remote code execution workflow — edit locally, sync, run remotely, analyze output, iterate
primaryIntent: remote_experiment_execution
capabilities:
  - remote_code_sync
  - remote_command_execution
  - iterative_debugging
  - autonomous_optimization
domains:
  - general
  - machine_learning
  - data_processing
  - bioinformatics
keywords:
  - experiment
  - remote
  - server
  - ssh
  - sync
  - compute-helper
  - iterate
---

# Remote Experiment Execution

你可以通过 `compute-helper` CLI 在远程服务器上自主执行代码和命令。适用于任何算力/数据密集型远程任务——ML 训练、**生物信息学流程**（比对 / 变异检测 / 单细胞 / GWAS，需 rsync 大数据集）、大规模数据处理，不限于 GPU 作业。

> compute-helper 路径和服务器信息在 system prompt 的 `<compute_node>` 块中给出。
> 如果没有，用本技能自带的 `scripts/compute-helper.mjs`（与本 SKILL.md 同目录）。

## 节点配置

compute-helper 从 `~/.viewerleaf/compute-nodes.json` 读取节点信息（历史路径，沿用即可）。首次使用前手动创建：

```json
{
  "activeNodeId": "gpu-1",
  "nodes": [
    {
      "id": "gpu-1",
      "name": "Lab GPU server",
      "host": "192.168.1.100",
      "port": 22,
      "user": "researcher",
      "authMethod": "key",
      "keyPath": "~/.ssh/id_ed25519",
      "workDir": "~/experiments"
    }
  ]
}
```

`authMethod` 用 `key`（推荐，配 `keyPath`）。配置好后运行 `node <helper> info` 验证连接信息。

## 命令速查

| 命令 | 用途 | 何时用 |
|---|---|---|
| `node <helper> ssh "<cmd>"` | 仅远程执行命令 | 检查环境、查看文件、不涉及代码改动时 |
| `node <helper> sync up --cwd <root>` | 同步本地代码到服务器 | 手动同步（通常不需要，`run` 自动同步） |
| `node <helper> run "<cmd>" --cwd <root>` | 同步代码 + 远程执行 | 修改代码后需要在服务器运行时 |
| `node <helper> sync down --cwd <root> --files "logs/ results/"` | 从服务器拉回文件 | 需要查看结果文件时 |
| `node <helper> info` | 查看节点配置 | 确认连接信息时 |

## 核心行为规则

### 规则 1：主动执行，不等催促

修改代码后 **必须立即** `run` 远程执行验证，不要修改完就停下来等用户确认。

```
❌ 错误: "我已经修改了代码，你可以运行看看。"
✅ 正确: 修改代码 → 立即 run → 分析输出 → 汇报结果
```

### 规则 2：失败后自主分析修复

远程执行报错时，**立即分析错误输出 → 修改代码 → 再次 run**，形成自修复循环。除非遇到无法判断的问题才向用户求助。

```
❌ 错误: "执行出错了，错误信息如下：..."（等用户处理）
✅ 正确: 分析错误 → 修改代码 → 再次 run → 如果还是失败 → 换策略再试
```

### 规则 3：先探测环境

首次操作远程服务器时，先用 `ssh` 检查环境：
- `which python` / `python3 --version` — Python 是否可用
- `nvidia-smi` — GPU 状态（ML 训练时）
- `which samtools bcftools nextflow snakemake` / `conda env list` — 生信工具链是否就位（生信流程时）
- `pip list | grep <package>` — 依赖是否安装
- `ls <workdir>` / `ls <ref_genome_dir>` — 工作目录、参考基因组/索引状态

### 规则 4：区分 `run` vs `ssh`

- **改了本地代码** → 用 `run`（自动 sync + 执行）
- **只想在服务器上执行某个命令**（查看进程、安装包、看日志） → 用 `ssh`
- **仅需同步代码不执行** → 用 `sync up`

### 规则 5：单变量修改

每次迭代只修改一个变量或一个方面，方便定位问题。同时改多处出错时无法判断哪个改动导致。

## 迭代工作流

当用户要求在服务器上运行/测试/实验：

```
1. ssh 检查环境 ──→ 缺依赖？安装
                        │
2. 修改本地代码 ◄──────┘
        │
3. run 远程执行 ──→ 成功？
        │              ├─ 是 → 汇报结果，问下一步
        │              └─ 否 → 分析错误 → 回到步骤 2
        │
4. (可选) sync down 拉回结果文件
```

## 进度汇报

每次执行后简要说明：
- 做了什么改动、为什么
- 执行结果（成功/失败 + 关键输出）
- 下一步计划

```
📊 执行结果
━━━━━━━━━━
改动: 将 batch_size 从 32 改为 64
命令: python train.py --batch_size 64
结果: ✅ 训练完成，loss 从 0.45 降到 0.32
下一步: 尝试增大学习率到 3e-4
```
