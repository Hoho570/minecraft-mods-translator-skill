---
name: minecraft-mods-translator
description: 自動化 Minecraft 模組翻譯與資源包製作技能。包含提取、分類、分割大型檔案、翻譯以及合併打包的完整工作流。
---

# Minecraft 模組翻譯自動化 (Auto Translator)

此技能協助使用者自動化翻譯 Minecraft 模組。你將使用 Python 腳本來處理檔案操作（提取、分割、合併、打包），並專注於翻譯內容本身。

## 核心流程指南

整個自動化流程設計為四個階段，請依照順序執行。

### 階段一：初始化與掃描 (Scan & Extract)

此階段負責從 Jar 檔中提取語言文件，並過濾掉已經有繁體中文的模組。

1.  **收集資訊**：
    - 詢問使用者 **模組資料夾路徑** (`mods_dir`)。
    - 詢問使用者 **目標 Minecraft 版本** (`mc_version`)。
    - **確認資源包格式 (`pack_format`)**：
        - 使用 `google_web_search` 查詢該版本的 `pack_format` (例如 "minecraft 1.20.1 pack format")。
        - 告知使用者查詢結果並確認。
        - 參考值：1.21+(46+), 1.20.4(22), 1.20.1(15), 1.12.2(3)。
    - 設定 **工作目錄** (`work_dir`)，預設為 `./translation_workspace`。

2.  **執行掃描與分割**：
    - 執行 Python 腳本：
    ```bash
    python .gemini/skills/minecraft-mods-translater/scripts/manager.py scan --mods_dir "<mods_dir>" --work_dir "<work_dir>"
    ```
    - **背後邏輯**：
        - 腳本會遍歷所有 `.jar` 檔。
        - 略過已有 `zh_tw.json` 或 `zh_TW.lang` 的模組。
        - 提取 `en_us` 檔，若為 `.lang` 格式會轉為 Python Dict 結構。
        - **智能分割**：若檔案超過 1000 行，會自動分割為多個 `en_us_partX.json`，避免 AI 上下文超載。

3.  **讀取任務**：
    - 讀取 `<work_dir>/tasks.json` 以獲取待翻譯清單。

### 階段二：執行翻譯 (Execute Translation)

此階段為核心工作，Agent 需逐一翻譯提取出的 JSON 檔案。

1.  **遍歷任務**：讀取 `tasks.json` 中的每個 `files_to_translate`。
2.  **翻譯內容**：
    - 讀取來源 JSON 檔案。
    - 將 **Value (值)** 翻譯為 **繁體中文 (Traditional Chinese)**。
    - **翻譯規範**：
        - 絕對 **不可** 修改 Key (鍵)。
        - **保留** 格式化代碼：`%s`, `%d`, `%1$s`, `{0}`。
        - **保留** 顏色代碼：`§a`, `§1`, `§r` 等。
        - **保留** 轉義符號：若翻譯中有雙引號，需用 `\"`。
        - 專有名詞參考 Minecraft 官方繁中譯名。
3.  **存檔**：
    - 翻譯後的檔案必須存在與來源檔 **相同的目錄**。
    - 命名規則：
        - 來源 `en_us.json` -> 輸出 `zh_tw.json`
        - 來源 `en_us_part1.json` -> 輸出 `zh_tw_part1.json`

### 階段三：合併與打包 (Merge & Pack)

翻譯完成後，將分割的檔案合併並製作成符合 Minecraft 版本的資源包。

1.  **合併檔案**：
    - 執行指令：
    ```bash
    python .gemini/skills/minecraft-mods-translater/scripts/manager.py merge --work_dir "<work_dir>"
    ```
    - **邏輯**：腳本會尋找所有的 `zh_tw_partX.json` 並合併為完整的 `final_zh_tw.json`。

2.  **製作資源包**：
    - 詢問/確認輸出路徑 (`output_path`)，例如 `Translated_Pack.zip`。
    - 執行指令 (務必包含版本資訊以處理格式轉換)：
    ```bash
    python .gemini/skills/minecraft-mods-translater/scripts/manager.py pack --work_dir "<work_dir>" --output "<output_path>" --mc_version "<mc_version>" --pack_format <pack_format>
    ```
    - **邏輯**：
        - 若 `<mc_version>` <= 1.12.2，自動將 JSON 轉回 `.lang` 格式 (`zh_TW.lang`)。
        - 若為新版，維持 JSON 格式 (`zh_tw.json`)。
        - 生成包含正確 `pack_format` 的 `pack.mcmeta`。
        - 輸出最終 ZIP 檔。

## 腳本功能速查

所有操作皆依賴 `scripts/manager.py`：

| 指令 | 參數 | 功能 |
| :--- | :--- | :--- |
| `scan` | `--mods_dir`, `--work_dir` | 掃描 Jar、提取語言檔、轉 JSON、分割大檔 (>1000行) |
| `merge` | `--work_dir` | 將分割的 `zh_tw_partX.json` 合併為完整檔案 |
| `pack` | `--work_dir`, `--output`, `--mc_version`, `--pack_format` | 根據版本生成 lang/json 資源包並壓縮 |

## 錯誤處理
- 若腳本報錯，請檢查 Python 環境與路徑。
- 翻譯過程中若遇 JSON 格式錯誤，嘗試修復或記錄錯誤並跳過該檔。
