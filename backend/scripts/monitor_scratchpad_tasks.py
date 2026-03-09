#!/usr/bin/env python3

import hashlib
import os
import re
import subprocess
import time
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path


SCRATCHPAD_PATH = Path("/home/ander/CascadeProjects/cryptoalpha_lite/docs/scratchpad.md")
REPO_ROOT = Path("/home/ander/CascadeProjects/cryptoalpha_lite")
CODEX_OUT_DIR = REPO_ROOT / "backend" / ".codex_out"
POLL_SECONDS = 30


def _extract_parallel_tasks(markdown_text: str) -> list[str]:
    lines = markdown_text.splitlines()

    in_section = False
    tasks: list[str] = []

    for ln in lines:
        if ln.strip() == "## Задачи для параллельного выполнения":
            in_section = True
            continue
        if in_section and ln.startswith("## "):
            break
        if not in_section:
            continue

        # Match unchecked markdown checkboxes: - [ ] ...
        m = re.match(r"^\s*-\s*\[\s\]\s+(.*)$", ln)
        if not m:
            continue
        tasks.append(m.group(1).strip())

    return tasks


def _task_id(task_text: str) -> str:
    digest = hashlib.sha256(task_text.strip().encode("utf-8")).hexdigest()[:12]
    return digest


def _append_progress_line(markdown_text: str, line: str) -> str:
    lines = markdown_text.splitlines()
    header = "## Прогресс выполнения"

    for i, ln in enumerate(lines):
        if ln.strip() == header:
            insert_at = i + 1
            while insert_at < len(lines) and lines[insert_at].strip() == "":
                insert_at += 1
            lines.insert(insert_at, line)
            return "\n".join(lines) + "\n"

    lines.append("")
    lines.append(header)
    lines.append(line)
    return "\n".join(lines) + "\n"


def _notify(title: str, body: str) -> None:
    try:
        subprocess.run(
            ["notify-send", "--app-name", "CryptoAlpha", title, body],
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except FileNotFoundError:
        return
    except Exception:  # noqa: BLE001
        return


@contextmanager
def _codex_run_lock() -> object:
    CODEX_OUT_DIR.mkdir(parents=True, exist_ok=True)
    lock_path = CODEX_OUT_DIR / ".codex_run.lock"
    fd = os.open(str(lock_path), os.O_CREAT | os.O_RDWR, 0o600)
    try:
        import fcntl

        fcntl.flock(fd, fcntl.LOCK_EX)
        yield
    finally:
        try:
            import fcntl

            fcntl.flock(fd, fcntl.LOCK_UN)
        finally:
            os.close(fd)


def _checkoff_parallel_task(markdown_text: str, task_text: str) -> str:
    lines = markdown_text.splitlines()
    in_section = False
    replaced = False

    for i, ln in enumerate(lines):
        if ln.strip() == "## Задачи для параллельного выполнения":
            in_section = True
            continue
        if in_section and ln.startswith("## "):
            break
        if not in_section:
            continue

        if replaced:
            continue

        m = re.match(r"^(\s*-\s*)\[(.)\](\s+)(.*)$", ln)
        if not m:
            continue

        prefix, status, spacer, rest = m.groups()
        if status != " ":
            continue
        if rest.strip() != task_text.strip():
            continue

        lines[i] = f"{prefix}[x]{spacer}{rest}"
        replaced = True

    return "\n".join(lines) + "\n"


def _run_codex_for_task(task_text: str) -> tuple[Path, int]:
    CODEX_OUT_DIR.mkdir(parents=True, exist_ok=True)

    ts = datetime.now().isoformat(timespec="seconds").replace(":", "-")
    task_digest = _task_id(task_text)
    out_path = CODEX_OUT_DIR / f"{ts}_{task_digest}.md"

    prompt = (
        "Прочитай docs/scratchpad.md. Возьми задачу из раздела '## Задачи для параллельного выполнения' "
        "и выполни именно эту задачу: '\n" + task_text + "\n'. "
        "Работай БЕЗ изменений файлов (только анализ/план/дифф в тексте). "
        "Если можешь, выдай unified diff. Если нет — дай точный список правок по файлам и строкам. "
        "В конце выведи блок 'RESULT:' с итогом."
    )

    cmd = [
        "codex",
        "exec",
        "--sandbox",
        "read-only",
        "-C",
        str(REPO_ROOT),
        "--skip-git-repo-check",
        "--output-last-message",
        str(out_path),
        prompt,
    ]

    with _codex_run_lock():
        completed = subprocess.run(cmd, check=False, capture_output=True, text=True)

    sidecar = out_path.with_suffix(out_path.suffix + ".run.log")
    try:
        sidecar.write_text(
            (completed.stdout or "")
            + "\n\n--- STDERR ---\n"
            + (completed.stderr or "")
            + "\n",
            encoding="utf-8",
            errors="replace",
        )
    except Exception:  # noqa: BLE001
        pass

    if (not out_path.exists()) or out_path.stat().st_size == 0:
        out_path.write_text("RESULT: codex did not produce output\n", encoding="utf-8")
    return out_path, completed.returncode


def main() -> None:
    last_seen: set[str] = set()
    last_mtime: float | None = None

    while True:
        try:
            stat = SCRATCHPAD_PATH.stat()
            if last_mtime is None or stat.st_mtime != last_mtime:
                last_mtime = stat.st_mtime
                text = SCRATCHPAD_PATH.read_text(encoding="utf-8", errors="replace")
                tasks = _extract_parallel_tasks(text)

                new = [t for t in tasks if t not in last_seen]
                if new:
                    ts = datetime.now().isoformat(timespec="seconds")
                    for t in new:
                        print(f"{ts}  scratchpad_new_task  {t}", flush=True)
                        out_path, returncode = _run_codex_for_task(t)
                        try:
                            updated = SCRATCHPAD_PATH.read_text(encoding="utf-8", errors="replace")
                            line = f"- [{ts}] codex: задача '{t}' -> {out_path}"
                            updated = _append_progress_line(updated, line)
                            updated = _checkoff_parallel_task(updated, t)
                            SCRATCHPAD_PATH.write_text(updated, encoding="utf-8")
                            if returncode == 0:
                                _notify("Codex: задача выполнена", f"{t}\n{out_path}")
                            else:
                                _notify("Codex: ошибка", f"rc={returncode}\n{t}\n{out_path}")
                        except Exception as exc:  # noqa: BLE001
                            ts2 = datetime.now().isoformat(timespec="seconds")
                            print(
                                f"{ts2}  scratchpad_progress_write_failed  error={exc}  out={out_path}",
                                flush=True,
                            )
                            _notify("Scratchpad: ошибка записи", f"{exc}\n{out_path}")
                last_seen = set(tasks)
        except FileNotFoundError:
            ts = datetime.now().isoformat(timespec="seconds")
            print(f"{ts}  scratchpad_missing  path={SCRATCHPAD_PATH}", flush=True)
        except Exception as exc:  # noqa: BLE001
            ts = datetime.now().isoformat(timespec="seconds")
            print(f"{ts}  scratchpad_monitor_error  error={exc}", flush=True)

        time.sleep(POLL_SECONDS)


if __name__ == "__main__":
    main()
