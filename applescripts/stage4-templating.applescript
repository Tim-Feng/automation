-- Helper function to write logs
on writeLog(level, message)
    set logPath to "/Users/Mac/Library/Logs/ig_template_processor.log"
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

-- Helper function to join list items
on joinList(theList)
    set AppleScript's text item delimiters to ", "
    set theString to theList as string
    set AppleScript's text item delimiters to ""
    return theString
end joinList

-- Helper function to remove emoji
on removeEmoji(inputText)
    if inputText contains " " then
        set AppleScript's text item delimiters to " "
        set textItems to text items of inputText
        set AppleScript's text item delimiters to ""
        return (items 2 thru -1 of textItems) as text
    else
        return (text 2 thru -1 of inputText)
    end if
end removeEmoji



on run {input, parameters}
    -- 初始化失敗檔案列表和計數器
    set failedFiles to {}
    set successCount to 0
    set totalFiles to count of input
    
    my writeLog("INFO", "開始處理範本轉換，共 " & totalFiles & " 個檔案")

    -- 循環處理每個影片
    repeat with movieFile in input
        try
            -- 獲取影片路徑
            set movieFilePath to POSIX path of movieFile
            
            -- 使用 shell 命令提取影片 ID
            set movieID to do shell script "basename " & quoted form of movieFilePath & " | sed 's/-1920\\*1340.*$//'"
            set movieDirectory to do shell script "dirname " & quoted form of movieFilePath
            
            my writeLog("INFO", "開始處理：" & movieID)

            -- 獲取機密資訊從環境變數
            try
                set envPath to "/Users/Mac/Library/Mobile Documents/com~apple~Automator/Documents/.env"

                set refreshToken to do shell script "grep '^REFRESH_TOKEN=' " & quoted form of envPath & " | cut -d '=' -f 2 | tr -d '\"' | tr -d '\n' | tr -d '\r'"
                set clientId to do shell script "grep '^CLIENT_ID=' " & quoted form of envPath & " | cut -d '=' -f 2 | tr -d '\"' | tr -d '\n' | tr -d '\r'"
                set clientSecret to do shell script "grep '^CLIENT_SECRET=' " & quoted form of envPath & " | cut -d '=' -f 2 | tr -d '\"' | tr -d '\n' | tr -d '\r'"
            on error errMsg
                my writeLog("ERROR", "環境變數讀取失敗：" & errMsg)
                error "環境變數讀取失敗"
            end try

            -- 使用 refresh token 來獲取新的 access token
            try
                set refreshURL to "https://oauth2.googleapis.com/token"
                set refreshCommand to "curl -s -X POST " & quoted form of refreshURL & " -d client_id=" & clientId & " -d client_secret=" & clientSecret & " -d refresh_token=" & refreshToken & " -d grant_type=refresh_token"
                
                set refreshResponse to do shell script refreshCommand
                set accessToken to do shell script "echo " & quoted form of refreshResponse & " | python3 -c \"import sys, json; print(json.load(sys.stdin)['access_token'])\""
            on error errMsg
                my writeLog("ERROR", "Access Token 獲取失敗：" & errMsg)
                error "Access Token 獲取失敗"
            end try

            -- 搜尋共用雲端硬碟中的資料夾
            try
                set searchFolderQuery to "mimeType='application/vnd.google-apps.folder' and name='" & movieID & "' and trashed = false"
                set encodedQuery to do shell script "echo " & quoted form of searchFolderQuery & " | python3 -c \"import sys, urllib.parse; print(urllib.parse.quote(sys.stdin.read().strip()))\""
                set searchFolderCommand to "curl -s -X GET 'https://www.googleapis.com/drive/v3/files?q=" & encodedQuery & "&supportsAllDrives=true&includeItemsFromAllDrives=true&corpora=allDrives' -H 'Authorization: Bearer " & accessToken & "'"

                set folderResponse to do shell script searchFolderCommand
                set folderId to do shell script "echo " & quoted form of folderResponse & " | python3 -c \"import sys, json; files = json.load(sys.stdin).get('files', []); print(files[0]['id'] if files else '')\""
                
                if folderId is equal to "" then
                    my writeLog("ERROR", "找不到對應資料夾：" & movieID)
                    error "找不到對應資料夾"
                end if
            on error errMsg
                my writeLog("ERROR", "搜尋資料夾失敗：" & errMsg)
                error "搜尋資料夾失敗"
            end try

            -- 在找到的資料夾中搜尋 Google Doc
            try
                set searchDocQuery to "mimeType='application/vnd.google-apps.document' and '" & folderId & "' in parents and trashed = false"
                set encodedDocQuery to do shell script "echo " & quoted form of searchDocQuery & " | python3 -c \"import sys, urllib.parse; print(urllib.parse.quote(sys.stdin.read().strip()))\""
                set searchDocCommand to "curl -s -X GET 'https://www.googleapis.com/drive/v3/files?q=" & encodedDocQuery & "&supportsAllDrives=true&includeItemsFromAllDrives=true&corpora=allDrives' -H 'Authorization: Bearer " & accessToken & "'"

                set docResponse to do shell script searchDocCommand
                set fileID to do shell script "echo " & quoted form of docResponse & " | python3 -c \"import sys, json; files = json.load(sys.stdin).get('files', []); print(files[0]['id'] if files else '')\""
                
                if fileID is equal to "" then
                    my writeLog("ERROR", "找不到對應的 Google Doc")
                    error "找不到對應的 Google Doc"
                end if
            on error errMsg
                my writeLog("ERROR", "搜尋 Google Doc 失敗：" & errMsg)
                error "搜尋 Google Doc 失敗"
            end try

            -- 下載並解析文件內容
            try
                set curlCommand to "curl -s -X GET 'https://www.googleapis.com/drive/v3/files/" & fileID & "/export?mimeType=text/plain' -H 'Authorization: Bearer " & accessToken & "'"

                set fileContent to do shell script curlCommand
                if fileContent contains "error" then
                    my writeLog("ERROR", "下載文件內容失敗")
                    error "下載文件內容失敗"
                end if

                -- 解析文件內容
                set allLines to paragraphs of fileContent
                if (count of allLines) < 5 then
                    my writeLog("ERROR", "文件內容格式不正確")
                    error "文件內容格式不正確"
                end if

                set firstText to removeEmoji(item 1 of allLines)
                set secondText to removeEmoji(item 2 of allLines)
                set thirdText to item 5 of allLines
                
                my writeLog("SUCCESS", "內容下載解析完成")
            on error errMsg
                my writeLog("ERROR", "下載文件內容失敗：" & errMsg)
                error "下載或解析文件內容失敗"
            end try
            
            -- 使用 Python 產生影片和封面
            try
                -- 產生封面圖
                my writeLog("INFO", "開始以 Python 腳本產生封面圖")
                set pythonPath to "/Library/Frameworks/Python.framework/Versions/3.11/bin/python3"
                set igCoverScriptPath to "/Users/Mac/GitHub/automation/scripts/ig_cover_generator.py"
                
                set coverCommand to quoted form of pythonPath & " " & quoted form of igCoverScriptPath & ¬
                    " " & quoted form of movieID & ¬
                    " " & quoted form of firstText & ¬
                    " " & quoted form of secondText & ¬
                    " " & quoted form of movieDirectory
                
                do shell script coverCommand
                my writeLog("SUCCESS", "封面圖產生完成")

                -- 產生影片
                my writeLog("INFO", "開始以 Python 腳本產生影片")
                set igVideoScriptPath to "/Users/Mac/GitHub/automation/scripts/ig_video_generator.py"
                
                set videoCommand to quoted form of pythonPath & " " & quoted form of igVideoScriptPath & ¬
                    " " & quoted form of movieFilePath & ¬
                    " " & quoted form of firstText & ¬
                    " " & quoted form of secondText & ¬
                    " " & quoted form of thirdText & ¬
                    " --output_dir " & quoted form of movieDirectory

                do shell script videoCommand
                my writeLog("SUCCESS", "影片產生完成")
                
                set pythonPath to "/Library/Frameworks/Python.framework/Versions/3.11/bin/python3"
                set driveScriptPath to "/Users/Mac/GitHub/automation/scripts/google_drive.py"
                
                -- 搜尋「嵌入影片」資料夾
                my writeLog("INFO", "搜尋「嵌入影片」資料夾...")
                set findEmbedFolderCommand to quoted form of pythonPath & " " & quoted form of driveScriptPath & ¬
                    " --find-folder \"嵌入影片\" " & quoted form of folderId
                
                set embedFolderId to do shell script findEmbedFolderCommand
                
                if embedFolderId is equal to "" then
                    error "找不到「嵌入影片」資料夾"
                end if
                
                -- 搜尋「截圖」資料夾
                my writeLog("INFO", "搜尋「截圖」資料夾...")
                set findScreenshotFolderCommand to quoted form of pythonPath & " " & quoted form of driveScriptPath & ¬
                    " --find-folder \"截圖\" " & quoted form of folderId
                
                set screenshotFolderId to do shell script findScreenshotFolderCommand
                
                if screenshotFolderId is equal to "" then
                    error "找不到「截圖」資料夾"
                end if
                
                -- 上傳影片和封面
                try
                    -- 上傳影片到「嵌入影片」資料夾
                    set videoPath to movieDirectory & "/" & movieID & "-1920*3414-zh.mp4"
                    set videoName to movieID & "-1920*3414-zh.mp4"
                    my writeLog("INFO", "開始上傳影片到「嵌入影片」資料夾：" & videoName)
                    
                    set uploadVideoCommand to quoted form of pythonPath & " " & quoted form of driveScriptPath & ¬
                        " --upload-file " & quoted form of videoPath & ¬
                        " " & quoted form of videoName & ¬
                        " " & quoted form of embedFolderId
                    
                    do shell script uploadVideoCommand
                    my writeLog("SUCCESS", "影片上傳完成")
                    
                    -- 上傳封面圖到「截圖」資料夾
                    set coverPath to movieDirectory & "/" & movieID & "_cover.jpg"
                    set coverName to movieID & "_cover.jpg"
                    my writeLog("INFO", "開始上傳封面圖到「截圖」資料夾：" & coverName)
                    
                    set uploadCoverCommand to quoted form of pythonPath & " " & quoted form of driveScriptPath & ¬
                        " --upload-file " & quoted form of coverPath & ¬
                        " " & quoted form of coverName & ¬
                        " " & quoted form of screenshotFolderId
                    
                    do shell script uploadCoverCommand
                    my writeLog("SUCCESS", "封面圖上傳完成")
                on error errMsg
                    my writeLog("ERROR", "檔案上傳失敗：" & errMsg)
                    error "檔案上傳失敗"
                end try

                -- 記錄成功
                set successCount to successCount + 1
                my writeLog("SUCCESS", "完成處理：" & movieID)

            on error errMsg
                my writeLog("ERROR", "Python 處理失敗：" & errMsg)
                error "Python 處理失敗"
            end try

        on error errMsg
            -- 在最外層記錄失敗的檔案
            set end of failedFiles to movieID
        end try
    end repeat
    
    -- 確保一定會執行統計
    my writeLog("INFO", "==== 批次處理統計 ====")
    my writeLog("INFO", "總處理檔案：" & totalFiles & " 個")
    my writeLog("INFO", "完全成功：" & successCount & " 個")
    
    if length of failedFiles is greater than 0 then
        my writeLog("INFO", "失敗檔案：" & my joinList(failedFiles))
    end if
    
    return input
end run