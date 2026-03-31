"""
Minecraft Mod Translation Dispatcher
Reads tasks from tasks.json, launches Gemini CLI subprocesses (stdin/stdout mode),
validates translation results, and updates task status.

Architecture: stdin/stdout mode
- Python reads en_us.json content
- Pipes it via stdin to Gemini CLI subprocess
- Subprocess outputs translated JSON to stdout only (no filesystem access)
- Python parses stdout and writes zh_tw.json
- No --approval-mode=yolo, no Docker sandbox
"""
import os
import json
import subprocess
import argparse
import time
import sys
import re
import tempfile
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

# ======== Translation Prompt ========
TRANSLATION_PROMPT = """你是一位專業的 Minecraft 模組翻譯員。

【任務】
將以下 JSON 的 value 翻譯為繁體中文（台灣）。

【翻譯規範】
1. Key (鍵)：絕對不可修改。
2. 格式化代碼：保留 %s, %d, %1$s, {0}, {1} 等變數符號。
3. 顏色代碼：保留 §a, §1, §r, §l, §o 等 Minecraft 格式代碼。
4. 換行符號：翻譯中的換行必須寫為 \\n，不能使用實際換行。每個字串值必須在同一行。
5. 轉義符號：翻譯中的雙引號使用 \\"。
6. 術語一致性：專有名詞參考 Minecraft 官方繁中譯名。
7. 數字與符號：純數字、純符號的值不需翻譯，保持原樣。

【輸出格式】
- 只輸出翻譯後的完整 JSON
- 不要加入任何解釋、markdown 標記、或其他文字
- 用 ```json 包裹
- 直接以  ```json開頭，```結尾
"""



def get_target_path(source_file):
    """Derive zh_tw target path from en_us source path."""
    source = Path(source_file)
    target_name = source.name.replace("en_us", "zh_tw")
    return str(source.parent / target_name)


def extract_json_from_output(raw_output):
    """
    Extract translated JSON from Gemini CLI raw stdout.
    Tries multiple strategies: ```json block -> direct parse -> { } extraction
    """
    text = raw_output.strip()
    if not text:
        return None

    # Strategy 1: Extract from ```json ... ``` code block (most common)
    code_block_match = re.search(r'```(?:json)?\s*\n(.*?)\n```', text, re.DOTALL)
    if code_block_match:
        try:
            return json.loads(code_block_match.group(1).strip())
        except json.JSONDecodeError:
            pass

    # Strategy 2: Direct parse (if Gemini outputs clean JSON only)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Strategy 3: Find outermost { ... } block
    brace_start = text.find('{')
    brace_end = text.rfind('}')
    if brace_start != -1 and brace_end != -1 and brace_end > brace_start:
        try:
            return json.loads(text[brace_start:brace_end + 1])
        except json.JSONDecodeError:
            pass

    return None


def validate_translation(en_data, zh_data):
    """
    Validate translation completeness.
    Returns: (status, message)
    """
    en_keys = set(en_data.keys())
    zh_keys = set(zh_data.keys())
    missing = en_keys - zh_keys

    if len(missing) > 0:
        ratio = len(zh_keys) / len(en_keys) * 100 if en_keys else 0
        return "partial", f"Missing {len(missing)} keys ({ratio:.0f}% complete)"

    return "completed", f"Translated {len(zh_data)} keys"


def translate_file(source_file, target_file, timeout, work_dir=None):
    """
    Translate a single file.
    Flow: read en_us -> stdin to Gemini -> parse stdout -> write zh_tw
    Returns: (status, message)
    """
    # 1. Read source file
    try:
        with open(source_file, 'r', encoding='utf-8') as f:
            en_content = f.read()
        en_data = json.loads(en_content)
    except Exception as e:
        return "failed", f"Cannot read source file: {e}"

    # 2. Build prompt
    prompt = TRANSLATION_PROMPT

    # 3. Launch Gemini CLI subprocess (stdin/stdout mode)
    #    cwd set to temp dir to prevent workspace-level Skill detection
    try:
        result = subprocess.run(
            ["gemini", "-p", prompt],
            input=en_content,
            capture_output=True,
            text=True,
            encoding='utf-8',
            timeout=timeout,
            cwd=tempfile.gettempdir(),
            shell=(os.name == 'nt')
        )

        if result.returncode != 0:
            _save_error_log(work_dir, source_file, result.stdout, result.stderr)
            stderr_snippet = (result.stderr or "")[:500]
            return "failed", f"Translator exited with code {result.returncode}: {stderr_snippet}"

    except subprocess.TimeoutExpired:
        return "failed", f"Translator timed out ({timeout}s)"
    except Exception as e:
        return "failed", f"Failed to launch translator: {e}"

    # 4. Extract translated JSON from raw stdout
    zh_data = extract_json_from_output(result.stdout)
    if zh_data is None:
        _save_error_log(work_dir, source_file, result.stdout, result.stderr)
        return "failed", f"Cannot parse JSON from translator output (log saved)"

    # 5. Validate translation completeness
    status, message = validate_translation(en_data, zh_data)

    # 6. Write target file (write even if partial - some translation is better than none)
    try:
        with open(target_file, 'w', encoding='utf-8') as f:
            json.dump(zh_data, f, indent=2, ensure_ascii=False)
    except Exception as e:
        return "failed", f"Cannot write target file: {e}"

    return status, message


