from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pylingual_portable import sessions


ROOT = Path(__file__).resolve().parent.parent
DEFAULT_TASKS = ROOT / "harness" / "tasks.json"
DEFAULT_OUT = ROOT / "harness" / "results"
SESSION_RE = re.compile(r"ses_[0-9a-f]{16}")


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def load_tasks(path: Path) -> tuple[dict, list[dict]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    defaults = data.get("defaults", {})
    tasks = []
    for item in data.get("tasks", []):
        task = {**defaults, **item}
        task["pyc_path"] = (ROOT / task["pyc"]).resolve()
        tasks.append(task)
    return data, tasks


def opencode_prefix(opencode: str) -> list[str]:
    path = Path(opencode)
    if path.suffix.lower() in {".cmd", ".bat"}:
        return ["cmd.exe", "/c", str(path)]
    if path.suffix.lower() == ".ps1":
        return ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(path)]
    return [opencode]


def resolve_opencode(opencode: str) -> str | None:
    path = Path(opencode)
    if path.suffix.lower() in {".cmd", ".bat", ".ps1"}:
        return str(path) if path.is_file() else None
    if path.is_file():
        return str(path)
    return shutil.which(opencode)


def terminate_process_tree(process: subprocess.Popen) -> None:
    if os.name == "nt":
        subprocess.run(
            ["taskkill", "/PID", str(process.pid), "/T", "/F"],
            capture_output=True,
        )
    else:
        process.kill()


def iter_dicts(value: Any):
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from iter_dicts(child)
    elif isinstance(value, list):
        for child in value:
            yield from iter_dicts(child)


def inspect_events(stdout: str, stderr: str) -> dict:
    events = []
    for line in stdout.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            events.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    tool_names = set()
    usage: dict[str, float] = {}
    for event in events:
        for node in iter_dicts(event):
            name = node.get("name") or node.get("tool") or node.get("toolName")
            if isinstance(name, str) and name.startswith("pylingual_"):
                tool_names.add(name)
            for key in ("input_tokens", "output_tokens", "total_tokens", "cost"):
                value = node.get(key)
                if isinstance(value, (int, float)):
                    usage[key] = usage.get(key, 0) + float(value)
    all_text = stdout + "\n" + stderr
    return {
        "events": events,
        "tool_calls": sorted(tool_names),
        "session_hints": sorted(set(SESSION_RE.findall(all_text))),
        "usage": usage or None,
    }


def find_session(target: Path, before_ids: set[str], hints: list[str]) -> str | None:
    target_text = str(target).lower()
    candidates = []
    for session_id in hints:
        meta_path = sessions.SESSIONS / session_id / "session.json"
        if not meta_path.exists():
            continue
        try:
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if str(meta.get("input", {}).get("path", "")).lower() == target_text:
            candidates.append(session_id)
    for session_dir in sessions.SESSIONS.glob("ses_*"):
        session_id = session_dir.name
        if session_id in before_ids or session_id in candidates:
            continue
        meta_path = session_dir / "session.json"
        if not meta_path.exists():
            continue
        try:
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        input_path = str(meta.get("input", {}).get("path", "")).lower()
        if input_path == target_text:
            candidates.append(session_id)
    if not candidates:
        return None
    return max(candidates, key=lambda item: (sessions.SESSIONS / item).stat().st_mtime)


