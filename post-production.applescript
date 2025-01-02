(*
  說明：
  - 需要在 .env 裡配置 REFRESH_TOKEN, CLIENT_ID, CLIENT_SECRET
  - 會搜尋「與字幕檔 (去掉 -zh.srt) 同名」的資料夾 → 再搜尋同名 Google Docs → 把去除時間碼的字幕插入
  - 執行 Python 腳本轉換字幕格式
  - 執行 ffmpeg 硬燒字幕
  - 用 display notification (或 display dialog) 簡單提示「開始轉檔」「轉檔完成」
*)

on writeLog(level, message)
    set logPath to "/Users/Mac/Library/Logs/subtitle_processor.log"
    set dateStr to do shell script "date '+%Y-%m-%d %H:%M:%S'"

    -- 根據等級設定圖示
    set levelIcon to ""
    if level is "INFO" then
        set levelIcon to "ℹ️"
    else if level is "ERROR" then
        set levelIcon to "❌"
    else if level is "SUCCESS" then
        set levelIcon to "✓"
    end if

    do shell script "echo '" & dateStr & " " & levelIcon & " [" & level & "] " & message & "' >> " & quoted form of logPath
end writeLog

on joinList(theList)
    set AppleScript's text item delimiters to ", "
    set theString to theList as string
    set AppleScript's text item delimiters to ""
    return theString
end joinList

