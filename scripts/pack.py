import os
import json
import shutil
import argparse
from pathlib import Path

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
        print("tasks.json not found in work directory.")
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
    parser = argparse.ArgumentParser(description="Create translations resource pack")
    parser.add_argument("--work_dir", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--mc_version", required=True, help="Target Minecraft Version (e.g. 1.12.2, 1.20.1)")
    parser.add_argument("--pack_format", required=True, type=int, help="pack_format number")
    args = parser.parse_args()
    
    create_resource_pack(args.work_dir, args.output, args.mc_version, args.pack_format)
