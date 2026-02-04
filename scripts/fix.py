import os
import json
import argparse
import re
from pathlib import Path

def fix_broken_json(work_dir):
    """
    掃描並修復因未轉義換行符號而損壞的 JSON 檔案。
    邏輯：如果一行中的雙引號數量是奇數（代表字串未閉合），
    則將其與下一行合併，並補上轉義換行符號 \\n。
    """
    work_path = Path(work_dir)
    fixed_count = 0
    
    print(f"正在掃描 {work_dir} 中的損壞 JSON 檔案...")
    
    # 遞迴搜尋所有 json 檔
    for json_file in work_path.rglob("*.json"):
        # 1. 先嘗試讀取，如果是正常的就跳過，節省時間
        try:
            with open(json_file, 'r', encoding='utf-8') as f:
                json.load(f)
            continue
        except json.JSONDecodeError:
            pass # 檔案損壞，進入修復流程
        except Exception as e:
            print(f"無法讀取檔案 {json_file.name}: {e}")
            continue
            
        print(f"正在嘗試修復: {json_file.name}")
        
        try:
            with open(json_file, 'r', encoding='utf-8') as f:
                lines = f.readlines()
            
            fixed_lines = []
            buffer = ""
            in_multiline = False
            
            for line in lines:
                # 移除行尾的換行符號，保留前面的縮排
                stripped_line = line.rstrip('\n') 
                
                # 計算未被轉義的雙引號數量
                # Regex 解釋: 尋找所有前面不是反斜線 \ 的 "
                quotes_count = len(re.findall(r'(?<!\\)"', stripped_line))
                
                if in_multiline:
                    # 我們在一個斷掉的字串中
                    # 用 \\n 連接上一行與這一行 (模擬原本應該有的 \n)
                    #通常斷掉的第二行前面的縮排是不需要的，所以用 .strip() 去除
                    buffer += "\\n" + stripped_line.strip() 
                    
                    # 檢查這一行是否閉合了字串
                    # 邏輯: 之前是奇數(開)，現在又來奇數個引號，加起來就是偶數(閉)
                    if quotes_count % 2 != 0:
                        fixed_lines.append(buffer)
                        buffer = ""
                        in_multiline = False
                    # 如果這行又是偶數個引號，代表還沒閉合 (或者開了又閉了)
                else:
                    # 正常行處理
                    if quotes_count % 2 == 0:
                        # 偶數個引號，代表結構完整（或沒有字串）
                        fixed_lines.append(stripped_line)
                    else:
                        # 奇數個引號，代表字串被換行切斷了
                        buffer = stripped_line
                        in_multiline = True
            
            # 如果跑完最後一行還在 multiline 狀態，把 buffer 加進去（盡力而為）
            if in_multiline:
                fixed_lines.append(buffer)
            
            # 重組內容
            fixed_content = "\n".join(fixed_lines)
            
            # 2. 驗證修復結果
            try:
                json.loads(fixed_content)
                # 成功解析，寫回檔案
                with open(json_file, 'w', encoding='utf-8') as f:
                    f.write(fixed_content)
                print(f" -> 修復成功！")
                fixed_count += 1
            except json.JSONDecodeError as e:
                print(f" -> 修復失敗 (仍有無效語法): {e}")
                # 可以選擇在這裡輸出 debug 檔案方便檢查，例如 json_file.with_suffix('.debug.json')
                
        except Exception as e:
            print(f" -> 修復過程中發生錯誤: {e}")
            
    print(f"-" * 30)
    print(f"掃描完成。共修復了 {fixed_count} 個檔案。")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Fix broken JSON files (newline issues)")
    parser.add_argument("--work_dir", required=True, help="Path to the workspace directory containing extracted/translated files")
    
    args = parser.parse_args()
    
    if not os.path.exists(args.work_dir):
        print(f"錯誤: 找不到工作目錄 {args.work_dir}")
        exit(1)
        
    fix_broken_json(args.work_dir)