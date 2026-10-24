---
name: omp
description: Codex workflow entrypoint. Follow the Oh My Paper (OMP) research pipeline, including 按照omp流程来 and 下一步. Check stage and evidence before acting; broad topic selection starts with survey, then evidence-based ideation and user selection. Initialize, resume, execute and advance authorized research work without repeated workflow reminders.
version: 1.1.0
stages: [survey, ideation, experiment, publication, promotion]
---

# Oh My Paper for Codex

These runtime controls apply to Codex sessions. If a shared planner reaches this
skill from Claude Code or Qoder, use that host's native `/omp:*` commands and agent
instructions; do not register Codex continuation or install Codex project roles
as part of a Claude Code or Qoder research session. Shared research artifacts
remain compatible.

被宿主 Agent 委派的 Codex 子进程若有 `OMP_CODEX_DISPATCH=1`，只完成当前任务包，
不执行下方的全项目连续循环，不注册 continuation，不递归派发，也不擅自推进阶段。
适用的研究 skill 与证据要求仍须遵守；把缺少的用户决定或资源交回主会话。

Own the workflow, including its next step. Reuse the user's answers and current
authorization. Ask for missing research decisions, not repeated permission to
follow a pipeline the user already requested. Do not show a role-selection menu
when the task is clear.

For a full OMP project, use a continuous work loop: inspect → execute → verify →
record → route again, until the authorized deliverable or a real decision/blocker.
A section, task, phase or review report being finished is not itself a reason to
end the turn. Do not ask the user to operate the workflow by repeatedly saying next.

Resolve this skill's actual directory from its loaded `SKILL.md`. Its parent is
the shared skills directory, called `OMP_SKILLS` in command examples. Resolve and
quote that path before running scripts; never assume `.claude/skills` exists.

## Register continuous execution once per authorized session

After establishing the full requested scope and task plan, register this Codex
session (the CLI exposes CODEX_THREAD_ID). Use the real final paths and last
authorized stage; the example is a manuscript delivery, not permission to submit:

```bash
node "$OMP_SKILLS/omp/scripts/continuation.mjs" start --project . --objective "Complete the agreed manuscript and checks" --through publication --deliverable Publication/manuscript.md --deliverable Publication/delivery_report.md
```

Run `status` first on resume. Do not reset an active registration on every task.
The Stop hook checks only registered sessions. If tasks remain, it requests another
turn automatically; it never completes research tasks or changes approvals. Other
sessions and standalone requests are unaffected. Hooks must be trusted by the host;
when unavailable, follow the same continuous loop explicitly and report the missing
runtime protection rather than claiming it is active.

Before ending the turn:

- Execute the next authorized task if it is actionable. Only missing actual user
  decisions or external resources justify `wait --kind user-decision|external-blocker
  --reason "specific missing decision/resource"`. Name the next task and resume
  with `resume` when that condition is resolved. A routine stage change is not a blocker.
- If the user explicitly pauses/stops, call `pause --reason "user request"` and stop.
- When the full scope is verified, call `finish --summary "checked deliverables and
  results"`. It refuses pending tasks or missing delivery files. Do not mark tasks
  done, fabricate evidence, or shrink scope merely to make it accept completion.
- A repeated no-progress continuation is reported as stalled, not complete.

## First action: check state before choosing a workflow

For an OMP pipeline request, run the read-only preflight before recommending a
topic, choosing a downstream skill, or saying what comes next:

```bash
node "$OMP_SKILLS/omp/scripts/workflow.mjs" --project . --intent continue
```

Use `--intent choose-topic` for broad requests such as “从肿瘤领域选题”; these
require survey first. Use `--intent survey`, `ideate`, `experiment`, `write`,
`review`, `plan`, `sync`, or `delegate` for a named workflow. These intents do not
override unfinished prerequisites. Use `--standalone` only when the user explicitly
requests an isolated task, such as reviewing an existing paragraph without running
the pipeline. A user-specified later starting stage with supplied evidence is valid.

