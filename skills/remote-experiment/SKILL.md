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
  - clinical-medicine
keywords:
  - experiment
  - remote
  - server
  - ssh
  - sync
  - compute-helper
  - iterate
  - hpc
  - statistics
---

# Remote Experiment Execution

你可以通过 `compute-helper` CLI 在远程服务器上自主执行代码和命令。适用于任何需要在远程机器上跑的分析：

- **临床 / 流行病学统计**：在医院或课题组的分析服务器上跑 R / Stata / SAS / Python 统计脚本——患者数据按规定只能留在那台机器上时尤其需要。
- **系统综述 / Meta 分析**：在远程 R 环境跑 `metafor` / `meta`。
- **生物信息学流程**：比对 / 变异检测 / 单细胞 / GWAS，需要 HPC 和大数据集。
- **机器学习训练**：GPU 服务器。

> compute-helper 路径和服务器信息在 system prompt 的 `<compute_node>` 块中给出。
> 如果没有，用本技能自带的 `scripts/compute-helper.mjs`（与本 SKILL.md 同目录）。

**开始前先读 `.pipeline/docs/research_brief.json` 里的 `pipeline.track` 和 `pipeline.analysisMode`**——它决定下面规则 2 和规则 5 能做到哪一步。

## 节点配置

compute-helper 从 `~/.viewerleaf/compute-nodes.json` 读取节点信息（历史路径，沿用即可）。首次使用前手动创建：

```json
{
  "activeNodeId": "analysis-1",
  "nodes": [
    {
      "id": "analysis-1",
      "name": "Lab analysis server",
      "host": "192.168.1.100",
      "port": 22,
      "user": "researcher",
      "authMethod": "key",
      "keyPath": "~/.ssh/id_ed25519",
      "workDir": "~/projects"
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

**同步是怎么工作的**：`sync up`（以及每次 `run`）把整个 `--cwd` 目录 rsync 到服务器，遵守 `.gitignore`，并带 `--delete`——服务器项目目录里本地没有、又没被 `.gitignore` 排除的文件**会被删掉**。所以远程生成的结果目录（`results/`、`logs/` 等）要么写进 `.gitignore`，要么在下一次 `run` 之前先 `sync down`。`sync down` 不带 `--files` 时默认拉 `logs/ checkpoints/ results/`。

## 核心行为规则

### 规则 0：患者数据不离开批准的服务器（临床 / 综述中涉及个体数据时）

- 个体层面的数据（病历、检验结果、随访表，即使做过去标识化）只存在于伦理 / 数据使用协议批准的那台服务器上。**不要把它放进本地项目目录**——放了，`run` 就会把它 rsync 到当前节点，而当前节点未必是批准的那台。本地若确有数据目录，先确认它在 `.gitignore` 里。
- `sync down` **只拉汇总结果**：统计表、模型摘要、图、日志。不拉行级数据，也不拉可以还原出个体的明细（例如小格子计数 < 5 的交叉表，按机构规定处理）。
- 不确定某个文件能不能拉回本地时，先问用户，不要自己判断。

### 规则 1：主动执行，不等催促

修改代码后 **必须立即** `run` 远程执行验证，不要修改完就停下来等用户确认。

```
❌ 错误: "我已经修改了代码，你可以运行看看。"
✅ 正确: 修改代码 → 立即 run → 分析输出 → 汇报结果
```

### 规则 2：失败后自主分析修复——修的是"跑不通"，不是"结果不好"

远程执行报错时，**立即分析错误输出 → 修改代码 → 再次 run**，形成自修复循环。除非遇到无法判断的问题才向用户求助。

```
❌ 错误: "执行出错了，错误信息如下：..."（等用户处理）
✅ 正确: 分析错误 → 修改代码 → 再次 run → 如果还是失败 → 换策略再试
```

自修复只针对**执行错误**：缺包、路径错、语法错、内存不足、数据读入格式不对。`analysisMode` 为 **confirmatory**（临床 / 综述默认）时，**不准为了改变结果去动分析本身**——结局定义、纳排标准、协变量、模型、缺失值处理、亚组、检验阈值都以冻结的 SAP 为准，结果不显著也照实报告。修执行错误时如果不得不碰到分析方案（例如 SAP 里指定的包已经下架、必须换实现），先停下来问用户，确认后写进 `.pipeline/memory/protocol_deviations.md`。

### 规则 3：先探测环境

首次操作远程服务器时，先用 `ssh` 检查环境：
- `which Rscript && Rscript --version` / `Rscript -e 'packageVersion("<pkg>")'` — R 与统计包版本（统计分析时；版本要记下来，写进方法部分）
- `which python` / `python3 --version`、`pip list | grep <package>` — Python 与依赖
- `which samtools bcftools nextflow snakemake` / `conda env list` — 生信工具链是否就位（生信流程时）
- `nvidia-smi` — GPU 状态（ML 训练时）
- `ls <workdir>` / `ls <data_dir>` — 工作目录、数据或参考基因组 / 索引是否到位（只看文件名和大小，不要 `cat` / `head` 患者数据）

### 规则 4：区分 `run` vs `ssh`

- **改了本地代码** → 用 `run`（自动 sync + 执行）
- **只想在服务器上执行某个命令**（查看进程、安装包、看日志） → 用 `ssh`
- **仅需同步代码不执行** → 用 `sync up`

### 规则 5：迭代怎么迭代，看 analysisMode

- **exploratory**（ML / 生信默认）：每次迭代只改一个变量或一个方面，方便定位问题；同时改多处出错时无法判断是哪个改动导致的。
- **confirmatory**（临床 / 综述默认）：没有"调参迭代"这回事。预设分析跑通一次就是结果；想额外看的分析（敏感性分析以外的新亚组、新模型）要明确标成探索性，单独汇报，不能替换主分析。

## 迭代工作流

当用户要求在服务器上运行/测试/实验：

```
1. ssh 检查环境 ──→ 缺依赖？安装
                        │
2. 修改本地代码 ◄──────┘
        │
3. run 远程执行 ──→ 成功？
        │              ├─ 是 → 汇报结果，问下一步
        │              └─ 否 → 执行错误？分析错误 → 回到步骤 2
        │                      （confirmatory 下只修执行错误，见规则 2）
        │
4. (可选) sync down 拉回结果文件（只拉汇总结果，见规则 0）
```

## 进度汇报

每次执行后简要说明：
- 做了什么改动、为什么
- 执行结果（成功/失败 + 关键输出）
- 下一步计划

探索性（ML）示例：

```
📊 执行结果
━━━━━━━━━━
改动: 将 batch_size 从 32 改为 64
命令: python train.py --batch_size 64
结果: ✅ 训练完成，loss 从 0.45 降到 0.32
下一步: 尝试增大学习率到 3e-4
```

确证性（临床）示例：

```
📊 执行结果
━━━━━━━━━━
改动: 补装 survival 3.5-8（执行错误：包缺失；未改动分析方案）
命令: Rscript analysis/primary_cox.R
结果: ✅ 主分析完成，HR 0.87（95% CI 0.71–1.06），P = 0.17，未达统计学显著
下一步: 按 SAP 跑预设的两项敏感性分析；结果如实写入 experiment_ledger
```
