import os
import json
import zipfile
import argparse
import math
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
                    # Find en_us first (source of truth)
                    en_us_path = None
                    is_en_lang = False
                    for f in assets:
                         if f.lower().endswith(f'assets/{mod_id}/lang/en_us.json'):
                             en_us_path = f
                             break
                         elif f.endswith(f'assets/{mod_id}/lang/en_us.lang'):
                             en_us_path = f
                             is_en_lang = True
                             break
                    
                    if not en_us_path:
                        continue

                    # Read and parse en_us
                    with z.open(en_us_path) as source:
                        en_content = source.read().decode('utf-8', errors='ignore')
                    
                    if is_en_lang:
                        en_data = parse_lang_file(en_content)
                    else:
                        try:
                            en_data = json.loads(en_content)
                        except json.JSONDecodeError:
                            print(f"Error decoding JSON for {mod_id} (en_us)")
                            continue

                    # Check for existing zh_tw and verify completeness
                    zh_tw_path = None
                    is_zh_lang = False
                    for f in assets:
                        if f.lower().endswith(f'assets/{mod_id}/lang/zh_tw.json'):
                            zh_tw_path = f
                            break
                        elif f.endswith(f'assets/{mod_id}/lang/zh_tw.lang'): # Check zh_TW.lang too? case sensitive in zip?
                            zh_tw_path = f
                            is_zh_lang = True
                            break
                        elif f.endswith(f'assets/{mod_id}/lang/zh_tw.lang'): # strictly zh_TW.lang
                             zh_tw_path = f
                             is_zh_lang = True
                             break
                    
                    # Correction: search properly for zh_tw variants
                    if not zh_tw_path:
                        # Try case insensitive search for zh_TW.lang or zh_tw.lang
                        for f in assets:
                             if f.lower().endswith(f'assets/{mod_id}/lang/zh_tw.lang'):
                                 zh_tw_path = f
                                 is_zh_lang = True
                                 break

                    if zh_tw_path:
                        try:
                            with z.open(zh_tw_path) as zh_source:
                                zh_content = zh_source.read().decode('utf-8', errors='ignore')
                            
                            if is_zh_lang:
                                zh_data = parse_lang_file(zh_content)
                            else:
                                zh_data = json.loads(zh_content)
                            
                            # Completeness Check
                            en_keys = set(en_data.keys())
                            zh_keys = set(zh_data.keys())
                            
                            # 1. Missing Keys
                            missing_keys = en_keys - zh_keys
                            
                            # 2. Identical Values (Heuristic)
                            # Ignore empty values or pure numbers/symbols if possible, but keep simple for now
                            identical_count = 0
                            for k in (en_keys & zh_keys):
                                if en_data[k] == zh_data[k] and en_data[k].strip() != "":
                                    # Optional: Filter out pure numbers or short symbols?
                                    # User requested "Verify value is identical", implies strict check.
                                    identical_count += 1
                            
                            if len(missing_keys) == 0 and identical_count == 0:
                                print(f"Skipping {mod_id} (Complete Translation Found)")
                                continue
                            else:
                                print(f"Extracting {mod_id}: Found {len(missing_keys)} missing keys, {identical_count} identical values.")
                        
                        except Exception as e:
                            print(f"Error checking zh_tw for {mod_id}: {e}. Treating as untranslated.")
                            # Fallthrough to extract en_us

                    # Save standard JSON (en_us)
                    mod_out_dir = extracted_path / mod_id
                    mod_out_dir.mkdir(parents=True, exist_ok=True)
                    json_path = mod_out_dir / "en_us.json"
                    
                    with open(json_path, 'w', encoding='utf-8') as f:
                        json.dump(en_data, f, indent=2, ensure_ascii=False)

                    # Classify
                    line_count = len(en_data) # Using key count as "lines" approximation
                    
                    task_info = {
                        "mod_id": mod_id,
                        "original_file": str(json_path),
                        "key_count": line_count,
                        "split_needed": line_count > 1000
                    }

                    if line_count > 1000:
                        split_files = split_json(en_data, mod_out_dir, line_count)
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

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Scan and classify Minecraft mod language files")
    parser.add_argument("--mods_dir", required=True)
    parser.add_argument("--work_dir", required=True)
    args = parser.parse_args()
    
    extract_and_classify(args.mods_dir, args.work_dir)
