import os
import json
import argparse
import re
import sys
from pathlib import Path

def fix_broken_json(work_dir):
    """
    Scan and fix JSON files broken by unescaped newlines.
    Logic: if a line has an odd number of unescaped double quotes (string not closed),
    merge it with the next line and insert an escaped newline \\n.
    """
    work_path = Path(work_dir)
    fixed_count = 0
    
    print(f"Scanning for broken JSON files in {work_dir}...")
    
    for json_file in work_path.rglob("*.json"):
        # Skip non-translation files
        filename = json_file.name.lower()
        if filename == "tasks.json":
            continue
        if filename.startswith("en_us"):
            continue
        # Only fix zh_tw related files
        if not (filename.startswith("zh_tw") or filename == "final_zh_tw.json"):
            continue

        # 1. Try reading first, skip if valid JSON
        try:
            with open(json_file, 'r', encoding='utf-8') as f:
                json.load(f)
            continue
        except json.JSONDecodeError:
            pass
        except Exception as e:
            print(f"Cannot read file {json_file.name}: {e}")
            continue
            
        print(f"Attempting to fix: {json_file.name}")
        
        try:
            with open(json_file, 'r', encoding='utf-8') as f:
                lines = f.readlines()
            
            fixed_lines = []
            buffer = ""
            in_multiline = False
            
            for line in lines:
                stripped_line = line.rstrip('\n') 
                
                # Count unescaped double quotes
                quotes_count = len(re.findall(r'(?<!\\)"', stripped_line))
                
                if in_multiline:
                    buffer += "\\n" + stripped_line.strip() 
                    
                    if quotes_count % 2 != 0:
                        fixed_lines.append(buffer)
                        buffer = ""
                        in_multiline = False
                else:
                    if quotes_count % 2 == 0:
                        fixed_lines.append(stripped_line)
                    else:
                        buffer = stripped_line
                        in_multiline = True
            
            if in_multiline:
                fixed_lines.append(buffer)
            
            fixed_content = "\n".join(fixed_lines)
            
            # 2. Validate fix result
            try:
                json.loads(fixed_content)
                with open(json_file, 'w', encoding='utf-8') as f:
                    f.write(fixed_content)
                print(f" -> Fixed successfully!")
                fixed_count += 1
            except json.JSONDecodeError as e:
                print(f" -> Fix failed (still invalid): {e}")
                
        except Exception as e:
            print(f" -> Error during fix: {e}")
            
    print("-" * 30)
    print(f"Scan complete. Fixed {fixed_count} file(s).")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Fix broken JSON files (newline issues)")
    parser.add_argument("--work_dir", required=True, help="Path to the workspace directory")
    
    args = parser.parse_args()
    
    if not os.path.exists(args.work_dir):
        print(f"Error: work directory not found: {args.work_dir}")
        exit(1)
        
    fix_broken_json(args.work_dir)