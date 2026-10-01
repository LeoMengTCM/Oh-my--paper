<p align="center">
  <img src="./icons/icon.png" alt="Oh My Paper" width="120" height="120" />
</p>

<h1 align="center">Oh My Paper</h1>

<p align="center">
  <strong>A research workflow for Codex and Claude Code — from literature to experiments and publication.</strong>
</p>

<p align="center">
  <a href="./README.zh.md">中文文档</a>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/claude--code-plugin-blueviolet?style=flat-square" />
  <img src="https://img.shields.io/badge/agents-5-ff69b4?style=flat-square" />
  <img src="https://img.shields.io/badge/skills-45-green?style=flat-square" />
  <img src="https://img.shields.io/badge/commands-9-blue?style=flat-square" />
  <img src="https://img.shields.io/badge/license-MIT-orange?style=flat-square" />
</p>

---

## TL;DR — Codex

From this checkout:

```bash
./scripts/install-codex-plugin.sh
# Windows: powershell -ExecutionPolicy Bypass -File .\scripts\install-codex-plugin.ps1
```

Start a new Codex session in your research project and ask: **“Use omp to initialize this research project. The topic is …”** Then ask for literature surveys, plans, experiments, writing, review, or progress sync. See [Codex Support](#codex-support) and the [complete workflow guide](docs/codex-workflow.md). Claude Code installation remains below.

---

## 2.1.0: continuous Codex workflows

- Adds the `omp` entrypoint, nine workflows, five project roles, preserved project setup, and session-bound continuation through trusted native hooks.
- Connects survey, the five-direction idea/evaluation workflow, evidence integration or experiments, drafting, review, revision and delivery. Narrative reviews keep their own structure; shared Claude Code workflows remain available.
- Adds resumable PubMed retrieval, structured systematic-review records, RR/MD/SMD analysis and writing handoffs with offline and real-R regression checks.
- Includes end-to-end Codex replay tools and an installed-content/hook-readiness check. See [the workflow guide](docs/codex-workflow.md) and [continuous execution validation](docs/codex-continuous-validation.md).

## This Fork

This is a personal maintenance fork of **[LigphiDonk/Oh-my--paper](https://github.com/LigphiDonk/Oh-my--paper)** (the original, now-unmaintained upstream). All credit for the project goes to the original author; the install commands in this README point to this fork (`LeoMengTCM/Oh-my--paper`).

**Local changes vs upstream:**

- Merged community PRs #7–#10 (Codex skill loading + symlink `dereference`, agent/command YAML frontmatter, research-news prerequisite note).
- Removed agent `model` pins — sub-agents inherit the current session model instead of being locked to sonnet/haiku.
- Fixed a dead `PostToolUse` hook: `scripts/on-stage-transition.mjs` now reads tool input from stdin JSON (the `CLAUDE_TOOL_INPUT` env var does not exist); fixed stale `/vl:plan` → `/omp:plan`; removed the duplicate SessionStart registration in `setup.md`; cleaned up ViewerLeaf-era naming.
- Hardened AskUserQuestion guidance in the command prompts to reduce `Invalid tool parameters` errors (always include required fields; keep params plain text).
- Rewrote the literature OCR (`literature-pdf-ocr-library`) to the current **PaddleOCR-VL async job API** (submit → poll → download Markdown), replacing the old synchronous endpoint.
- Removed the legacy ViewerLeaf desktop GUI (Tauri/React app, sidecar, Cloudflare workers, desktop CI) — this repo is now plugin-only. `compute-helper.mjs` moved into `skills/remote-experiment/scripts/` so plugin users get it too.
- Hardened the experiment/write loop: experiments must over-produce figures into a `figure_ledger.md` (data figures via plotting code only, never image-generation models); writing enforces per-section word floors, full `experiment_ledger` coverage, and a completeness gate before review. Fixed dead `/codex:rescue` command, dead `omp_memory_sync` block, and inconsistent `result_summary.md` paths.
- Widened the stage-transition hook matcher to `Write|Edit` (plus the filesystem MCP write/edit tools) — `tasks.json` updates made via Edit no longer skip the "stage complete" prompt. Added `scripts/check-plugin-consistency.mjs` (run in CI as `npm run check:consistency`): version sync across all five manifests, JSON/`.mjs` validity, frontmatter fields, hook-script references, skills symlinks, README badge counts, and Claude↔Codex keyword parity to catch drift between the two plugin variants. Removed ~2 MB of leftover desktop-app icons.

**What 2.0.0 changes:**

- **Absorbed 7 skills from [CCFA-Skills](https://github.com/mikubaka88/CCFA-Skills) (MIT)**, dropping the `ccf-` prefix (that prefix means CCF conference ranking, which misleads this repo's clinical/bioinformatics tracks): `paper-writing`, `paper-reviewer`, `integrity-auditor`, `paper-humanization`, `rebuttal-writer`, `submission-checker`, `paper-to-exemplar`. **⚠️ Breaking:** the superseded `inno-paper-writing`, `ml-paper-writing`, and `inno-reference-audit` are deleted — if your projects or docs reference those names, point them at the new skills. The vendoring recipe lives in `scripts/vendor-ccfa.mjs`, and the upstream commit sits in each SKILL.md's `upstream` field to diff against later. CCFA's LaTeX templates (~31 MB) came along into `skills/paper-writing/templates/`.
- **Added CNKI (中国知网) search:** `skills/cnki-search/` consolidates the 10 chrome-devtools MCP skills from [cookjohn/cnki-skills](https://github.com/cookjohn/cnki-skills) into one. DOM selectors and extraction logic are carried over verbatim; only the transport changes, to this repo's existing CDP proxy — no new MCP dependency, and it skips gracefully when Chrome isn't in debug mode. Covers keyword/advanced search, pagination and sorting, paper detail, GB/T 7714 export, journal indexing lookup (北大核心/CSSCI/CSCD), and PDF download with archiving. `/omp:survey` gains step 3b (optional Chinese-literature pass, results tagged `cnki` in the screening table) and step 6b (download + archive, then the same OCR path). **Note: upstream cnki-skills ships no LICENSE file** (all rights reserved by default) — evaluate before relying on it.

**Fixed in 2.0.1:**

- **CNKI was verified end-to-end in a real browser** (Chrome 152, logged-in institutional account, across the new / old / journal-navigation interfaces), which turned up a batch of inherited selector and logic bugs: the sort wait signal, sort-item matching across the two interfaces (the old one has no ids and orders two entries differently), `navi.cnki.net`'s search-box id (it was filling a login field), a click that navigates and killed the whole command on a CDP timeout, and commands operating on the wrong tab when several were open. The sort also persists across searches, so results now carry `activeSort` and `search`/`advanced` take `--sort`.
- **Fixed a silent failure in the CDP proxy:** `/eval` answered `HTTP 200 + {"value":{}}` when a page script's promise rejected (the thrown Error serializes to `{}` under `returnByValue` and won the value branch first), downgrading page-side errors to "empty result". Reordering the checks restores 400 + the real message. `cnki.mjs` was the main victim — sort timeouts were silently returning empty. The change is annotated in the vendored file.

**Fixed in 2.0.2:**

- **PDF/CAJ download was completely dead, and silently so.** CNKI's `#pdfDown` / `#cajDown` are `<a target="_blank">`, and the CDP proxy's `Runtime.evaluate` carried no user gesture — so Chrome's popup blocker discarded the click outright: no new tab, no error, no download. `/eval` and `/click` now pass `userGesture: true`. Verified both ways (`window.open("about:blank")` returns `null` without it, opens with it). `/clickAt` needed no change — it dispatches real input events, which already carry activation.
- **`collect` no longer guesses which downloaded file you meant.** Two paths silently filed the wrong paper, both exiting 0: a title matching nothing archived *the most recently downloaded file*, and a title matching several picked the newest — so asking for "深度学习" filed "深度学习综述_李四.pdf". Matching is now exact-first (filename title part identical, or followed by `_author`), falling back to substring; ambiguity or no match exits 2 and lists the filenames actually present. Added a `--file` bypass, and PDF is now preferred over CAJ when both are downloaded.
- **The documented CNKI flow didn't actually work, and its output reached nothing downstream.** Found by testing the commands exactly as the docs spell them, on a real 6-paper corpus, rather than the `--url`-always form used in the first pass. Four separate problems: `detail` never remembered its tab, so the documented `download` (no `--url`) went back to the search-results tab and timed out — and reported that timeout at **exit code 0**, dressed up with a download-looking hint; `collect` wrote only `paper.pdf` while `build_library_index.py` and `build_bibliography.py` both iterate `papers/*/metadata.json`, so both silently reported zero entries (`indexed_papers 0 → 1`, `bib_entries 0 → 1` after the fix); "record-only" entries (no full text on CNKI at all — no download area on the page) were reported with the same message as "you may need institutional access", sending users to log in for nothing; and `download` leaked a browser tab per paper. `collect` now always writes `metadata.json` (`--meta` merges in a `detail`/`parse` record, normalising authors/journal/year), and `institution_pdf` was added to the `full_text_status` enum — "obtained via your own subscription" had no honest value before, and `open_pdf` would misstate a paywalled paper as open access.
- **The user-gesture fix was necessary but not sufficient: the gesture only lives ~5 seconds.** Measured on a fixed page and link, delaying before the click: 2s and 4s download; 6s and 8s do nothing. So the obvious shape — "await the page to be ready, then click" — is unreliable, and `download --url` navigates before it waits, which is exactly when it broke (same paper: downloads when its page is cached, fails when it loads for real), while still reporting `status: downloading`. `download` now runs two evaluations, the second of which only clicks, with no `await` ahead of it. Also found in the same sweep: `detail` remembering its tab (a fix from the previous commit) made `parse`/`pages`/`sort` land on the detail page and stop working until the next search — they now select a search-workbench tab explicitly; and `pages` could hang for the full CDP timeout, both from clicking a link that navigates (destroying the evaluation context mid-`await`, the same trap as the journal search button) and from clicking the page you are already on.
- Verified end-to-end on that corpus, including a 77-page thesis: every archived PDF's first page was opened and compared against the title it was filed under — all matched. Two findings worth knowing: CAJ is the `KDH 2.00` container, not a PDF (`pdfinfo` fails on it), so the OCR pipeline can't read it; and while CNKI PDFs do carry a text layer, its digits and punctuation extract **full-width** (`７５７`), so downstream regexes need NFKC normalization first. One thing left alone but worth knowing: `build_bibliography.py` derives citation keys from Latin letters only, so all-Chinese papers get keys like `anon2023paper` (kept unique by a suffix, but low-information). (All three get follow-ups in 2.0.3, below.)

**Fixed in 2.0.3:**

- **Citation keys for Chinese papers.** All-Chinese papers used to get `anon<year>paper`. The author's surname is now romanized from a built-in surname table (polyphonic surnames use their surname reading — 曾 zeng, 单 shan, 仇 qiu; compound surnames like 欧阳 and 司马 are recognized whole), and a mostly-Chinese title contributes the pinyin of its first two characters after filler openers like 基于 / 关于 — e.g. `zhang2023shendu`. Keys stay pure ASCII. The title part needs the optional `pypinyin` (`pip install pypinyin`) and falls back to `paper` without it. Keys already written into `metadata.json` are never recomputed, so existing `\cite{}`s keep working.
- **Chinese filenames overwrote each other.** `slugify` stripped every Chinese character, so OCR-ing a folder of Chinese PDFs sent every one of them to `paper/`, each overwriting the last; and same-year Chinese papers from Crossref / OpenAlex in `search_and_download_papers.py` all landed in a folder named after the year. Chinese characters are now kept.
- **Full-width digits.** Markdown written by the OCR script (both the API and pdfminer paths) now converts full-width digits, letters and `．％＋－／＝＜＞` to ASCII (`７５７` → `757`, `３．５` → `3.5`). Not a blanket NFKC — that would also flatten `，：（）`, which are correct punctuation in Chinese prose.
- **CAJ fails with a reason.** Handing a CAJ file to the OCR script (including one misnamed `.pdf`) now skips it and says what to do (re-download as PDF from CNKI, or print to PDF from CAJViewer) instead of failing obscurely.
- **`remote-experiment` is no longer ML-only.** Adds clinical statistics (R / Stata / SAS) and meta-analysis use; a "patient data stays on the approved server" rule (`run` rsyncs the whole project directory, `sync down` pulls aggregate results only); under confirmatory analysis the self-repair loop fixes execution errors only and never alters the analysis to change a result — a forced change to the plan goes to the user and into `protocol_deviations.md`; and documents that `sync up` runs with `--delete`, which removes remote result files not excluded by `.gitignore`.
- Removed the chat-group QR code from the top of the README: it belonged to the original author's group and has expired (upstream issue #5).

---

## Table of Contents

- [Why This Exists](#why-this-exists)
- [Install](#install)
- [Claude Code Slash Commands](#claude-code-slash-commands)
- [The Agent Team](#the-agent-team)
- [45 Research Skills](#45-research-skills)
- [Hooks](#hooks)
- [Research Pipeline](#research-pipeline)
- [Project Scaffold](#project-scaffold)
- [How Memory Works](#how-memory-works)
- [Codex Delegation](#codex-delegation)
- [Remote Experiments](#remote-experiments)
- [For LLM Agents](#for-llm-agents)
- [Philosophy](#philosophy)
- [Contributing](#contributing)
- [Uninstall](#uninstall)

---

## Why This Exists

Claude Code is already a great coding agent. But **research isn't just coding** — it's literature survey, idea evaluation, experiment design, paper writing, reference checking, and a dozen other things that require domain-specific workflows.

Oh My Paper makes Codex and Claude Code **research-aware** by adding:

- **A structured 5-stage pipeline** — Survey → Ideation → Experiment → Publication → Promotion
- **5 specialized agent roles** — each with isolated memory and clear responsibilities
- **45 built-in research skills** — from paper search to figure generation
- **Background hooks** — auto-inject project context at session start, prompt role selection, track task completion
- **Codex delegation** — hand off parallel tasks to Codex in a separate terminal

Install it and forget about it. Your sessions get smarter. Your research gets organized.

---

## Install

The following steps install the Claude Code plugin. For Codex, use the quickstart above or [Codex Support](#codex-support).

### Step 1: Add the marketplace

```bash
/plugin marketplace add LeoMengTCM/Oh-my--paper
```

### Step 2: Install the plugin

```bash
/plugin install omp@oh-my-paper
```

### Step 3: Restart Claude Code

Required for hooks to activate.

### Step 4: Initialize your project

```bash
/omp:setup
```

This scaffolds the `.pipeline/` directory, copies the bundled skills into `.claude/skills/`, and writes the initial memory files. The hooks ship with the plugin and are already active — there's nothing to register per project.

### Update

The most reliable way to get the latest version:

```bash
/plugin uninstall omp
/plugin install omp@oh-my-paper
/reload-plugins
```

Or overwrite the plugin cache directly (faster, no restart needed):

```bash
cp -r /path/to/oh-my-paper/plugins/oh-my-paper/. \
  ~/.claude/plugins/cache/oh-my-paper/omp/<installed-version>/
# Then in Claude Code:
/reload-plugins
```

### Install from Local Directory

```bash
git clone https://github.com/LeoMengTCM/Oh-my--paper.git /tmp/oh-my-paper
# In Claude Code:
/plugin marketplace add /tmp/oh-my-paper
/plugin install omp@oh-my-paper
```

---

## Claude Code Slash Commands

These slash commands are provided by the **Claude Code plugin**.
The Codex plugin does **not** currently auto-register `/omp-*` commands in the Codex CLI.

All commands are prefixed with `/omp:`.

| Command | What It Does |
|---------|-------------|
| `/omp:setup` | Scaffold a new research project — creates `.pipeline/`, memory files, and copies the bundled skills into `.claude/skills/` |
| `/omp:survey` | Literature survey (filter-first): multi-source search → screening table → pick core papers → download + OCR only those; builds `literature_bank.md` |
| `/omp:ideate` | Generate and evaluate research ideas based on survey findings |
| `/omp:experiment` | Design experiments, write evaluation code, run on remote compute nodes |
| `/omp:write` | Draft paper sections, generate figures and captions, manage LaTeX files |
| `/omp:review` | Peer-review your paper or experiment results before submission |
| `/omp:delegate` | Generate a Codex prompt for a coding/experiment task; wait for result and update project state |
| `/omp:plan` | Review global progress, confirm next steps, update research plan |
| `/omp:sync` | Force-rebuild the progress docs (`project_truth` / `orchestrator_state` / `execution_context`) when they've drifted from reality |

### Quick Start

```bash
/omp:setup          # scaffold the project
/omp:survey         # start literature survey
/omp:ideate         # generate ideas from survey
/omp:experiment     # design & run experiments
/omp:write          # draft the paper
/omp:review         # final quality gate
```

---

## The Agent Team

When you open Claude Code in an Oh My Paper project, the `SessionStart` hook fires and Claude immediately asks which role you want to take on. Each role has **isolated memory** — it only reads and writes the files it needs.

| Role | Responsibility | Memory Scope |
|------|---------------|-------------|
| **Conductor** | Global planning, review outputs, dispatch tasks, auto-update `project_truth` after each subtask | `project_truth` · `orchestrator_state` · `tasks.json` · `review_log` · `agent_handoff` · `decision_log` |
| **Literature Scout** | Search papers, organize literature bank | `project_truth` · `execution_context` · `literature_bank` · `decision_log` |
| **Experiment Driver** | Design experiments, write code, run evaluations, produce figures every round | `execution_context` · `experiment_ledger` · `figure_ledger` · `research_brief.json` · `project_truth` |
| **Paper Writer** | Draft sections, assemble multi-panel figures, audit references | `execution_context` · `result_summary` · `experiment_ledger` · `figure_ledger` · `literature_bank` · `agent_handoff` |
| **Reviewer** | Peer review, quality gate, consistency check | `execution_context` · `project_truth` · `result_summary` |

### How It Works

```
Session opens
    → SessionStart hook fires
        → Claude asks: which role today?
            → Agent loads role-specific memory files
                → Works as that persona
                    → On subtask complete: auto-updates tasks.json + project_truth
                        → Next session picks up right where you left off
```

**Key design decisions:**

- **Memory isolation** — the Paper Writer can't see the Conductor's orchestrator state; the Literature Scout can't see experiment results. This prevents context pollution.
- **Shared state** — `tasks.json` and `project_truth.md` are the common ground, updated by all roles after each subtask.
- **No manual sync** — the Conductor auto-updates `tasks.json` (marks tasks `done`) and appends a progress entry to `project_truth.md` whenever a subtask completes, without waiting for you to ask.

---

## 45 Research Skills

Skills are structured instruction sets that Claude loads on demand. Each skill is a markdown file covering a specific research task.

<details>
<summary><strong>Click to expand the full skill list</strong></summary>

| Category | Skills |
|----------|--------|
| **Literature** | `paper-finder` · `paper-analyzer` · `paper-image-extractor` · `research-literature-trace` · `biorxiv-database` · `dataset-discovery` · `literature-pdf-ocr-library` · `cnki-search` |
| **Clinical Research** | `pubmed-search` · `clinicaltrials-gov` · `systematic-review` · `clinical-study-design` |
| **Survey & Ideation** | `inno-deep-research` · `gemini-deep-research` · `inno-code-survey` · `inno-idea-generation` · `inno-idea-eval` · `research-idea-convergence` |
| **Experiment** | `inno-experiment-dev` · `inno-experiment-analysis` · `research-experiment-driver` · `remote-experiment` |
| **Writing** | `paper-writing` · `scientific-writing` · `paper-humanization` · `paper-to-exemplar` · `inno-figure-gen` · `research-paper-handoff` |
| **Review & Submission** | `paper-reviewer` · `inno-paper-reviewer` · `integrity-auditor` · `rebuttal-writer` · `submission-checker` · `inno-rclone-to-overleaf` |
| **Planning** | `inno-pipeline-planner` · `research-pipeline-planner` · `inno-prepare-resources` |
| **Presentation** | `making-academic-presentations` · `inno-grant-proposal` |
| **Agent Dispatch** | `claude-code-dispatch` · `codex-dispatch` |
| **Domain-Specific** | `academic-researcher` · `bioinformatics-init-analysis` · `research-news` |

</details>

Skills are auto-recommended based on your current pipeline stage. Add your own project-specific skills under `.claude/skills/` in your research project.

---

## Hooks

Oh My Paper registers three hooks that run in the background:

| Hook | Trigger | What It Does |
|------|---------|-------------|
| **SessionStart** | Every time you open Claude Code in this project | Outputs project context to Claude — current stage, active task, last handoff — then prompts you to pick a role via `AskUserQuestion` |
| **Stop** | When a task completes | Tracks task completion, updates `tasks.json` |
| **PostToolUse (Write)** | After any file write | Detects pipeline stage transitions |

**Important:** The three hooks ship with the plugin (`plugins/oh-my-paper/hooks/hooks.json`) and go live the moment the plugin is enabled — you do **not** register them per project. They stay dormant until `/omp:setup` creates the `.pipeline/` directory they look for: before that, each hook simply finds no `.pipeline/` and exits.

---

## Research Pipeline

A structured 5-stage workflow from idea to publication:

```
┌──────────┐    ┌──────────┐    ┌────────────┐    ┌─────────────┐    ┌───────────┐
│  Survey  │ →  │ Ideation │ →  │ Experiment │ →  │ Publication │ →  │ Promotion │
└──────────┘    └──────────┘    └────────────┘    └─────────────┘    └───────────┘
```

Each stage comes with:
- **Auto-generated task trees** — what to do next
- **Recommended skills** — which skills to load
- **Context-aware prompts** — agents read `tasks.json` and `research_brief.json` and know what to do

### Research tracks & gates

The pipeline adapts to a `pipeline.track` chosen at `/omp:setup` — `ml` (default), `clinical`, `systematic-review`, or `bioinformatics`. The track decides how each stage is interpreted, what figures it produces, and which gates apply:

- **Confirmatory vs exploratory** — clinical/SR work runs the pre-specified analysis once and reports it as-is (no iterate-until-significant); ML/bioinformatics iterate freely.
- **Lock & register gate** — for clinical/SR, no data collection or analysis starts until the protocol + SAP are frozen and the study is registered (ClinicalTrials.gov / PROSPERO) and IRB-approved.
- **Reporting-guideline gate** — the publication/review gate checks the registration number and the matching checklist (CONSORT / STROBE / STARD / PRISMA).
- **Figures early** — each stage produces its figures as the work happens (flow diagrams with real counts, forest/KM plots), never deferred to the end.

Defaults keep existing ML projects unchanged.

---

## Project Scaffold

A typical Oh My Paper project looks like this — `/omp:setup` scaffolds `.pipeline/` and copies the bundled skills into `.claude/skills/`; the rest is the recommended layout you grow into:

```
my-research/
├── paper/                  # LaTeX workspace
│   ├── main.tex
│   ├── sections/
│   └── refs/
├── experiment/             # Experiment code & scripts
├── survey/                 # Literature survey artifacts
├── ideation/               # Ideas, evaluations, plans
├── promotion/              # Slides, demos, outreach
├── .pipeline/
│   ├── tasks/
│   │   └── tasks.json      # Task tree across all stages
│   ├── docs/
│   │   └── research_brief.json
│   └── memory/             # Agent memory files
├── .claude/
│   └── skills/             # Bundled skills, copied here by /omp:setup
├── CLAUDE.md
└── AGENTS.md
```

---

## How Memory Works

Each agent role reads and writes specific memory files. The Conductor is responsible for keeping shared state in sync.

```
.pipeline/memory/
├── project_truth.md        # Ground truth + progress log (appended after each subtask)
├── orchestrator_state.md   # Conductor's planning state
├── execution_context.md    # Current task context for executors
├── experiment_ledger.md    # Experiment history & results
├── figure_ledger.md        # Figure inventory (collected during experiments, assembled at write time)
├── result_summary.md       # Latest results for writing & review
├── review_log.md           # Review feedback history
├── literature_bank.md      # Organized paper notes
├── agent_handoff.md        # Cross-agent handoff messages
└── decision_log.md         # Rejected directions & reasoning

.pipeline/tasks/
└── tasks.json              # Shared task tree (all roles read/write this)
```

Memory survives across sessions. The `SessionStart` hook reads these files and injects the relevant context — you pick up right where you left off.

**Auto-sync rule:** The Conductor updates `tasks.json` and `project_truth.md` automatically after every subtask completes (delegate / experiment / survey / write / review). You never need to ask it to sync.

---

## Codex Delegation

The Conductor can hand off coding and experiment tasks to Codex:

```bash
/omp:delegate
```

The flow:
1. Conductor reads project context and the current task
2. Presents task summary — you confirm
3. Generates a complete Codex prompt with context pre-injected
4. You copy it to a new terminal: `codex "..."`
5. Conductor polls for completion (`CODEX_DONE` signal in `agent_handoff.md`)
6. Reads result, asks you to accept/revise/reject
7. On accept: updates `tasks.json` and `project_truth.md` automatically

---

## Remote Experiments

The `remote-experiment` skill + `/omp:experiment` run your analysis on a remote machine:

```
Write analysis code → rsync to server → Run remotely → Read output → Fix errors and re-run
```

- For any analysis that has to run remotely — clinical / epidemiological statistics (R / Stata / SAS; essential when patient data may only live on a hospital server), meta-analysis, **bioinformatics pipelines** (alignment, variant calling, single-cell, GWAS), ML training
- SSH/rsync-based remote compute via `compute-helper` CLI
- Iteration follows `analysisMode`: exploratory projects (ML / bioinformatics) can iterate against success thresholds and iteration limits; confirmatory projects (clinical / systematic review) only fix execution errors — the pre-specified analysis, once it runs, is the result
- With patient-level data, the data stays on the approved server and only aggregate results come back
- Results flow back into `experiment_ledger.md` for the Paper Writer

---

## For LLM Agents

If you're an AI agent installing this plugin:

```bash
# Step 1: Add marketplace
/plugin marketplace add LeoMengTCM/Oh-my--paper

# Step 2: Install plugin
/plugin install omp@oh-my-paper

# Step 3: Verify installation
/plugin
# Should show: omp @ oh-my-paper, Status: Enabled

# Step 4: User must restart Claude Code (you cannot do this)
# Tell user: "Please restart Claude Code to activate hooks."

# Step 5: Initialize project
/omp:setup
```

---

## Philosophy

> **Enhance, don't replace.** Claude Code is already smart — we add research structure, not overrides.

- **Your context is for reasoning** — hooks inject only what's needed; memory files keep the rest on disk
- **Domain-specific, not generic** — every skill, agent, and command is designed for academic research
- **Invisible when not needed** — hooks run in the background; no noise if you're just coding
- **Composable** — use one command, use all of them, or just let the hooks do their thing
- **Memory over repetition** — agents remember project context so you don't re-explain every session

---

## Contributing

PRs welcome. If you add a new skill, drop it in `skills/<name>/SKILL.md` with proper YAML frontmatter (at least `name` and `description`), then run `npm run skills:research:sync` to regenerate `research-catalog.json` / `research-scope.json`. Run `npm run skills:research:check` before opening the PR — it verifies skill/command counts, frontmatter, and the README badge numbers all line up.

Any change to cached content requires version bumps in **both**:
- `plugins/oh-my-paper/.claude-plugin/plugin.json`
- `.claude-plugin/marketplace.json`

---

## Codex Support

The Codex plugin includes an invocable **omp skill**, nine workflows, five project roles, and native lifecycle hooks. It shares the research tools and `.pipeline` records with the Claude Code plugin.

### Install

Run `./scripts/install-codex-plugin.sh` from this checkout. On Windows use `scripts/install-codex-plugin.ps1`. The cross-platform equivalents are:

```bash
node scripts/manage-codex-plugin.mjs install
node scripts/manage-codex-plugin.mjs status
```

The installer copies a standalone bundle to `~/plugins/oh-my-paper-codex`, preserves other personal marketplace entries, and attempts installation through Codex app-server. If unavailable, open `/plugins`, install **Oh My Paper**, and start a new session.

### Use

Ask Codex to use **omp** to initialize, plan/resume, survey, ideate, experiment, write, review, delegate, or sync. Promotion materials use the write workflow. You do not need to copy prompt templates; `/omp-*` commands are not registered.

Initialization preserves existing research files and external AGENTS.md instructions, creates the missing project scaffold, and installs roles in `.codex/agents/omp-*.toml`. Roles inherit the session model. Restart the session to load new project roles. Re-running setup preserves tasks and custom roles.

### Hooks and research tracks

Codex supports SessionStart, PostToolUse, Stop and SubagentStop hooks. Review and trust the plugin definitions in `/hooks` to enable them. For an authorized full workflow, omp registers the current session and checks for unfinished work before stopping. Trusted Stop hooks continue a prematurely ended turn; real user decisions, external blockers and explicit pauses remain valid stopping points. Hooks never approve research or mark tasks complete. See [continuous execution](docs/codex-continuous-workflow.md) and the [end-to-end validation](docs/codex-continuous-validation.md).

All five stages support ML, clinical research, systematic review and bioinformatics. The systematic-review branch reuses retrieval/recovery, screening records, RR/MD/SMD analysis and writing-handoff tools. Human screening, extraction verification, RoB 2, GRADE and real clinical end-to-end validation still require research evidence and judgment. Software examples do not establish clinical completion.

See the [complete workflow guide](docs/codex-workflow.md) for the stage mapping, artifact contracts and commands.

### Maintain and verify

After editing Codex prompts or roles, run `npm run codex:sync`, then `npm run check`. Tests cover standalone installation, project preservation, all four track initializers, TOML roles and native hook envelopes. For full statistical checks, install the R dependencies and run `OMP_REQUIRE_R=1 npm run check`.

Verify the installed content **and** native Stop-hook readiness for your project:

```bash
node scripts/check-codex-runtime.mjs --installed --project /path/to/research --require-hooks
```

The check exits with status 2 if automatic continuation is not active. The opt-in real-model pipeline replay is `python3 scripts/eval-codex-pipeline.py`; it uses model calls and is separate from offline CI.

Interface references: [official plugin documentation](https://developers.openai.com/plugins/build/plugins), [subagents](https://developers.openai.com/codex/subagents), and [hooks](https://learn.chatgpt.com/docs/hooks).

---

## Uninstall

**Claude Code:**
```bash
/plugin uninstall omp@oh-my-paper
```

**Codex on macOS / Linux:**
```bash
./scripts/uninstall-codex-plugin.sh
```

**Codex on Windows (PowerShell):**
```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\uninstall-codex-plugin.ps1
```

---

## License

MIT. See [LICENSE](./LICENSE).

---

## Acknowledgments

Special thanks to the **[Linux.do](https://linux.do)** community for your support and feedback.
The paper writing, review, humanization, rebuttal, submission-check and exemplar-learning skills, along with LaTeX templates for 139 venues, are vendored from **[CCFA-Skills](https://github.com/mikubaka88/CCFA-Skills)** (MIT, by mikubaka88) at commit `fd5c7e3`, then rewritten to this repo's frontmatter conventions and `.pipeline/` model. Each skill records its origin in the `upstream` field of its `SKILL.md`. To re-vendor or diff against upstream, run `node scripts/vendor-ccfa.mjs --src <path to CCFA-Skills>`.

---

<p align="center">
  <strong>Oh My Paper</strong> — Where Research Meets the Terminal.
</p>
