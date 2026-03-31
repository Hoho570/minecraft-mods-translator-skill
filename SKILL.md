---
name: minecraft-mods-translator
description: 自動化 Minecraft 模組翻譯與資源包製作技能。使用「總指揮 + 翻譯員」架構，透過調度器啟動獨立 Gemini CLI 子程序進行翻譯，解決大量模組時的上下文限制問題。
---

# Minecraft 模組翻譯自動化 (Auto Translator)

此技能協助使用者自動化翻譯 Minecraft 模組。採用「**總指揮 + 翻譯員**」架構：你（Agent）作為總指揮執行 Python 腳本，腳本會自動啟動獨立的 Gemini CLI 子程序作為翻譯員，每個翻譯員只負責翻譯一個檔案。

## 架構說明

```
🎖️ 總指揮（你/Agent）
  ├── 執行 scan.py    → 掃描模組、提取語言檔、產生 tasks.json
  ├── 執行 dispatch.py → 自動啟動翻譯員子程序、驗證結果、更新進度
  │    ├── 🔤 翻譯員 #1: Python 讀取 en_us → stdin 傳給 gemini → stdout 取回翻譯
  │    ├── 🔤 翻譯員 #2: Python 讀取 en_us → stdin 傳給 gemini → stdout 取回翻譯
  │    └── ...
  ├── 執行 progress.py → 查看翻譯進度
  ├── 執行 fix.py      → 修復損壞的 JSON
  ├── 執行 merge.py    → 合併翻譯檔案
  └── 執行 pack.py     → 打包為資源包
```

**優勢**：每個翻譯員都是全新的上下文，不會因為模組數量多而品質下降。子程序不碰檔案系統（不需 Docker sandbox），Python 負責所有 I/O。支援斷點續傳和失敗重試。

---

## 核心流程指南

整個流程設計為三個主要階段，請依照順序執行。

---

## 階段一：初始化與掃描 (Scan & Extract)

### 1. 收集資訊
*   **模組資料夾路徑 (`mods_dir`)**：詢問使用者。
*   **目標 Minecraft 版本 (`mc_version`)**：詢問使用者。
*   **確認資源包格式 (`pack_format`)**：
    *   使用 `google_web_search` 查詢該版本的 `pack_format`。
    *   *參考值：1.21+(46+), 1.20.4(22), 1.20.1(15), 1.12.2(3)。*
*   **工作目錄 (`work_dir`)**：預設為 `./translation_workspace`。

### 2. 執行掃描
```bash
python .gemini/skills/minecraft-mods-translater/scripts/scan.py --mods_dir "<mods_dir>" --work_dir "<work_dir>"
```

**背後邏輯：**
*   遍歷 Jar 檔，提取 `en_us` 語言檔。
*   過濾已被完整翻譯的模組。
*   若檔案超過 500 key，自動分割為多個 `en_us_partX.json`。
*   產生 `tasks.json`，每個任務包含 `"status": "pending"`。

---

## 階段二：調度翻譯 (Dispatch Translation)

此階段使用 `dispatch.py` 自動化翻譯流程。**你不需要手動翻譯任何檔案**。

### 1. 執行調度器
```bash
python .gemini/skills/minecraft-mods-translater/scripts/dispatch.py --work_dir "<work_dir>"
```

**可用參數：**
| 參數 | 說明 | 預設 |
| :--- | :--- | :--- |
| `--work_dir` | 工作目錄 | 必填 |
| `--max_workers` | 最大並行翻譯員數 | `1` |
| `--batch_size` | 每次翻譯幾個模組 (0=全部) | `0` |
| `--timeout` | 每個翻譯員的超時秒數 | `300` |
| `--retry_failed` | 重試失敗的任務 | 否 |

**背後邏輯（stdin/stdout 模式）：**
*   讀取 `tasks.json` 中 `status == "pending"` 的任務。
*   **Python 讀取 `en_us.json` 內容** → 透過 stdin 傳給 `gemini -p "翻譯..."` 子程序。
*   **子程序只輸出翻譯結果到 stdout**，不碰檔案系統（不需 `--approval-mode=yolo`，不觸發 Docker sandbox）。
*   **Python 從 stdout 提取 JSON**（支援直接 JSON、` ```json ` 代碼區塊、`{...}` 提取）→ 驗證完整性（key 比對）→ 寫入 `zh_tw.json`。
*   每個任務完成後立即更新 `tasks.json` 的 `status`。

### 2. 查看翻譯進度
```bash
python .gemini/skills/minecraft-mods-translater/scripts/progress.py --work_dir "<work_dir>"
```

### 3. 重試失敗的任務
```bash
python .gemini/skills/minecraft-mods-translater/scripts/dispatch.py --work_dir "<work_dir>" --retry_failed
```

### 4. 修復格式問題（可選）
若部分檔案有 JSON 格式問題：
```bash
python .gemini/skills/minecraft-mods-translater/scripts/fix.py --work_dir "<work_dir>"
```

---

## 階段三：合併與打包 (Merge & Pack)

### 1. 先確認翻譯進度
```bash
python .gemini/skills/minecraft-mods-translater/scripts/progress.py --work_dir "<work_dir>"
```
*   確認大部分模組已完成翻譯。
*   未完成的模組不會被合併與打包（安全跳過）。

### 2. 合併檔案
```bash
python .gemini/skills/minecraft-mods-translater/scripts/merge.py --work_dir "<work_dir>"
```
**邏輯**：合併 `zh_tw_partX.json` 為 `final_zh_tw.json`，並做完整性校驗。

### 3. 製作資源包
```bash
python .gemini/skills/minecraft-mods-translater/scripts/pack.py --work_dir "<work_dir>" --output "<output_path>" --mc_version "<mc_version>" --pack_format <pack_format>
```

---

## 腳本功能速查表

| 階段 | 腳本 | 主要參數 | 功能描述 |
| :--- | :--- | :--- | :--- |
| **掃描** | `scan.py` | `--mods_dir`, `--work_dir` | 掃描 Jar、提取語言檔、大檔分割、產生 tasks.json。 |
| **調度** | `dispatch.py` | `--work_dir`, `--max_workers`, `--batch_size`, `--timeout`, `--retry_failed` | 啟動翻譯員子程序、驗證結果、更新進度。 |
| **進度** | `progress.py` | `--work_dir` | 查詢翻譯進度、同步 tasks.json 狀態。 |
| **修復** | `fix.py` | `--work_dir` | 修復損壞的 JSON（處理未轉義的換行與字串斷行）。 |
| **合併** | `merge.py` | `--work_dir` | 合併翻譯分段、Key/Value 完整性校驗。 |
| **打包** | `pack.py` | `--work_dir`, `--output`, `--mc_version`, `--pack_format` | 格式轉換、生成 `pack.mcmeta`、壓縮打包。 |

---

## tasks.json 結構

```json
[
  {
    "mod_id": "create",
    "original_file": "path/to/en_us.json",
    "key_count": 500,
    "split_needed": false,
    "status": "pending",
    "files_to_translate": ["path/to/en_us.json"]
  }
]
```

**status 值：** `pending` → `completed` / `failed` / `partial`

---

## 錯誤處理
1.  若 `dispatch.py` 報告失敗的模組，使用 `--retry_failed` 重試。
2.  若多次重試仍失敗，執行 `fix.py` 修復格式後再重試。
3.  若腳本報錯，請優先檢查 Python 環境與 Gemini CLI 是否正確安裝。