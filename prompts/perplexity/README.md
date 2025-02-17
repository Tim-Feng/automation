# Perplexity Prompts

這個資料夾包含所有用於 Perplexity API 的 prompts。

## 檔案說明
- `content_generation.json`: 用於影片內容生成的 prompt
  - 使用於：`/scripts/perplexity_client.py`
  - 功能：根據影片標題生成相關文章內容

## 注意事項
1. 請確保生成的內容符合預期格式
2. 建議在 prompt 中加入明確的輸出格式要求
3. 如果內容生成不理想，可以調整 prompt 的細節描述