on run {input, parameters}
    -- 初始化計數器和列表
    set totalFiles to count of input
    set successCount to 0
    set folderNotFoundCount to 0
    set subtitleConversionFailCount to 0
    set ffmpegFailCount to 0
    set startTime to current date
    
    set folderNotFoundList to {}
    set subtitleConversionFailList to {}
    set ffmpegFailList to {}

    ------------------------------------------------------------
    -- (A) 讀取環境變數 (REFRESH_TOKEN, CLIENT_ID, CLIENT_SECRET)
    ------------------------------------------------------------
    try
        my writeLog("INFO", "讀取環境變數...")
        set envPath to "/Users/Mac/Library/Mobile Documents/com~apple~Automator/Documents/.env"

        set refreshToken to do shell script "grep '^REFRESH_TOKEN=' " & quoted form of envPath & " | cut -d '=' -f 2 | tr -d '\"' | tr -d '\\n' | tr -d '\\r'"
        set clientId to do shell script "grep '^CLIENT_ID=' " & quoted form of envPath & " | cut -d '=' -f 2 | tr -d '\"' | tr -d '\\n' | tr -d '\\r'"
        set clientSecret to do shell script "grep '^CLIENT_SECRET=' " & quoted form of envPath & " | cut -d '=' -f 2 | tr -d '\"' | tr -d '\\n' | tr -d '\\r'"
        
        my writeLog("SUCCESS", "環境變數讀取完成")
    on error errMsg
        my writeLog("ERROR", "環境變數讀取失敗: " & errMsg)
        return
    end try

    my writeLog("INFO", "開始批次處理，共 " & totalFiles & " 個檔案")

    ------------------------------------------------------------
    -- (B) 處理多個字幕檔
    ------------------------------------------------------------
    repeat with currentSubtitlePath in input
        --------------------------------------------------------
        -- (1) 取得字幕路徑、檔名、影片副檔名
        --------------------------------------------------------
        set subtitlePath to POSIX path of currentSubtitlePath
        set subtitleDirectory to do shell script "dirname " & quoted form of subtitlePath
        set trimmedName to do shell script "basename " & quoted form of subtitlePath & " | sed 's/-zh\\.srt$//'"
        set videoExtension to do shell script "ls " & quoted form of subtitleDirectory & "/" & trimmedName & "-1920*1340.* | head -n 1 | awk -F'.' '{print $NF}'"
        set processStartTime to current date

        my writeLog("INFO", "開始處理：" & trimmedName)

        try
            --------------------------------------------------------
            -- (2) 取得 Access Token
            --------------------------------------------------------
            set refreshURL to "https://oauth2.googleapis.com/token"
            set refreshCommand to "curl -s -X POST " & quoted form of refreshURL & " -d client_id=" & clientId & " -d client_secret=" & clientSecret & " -d refresh_token=" & refreshToken & " -d grant_type=refresh_token"
            set refreshResponse to do shell script refreshCommand

            set accessToken to do shell script "echo " & quoted form of refreshResponse & " | python3 -c \"import sys, json; print(json.load(sys.stdin)['access_token'])\""

            --------------------------------------------------------
            -- (3) Google Docs：先找同名資料夾 → 再找該資料夾下同名 Docs → 寫入字幕
            --------------------------------------------------------
            -- 3.1 組出 "mimeType='application/vnd.google-apps.folder' and name='xxx' and trashed=false"
            set searchFolderQuery to "mimeType='application/vnd.google-apps.folder' and name='" & trimmedName & "' and trashed=false"

            -- 以 argv[1] 避免多層引號衝突
            set folderQueryEncoded to do shell script ¬
                "python3 -c \"import sys, urllib.parse; print(urllib.parse.quote(sys.argv[1]))\" " & ¬
                quoted form of searchFolderQuery

            set searchFolderCmd to "curl -s -X GET 'https://www.googleapis.com/drive/v3/files?q=" & folderQueryEncoded & "&supportsAllDrives=true&includeItemsFromAllDrives=true&corpora=allDrives' -H 'Authorization: Bearer " & accessToken & "'"

            set folderResponse to do shell script searchFolderCmd

            -- 從 JSON 解析 folderId
            set folderId to do shell script "echo " & quoted form of folderResponse & " | python3 -c \"import sys, json; arr=json.load(sys.stdin).get('files', []); print(arr[0]['id'] if arr else '')\""

            -- 如果找不到完全匹配，嘗試模糊搜尋
            if folderId is "" then
                -- 使用 contains 來搜尋包含 trimmedName 的資料夾
                set fuzzySearchQuery to "mimeType='application/vnd.google-apps.folder' and name contains '" & trimmedName & "' and trashed=false"
                
                set fuzzyQueryEncoded to do shell script ¬
                    "python3 -c \"import sys, urllib.parse; print(urllib.parse.quote(sys.argv[1]))\" " & ¬
                    quoted form of fuzzySearchQuery
                
                set fuzzySearchCmd to "curl -s -X GET 'https://www.googleapis.com/drive/v3/files?q=" & fuzzyQueryEncoded & "&supportsAllDrives=true&includeItemsFromAllDrives=true&corpora=allDrives' -H 'Authorization: Bearer " & accessToken & "'"
                
                set fuzzyResponse to do shell script fuzzySearchCmd
                
                -- 尋找最匹配的資料夾（名稱以 trimmedName 開頭的）
                set folderId to do shell script "echo " & quoted form of fuzzyResponse & " | python3 -c \"                                
                                import sys, json
                                response = json.load(sys.stdin)
                                files = response.get('files', [])
                                target = '" & trimmedName & "'
                                best_match = None

                                for file in files:
                                    if file['name'].startswith(target + '+') or file['name'] == target:
                                        best_match = file
                                        break

                                print(best_match['id'] if best_match else '')
                                \""
            end if

            if folderId is "" then
                my writeLog("ERROR", "找不到對應資料夾：" & trimmedName)
                set end of folderNotFoundList to trimmedName
                set folderNotFoundCount to folderNotFoundCount + 1
                display notification "找不到對應資料夾：「" & trimmedName & "」" with title "Google Docs"
            else
                -- 3.2 組出 "mimeType='application/vnd.google-apps.document' and 'folderId' in parents and trashed=false"
                set searchDocQuery to "mimeType='application/vnd.google-apps.document' and '" & folderId & "' in parents and trashed=false"

                set docQueryEncoded to do shell script ¬
                    "python3 -c \"import sys, urllib.parse; print(urllib.parse.quote(sys.argv[1]))\" " & ¬
                    quoted form of searchDocQuery

                set searchDocCmd to "curl -s -X GET 'https://www.googleapis.com/drive/v3/files?q=" & docQueryEncoded & "&supportsAllDrives=true&includeItemsFromAllDrives=true&corpora=allDrives' -H 'Authorization: Bearer " & accessToken & "'"

                set docResponse to do shell script searchDocCmd

                -- 解析 docID
                set docID to do shell script "echo " & quoted form of docResponse & " | python3 -c \"import sys, json; arr=json.load(sys.stdin).get('files', []); print(arr[0]['id'] if arr else '')\""

                if docID is "" then
                    my writeLog("ERROR", "找不到同名 Docs：" & trimmedName)
                    display notification "在此資料夾中找不到同名 Docs：「" & trimmedName & "」" with title "Google Docs"
                else
                    -- 讀取字幕：去除行號、時間碼、空行，每行末尾加 \n
                    set subtitleText to do shell script "
                      cat " & quoted form of subtitlePath & " | sed -E 's/\\r//g; /^[0-9]+$/d; / --> /d; /^$/d; s/$/\\\\n/' 
                    "

                    -- 送入 Docs
                    set requestBody to "{\"requests\":[{\"insertText\":{\"location\":{\"index\":1},\"text\":" & quoted form of subtitleText & "}}]}"
                    set docEndpoint to "https://docs.googleapis.com/v1/documents/" & docID & ":batchUpdate"
                    set updateCmd to "curl -s -X POST -H \"Authorization: Bearer " & accessToken & "\" -H \"Content-Type: application/json\" -d " & quoted form of requestBody & " " & quoted form of docEndpoint

                    try
                        do shell script updateCmd
                        my writeLog("SUCCESS", "Google Docs 字幕內容寫入完成")
                    on error errMsg
                        my writeLog("ERROR", "Google Docs 寫入失敗：" & errMsg)
                        display notification "Docs 寫入錯誤：" & errMsg with title "Google Docs"
                    end try
                end if
            end if

            --------------------------------------------------------
            -- (4) 執行 Python 腳本轉換字幕格式
            --------------------------------------------------------
            my writeLog("INFO", "開始執行字幕轉換腳本...")
            try
                set pythonScriptPath to "/Users/Mac/GitHub/automation/srt_to_ass_with_style.py"
                -- 使用完整的 Python 路徑和環境設定
                set pythonCmd to "/Library/Frameworks/Python.framework/Versions/3.11/bin/python3"
                set conversionCmd to "export PATH=/Library/Frameworks/Python.framework/Versions/3.11/bin:/usr/local/bin:$PATH && " & pythonCmd & " " & quoted form of pythonScriptPath & " " & quoted form of subtitlePath
                
                do shell script conversionCmd
                my writeLog("SUCCESS", "字幕格式轉換完成")
                
            on error errMsg
                my writeLog("ERROR", "字幕格式轉換失敗：" & errMsg)
                set end of subtitleConversionFailList to trimmedName
                set subtitleConversionFailCount to subtitleConversionFailCount + 1
            end try

            --------------------------------------------------------
            -- (5) ffmpeg 轉檔
            --------------------------------------------------------
            my writeLog("INFO", "開始 ffmpeg 轉檔...")

            try
                set videoPath to subtitleDirectory & "/" & trimmedName & "-1920*1340." & videoExtension
                set subtitleAssPath to subtitleDirectory & "/" & trimmedName & "-1920*1340-zh.ass"
                set outputPath to subtitleDirectory & "/" & trimmedName & "-1920*1340-zh.mp4"

                set ffmpegCommand to "/usr/local/bin/ffmpeg -i " & quoted form of videoPath & " -vf \"ass=" & quoted form of subtitleAssPath & "\" -c:a copy " & quoted form of outputPath

                display notification "開始轉檔：" & trimmedName with title "FFmpeg"
                do shell script ffmpegCommand
                display notification "轉檔完成：" & trimmedName with title "FFmpeg"
                
            on error errMsg
                my writeLog("ERROR", "ffmpeg 轉檔失敗：" & trimmedName)
                set end of ffmpegFailList to trimmedName
                set ffmpegFailCount to ffmpegFailCount + 1
                display notification "轉檔失敗：" & trimmedName with title "FFmpeg"
            end try

            -- 整個檔案處理完成
            set processEndTime to current date
            set processDuration to (processEndTime - processStartTime)
            my writeLog("SUCCESS", "處理完成：" & trimmedName & "，耗時：" & processDuration & " 秒")
            set successCount to successCount + 1

        on error errMsg
            my writeLog("ERROR", "處理失敗：" & errMsg)
        end try
    end repeat

    -- 輸出統計資訊
    my writeLog("INFO", "==== 批次處理統計 ====")
    my writeLog("INFO", "總處理檔案：" & totalFiles & " 個")
    my writeLog("INFO", "完全成功：" & successCount & " 個")

    if folderNotFoundCount > 0 then
        my writeLog("INFO", "找不到資料夾：" & folderNotFoundCount & " 個（" & joinList(folderNotFoundList) & "）")
    end if

    if subtitleConversionFailCount > 0 then
        my writeLog("INFO", "字幕轉換失敗：" & subtitleConversionFailCount & " 個（" & joinList(subtitleConversionFailList) & "）")
    end if

    if ffmpegFailCount > 0 then
        my writeLog("INFO", "ffmpeg 失敗：" & ffmpegFailCount & " 個（" & joinList(ffmpegFailList) & "）")
    end if

    my writeLog("INFO", "總耗時：" & ((current date) - startTime) & " 秒")

    return input
end run