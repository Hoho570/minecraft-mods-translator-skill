import os
import json
import zipfile
import argparse
import math
import shutil
from pathlib import Path

def parse_lang_file(content):
    """Parses .lang file content into a dictionary."""
    data = {}
    for line in content.splitlines():
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        if '=' in line:
            key, value = line.split('=', 1)
            data[key.strip()] = value.strip()
    return data

def extract_and_classify(mods_dir, output_dir):
    """
    Scans jars, extracts en_us.json/lang, converts lang to json,
    checks for existing zh_tw, categorizes by size.
    """
    mods_path = Path(mods_dir)
    out_path = Path(output_dir)
    extracted_path = out_path / "extracted"
    extracted_path.mkdir(parents=True, exist_ok=True)

    tasks = []

    for jar_file in mods_path.glob("*.jar"):
        try:
            with zipfile.ZipFile(jar_file, 'r') as z:
                # Identify mod ID and language files
                assets = [f for f in z.namelist() if f.startswith('assets/') and '/lang/' in f]
                mod_ids = set(f.split('/')[1] for f in assets)
                
                for mod_id in mod_ids:
                    has_zh_tw = any(f.lower().endswith(f'assets/{mod_id}/lang/zh_tw.json') or f.endswith(f'assets/{mod_id}/lang/zh_TW.lang') for f in assets)
                    
                    if has_zh_tw:
                        print(f"Skipping {mod_id} (already has zh_tw)")
                        continue

                    # Find en_us
                    en_us_path = None
                    is_lang = False
                    for f in assets:
                         if f.lower().endswith(f'assets/{mod_id}/lang/en_us.json'):
                             en_us_path = f
                             break
                         elif f.endswith(f'assets/{mod_id}/lang/en_us.lang'):
                             en_us_path = f
                             is_lang = True
                             break
                    
                    if not en_us_path:
                        continue

                    # Extract
                    with z.open(en_us_path) as source:
                        content = source.read().decode('utf-8', errors='ignore')
                    
                    if is_lang:
                        data = parse_lang_file(content)
                    else:
                        try:
                            data = json.loads(content)
                        except json.JSONDecodeError:
                            print(f"Error decoding JSON for {mod_id}")
                            continue

                    # Save standard JSON
                    mod_out_dir = extracted_path / mod_id
                    mod_out_dir.mkdir(parents=True, exist_ok=True)
                    json_path = mod_out_dir / "en_us.json"
                    
                    # Clean data (ensure keys use standard dots if possible? No, keep as is)
                    with open(json_path, 'w', encoding='utf-8') as f:
                        json.dump(data, f, indent=2, ensure_ascii=False)

                    # Classify
                    line_count = len(data) # Using key count as "lines" approximation
                    
                    task_info = {
                        "mod_id": mod_id,
                        "original_file": str(json_path),
                        "key_count": line_count,
                        "split_needed": line_count > 1000
                    }

                    if line_count > 1000:
                        split_files = split_json(data, mod_out_dir, line_count)
                        task_info["files_to_translate"] = split_files
                    else:
                        task_info["files_to_translate"] = [str(json_path)]
                    
                    tasks.append(task_info)

        except Exception as e:
            print(f"Error processing {jar_file}: {e}")

    # Output manifest
    with open(out_path / "tasks.json", 'w', encoding='utf-8') as f:
        json.dump(tasks, f, indent=2, ensure_ascii=False)
    
    print(f"Extraction complete. Found {len(tasks)} mods to translate.")
    return tasks

def split_json(data, output_dir, total_keys):
    """Splits JSON data into chunks."""
    num_parts = math.ceil(total_keys / 1000)
    chunk_size = math.ceil(total_keys / num_parts)
    
    items = list(data.items())
    files = []
    
    for i in range(num_parts):
        start = i * chunk_size
        end = start + chunk_size
        chunk = dict(items[start:end])
        
        part_path = output_dir / f"en_us_part{i+1}.json"
        with open(part_path, 'w', encoding='utf-8') as f:
            json.dump(chunk, f, indent=2, ensure_ascii=False)
        files.append(str(part_path))
        
    return files

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
        # Expecting filenames like: en_us_zh_tw.json or en_us_part1_zh_tw.json
        # BUT standard convention usually replaces name. Let's assume agent saves as [original_name]_translated.json or overwrites?
        # Let's assume agent creates 'zh_tw.json' or 'zh_tw_part1.json' in the same folder.
        
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
            final_path = mod_dir / "final_zh_tw.json"
            with open(final_path, 'w', encoding='utf-8') as f:
                json.dump(merged_data, f, indent=2, ensure_ascii=False)