def prompt_for(task: dict) -> str:
    version = task.get("version")
    version_line = version or "auto-detect (omit the version argument)"
    return f"""You are running a headless PyLingual decompilation/repair task.

Target: {task['pyc_path']}
Target Python: {version_line}
Task: {task.get('description', 'decompile and repair')}
Decompile options: top_k={task.get('top_k', 10)}, device={task.get('device', 'auto')}

You are the primary orchestrator. Start exactly one `pylingual-worker` subagent
for this one `.pyc`, wait for it to finish, verify its session report, and then
finish. The worker owns the decompile and repair loop; do not decompile or patch
the file yourself. If the worker reports a technical failure, start a fresh
worker on the same file. Do not run two workers concurrently.

Do not use shell, edit, or web tools. Do not install, download, invoke, compare
with, or check the availability of uncompyle6, decompyle3, pycdc, pycdas, or any
other decompiler. PyLingual is the only allowed decompiler; a failed result
must be repaired through PyLingual. Do not ask questions.

Continue until the verifier reports `status: "perfect"`. There is no fixed
revision budget and no partial-success outcome. If the host reaches its
step/context limit, report the technical failure with the last revision and
remaining code-object IDs. Call `pylingual_finalize` only when the verifier says
status=perfect; do not export or finalize a non-perfect revision as success.

In your final message include the session ID, final revision, status,
perfect/total count, and remaining code-object IDs. Do not claim success unless
the verifier says status=perfect.
"""


def run_task(task: dict, output_dir: Path, opencode: str, agent: str, model: str | None) -> dict:
    target = Path(task["pyc_path"])
    before_ids = {path.name for path in sessions.SESSIONS.glob("ses_*")}
    started = time.monotonic()
    started_at = utc_now()
    task_dir = output_dir / task["id"]
    task_dir.mkdir(parents=True, exist_ok=True)
    prompt = prompt_for(task)
    command = [
        *opencode_prefix(opencode),
        "run",
        "--standalone",
        "--agent",
        agent,
        "--format",
        "json",
        "--auto",
    ]
    if model:
        command += ["--model", model]
    command.append(prompt)

    timed_out = False
    return_code: int | None = None
    stdout = ""
    stderr = ""
    task_env = {
        **os.environ,
        "PYLINGUAL_HARNESS_TASK": str(target),
        "PYLINGUAL_HARNESS_VERSION": str(task.get("version", "")),
    }
    try:
        process = subprocess.Popen(
            command,
            cwd=str(ROOT),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            env=task_env,
        )
        try:
            stdout, stderr = process.communicate(timeout=float(task.get("timeout_seconds", 1800)))
            return_code = process.returncode
        except subprocess.TimeoutExpired:
            timed_out = True
            terminate_process_tree(process)
            stdout, stderr = process.communicate()
            return_code = process.returncode
    except OSError as exc:
        stderr = f"failed to start OpenCode: {exc!r}"
        return_code = -1

    duration = round(time.monotonic() - started, 3)
    (task_dir / "opencode.stdout.jsonl").write_text(stdout, encoding="utf-8")
    (task_dir / "opencode.stderr.txt").write_text(stderr, encoding="utf-8")
    inspected = inspect_events(stdout, stderr)
    session_id = find_session(target, before_ids, inspected["session_hints"])

    result: dict[str, Any] = {
        "task": task["id"],
        "target": str(target),
        "version": task.get("version"),
        "difficulty": task.get("difficulty"),
        "description": task.get("description"),
        "started_at": started_at,
        "duration_seconds": duration,
        "opencode_exit_code": return_code,
        "timed_out": timed_out,
        "session_id": session_id,
        "tool_calls": inspected["tool_calls"],
        "usage": inspected["usage"],
        "event_count": len(inspected["events"]),
        "success": False,
    }
    if session_id is None:
        result["error"] = "no_session_created"
        result["stderr_tail"] = stderr[-2000:]
        write_json(task_dir / "result.json", result)
        return result

    try:
        meta = sessions.get_session(session_id)
        final_report = sessions.get_report(session_id, detail="full")
        initial_report = sessions.get_report(session_id, 0, detail="full")
        source = sessions.get_source(session_id)["source"]
        write_json(task_dir / "session.json", meta)
        write_json(task_dir / "report.json", final_report)
        (task_dir / "final.py").write_text(source, encoding="utf-8")
        result.update(
            {
                "success": final_report["status"] == "perfect",
                "final_revision": meta.get("current_revision"),
                "revisions": len(meta.get("revisions", [])),
                "patches": max(0, int(meta.get("current_revision", 0))),
                "initial": initial_report["summary"],
                "final": final_report["summary"],
                "status": final_report["status"],
                "improvement": round(
                    float(final_report["summary"].get("score", 0.0))
                    - float(initial_report["summary"].get("score", 0.0)),
                    6,
                ),
                "remaining": [
                    {"id": item["id"], "name": item["name"], "message": item["message"]}
                    for item in final_report.get("code_objects", [])
                    if item["status"] != "perfect"
                ],
                "export_path": f"{task_dir.relative_to(ROOT).as_posix()}/final.py",
            }
        )
    except Exception as exc:
        result["error"] = f"verification failed: {exc!r}"
        result["stderr_tail"] = stderr[-2000:]

    write_json(task_dir / "result.json", result)
    return result


