import os
import json
import argparse
from pathlib import Path

def merge_files(work_dir):
    """Merges translated part files back into single zh_tw.json."""
    work_path = Path(work_dir)
    extracted_path = work_path / "extracted"
    
    # Load tasks
    if not (work_path / "tasks.json").exists():
        print("No tasks.json found.")
        return

    with open(work_path / "tasks.json", 'r', encoding='utf-8') as f:
        tasks = json.load(f)

    for task in tasks:
        mod_id = task["mod_id"]
        mod_dir = extracted_path / mod_id
        
        merged_data = {}
        
        # Look for translated files
        if task["split_needed"]:
            num_parts = len(task["files_to_translate"])
            for i in range(num_parts):
                part_path = mod_dir / f"zh_tw_part{i+1}.json"
                if not part_path.exists():
                     # Fallback check
                     part_path = mod_dir / f"en_us_part{i+1}_zh_tw.json"
                
                if part_path.exists():
                    try:
                        with open(part_path, 'r', encoding='utf-8') as f:
                            content = f.read()
                        merged_data.update(json.loads(content, strict=False))
                    except json.JSONDecodeError as e:
                        print(f"CRITICAL ERROR: Failed to parse JSON in {part_path}")
                        print(f"Error details: {e}")
                        print("Skipping this file content.")
                else:
                    print(f"Warning: Missing translation part {part_path} for {mod_id}")
        else:
            zh_tw_path = mod_dir / "zh_tw.json"
            if not zh_tw_path.exists():
                 zh_tw_path = mod_dir / "en_us_zh_tw.json"
            
            if zh_tw_path.exists():
                try:
                    with open(zh_tw_path, 'r', encoding='utf-8') as f:
                        content = f.read()
                    merged_data = json.loads(content, strict=False)
                except json.JSONDecodeError as e:
                    print(f"CRITICAL ERROR: Failed to parse JSON in {zh_tw_path}")
                    print(f"Error details: {e}")
                    print("Skipping this file content.")
            else:
                 print(f"Warning: Missing translation for {mod_id}")

        # Save merged/final zh_tw.json
        if merged_data:
            # Completeness Check
            # Load original en_us for comparison
            en_us_path = mod_dir / "en_us.json"
            if en_us_path.exists():
                try:
                    with open(en_us_path, 'r', encoding='utf-8') as f:
                        en_data = json.load(f)
                    
                    en_keys = set(en_data.keys())
                    zh_keys = set(merged_data.keys())
                    
                    missing_keys = en_keys - zh_keys
                    identical_count = 0
                    for k in (en_keys & zh_keys):
                        if en_data[k] == merged_data[k] and en_data[k].strip() != "":
                            identical_count += 1
                    
                    if missing_keys:
                        print(f"WARNING: {mod_id} is missing {len(missing_keys)} keys in translation.")
                    if identical_count > 0:
                        print(f"WARNING: {mod_id} has {identical_count} items identical to original (untranslated?).")
                        
                    if not missing_keys and identical_count == 0:
                        print(f"Success: {mod_id} merged and verified complete.")
                        
                except Exception as e:
                    print(f"Warning: Could not verify completeness for {mod_id}: {e}")

            final_path = mod_dir / "final_zh_tw.json"
            with open(final_path, 'w', encoding='utf-8') as f:
                json.dump(merged_data, f, indent=2, ensure_ascii=False)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Merge translated JSON parts")
    parser.add_argument("--work_dir", required=True)
    args = parser.parse_args()
    
    merge_files(args.work_dir)