Read the current brief, normalized tasks, acceptance criteria and referenced
artifacts. `workflow.mjs` checks structural prerequisites; it does not establish
literature coverage, scientific quality or researcher approval. Follow its next
action and inspect the actual evidence before advancing.
Within the routed workflow, resume the specific task/step already in progress.
叙述性综述复用已确认重点和提纲，不要求创建五方向或评分记录。其他研究已有
five-direction board、evaluation scope 或 evaluation 时复用，继续尚未完成的步骤，
不因参考文件从第一步写起而重新生成候选或重复提问。

- **No initialized state / empty tasks:** initialize or plan from the stated goal,
  then run survey. Do not fill the gap by inventing candidate recommendations.
- **Survey incomplete or only preliminary search:** collect and synthesize evidence
  first. Possible search themes are provisional search directions; do not rank a
  preferred publication topic or ask the user to select one yet.
- **Survey says done:** read the report, source records, review-overlap analysis,
  representative original studies, full-text reading scope and limitations. Counts
  and elapsed time do not establish completion. Keep unresolved evidence in review.
- **Survey checked and ideation authorized:** read `references/omp-ideate.md`.
  narrative-review 使用综述重点分支，依据已有综述和原始研究确定论证问题与提纲，
  不强制五个创新点或 inno-idea-eval。普通创新研究仍执行 five-direction idea board
  → user confirms evaluation scope → `inno-idea-eval` → final direction，不能用
  standalone `research-idea-convergence` 的 2–4 候选流程替代。复用已确认的范围和选择，
  本轮执行已授权步骤，不以“下一步将收敛题目”代替实际工作。

Reuse supplied directories, including `Survey/`, without renaming or duplicating
them. Add their actual paths to task `artifacts` and record what was checked in
`completionSummary`. Missing metadata is a reason to inspect existing work, not
to repeat the survey automatically. Never populate these fields from a claim alone.

Distinguish a narrative review from a systematic review or an original clinical
study. An oncology topic alone does not require RCT/Meta, IRB, datasets or ML
experiments. Use the brief's stated research design to interpret the stages.

## Entry points

After preflight, read the routed reference. These are workflows, not `/omp-*` CLI commands.

| Request | Reference | Role |
|---|---|---|
| Initialize a project | [setup](references/omp-setup.md) | conductor |
| Plan or resume | [plan](references/omp-plan.md) | conductor |
| Search literature | [survey](references/omp-survey.md) | literature-scout |
| 确定叙述综述重点 / Five-direction idea board / SR protocol | [ideate](references/omp-ideate.md) | conductor |
| Run experiments / 叙述综述证据综合 / SR retrieval, screening and synthesis | [experiment](references/omp-experiment.md) | experiment-driver |
| Write a paper or prepare promotion material | [write](references/omp-write.md) | paper-writer |
| Review a manuscript | [review](references/omp-review.md) | reviewer |
| Delegate authorized work | [delegate](references/omp-delegate.md) | task-specific |
| Reconcile tasks and memory | [sync](references/omp-sync.md) | conductor |

Initialize with `scripts/project.mjs init`; inspect without changing files with
`scripts/project.mjs status`. Setup installs the five role definitions under the
project's `.codex/agents/` and appends a managed block to `AGENTS.md`, preserving
existing instructions and research files. Roles inherit the current model.
Read the corresponding file in `roles/` when working in that role yourself.
Use native subagents only when delegation is requested or already authorized.

## Resume and completion

Read `.pipeline/docs/research_brief.json`, validate tasks through
`../inno-pipeline-planner/scripts/task-contract.mjs`, then read the selected role's
memory. Resume the current task from its actual artifacts and live process handle.
An old completion marker or a `running` field alone does not prove process state.

After verifying a subtask, update its task record and append progress to
`project_truth.md`: include actual `artifacts` and `completionSummary`. Preserve
legacy task IDs and formats. Use `review` when output still needs research judgment.
Then run preflight again, prepare `execution_context.md`, and execute the next
authorized task. Update the brief's stage when that evidence-based handoff occurs.
If the task list ends before the user's objective, plan the remaining tasks.

## Downstream handoffs and revision loop