def summarize(results: list[dict], meta: dict) -> dict:
    total = len(results)
    successes = sum(1 for item in results if item.get("success"))
    errors = sum(1 for item in results if item.get("error"))
    final_scores = [float(item.get("final", {}).get("score", 0.0)) for item in results]
    durations = [float(item.get("duration_seconds", 0.0)) for item in results]
    revisions = [int(item.get("revisions", 0)) for item in results]
    return {
        "started_at": meta["started_at"],
        "finished_at": utc_now(),
        "model": meta.get("model"),
        "agent": meta.get("agent"),
        "opencode": meta.get("opencode"),
        "tasks": total,
        "successes": successes,
        "errors": errors,
        "success_rate": (successes / total) if total else 0.0,
        "average_final_score": (sum(final_scores) / total) if total else 0.0,
        "average_duration_seconds": (sum(durations) / total) if total else 0.0,
        "average_revisions": (sum(revisions) / total) if total else 0.0,
        "results": results,
    }


def markdown_summary(summary: dict) -> str:
    lines = [
        "# PyLingual OpenCode harness",
        "",
        f"- Started: `{summary['started_at']}`",
        f"- Finished: `{summary['finished_at']}`",
        f"- Agent: `{summary['agent']}`",
        f"- Model: `{summary['model'] or 'OpenCode default'}`",
        f"- Success: **{summary['successes']}/{summary['tasks']}** ({summary['success_rate']:.0%})",
        f"- Average final score: **{summary['average_final_score']:.3f}**",
        f"- Average revisions: **{summary['average_revisions']:.1f}**",
        f"- Average duration: **{summary['average_duration_seconds']:.1f}s**",
        "",
        "| Task | Status | Initial | Final | Revisions | Time | Session |",
        "|---|---|---:|---:|---:|---:|---|",
    ]
    for item in summary["results"]:
        status = item.get("status") or item.get("error", "error")
        initial = item.get("initial", {}).get("score", 0.0)
        final = item.get("final", {}).get("score", 0.0)
        lines.append(
            f"| {item['task']} | {status} | {initial:.3f} | {final:.3f} | "
            f"{item.get('revisions', 0)} | {item.get('duration_seconds', 0):.1f}s | "
            f"`{item.get('session_id') or '-'}` |"
        )
    lines.extend(
        [
            "",
            "A task is successful only when the independently read final session report has `status: perfect`.",
            "See each task directory for `final.py`, `report.json`, `session.json`, and raw OpenCode events.",
        ]
    )
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run OpenCode against the PyLingual MCP server and score exact verification")
    parser.add_argument("--tasks", default=str(DEFAULT_TASKS))
    parser.add_argument("--out", default=str(DEFAULT_OUT))
    parser.add_argument(
        "--opencode",
        default=os.environ.get("OPENCODE_BIN", "opencode"),
        help="OpenCode executable, .cmd, or .ps1 wrapper",
    )
    parser.add_argument("--agent", default="pylingual")
    parser.add_argument("--model", default=os.environ.get("OPENCODE_MODEL"))
    parser.add_argument("--only", default=None, help="comma-separated task IDs")
    parser.add_argument("--max-tasks", type=int, default=None)
    parser.add_argument("--repeat", type=int, default=1)
    parser.add_argument("--require-all", action="store_true", help="return 1 unless every task is perfect")
    parser.add_argument("--list", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--no-policy-check", action="store_true", help="skip the PyLingual-only preflight")
    args = parser.parse_args(argv)

    tasks_path = Path(args.tasks).resolve()
    _, tasks = load_tasks(tasks_path)
    if args.only:
        allowed = {item.strip() for item in args.only.split(",") if item.strip()}
        tasks = [item for item in tasks if item["id"] in allowed]
    if args.max_tasks is not None:
        tasks = tasks[: max(0, args.max_tasks)]
    if args.repeat < 1:
        parser.error("--repeat must be >= 1")

    if args.list:
        for item in tasks:
            print(f"{item['id']:16} {item.get('difficulty', '-'):8} {item['pyc_path']}")
        return 0

    missing = [str(item["pyc_path"]) for item in tasks if not Path(item["pyc_path"]).is_file()]
    if missing:
        print("missing fixture files:", file=sys.stderr)
        for path in missing:
            print(f"  {path}", file=sys.stderr)
        print("run: .\\scripts\\python.cmd .\\scripts\\build_harness_fixtures.py", file=sys.stderr)
        return 2

    if not args.no_policy_check:
        policy = subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "check_opencode_harness.py")],
            cwd=str(ROOT),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        if policy.returncode != 0:
            print("PyLingual-only policy preflight failed:", file=sys.stderr)
            print(policy.stdout.strip(), file=sys.stderr)
            print(policy.stderr.strip(), file=sys.stderr)
            return 2

    resolved = resolve_opencode(args.opencode)
    if args.check:
        print(f"opencode: {resolved or 'NOT FOUND'}")
        print(f"tasks: {len(tasks)}")
        print(f"agent: {args.agent}")
        return 0 if resolved else 2

    if args.dry_run:
        for item in tasks:
            print(f"[dry-run] {item['id']} ({item.get('version')}) -> {item['pyc_path']}")
            command = [
                *opencode_prefix(resolved or args.opencode),
                "run",
                "--standalone",
                "--agent",
                args.agent,
                "--format",
                "json",
                "--auto",
            ]
            if args.model:
                command += ["--model", args.model]
            print("  " + " ".join(command) + " <prompt>")
        return 0

    if not resolved:
        print(f"OpenCode executable not found: {args.opencode}", file=sys.stderr)
        print("Install OpenCode or pass --opencode <path>. Use --dry-run to validate tasks without it.", file=sys.stderr)
        return 2

    run_dir = Path(args.out).resolve() / stamp()
    run_dir.mkdir(parents=True, exist_ok=True)
    started_at = utc_now()
    results = []
    total_runs = len(tasks) * args.repeat
    run_index = 0
    for repeat_index in range(args.repeat):
        for task in tasks:
            run_index += 1
            repeat_task = dict(task)
            if args.repeat > 1:
                repeat_task["id"] = f"{task['id']}__r{repeat_index + 1}"
            print(f"[{run_index}/{total_runs}] {repeat_task['id']} ...", flush=True)
            result = run_task(repeat_task, run_dir, resolved, args.agent, args.model)
            result["repeat"] = repeat_index + 1
            results.append(result)
            status = "perfect" if result.get("success") else (result.get("status") or result.get("error") or "failed")
            print(
                f"    {status} session={result.get('session_id')} "
                f"revisions={result.get('revisions', 0)} duration={result.get('duration_seconds', 0):.1f}s",
                flush=True,
            )

    summary = summarize(results, {"started_at": started_at, "model": args.model, "agent": args.agent, "opencode": resolved})
    write_json(run_dir / "summary.json", summary)
    (run_dir / "summary.md").write_text(markdown_summary(summary), encoding="utf-8")
    print(f"\nresults: {run_dir}")
    print(f"success: {summary['successes']}/{summary['tasks']}  avg_score={summary['average_final_score']:.3f}")
    if summary["errors"]:
        print(f"infrastructure errors: {summary['errors']}")
    if args.require_all and summary["successes"] != summary["tasks"]:
        return 1
    return 0 if summary["errors"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
