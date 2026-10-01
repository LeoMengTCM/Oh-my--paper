#!/usr/bin/env python3
"""Opt-in real Codex replay. Uses model calls; not part of offline npm tests.

The driver supplies only two simulated author decisions. If Codex stops early,
the real Stop adapter decides whether to continue; the driver replays that hook
response using Codex resume. This tests the contract without changing hook trust.
"""
import json
import os
from pathlib import Path
import subprocess
import tempfile

REPO = Path(__file__).resolve().parents[1]
PLUGIN = Path.home() / "plugins/oh-my-paper-codex"
PROJECT = Path(tempfile.mkdtemp(prefix="omp-whole-pipeline-"))
LOG = PROJECT / "replay-logs"
LOG.mkdir()
FIXTURES = PROJECT / "fixtures"
FIXTURES.mkdir()

topics = ["dying-cell clearance", "therapy-induced senescence", "lymphoid structure maturation", "T-cell mechanical adaptation", "ADC release location"]
sources = ["# Fictional software fixtures — not research evidence", "All records below are invented test inputs. No real citation, human trial or publication-readiness claim is permitted."]
for i, topic in enumerate(topics, 1):
    sources.append(f"## F{i}: {topic}\nA fictional review already covers the mechanism. A fictional mouse experiment reports a context-dependent tumour measure change; no human survival or safety data are supplied. A useful testing angle compares the mechanistic hypothesis, conditional application and translational limits. Full fixture text is this paragraph; no network or OCR is needed.")
(FIXTURES / "sources.md").write_text("\n\n".join(sources))
(FIXTURES / "delivery-rules.md").write_text("# Software delivery rules, not a real journal\nEnglish narrative test manuscript about 300 words; four thematic sections; clearly fictional label; only F1-F5 local references; no unsupported human benefit; current review/revision records. Report ready_for_real_submission=false. Do not submit, upload or produce promotion materials.\n")

def task(task_id, stage, title, deps, workflow, **extra):
    return dict(id=task_id, stage=stage, title=title, status="pending", dependencies=deps, workflow=workflow, **extra)

tasks = [
    task("survey", "survey", "Synthesize the complete fictional source set and review overlap", [], "survey"),
    task("ideas", "ideation", "Produce the standard five-direction idea board", ["survey"], "ideate"),
    task("confirm-scope", "ideation", "User confirms which directions to evaluate", ["ideas"], "ideate", taskType="gate", checkpointType="user"),
    task("evaluate", "ideation", "Apply inno-idea-eval perspectives to the fictional records; label all judgments as simulated", ["confirm-scope"], "ideate"),
    task("select-direction", "ideation", "User chooses the final direction", ["evaluate"], "ideate", taskType="gate", checkpointType="user"),
    task("evidence", "experiment", "Integrate claims, source limits and contrary evidence for the selected angle", ["select-direction"], "experiment"),
    task("draft", "publication", "Write Publication/manuscript.md from the evidence matrix and agreed narrative format", ["evidence"], "write"),
    task("integrity", "publication", "Check only local fictional source/claim consistency", ["draft"], "review", suggestedSkills=["integrity-auditor"]),
    task("review", "publication", "Scientifically assess internal coherence and evidence limits of the simulated manuscript", ["integrity"], "review"),
    task("revise", "publication", "Correct substantiated issues; if none, document why no revision is needed", ["review"], "write"),
    task("re-review", "publication", "Verify current manuscript and resolution of actual issues; do not invent new ones", ["revise"], "review"),
    task("delivery-check", "publication", "Check fixtures/delivery-rules.md; this is simulation-only and cannot establish real submission readiness", ["re-review"], "review", suggestedSkills=["submission-checker"], taskType="gate", checkpointType="artifact"),
    task("deliver", "publication", "Write Publication/delivery_report.md and verify the complete requested scope", ["delivery-check"], "write"),
]
(PROJECT / "scenario.json").write_text(json.dumps({"purpose": "software_validation", "researchType": "narrative-review", "tasks": tasks}, indent=2))
message = """用 OMP 从零初始化当前临时项目，完整走完 survey、五方向 idea board、评估、最终选题、证据整合、约300英文词的叙述性综述测试稿、核验、评审、必要返修、复审和交付。不要在普通阶段转换时让我提醒。
这是离线软件回放。唯一资料是 fixtures/sources.md，均明确为虚构的模拟材料，按模拟资料执行所有可执行步骤，不要求它们成为真实文献。完整任务计划在 scenario.json，保留这些任务 ID 并写入 .pipeline/tasks/tasks.json。研究类型为 narrative-review，即使 track 使用兼容值 ml 也不能安排训练。检查终点为 publication，最终文件为 Publication/manuscript.md 和 Publication/delivery_report.md；交付要求在 fixtures/delivery-rules.md。
不联网、不访问真实研究目录、不调用子代理、不投稿或推广。选题范围和最终选题由我在实际决策点回复，其余已授权动作持续执行。所有研究判断和稿件标为模拟，不编造真实引用或审批。
"""
thread_id = None
decisions = []
continuations = 0
result = {"project": str(PROJECT), "mode": "real-codex-with-stop-contract-replay", "userWorkflowReminders": 0}
print(f"Replay project: {PROJECT}", flush=True)

