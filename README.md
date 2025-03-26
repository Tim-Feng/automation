# Automation Scripts

這個倉庫包含各種自動化腳本，用於處理影片製作和發布的工作流程。

## 功能列表

### 1. 工作流程自動化 (AppleScript)
- 目錄：`applescripts/`
- 腳本：
  - `stage1-preparation.applescript`：準備階段自動化
  - `stage2-processing.applescript`：處理階段自動化
  - `stage3-subtitling.applescript`：字幕階段自動化
  - `stage4-templating.applescript`：模板階段自動化
- 說明：這些腳本是為 macOS 環境定制的工作流程自動化，主要用於控制和協調各個應用程式的操作

### 2. 前製作業 (Pre-production)
- 腳本：`scripts/pre_production_pipeline.py`
- 功能：處理影片前製作業，包括下載、剪輯和格式轉換等

### 3. 影片處理
#### 智慧裁切
- 腳本：`scripts/face_center_crop.py`
- 功能：使用人臉檢測進行智慧裁切，適用於垂直影片
- 類別：`SmartImageProcessor`

#### Instagram 相關
- 腳本：
  - `scripts/ig_video_generator.py`：生成 Instagram 格式的影片
  - `scripts/ig_cover_generator.py`：生成 Instagram 封面圖

### 4. 字幕處理
- 腳本：
  - `scripts/subtitle_splitter.py`：分割字幕檔案
  - `scripts/srt_to_ass_with_style.py`：將 SRT 轉換為帶樣式的 ASS
  - `scripts/add_spaces.py`：在中英文之間添加空格
  - `scripts/upload_vtt.py`：上傳 VTT 字幕到 WordPress

### 5. WordPress 內容管理
#### API 客戶端
- 腳本：`scripts/wordpress_api.py`
- 類別：`WordPressAPI`
- 功能：處理 WordPress API 相關操作，包括建立草稿、上傳媒體等

### 6. AI 整合
#### Perplexity API
- 腳本：`scripts/perplexity_client.py`
- 類別：`PerplexityClient`
- 功能：使用 Perplexity API 生成內容

#### 標籤生成
- 腳本：`scripts/tag_suggestion.py`
- 類別：`TagSuggester`
- 功能：使用 OpenAI Assistant 生成標籤

### 7. Google 服務整合
- 腳本：
  - `scripts/google_sheets.py`：Google Sheets 操作
  - `scripts/google_drive.py`：Google Drive 檔案管理

### 8. 工具類
#### 日誌系統
- 腳本：
  - `scripts/logger.py`：工作流程日誌系統
  - `scripts/log_bridge.py`：日誌橋接器

## 開發指南

### 環境設置
1. 安裝依賴：
```bash
pip install -r requirements.txt
```

2. 設置環境變數（在 `config/.env`）：
```
GOOGLE_APPLICATION_CREDENTIALS=path/to/service_account.json
WORDPRESS_API_URL=your_wordpress_url
WORDPRESS_USERNAME=your_username
WORDPRESS_APP_PASSWORD=your_app_password
PERPLEXITY_API_KEY=your_api_key
OPENAI_API_KEY=your_api_key
```

### 代碼改進
- WordPress API 重試機制：參考 MEMORIES 中的實現方案
- 批次更新草稿：參考 MEMORIES 中的完整代碼

## 專案結構
```
automation/
├── applescripts/                # macOS 工作流程自動化
│   ├── stage1-preparation.applescript
│   ├── stage2-processing.applescript
│   ├── stage3-subtitling.applescript
│   └── stage4-templating.applescript
├── config/
│   ├── .env                    # 環境變數
│   └── service_account.json    # Google API 憑證
├── scripts/
│   ├── pre_production_pipeline.py
│   ├── face_center_crop.py
│   ├── ig_video_generator.py
│   ├── ig_cover_generator.py
│   ├── subtitle_splitter.py
│   ├── srt_to_ass_with_style.py
│   ├── add_spaces.py
│   ├── upload_vtt.py
│   ├── wordpress_api.py
│   ├── perplexity_client.py
│   ├── tag_suggestion.py
│   ├── google_sheets.py
│   ├── google_drive.py
│   ├── logger.py
│   └── log_bridge.py
└── README.md
```

## 注意事項
1. 所有敏感資訊都應該存放在 `config/.env` 檔案中
2. 重要的代碼實現都會保存在 MEMORIES 中，方便日後參考和重用
3. 使用 Python 3.8 或更高版本
4. 每個腳本都有獨立的日誌記錄，方便追蹤問題
5. 大部分腳本都支援命令行參數，使用 `-h` 或 `--help` 查看用法