Route by the **current task**, not only the stage. `publication` includes writing,
review, revision, integrity checks and submission checks. Set a task's `workflow`
explicitly (`write` or `review`) and its `suggestedSkills` when the owner would be
ambiguous. `workflow.mjs` returns `skill` for integrity-auditor/submission-checker.
Follow that operation within the routed reference; do not draft again for a review
task. `checkpointType: artifact` means execute the check; `checkpointType: user`
means a real user decision. Existing untyped gate tasks remain checkpoints until
their purpose and existing authorization have been checked.

| Completed work | Required handoff | Next authorized work |
|---|---|---|
| idea eval | Evaluation evidence and user-selected direction | Plan the chosen direction; do not regenerate the idea board |
| Final selection | Selected angle, scope, open evidence questions, planned outline | Experiment/evidence integration appropriate to research design |
| Evidence integration or experiments | Claim-to-source/result mapping, limitations, figure inventory, result_summary | Draft the agreed manuscript from these artifacts |
| Draft and figures | Current manuscript path/version and coverage check | Integrity check and scientific review |
| Review with actionable issues | Issue IDs, locations, evidence and affected files | Writer revises; evidence gaps return to research before rewriting claims |
| Revision | Revised manuscript and issue-to-change ledger | Recheck the revised version; repeat only for remaining substantiated issues |
| Review issues resolved | Current manuscript, current checks, actual venue requirements | Submission-readiness check and delivery within the requested scope |

Treat a completed review report as completion of the **review task**, not acceptance
of the manuscript. Add revision/re-review tasks and dependencies so submission or
promotion cannot jump over unresolved blocking issues. A manuscript change invalidates
affected old checks: bind each review to the actual manuscript version and reread the
changed parts. Do not endlessly re-score unchanged text or invent new requirements.

`pipeline.track=narrative-review` 为正式叙述性综述类型；兼容旧项目的
`projectContext.researchType/articleType` 和根级 `researchType/articleType`。
读取 `../inno-pipeline-planner/references/narrative-review-profile.md`：experiment
表示证据提取、核对与综合，不是训练或 RCT/Meta。旧 track=ml 不强制训练、消融、
IMRaD 或会议投稿规则；类型冲突须核对原始决定，不能静默迁移。按实际格式、
路径和已确认 `writingLanguage` 写作，交代真实检索方法，不虚构 PRISMA 计数。

During a full authorized manuscript task, continue across sections, routine checks,
and supported repairs without a menu at each step. Ask for a changed direction,
changed protocol/analysis, unresolved scientific judgment or other genuinely missing
decision. Submission readiness does not authorize submitting, uploading or contacting
anyone. Promotion is optional and starts only when requested; it is not the default
success condition for every paper project.

Do not replace a real research decision with automation: the user selects the
final direction and approves applicable protocol/method changes. A task status
does not prove such approval. If the user requested only survey, deliver survey
with the concrete next task and stop at that scope boundary. If they requested
the full pipeline, the mere change of stage is not another permission question.

## Research tracks

Retain all five stages: survey → ideation → experiment → publication → promotion.
ML、bioinformatics 和 narrative-review 默认 exploratory；clinical 和
systematic-review 默认 confirmatory。narrative-review 的 exploratory 表示可按证据
完善重点与覆盖，不是优化实验指标。五种类型保留原阶段；新项目不能用 ml/clinical
代替叙述性综述，不自动创建其不适用的临床 protocol/SAP 或注册、IRB 要求。

For systematic review, read
`../systematic-review/references/rct-pairwise-profile.md`: exploratory survey;
approved PICO/protocol/SAP; formal retrieval and screening; study/report mapping,
extraction, RoB 2 and synthesis; writing handoff, GRADE and reporting. Use the
shared validators and R adapter. Never substitute example data, AI decisions or
task statuses for human research evidence. Publication uses
`../systematic-review/references/writing-handoff.md`; a software benchmark is not
a completed clinical review.

The plugin's optional native hooks restore session context, flag completed
stages, log executor reports, and check premature stops for registered workflows.
They require the host's hook trust review.
When hooks are unavailable, the `AGENTS.md` instructions above provide the same
explicit resume and completion routine. Do not change trust or approval settings.