def load_tasks():
    return json.loads((PROJECT / ".pipeline/tasks/tasks.json").read_text())["tasks"]

try:
    for exchange in range(1, 9):
        stdout = LOG / f"turn-{exchange}.jsonl"
        reply = LOG / f"reply-{exchange}.md"
        args = ["codex", "exec", "--json", "--output-last-message", str(reply)]
        if thread_id:
            args += ["resume", "--skip-git-repo-check", thread_id, "-"]
        else:
            args += ["--skip-git-repo-check", "--sandbox", "workspace-write", "-"]
        with stdout.open("w") as out, (LOG / f"stderr-{exchange}.log").open("w") as err:
            process = subprocess.run(args, input=message, text=True, cwd=PROJECT, stdout=out, stderr=err)
        if process.returncode:
            raise RuntimeError(f"Codex exit {process.returncode} in exchange {exchange}; inspect stderr log")
        events = [json.loads(line) for line in stdout.read_text().splitlines() if line.strip()]
        for event in events:
            if event.get("type") == "thread.started":
                thread_id = event["thread_id"]
        if not thread_id:
            raise RuntimeError("No authoritative Codex thread ID returned")
        state_file = PROJECT / ".pipeline/.codex-continuation" / f"{thread_id}.json"
        if not state_file.exists():
            raise RuntimeError("Continuous workflow was not registered by the agent")
        state = json.loads(state_file.read_text())
        current = {t["id"]: t for t in load_tasks()}
        print(f"Exchange {exchange}: {state['status']}; {sum(t['status']=='done' for t in current.values())}/{len(current)} tasks done", flush=True)
        if state["status"] == "complete":
            if not all(current[t["id"]]["status"] == "done" for t in tasks):
                raise RuntimeError("Declared complete while required task remains")
            for artifact in ["Publication/manuscript.md", "Publication/delivery_report.md"]:
                if not (PROJECT / artifact).is_file() or not (PROJECT / artifact).stat().st_size:
                    raise RuntimeError(f"Missing final artifact {artifact}")
            result.update(passed=True, exchanges=exchange, simulatedAuthorDecisions=decisions, automaticStopContinuations=continuations, finalTaskCount=len(current), threadId=thread_id)
            break
        hook_input = dict(hook_event_name="Stop", session_id=thread_id, turn_id=f"replay-{exchange}", cwd=str(PROJECT), last_assistant_message=reply.read_text())
        response = subprocess.run(["node", str(PLUGIN / "scripts/codex-hook.mjs")], input=json.dumps(hook_input), text=True, capture_output=True, cwd=PROJECT, check=True)
        decision = json.loads(response.stdout)
        (LOG / f"stop-{exchange}.json").write_text(json.dumps(decision, indent=2))
        if decision.get("decision") == "block":
            message = decision["reason"]
            continuations += 1
            continue
        if "confirm-scope" not in decisions and current["confirm-scope"]["status"] != "done" and current["ideas"]["status"] == "done":
            message = "全部五个方向都评估，评估范围已确认。"
            decisions.append("confirm-scope")
        elif "select-direction" not in decisions and current["select-direction"]["status"] != "done" and current["evaluate"]["status"] == "done":
            message = "我选择 idea board 中列出的第一个方向作为最终方向。"
            decisions.append("select-direction")
        else:
            raise RuntimeError(f"Unexpected stop: {state.get('status')}; {state.get('reason')}; hook={decision}")
    else:
        raise RuntimeError("Replay limit reached without full delivery; not a pass")
except Exception as exc:
    result.update(passed=False, error=str(exc), simulatedAuthorDecisions=decisions, automaticStopContinuations=continuations, threadId=thread_id)
finally:
    (PROJECT / "replay-result.json").write_text(json.dumps(result, ensure_ascii=False, indent=2))
    print(json.dumps(result, ensure_ascii=False, indent=2), flush=True)
if not result.get("passed"):
    raise SystemExit(1)
