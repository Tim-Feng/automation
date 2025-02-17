# Prompts

這個資料夾包含所有用於 AI 服務的 prompts。

## 目錄結構
- `/openai`: OpenAI API 相關的 prompts，主要用於標籤建議
- `/perplexity`: Perplexity API 相關的 prompts，主要用於內容生成

## 使用說明
1. 所有 prompts 都使用 JSON 格式儲存
2. 每個 prompt 檔案都應包含：
   - `version`: prompt 版本
   - `description`: prompt 用途說明
   - `template`: prompt 主體內容
   - `parameters`: 可替換的參數說明（如果有的話）

## 維護指南
1. 修改 prompt 時請更新版本號
2. 建議在修改前先測試新的 prompt 效果
3. 重要的更改請在 commit message 中說明原因和預期效果