def json_to_lang(data):
    """Converts dictionary to .lang format content."""
    lines = []
    for key, value in data.items():
        # .lang files usually don't need escaping for quotes like JSON, but newlines might need handling
        # standard format: key=value
        lines.append(f"{key}={value}")
    return "\n".join(lines)

def get_major_version(version_str):
    """Parses version string "1.12.2" -> (1, 12, 2)"""
    try:
        parts = [int(p) for p in version_str.split('.')]
        return tuple(parts)
    except:
        return (1, 20, 1) # Default fallback

def create_resource_pack(work_dir, pack_output_path, mc_version, pack_format):
    """Creates the final resource pack with version-specific formatting."""
    work_path = Path(work_dir)
    extracted_path = work_path / "extracted"
    
    if not (work_path / "tasks.json").exists():
        return

    with open(work_path / "tasks.json", 'r', encoding='utf-8') as f:
        tasks = json.load(f)

    # Create temporary pack structure
    pack_root = work_path / "resource_pack_temp"
    if pack_root.exists():
        shutil.rmtree(pack_root)
    pack_root.mkdir()
    
    assets_dir = pack_root / "assets"
    assets_dir.mkdir()
    
    version_tuple = get_major_version(mc_version)
    is_legacy = version_tuple < (1, 13) # 1.12.2 and older use .lang
    
    count = 0
    for task in tasks:
        mod_id = task["mod_id"]
        mod_dir = extracted_path / mod_id
        final_zh = mod_dir / "final_zh_tw.json"
        
        if final_zh.exists():
            mod_lang_dir = assets_dir / mod_id / "lang"
            mod_lang_dir.mkdir(parents=True, exist_ok=True)
            
            with open(final_zh, 'r', encoding='utf-8') as f:
                trans_data = json.load(f)

            if is_legacy:
                # Output zh_TW.lang
                content = json_to_lang(trans_data)
                with open(mod_lang_dir / "zh_TW.lang", 'w', encoding='utf-8') as f:
                    f.write(content)
            else:
                # Output zh_tw.json
                with open(mod_lang_dir / "zh_tw.json", 'w', encoding='utf-8') as f:
                    json.dump(trans_data, f, indent=2, ensure_ascii=False)
            
            count += 1
    
    # mcmeta
    with open(pack_root / "pack.mcmeta", 'w', encoding='utf-8') as f:
        json.dump({
            "pack": {
                "pack_format": int(pack_format),
                "description": f"Automated TC Translation Pack for {mc_version}"
            }
        }, f, indent=2)
        
    # Zip
    shutil.make_archive(str(Path(pack_output_path).with_suffix('')), 'zip', pack_root)
    print(f"Resource pack created with {count} mods at {pack_output_path}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Minecraft Mod Translation Manager")
    subparsers = parser.add_subparsers(dest="command")
    
    # Scan/Extract
    scan_parser = subparsers.add_parser("scan")
    scan_parser.add_argument("--mods_dir", required=True)
    scan_parser.add_argument("--work_dir", required=True)
    
    # Merge
    merge_parser = subparsers.add_parser("merge")
    merge_parser.add_argument("--work_dir", required=True)
    
    # Pack
    pack_parser = subparsers.add_parser("pack")
    pack_parser.add_argument("--work_dir", required=True)
    pack_parser.add_argument("--output", required=True)
    pack_parser.add_argument("--mc_version", required=True, help="Target Minecraft Version (e.g. 1.12.2, 1.20.1)")
    pack_parser.add_argument("--pack_format", required=True, type=int, help="pack_format number")
    
    args = parser.parse_args()
    
    if args.command == "scan":
        extract_and_classify(args.mods_dir, args.work_dir)
    elif args.command == "merge":
        merge_files(args.work_dir)
    elif args.command == "pack":
        create_resource_pack(args.work_dir, args.output, args.mc_version, args.pack_format)
