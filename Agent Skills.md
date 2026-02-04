# Agent Skills

Agent Skills 讓您能夠透過專業知識、程序化工作流和特定任務資源來擴展 Gemini CLI。基於 [Agent Skills](https://agentskills.io) 開放標準，一個「技能」是一個包含指令和資產的獨立目錄，並封裝成可被發現的功能。

## 概覽

與提供持續性工作區背景的通用上下文文件 ([`GEMINI.md`](/docs/cli/gemini-md)) 不同，技能代表 **隨選專業知識**。這讓 Gemini 能夠維護龐大的專業功能庫（例如安全稽核、雲端部署或程式碼庫遷移），而不會擁塞模型的即時上下文視窗。

Gemini 會根據您的請求和技能描述自主決定何時使用技能。當識別出相關技能時，模型會使用 `activate_skill` 工具「拉入」完成任務所需的完整指令和資源。

## 關鍵優勢

- **共享專業知識：** 將複雜的工作流（例如特定團隊的 PR 審查流程）封裝到一個任何人都可以使用的資料夾中。
- **可重複的工作流：** 透過提供程序化框架，確保複雜的多步驟任務能一致地執行。
- **資源綑綁：** 將腳本、模板或範例數據與指令放在一起，讓代理擁有完成任務所需的一切。
- **漸進式揭露：** 最初僅載入技能元數據（名稱和描述）。只有當模型明確啟用技能時，才會揭露詳細指令和資源，節省上下文 token。

## 技能探索層級

Gemini CLI 從三個主要位置探索技能：

1.  **工作區技能** (`.gemini/skills/`)：通常提交至版本控制並與團隊共享的工作區特定技能。
2.  **使用者技能** (`~/.gemini/skills/`)：可在您所有工作區使用的個人技能。
3.  **擴充技能**：綑綁在已安裝 [擴充功能](/docs/extensions) 中的技能。

**優先順序：** 如果多個技能共享相同名稱，較高等級的位置會覆蓋較低等級的位置：**工作區 > 使用者 > 擴充功能**。

## 管理技能

### 在互動式會話中

使用 `/skills` 斜線指令來查看和管理可用的專業知識：

- `/skills list` (預設)：顯示所有探索到的技能及其狀態。
- `/skills disable <name>`：防止使用特定技能。
- `/skills enable <name>`：重新啟用已停用的技能。
- `/skills reload`：重新整理從所有層級探索到的技能列表。

_註：`/skills disable` 和 `/skills enable` 預設為 `user` 範圍。使用 `--scope workspace` 來管理工作區特定設定。_

### 從終端機

`gemini skills` 指令提供管理工具：

```bash
# 列出所有探索到的技能
gemini skills list

# 從 Git 儲存庫、本地目錄或壓縮的技能文件 (.skill) 安裝技能
# 預設使用使用者範圍 (~/.gemini/skills)
gemini skills install https://github.com/user/repo.git
gemini skills install /path/to/local/skill
gemini skills install /path/to/local/my-expertise.skill

# 使用 --path 從 monorepo 或子目錄安裝特定技能
gemini skills install https://github.com/my-org/my-skills.git --path skills/frontend-design

# 安裝到工作區範圍 (.gemini/skills)
gemini skills install /path/to/skill --scope workspace

# 依名稱卸載技能
gemini skills uninstall my-expertise --scope workspace

# 啟用技能 (全域)
gemini skills enable my-expertise

# 停用技能。可以使用 --scope 指定 workspace 或 user (預設為 workspace)
gemini skills disable my-expertise --scope workspace
```

## 運作原理 (安全與隱私)

1.  **探索**：在會話開始時，Gemini CLI 掃描探索層級，並將所有已啟用技能的名稱和描述注入系統提示詞中。
2.  **啟用**：當 Gemini 識別出與技能描述匹配的任務時，它會調用 `activate_skill` 工具。
3.  **同意**：您將在 UI 中看到確認提示，詳細說明技能的名稱、用途以及它將獲得存取權限的目錄路徑。
4.  **注入**：經您批准後：
    - `SKILL.md` 的正文和資料夾結構將被添加到對話歷史中。
    - 技能目錄將被添加到代理的允許檔案路徑中，授予其讀取任何綑綁資產的權限。
5.  **執行**：模型在啟用了專業知識的情況下繼續進行。它被指示在合理範圍內優先考慮技能的程序化指引。

## 建立您自己的技能

要建立您自己的技能，請參閱 [建立 Agent Skills](/docs/cli/creating-skills) 指南。