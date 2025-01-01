(*
  說明：
  - 需要在 .env 裡配置 REFRESH_TOKEN, CLIENT_ID, CLIENT_SECRET
  - 會搜尋「與字幕檔 (去掉 -zh.srt) 同名」的資料夾 → 再搜尋同名 Google Docs → 把去除時間碼的字幕插入
  - 執行 Aegisub 相關自動化
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
    set aegisubFailCount to 0
    set ffmpegFailCount to 0
    set startTime to current date
    
    set folderNotFoundList to {}
    set aegisubFailList to {}
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
                
                -- 嘗試找到最匹配的資料夾（名稱以 trimmedName 開頭的）
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
            -- (4) Aegisub 自動化操作
            --------------------------------------------------------
            my writeLog("INFO", "開始 Aegisub 操作...")
            try
                tell application "Aegisub"
                    activate
                    delay 5 -- 等待程式打開
                end tell

                tell application "System Events"
                    tell process "Aegisub"
                        if exists (window 1) then
                        -- 使用快捷鍵 Command+O 打開字幕檔案（開啟檔案選取對話框）
                        keystroke "o" using {command down}
                        delay 2 -- 等待打開對話框出現

                        -- 按下 Command+Shift+G 來打開「前往文件夾」的輸入框
                        keystroke "g" using {command down, shift down}
                        delay 2 -- 等待「前往文件夾」的輸入框出現

                        -- 使用逐字鍵入字幕檔路徑來避免輸入錯誤
                        repeat with i from 1 to (count of characters of subtitlePath)
                            if i ≤ 5 then
                                -- 對於前五個字符增加延遲
                                keystroke (character i of subtitlePath)
                                delay 0.3 -- 增加延遲，確保系統接受開頭字符
                            else
                                -- 後續字符正常輸入
                                keystroke (character i of subtitlePath)
                            end if
                        end repeat
                        delay 1 -- 等待輸入完成

                        -- 第一次按下回車鍵來確認路徑
                        keystroke return
                        delay 1 -- 等待路徑跳轉

                        -- 第二次按下回車鍵來打開字幕檔案
                        keystroke return
                        delay 5 -- 等待字幕檔案加載完成

                        -- 全選字幕
                        click menu item "Select All" of menu "Edit" of menu bar 1
                        delay 3 -- 給它一些時間來完成全選操作

                        -- 使用鼠標點擊特定的 XY 座標來展開下拉選單
                        set mouseX to 387
                        set mouseY to 98
                        do shell script "/usr/bin/env osascript -e 'tell application \"System Events\" to click at {" & mouseX & ", " & mouseY & "}'"
                        delay 1 -- 等待選單展開

                        -- 使用鍵盤箭頭向下鍵選擇 "蘋方 1340"
                        key code 125 -- 按下向下箭頭
                        delay 1 -- 等待選擇完成
                        key code 36 -- 按下 Enter 鍵選擇模板
                        delay 2 -- 等待模板套用完成

                        -- 儲存檔案時修改檔名
                        keystroke "s" using {command down} -- 模擬 Command+S 來保存文件
                        delay 3

                        -- 刪除預設檔名
                        key code 51 -- 按下 delete 鍵清除整個欄位（假設全選狀態）
                        delay 1 -- 增加延遲以確保欄位被完全清空

                        -- 獲取新檔名並加上後置
                        set newSubtitleName to trimmedName & "-1920*1340-zh"
                        keystroke newSubtitleName
                        delay 1

                        -- 點擊 "儲存" 按鈕
                        keystroke return
                        delay 1 -- 等待儲存完成

                        -- 開啟影片檔案 (使用 Aegisub 的 "Open Video..." 選項)
                        click menu item "Open Video..." of menu "Video" of menu bar 1
                        delay 2 -- 等待視窗打開

                        -- 使用逐字鍵入影片路徑
                        set videoPath to subtitleDirectory & "/" & trimmedName & "-1920*1340." & videoExtension

                        repeat with i from 1 to (count of characters of videoPath)
                            if i ≤ 5 then
                                -- 對於前五個字符增加延遲
                                keystroke (character i of videoPath)
                                delay 0.3 -- 增加延遲，確保系統接受開頭字符
                            else
                                -- 後續字符正常輸入
                                keystroke (character i of videoPath)
                            end if
                        end repeat
                        delay 2 -- 等待輸入完成

                        -- 第一次按下回車鍵來確認影片路徑
                        keystroke return
                        delay 1 -- 等待路徑跳轉

                        -- 第二次按下回車鍵來打開影片檔案
                        keystroke return
                        delay 10 -- 等待影片加載完成

                        -- 再次儲存檔案
                        keystroke "s" using {command down} -- 模擬 Command+S 來保存影片與字幕的關聯
                        delay 2 -- 等待保存完成

                        end if
                    end tell
                end tell

                tell application "Aegisub"
                    quit
                end tell
                delay 5
            on error errMsg
                if errMsg contains "AppleEvent逾時" then
                    my writeLog("ERROR", "Aegisub 執行失敗：逾時")
                    set end of aegisubFailList to trimmedName
                    set aegisubFailCount to aegisubFailCount + 1
                else
                    my writeLog("ERROR", "Aegisub 執行失敗：" & errMsg)
                    set end of aegisubFailList to trimmedName
                    set aegisubFailCount to aegisubFailCount + 1
                end if
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

    if aegisubFailCount > 0 then
        my writeLog("INFO", "Aegisub 失敗：" & aegisubFailCount & " 個（" & joinList(aegisubFailList) & "）")
    end if

    if ffmpegFailCount > 0 then
        my writeLog("INFO", "ffmpeg 失敗：" & ffmpegFailCount & " 個（" & joinList(ffmpegFailList) & "）")
    end if

    my writeLog("INFO", "總耗時：" & ((current date) - startTime) & " 秒")

    return input
end run
