"""
Minecraft Mod Translation Progress Checker
Reads tasks.json, scans filesystem for actual translation status,
syncs status updates, and outputs a progress summary.
"""
import os
import json
import argparse
import sys
from pathlib import Path


def get_target_path(source_file):
    """Derive zh_tw target path from en_us source path."""
    source = Path(source_file)
    target_name = source.name.replace("en_us", "zh_tw")
    return str(source.parent / target_name)


def check_file_status(source_file, target_file):
    """
    Check translation status of a single file.
    Returns: (is_complete, message)
    """
    if not os.path.exists(target_file):
        return False, "Not translated"

    try:
        with open(target_file, 'r', encoding='utf-8') as f:
            zh_data = json.load(f)
    except json.JSONDecodeError:
        return False, "Corrupted JSON"

    try:
        with open(source_file, 'r', encoding='utf-8') as f:
            en_data = json.load(f)
        
        missing = set(en_data.keys()) - set(zh_data.keys())
        if len(missing) > 0:
            return False, f"Missing {len(missing)} keys"
    except Exception:
        pass

    return True, f"{len(zh_data)} keys"


def check_progress(work_dir, sync=True):
    """Check translation progress and optionally sync tasks.json status."""
    tasks_path = Path(work_dir) / "tasks.json"
    if not tasks_path.exists():
        print(f"Error: {tasks_path} not found")
        sys.exit(1)

    with open(tasks_path, 'r', encoding='utf-8') as f:
        tasks = json.load(f)

    stats = {"completed": 0, "pending": 0, "failed": 0, "partial": 0}
    total_keys = 0
    translated_keys = 0
    updated = False

    print("=" * 60)
    print("Minecraft Mod Translation Progress")
    print("=" * 60)

    for task in tasks:
        mod_id = task["mod_id"]
        key_count = task.get("key_count", 0)
        files = task.get("files_to_translate", [])
        total_keys += key_count

        if sync:
            # Scan filesystem for actual status
            all_complete = True

            for source_file in files:
                target_file = get_target_path(source_file)
                is_ok, _ = check_file_status(source_file, target_file)
                if not is_ok:
                    all_complete = False

            old_status = task.get("status", "pending")
            if all_complete and old_status != "completed":
                task["status"] = "completed"
                updated = True
            elif not all_complete and old_status == "completed":
                # File was deleted or corrupted
                task["status"] = "failed"
                updated = True

        status = task.get("status", "pending")
        stats[status] = stats.get(status, 0) + 1
        if status == "completed":
            translated_keys += key_count

    # Print stats
    total_mods = len(tasks)
    pct = (stats["completed"] / total_mods * 100) if total_mods > 0 else 0
    key_pct = (translated_keys / total_keys * 100) if total_keys > 0 else 0

    print(f"\nMod progress:  {stats['completed']}/{total_mods} ({pct:.1f}%)")
    print(f"Key progress:  {translated_keys}/{total_keys} ({key_pct:.1f}%)")
    print()
    print(f"  completed: {stats['completed']}")
    print(f"  pending:   {stats['pending']}")
    print(f"  failed:    {stats['failed']}")

    if stats.get("partial", 0) > 0:
        print(f"  partial:   {stats['partial']}")

    # List failed mods
    failed_mods = [t for t in tasks if t.get("status") in ("failed", "partial")]
    if failed_mods:
        print(f"\n{'-' * 40}")
        print("Failed/incomplete mods:")
        for t in failed_mods:
            print(f"  [FAIL] {t['mod_id']} ({t.get('key_count', '?')} keys) - {t.get('status')}")

    # Sync back
    if sync and updated:
        with open(tasks_path, 'w', encoding='utf-8') as f:
            json.dump(tasks, f, indent=2, ensure_ascii=False)
        print(f"\ntasks.json status synced")

    print("=" * 60)

    return stats


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Minecraft Mod Translation Progress Checker"
    )
    parser.add_argument("--work_dir", required=True,
                        help="Work directory path (containing tasks.json)")
    parser.add_argument("--no_sync", action="store_true",
                        help="View progress only, do not sync tasks.json")

    args = parser.parse_args()

    if not os.path.exists(args.work_dir):
        print(f"Error: work directory not found: {args.work_dir}")
        sys.exit(1)

    check_progress(args.work_dir, sync=not args.no_sync)
