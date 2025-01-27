(*
  說明：
  - 需要在 .env 裡配置 REFRESH_TOKEN, CLIENT_ID, CLIENT_SECRET
  - 會搜尋「與字幕檔 (去掉 -zh.srt) 同名」的資料夾 → 再搜尋同名 Google Docs → 把去除時間碼的字幕插入
  - 執行 Python 腳本轉換字幕格式
  - 執行 ffmpeg 硬燒字幕
  - 用 display notification (或 display dialog) 簡單提示「開始轉檔」「轉檔完成」
*)

on writeLog(level, message)
    try
        -- 主要日誌位置
        set mainLogPath to "/Users/Mac/Library/Logs/subtitle_processor.log"
        
        -- 確保主要日誌目錄存在
        do shell script "mkdir -p /Users/Mac/Library/Logs"
        
        -- 創建符號連結（如果不存在）
        set symLinkPath to "/Users/Mac/GitHub/automation/logs/subtitle_processor.log"
        do shell script "mkdir -p /Users/Mac/GitHub/automation/logs"
        do shell script "[ ! -L " & quoted form of symLinkPath & " ] && ln -s " & quoted form of mainLogPath & " " & quoted form of symLinkPath & " || true"
        
        -- 取得時間
        set dateStr to do shell script "date '+%Y-%m-%d %H:%M:%S'"
        
        -- 寫入日誌
        set logText to dateStr & " [" & level & "] " & message & "\n"
        do shell script "/bin/echo '" & logText & "' >> " & quoted form of mainLogPath
        
        -- 如果是錯誤，顯示通知
        if level is "ERROR" then
            display notification message with title "錯誤"
        end if
        
        return true
    on error errMsg
        display notification errMsg with title "日誌錯誤"
        return false
    end try
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

    -- 設定目標資料夾路徑
    set baseTargetPath to "/Users/Mac/Desktop/Video Production/2. To be Translated"

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
        set subtitleID to do shell script "basename " & quoted form of subtitlePath & " | sed 's/\\.srt$//'"
        set processStartTime to current date

        my writeLog("INFO", "開始處理：" & subtitleID)
        -- 檢查目標資料夾是否存在
        set targetFolderPath to baseTargetPath & "/" & subtitleID
        
        if (do shell script "[ -d " & quoted form of targetFolderPath & " ] && echo 'yes' || echo 'no'") is "yes" then
            my writeLog("INFO", "找到對應資料夾：" & subtitleID)
            
            -- 複製並重命名字幕檔
            set shouldContinue to true
            try
                set newSrtPath to targetFolderPath & "/" & subtitleID & "-zh.srt"
                
                -- 執行字幕格式化
                set formatCmd to "/Library/Frameworks/Python.framework/Versions/3.11/bin/python3 /Users/Mac/GitHub/automation/scripts/add_spaces.py " & quoted form of subtitlePath & " " & quoted form of newSrtPath
                do shell script formatCmd
                
                my writeLog("SUCCESS", "成功複製並重命名字幕檔：" & subtitleID)
                display notification "檔案複製成功：" & subtitleID with title "字幕處理"
    
                # 生成 VTT 格式
                if subtitleID contains "+" then
                    set videoIDs to do shell script "echo " & quoted form of subtitleID & " | tr '+' ' '"
                    my writeLog("INFO", "處理多影片字幕：" & videoIDs)
                else if subtitleID contains "-" then
                    set dashPos to offset of "-" in subtitleID
                    set startID to text 1 thru (dashPos - 1) of subtitleID
                    set endID to text (dashPos + 1) through -1 of subtitleID
                    
                    try
                        set startIDNum to startID as number
                        set endIDNum to endID as number
                    on error
                        my writeLog("ERROR", "無效的影片 ID 範圍：" & subtitleID)
                        return
                    end try
                    
                    set idList to ""
                    repeat with i from startID to endID
                        set idList to idList & " " & i
                    end repeat
                    set videoIDs to text 2 thru -1 of idList
                    my writeLog("INFO", "處理範圍字幕：" & videoIDs)
                else
                    set videoIDs to subtitleID
                end if

                set getDurationsCmd to "/Library/Frameworks/Python.framework/Versions/3.11/bin/python3 /Users/Mac/GitHub/automation/scripts/google_sheets.py --get-durations " & videoIDs
                try 
                    my writeLog("INFO", "開始獲取影片時長...")
                    set durations to do shell script getDurationsCmd
                    my writeLog("INFO", "獲取時長成功：" & durations)
                    
                    set splitCmd to "/Library/Frameworks/Python.framework/Versions/3.11/bin/python3 /Users/Mac/GitHub/automation/scripts/subtitle_splitter.py " & quoted form of newSrtPath & " " & quoted form of targetFolderPath & " " & durations
                    my writeLog("INFO", "執行字幕拆分指令...")
                    do shell script splitCmd
                    my writeLog("SUCCESS", "VTT 格式轉換完成：" & subtitleID)
                on error errMsg
                    my writeLog("ERROR", "VTT 格式轉換失敗：" & errMsg)
                end try

            on error errMsg
                my writeLog("ERROR", "複製檔案失敗：" & errMsg)
                display notification "複製失敗：" & subtitleID with title "字幕處理"
                set end of subtitleConversionFailList to subtitleID
                set subtitleConversionFailCount to subtitleConversionFailCount + 1
                set shouldContinue to false
            end try        
            --------------------------------------------------------
            -- (2) 執行 Python 腳本轉換字幕格式
            --------------------------------------------------------
            try
                my writeLog("INFO", "開始執行字幕轉換腳本...")
                set pythonScriptPath to "/Users/Mac/GitHub/automation/scripts/srt_to_ass_with_style.py"
                -- 使用完整的 Python 路徑和環境設定
                set pythonCmd to "/Library/Frameworks/Python.framework/Versions/3.11/bin/python3"
                set conversionCmd to "export PATH=/Library/Frameworks/Python.framework/Versions/3.11/bin:/usr/local/bin:$PATH && " & pythonCmd & " " & quoted form of pythonScriptPath & " " & quoted form of newSrtPath
                
                do shell script conversionCmd
                my writeLog("SUCCESS", "字幕格式轉換完成")
            on error errMsg
                my writeLog("ERROR", "字幕格式轉換失敗：" & errMsg)
                set end of subtitleConversionFailList to subtitleID
                set subtitleConversionFailCount to subtitleConversionFailCount + 1
            end try

            --------------------------------------------------------
            -- (3) ffmpeg 轉檔
            --------------------------------------------------------
            my writeLog("INFO", "開始 ffmpeg 轉檔...")
            try
                -- 使用 find 命令搜尋影片檔案
                set videoSearchPattern to targetFolderPath & "/" & subtitleID & "-1920*1340"
                my writeLog("INFO", "搜尋影片檔案：" & videoSearchPattern & ".*")
                
                -- 使用 find 命令找到實際的影片檔案
                set findCommand to "find " & quoted form of targetFolderPath & " -maxdepth 1 -type f -name '" & subtitleID & "-1920\\*1340.*' | head -n 1"
                my writeLog("INFO", "執行搜尋命令：" & findCommand)
                
                set foundVideo to do shell script findCommand
                
                if foundVideo is "" then
                    error "找不到符合格式的影片檔案"
                end if
                
                my writeLog("INFO", "找到影片檔案：" & foundVideo)
                
                -- 設定字幕和輸出路徑
                set subtitleAssPath to targetFolderPath & "/" & subtitleID & "-1920*1340-zh.ass"
                
                -- 檢查字幕檔案
                my writeLog("INFO", "檢查字幕檔案：" & subtitleAssPath)
                if not (do shell script "[ -f " & quoted form of subtitleAssPath & " ] && echo 'yes' || echo 'no'") is "yes" then
                    error "找不到字幕檔案：" & subtitleAssPath
                end if
                
                -- 設定輸出路徑
                set outputPath to targetFolderPath & "/" & subtitleID & "-1920*1340-zh.mp4"
                
                -- 構建 FFmpeg 命令
                set ffmpegCommand to "/usr/local/bin/ffmpeg -y -i " & quoted form of foundVideo & " -vf \"ass=" & quoted form of subtitleAssPath & "\" -c:a copy " & quoted form of outputPath & " 2>&1"
                my writeLog("INFO", "執行命令：" & ffmpegCommand)
                
                -- 執行轉檔
                display notification "開始轉檔：" & subtitleID with title "FFmpeg"
                set ffmpegOutput to do shell script ffmpegCommand
                
                -- 檢查輸出檔案
                if (do shell script "[ -f " & quoted form of outputPath & " ] && echo 'yes' || echo 'no'") is "yes" then
                    my writeLog("SUCCESS", "轉檔完成：" & outputPath)
                    display notification "轉檔完成：" & subtitleID with title "FFmpeg"
                else
                    error "輸出檔案未生成"
                end if
                
            on error errMsg
                my writeLog("ERROR", "ffmpeg 轉檔失敗：" & errMsg)
                set end of ffmpegFailList to subtitleID
                set ffmpegFailCount to ffmpegFailCount + 1
                display notification "轉檔失敗：" & subtitleID with title "FFmpeg"
                return
            end try

            -- 轉檔成功後，開始處理 Google Drive 相關操作
            my writeLog("INFO", "開始處理 Google Drive 上傳...")
            
            --------------------------------------------------------
            -- (4) 處理 Google Drive 相關操作
            --------------------------------------------------------
            -- 4.1 取得 Access Token
            set refreshURL to "https://oauth2.googleapis.com/token"
            set refreshCommand to "curl -s -X POST " & quoted form of refreshURL & " -d client_id=" & clientId & " -d client_secret=" & clientSecret & " -d refresh_token=" & refreshToken & " -d grant_type=refresh_token"
            set refreshResponse to do shell script refreshCommand
            set accessToken to do shell script "echo " & quoted form of refreshResponse & " | python3 -c \"import sys, json; print(json.load(sys.stdin)['access_token'])\""

            -- 4.2 搜尋同名資料夾
            set searchFolderQuery to "mimeType='application/vnd.google-apps.folder' and name='" & subtitleID & "' and trashed=false"
            set folderQueryEncoded to do shell script "python3 -c 'import sys,urllib.parse; print(urllib.parse.quote(sys.argv[1]))' " & quoted form of searchFolderQuery
            set searchFolderCmd to "curl -s -X GET 'https://www.googleapis.com/drive/v3/files?q=" & folderQueryEncoded & ¬
                "&supportsAllDrives=true&includeItemsFromAllDrives=true&corpora=allDrives' " & ¬
                "-H 'Authorization: Bearer " & accessToken & "'"
            set folderResponse to do shell script searchFolderCmd
            set folderId to do shell script "echo " & quoted form of folderResponse & " | python3 -c \"import sys, json; arr=json.load(sys.stdin).get('files', []); print(arr[0]['id'] if arr else '')\""

            -- 4.3 如果找不到完全匹配，嘗試模糊搜尋
            if folderId is "" then
                my writeLog("INFO", "開始進行模糊搜尋：" & subtitleID)
                
                set fuzzySearchQuery to "mimeType='application/vnd.google-apps.folder' and name contains '" & subtitleID & "' and trashed=false"
                set fuzzyQueryEncoded to do shell script "python3 -c 'import sys,urllib.parse; print(urllib.parse.quote(sys.argv[1]))' " & quoted form of fuzzySearchQuery
                
                set fuzzySearchCmd to "curl -s -X GET 'https://www.googleapis.com/drive/v3/files?q=" & fuzzyQueryEncoded & ¬
                    "&supportsAllDrives=true&includeItemsFromAllDrives=true&corpora=allDrives' " & ¬
                    "-H 'Authorization: Bearer " & accessToken & "'"
                
                set fuzzyResponse to do shell script fuzzySearchCmd
                set folderId to do shell script "echo " & quoted form of folderResponse & " | python3 -c 'import sys,json; arr=json.load(sys.stdin).get(\"files\",[]); print(arr[0][\"id\"] if arr else \"\")'"
            end if

            -- 如果找不到資料夾，記錄錯誤
            if folderId is "" then
                my writeLog("ERROR", "找不到對應資料夾：" & subtitleID)
                set end of folderNotFoundList to subtitleID
                set folderNotFoundCount to folderNotFoundCount + 1
                display notification "找不到對應資料夾：「" & subtitleID & "」" with title "Google Drive"
            else
                my writeLog("SUCCESS", "找到對應資料夾，ID: " & folderId)
                
                -- 4.4 搜尋同名 Google Docs
                set searchDocQuery to "mimeType='application/vnd.google-apps.document' and '" & folderId & "' in parents and trashed=false"
                set docQueryEncoded to do shell script ¬
                    "python3 -c \"import sys, urllib.parse; print(urllib.parse.quote(sys.argv[1]))\" " & ¬
                    quoted form of searchDocQuery
                
                set searchDocCmd to "curl -s -X GET 'https://www.googleapis.com/drive/v3/files?q=" & docQueryEncoded & ¬
                    "&supportsAllDrives=true&includeItemsFromAllDrives=true&corpora=allDrives' " & ¬
                    "-H 'Authorization: Bearer " & accessToken & "'"
                
                set docResponse to do shell script searchDocCmd
                set docID to do shell script "echo " & quoted form of docResponse & " | python3 -c 'import sys,json; arr=json.load(sys.stdin).get(\"files\",[]); print(arr[0][\"id\"] if arr else \"\")'"

                -- 4.5 搜尋「嵌入影片」資料夾
                my writeLog("INFO", "搜尋「嵌入影片」資料夾...")

                set searchEmbedFolderQuery to "mimeType='application/vnd.google-apps.folder' and name='嵌入影片' and '" & folderId & "' in parents and trashed=false"
                set embedFolderQueryEncoded to do shell script ¬
                    "python3 -c \"import sys, urllib.parse; print(urllib.parse.quote(sys.argv[1]))\" " & ¬
                    quoted form of searchEmbedFolderQuery

                set searchEmbedFolderCmd to "curl -s -X GET 'https://www.googleapis.com/drive/v3/files?q=" & embedFolderQueryEncoded & ¬
                    "&supportsAllDrives=true&includeItemsFromAllDrives=true&corpora=allDrives' " & ¬
                    "-H 'Authorization: Bearer " & accessToken & "'"

                set embedFolderResponse to do shell script searchEmbedFolderCmd
                set embedFolderId to do shell script "echo " & quoted form of embedFolderResponse & ¬
                    " | python3 -c \"import sys, json; arr=json.load(sys.stdin).get('files', []); " & ¬
                    "print(arr[0]['id'] if arr else '')\""

                -- 4.6 上傳轉檔完成的影片到「嵌入影片」資料夾
                my writeLog("INFO", "開始上傳影片檔案...")

                -- 先建立檔案 metadata
                set createFileBody to "{\"name\": \"" & subtitleID & "-1920x1340-zh.mp4\", \"parents\": [\"" & embedFolderId & "\"]}"

                -- 建立上傳 session
                set sessionCmd to "curl -s -X POST 'https://www.googleapis.com/upload/drive/v3/files?uploadType=resumable&supportsAllDrives=true' " & ¬
                    "-H 'Authorization: Bearer " & accessToken & "' " & ¬
                    "-H 'Content-Type: application/json' " & ¬
                    "-H 'X-Upload-Content-Type: video/mp4' " & ¬
                    "--data '" & createFileBody & "' " & ¬
                    "-D - " & ¬
                    "| grep -i 'Location: ' | cut -d' ' -f2- | tr -d '\\r'"

                my writeLog("INFO", "建立上傳 session...")
                set uploadUrl to do shell script sessionCmd
                my writeLog("INFO", "獲得上傳 URL: " & uploadUrl)

                if uploadUrl is not "" then
                    -- 上傳檔案內容
                    set uploadCmd to "curl -s -X PUT '" & uploadUrl & "' " & ¬
                        "-H 'Authorization: Bearer " & accessToken & "' " & ¬
                        "-H 'Content-Type: video/mp4' " & ¬
                        "--data-binary '@" & outputPath & "'"

                    try
                        set uploadResponse to do shell script uploadCmd
                        my writeLog("SUCCESS", "影片檔案上傳完成")
                        display notification "檔案上傳成功：" & subtitleID with title "Google Drive"
                    on error errMsg
                        my writeLog("ERROR", "檔案上傳失敗：" & errMsg)
                        display notification "檔案上傳失敗：" & subtitleID with title "Google Drive"
                    end try
                else
                    my writeLog("ERROR", "無法建立上傳 session")
                    display notification "無法建立上傳 session：" & subtitleID with title "Google Drive"
                end if

                -- 4.7 如果找到了對應的 Google Docs，更新其內容
                if docID is not "" then
                    my writeLog("INFO", "開始更新 Google Docs 內容...")
                    
                    -- 使用較簡單的 Python 腳本，注意這裡所有代碼都要靠左對齊
                    set pythonScript to "'import sys,json; f=open(sys.argv[1],\"r\",encoding=\"utf-8-sig\"); lines=[line.strip() for line in f.readlines()]; filtered=[line for line in lines if line and not line.isdigit() and \" --> \" not in line]; print(json.dumps(\"\\n\".join(filtered)))'"
                    
                    set subtitleText to do shell script "/usr/local/bin/python3 -c " & pythonScript & " " & quoted form of subtitlePath
                    
                    -- 送入 Docs
                    set requestBody to "{\"requests\":[{\"insertText\":{\"location\":{\"index\":1},\"text\":" & subtitleText & "}}]}"
                    set docEndpoint to "https://docs.googleapis.com/v1/documents/" & docID & ":batchUpdate"
                    set updateCmd to "curl -s -X POST " & ¬
                        "-H \"Authorization: Bearer " & accessToken & "\" " & ¬
                        "-H \"Content-Type: application/json\" " & ¬
                        "--data " & quoted form of requestBody & " " & ¬
                        quoted form of docEndpoint
                        
                    try
                        set updateResponse to do shell script updateCmd
                        if updateResponse contains "error" then
                            my writeLog("ERROR", "Google Docs API 錯誤：" & updateResponse)
                            display notification "Docs 更新失敗：API 錯誤" with title "Google Docs"
                        else
                            my writeLog("SUCCESS", "Google Docs 字幕內容寫入完成")
                            display notification "Docs 更新成功：" & subtitleID with title "Google Docs"
                        end if
                    on error errMsg
                        my writeLog("ERROR", "Google Docs 寫入失敗：" & errMsg)
                        display notification "Docs 寫入錯誤：" & errMsg with title "Google Docs"
                    end try
                else
                    my writeLog("INFO", "未找到對應的 Google Docs，跳過更新內容")
                end if

                -- 整個檔案處理完成
                set processEndTime to current date
                set processDuration to (processEndTime - processStartTime)
                my writeLog("SUCCESS", "處理完成：" & subtitleID & "，耗時：" & processDuration & " 秒")
                set successCount to successCount + 1
            end if
        else
            my writeLog("ERROR", "找不到對應資料夾：" & subtitleID)
            set end of folderNotFoundList to subtitleID
            set folderNotFoundCount to folderNotFoundCount + 1
            display notification "找不到對應資料夾：" & subtitleID with title "字幕處理"
        end if    
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