def _save_error_log(work_dir, source_file, stdout, stderr):
    """Save raw Gemini output to a log file for debugging."""
    if not work_dir:
        return
    log_dir = Path(work_dir) / "logs"
    log_dir.mkdir(exist_ok=True)
    source_name = Path(source_file).stem
    log_path = log_dir / f"{source_name}_error.log"
    try:
        with open(log_path, 'w', encoding='utf-8') as f:
            f.write(f"=== Source: {source_file} ===\n")
            f.write(f"=== STDOUT ===\n")
            f.write(stdout or "(empty)")
            f.write(f"\n\n=== STDERR ===\n")
            f.write(stderr or "(empty)")
        print(f"     Error log saved: logs/{log_path.name}")
    except Exception:
        pass


def translate_task(task, timeout, work_dir=None):
    """
    Translate a complete mod task (may contain multiple split files).
    Returns: (mod_id, status, message)
    """
    mod_id = task["mod_id"]
    files = task["files_to_translate"]
    results = []

    for source_file in files:
        target_file = get_target_path(source_file)

        # Skip if target already exists and is valid JSON
        if os.path.exists(target_file):
            try:
                with open(target_file, 'r', encoding='utf-8') as f:
                    json.load(f)
                results.append(("completed", f"Already exists: {Path(target_file).name}"))
                continue
            except (json.JSONDecodeError, Exception):
                pass  # Corrupted, re-translate

        print(f"  Translating: {Path(source_file).name} -> {Path(target_file).name}")
        status, message = translate_file(source_file, target_file, timeout, work_dir)
        results.append((status, message))
        icon = "[OK]" if status == "completed" else "[FAIL]"
        print(f"     {icon} {message}")

    # Summarize results
    failed = [r for r in results if r[0] == "failed"]
    partial = [r for r in results if r[0] == "partial"]

    if failed:
        return mod_id, "failed", f"{len(failed)}/{len(files)} file(s) failed"
    elif partial:
        return mod_id, "partial", f"{len(partial)}/{len(files)} file(s) incomplete"
    else:
        return mod_id, "completed", f"All {len(files)} file(s) translated"


def load_tasks(work_dir):
    """Load tasks.json"""
    tasks_path = Path(work_dir) / "tasks.json"
    if not tasks_path.exists():
        print(f"Error: {tasks_path} not found")
        sys.exit(1)
    with open(tasks_path, 'r', encoding='utf-8') as f:
        return json.load(f)


def save_tasks(work_dir, tasks):
    """Save tasks.json"""
    tasks_path = Path(work_dir) / "tasks.json"
    with open(tasks_path, 'w', encoding='utf-8') as f:
        json.dump(tasks, f, indent=2, ensure_ascii=False)


def dispatch(work_dir, max_workers=1, batch_size=0, timeout=300, retry_failed=False):
    """Main dispatch function"""
    tasks = load_tasks(work_dir)

    # Filter pending tasks
    pending = []
    for task in tasks:
        status = task.get("status", "pending")
        if status == "pending":
            pending.append(task)
        elif status == "failed" and retry_failed:
            pending.append(task)

    if not pending:
        print("[OK] No pending tasks. All mods completed.")
        return

    # Disable all skills to prevent translator subprocesses from activating them
    print("Disabling Gemini skills for translator subprocesses...")
    subprocess.run(
        ["gemini", "skills", "disable", "--all"],
        capture_output=True, shell=(os.name == 'nt')
    )

    try:
        _run_dispatch(tasks, pending, work_dir, max_workers, batch_size, timeout)
    finally:
        # Re-enable all skills when done
        print("Re-enabling Gemini skills...")
        subprocess.run(
            ["gemini", "skills", "enable", "--all"],
            capture_output=True, shell=(os.name == 'nt')
        )


