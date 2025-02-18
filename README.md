# Automation Scripts

這個倉庫包含各種自動化腳本，用於處理日常工作流程。

## 功能列表

### 1. WordPress 內容管理

#### 批次更新草稿 (Archived)
- 腳本：`scripts/batch_update_drafts.py`
- 功能：從 Google Sheets 讀取影片資訊，使用 AI 生成內容和標籤，並更新 WordPress 草稿
- 狀態：已存檔，代碼可在 MEMORIES 中找到
- 使用場景：當需要批次處理多個 WordPress 草稿時
- 依賴：
  - Google Sheets API
  - Perplexity API
  - OpenAI API
  - WordPress API

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

## 注意事項
1. 所有敏感資訊都應該存放在 `config/.env` 檔案中
2. 重要的代碼實現都會保存在 MEMORIES 中，方便日後參考和重用
3. 使用 Python 3.8 或更高版本