def _run_dispatch(tasks, pending, work_dir, max_workers, batch_size, timeout):
    """Internal dispatch logic"""

    # Apply batch_size limit
    if batch_size > 0:
        pending = pending[:batch_size]

    total = len(pending)
    completed_count = 0
    failed_count = 0

    print("=" * 50)
    print("Minecraft Mod Translation Dispatcher")
    print("=" * 50)
    print(f"Pending mods: {total}")
    print(f"Workers:      {max_workers}")
    print(f"Timeout:      {timeout}s")
    print(f"Mode:         stdin/stdout (no sandbox)")
    print("=" * 50)

    if max_workers == 1:
        # Sequential mode
        for i, task in enumerate(pending, 1):
            mod_id = task["mod_id"]
            key_count = task.get("key_count", "?")
            print(f"\n[{i}/{total}] {mod_id} ({key_count} keys)")

            mod_id, status, message = translate_task(task, timeout, work_dir)

            # Update status
            for t in tasks:
                if t["mod_id"] == mod_id:
                    t["status"] = status
                    break

            # Save progress after each task
            save_tasks(work_dir, tasks)

            if status == "completed":
                completed_count += 1
                print(f"  [OK] {message}")
            else:
                failed_count += 1
                print(f"  [FAIL] {message}")

            # Rate limit delay
            if i < total:
                time.sleep(2)
    else:
        # Parallel mode
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {}
            for task in pending:
                future = executor.submit(translate_task, task, timeout, work_dir)
                futures[future] = task

            for i, future in enumerate(as_completed(futures), 1):
                task = futures[future]
                mod_id = task["mod_id"]

                try:
                    ret_mod_id, status, message = future.result()
                except Exception as e:
                    status = "failed"
                    message = f"Unexpected error: {e}"

                # Update status
                for t in tasks:
                    if t["mod_id"] == mod_id:
                        t["status"] = status
                        break

                save_tasks(work_dir, tasks)

                icon = "[OK]" if status == "completed" else "[FAIL]"
                print(f"[{i}/{total}] {icon} {mod_id}: {message}")

    # Final summary - count from actual task statuses to avoid counter bugs
    final_completed = sum(1 for t in tasks if t.get("status") == "completed")
    final_failed = sum(1 for t in tasks if t.get("status") in ("failed", "partial"))
    final_pending = sum(1 for t in tasks if t.get("status") == "pending")

    print(f"\n{'=' * 50}")
    print("Translation Summary")
    print("=" * 50)
    print(f"  Completed: {final_completed}")
    print(f"  Failed:    {final_failed}")
    print(f"  Pending:   {final_pending}")
    print(f"  Progress saved to tasks.json")

    # Check if error logs exist
    log_dir = Path(work_dir) / "logs"
    if log_dir.exists():
        log_count = len(list(log_dir.glob("*_error.log")))
        if log_count > 0:
            print(f"  Error logs: {log_count} file(s) in logs/")

    if final_failed > 0:
        print(f"\nRetry failed tasks:")
        print(f"  python dispatch.py --work_dir \"{work_dir}\" --retry_failed")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Minecraft Mod Translation Dispatcher"
    )
    parser.add_argument("--work_dir", required=True,
                        help="Work directory path (containing tasks.json)")
    parser.add_argument("--max_workers", type=int, default=1,
                        help="Max parallel translator count (default: 1)")
    parser.add_argument("--batch_size", type=int, default=0,
                        help="Mods per batch, 0=all pending (default: 0)")
    parser.add_argument("--timeout", type=int, default=300,
                        help="Timeout per translator in seconds (default: 300)")
    parser.add_argument("--retry_failed", action="store_true",
                        help="Retry previously failed tasks")

    args = parser.parse_args()

    if not os.path.exists(args.work_dir):
        print(f"Error: work directory not found: {args.work_dir}")
        sys.exit(1)

    dispatch(
        work_dir=args.work_dir,
        max_workers=args.max_workers,
        batch_size=args.batch_size,
        timeout=args.timeout,
        retry_failed=args.retry_failed
    )
