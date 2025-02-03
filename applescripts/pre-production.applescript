-- 定義寫入日誌的函數
on writeLog(level, message)
    set logPath to "/Users/Mac/Library/Logs/gdrive_upload.log"
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

-- Helper function for face detection and cover generation
on generateCoverImage(videoPath, outputDir)
    try
        my writeLog("INFO", "開始進行封面生成：" & videoPath)
        
        set pythonCmd to "/Library/Frameworks/Python.framework/Versions/3.11/bin/python3"
        set scriptPath to "/Users/Mac/GitHub/automation/scripts/face_center_crop.py"
        
        set shellCommand to pythonCmd & " " & quoted form of scriptPath & " " & quoted form of videoPath & " -o " & quoted form of outputDir
        
        set coverPath to do shell script shellCommand
        my writeLog("SUCCESS", "封面生成完成：" & coverPath)
        return coverPath
    on error errMsg
        my writeLog("ERROR", "封面生成失敗：" & errMsg)
        error "封面生成失敗：" & errMsg
    end try
end generateCoverImage

on run {input, parameters}
    -- 獲取環境變數
    set envPath to "/Users/Mac/Library/Mobile Documents/com~apple~Automator/Documents/.env"
    set refreshToken to my getEnvValue(envPath, "REFRESH_TOKEN")
    set clientId to my getEnvValue(envPath, "CLIENT_ID")
    set clientSecret to my getEnvValue(envPath, "CLIENT_SECRET")
    set parentID to my getEnvValue(envPath, "GOOGLE_DRIVE_PARENT_ID")
    set trelloAPIKey to my getEnvValue(envPath, "TRELLO_API_KEY")
    set trelloToken to my getEnvValue(envPath, "TRELLO_TOKEN")
    set trelloListID to my getEnvValue(envPath, "TRELLO_LIST_ID")
    set templateCardID to my getEnvValue(envPath, "TEMPLATE_CARD_ID")
    
    my writeLog("INFO", "開始處理影片，共 " & (count of input) & " 支影片")
    
    -- 循環處理每支影片
    repeat with movieFile in input
        try
            -- 獲取影片路徑與檔名
            set movieFilePath to POSIX path of movieFile
            set fileName to do shell script "basename " & quoted form of movieFilePath
            set fileBaseName to do shell script "basename " & quoted form of movieFilePath & " | sed 's/\\.[^.]*$//'"
            
            my writeLog("INFO", "開始處理影片：" & fileName)
            
            -- 創建輸出目錄和子資料夾
            set outputDirectory to "/Users/Mac/Desktop/Video Production/2. To be Translated"
            set trimmedName to fileBaseName
            set subDirectory to outputDirectory & "/" & trimmedName
            do shell script "mkdir -p " & quoted form of subDirectory
            
            -- 生成封面圖片
            try
                set coverPath to my generateCoverImage(movieFilePath, subDirectory)
                my writeLog("SUCCESS", "封面圖片已生成：" & coverPath)
            on error errMsg
                my writeLog("ERROR", "生成封面圖片失敗：" & errMsg)
            end try
            
            -- 更新輸出檔案路徑到子資料夾中
            set outputFilePath to subDirectory & "/" & trimmedName & "-1920*1340.mp4"
            
            -- 轉檔（加黑色方塊）
            try
                -- 構建 FFmpeg 命令
                set ffmpegCommand to "/usr/local/bin/ffmpeg -i " & quoted form of movieFilePath & ¬
                    " -vf \"pad=width=1920:height=1340:x=0:y=1080:color=black\" " & ¬
                    "-c:v libx264 -preset medium -crf 23 " & ¬
                    "-c:a aac -b:a 128k " & ¬
                    "-movflags +faststart " & ¬
                    "-y " & quoted form of outputFilePath & " 2>&1"
                
                -- 執行 FFmpeg 命令並捕獲輸出
                set ffmpegOutput to do shell script ffmpegCommand
                
                -- 檢查輸出文件是否存在
                if (do shell script "test -f " & quoted form of outputFilePath & " && echo yes || echo no") is not "yes" then
                    error "轉檔失敗：輸出文件不存在"
                end if
                
                my writeLog("SUCCESS", "影片轉檔完成：" & outputFilePath)
                
            on error errMsg
                my writeLog("ERROR", "FFmpeg 轉檔失敗：" & errMsg)
                error "FFmpeg 轉檔失敗，中止處理"
            end try
            
            -- 創建 Google Drive 資料夾（主資料夾）
            set driveFolderID to my createGoogleDriveFolder(fileBaseName, parentID, refreshToken, clientId, clientSecret)
            
            -- 使用新的函數創建子資料夾
            set folderIDs to my createSubFolders(driveFolderID, refreshToken, clientId, clientSecret)
            
            -- 使用新的方式獲取資料夾 ID
            set originalFolderID to my getFolderID(folderIDs, "原始影片")
            set embeddedFolderID to my getFolderID(folderIDs, "嵌入影片")
            
            -- 複製原始影片到 Google Drive 的「原始影片」資料夾
            my uploadToGoogleDrive(movieFilePath, fileName, originalFolderID, refreshToken, clientId, clientSecret)
            
            -- 複製轉檔影片到 Google Drive 的「嵌入影片」資料夾
            my uploadToGoogleDrive(outputFilePath, trimmedName & "-1920x1340.mp4", embeddedFolderID, refreshToken, clientId, clientSecret)
            
            -- 創建 Trello 卡片
            my createTrelloCard(fileBaseName, trelloAPIKey, trelloToken, trelloListID, templateCardID)
            
            my writeLog("SUCCESS", "影片處理完成：" & fileName)
            
        on error errMsg
            my writeLog("ERROR", "處理影片 " & fileName & " 時發生錯誤：" & errMsg)
        end try
    end repeat
    
    my writeLog("INFO", "所有影片處理完成")
    return input
end run

-- Helper 函數：取得環境變數值
on getEnvValue(envPath, key)
    return do shell script "grep '^" & key & "=' " & quoted form of envPath & " | cut -d '=' -f 2 | tr -d '\"' | tr -d '\\n' | tr -d '\\r'"
end getEnvValue

-- Helper 函數：創建 Google Drive 資料夾
on createGoogleDriveFolder(folderName, parentID, refreshToken, clientId, clientSecret)
    set accessToken to my getGoogleAccessToken(refreshToken, clientId, clientSecret)
    -- 增加了 includeItemsFromAllDrives=true 參數
    set createFolderURL to "https://www.googleapis.com/drive/v3/files?supportsAllDrives=true&includeItemsFromAllDrives=true"
    
    -- 獲取父資料夾的 driveId
    set getDriveIdCommand to "curl -s -X GET -H \"Authorization: Bearer " & accessToken & "\" \"https://www.googleapis.com/drive/v3/files/" & parentID & "?fields=driveId&supportsAllDrives=true\""
    set driveIdResponse to do shell script getDriveIdCommand
    set driveId to do shell script "echo " & quoted form of driveIdResponse & " | python3 -c \"import sys, json; print(json.load(sys.stdin).get('driveId', ''))\""
    
    -- 如果是共用雲端硬碟，添加 driveId
    set folderMetadata to "{\"name\": \"" & folderName & "\", \"mimeType\": \"application/vnd.google-apps.folder\", \"parents\": [\"" & parentID & "\"]}"
    if driveId is not "" then
        set folderMetadata to "{\"name\": \"" & folderName & "\", \"mimeType\": \"application/vnd.google-apps.folder\", \"parents\": [\"" & parentID & "\"], \"driveId\": \"" & driveId & "\"}"
    end if
    
    set curlCommand to "curl -s -X POST -H \"Authorization: Bearer " & accessToken & "\" -H \"Content-Type: application/json\" -d " & quoted form of folderMetadata & " \"" & createFolderURL & "\""
    set response to do shell script curlCommand
    return do shell script "echo " & quoted form of response & " | python3 -c \"import sys, json; print(json.load(sys.stdin)['id'])\""
end createGoogleDriveFolder

-- Helper 函數：獲取特定資料夾 ID 的函數
on getFolderID(folderDict, targetName)
    if targetName is "原始影片" then
        try
            set targetID to |原始影片| of folderDict
            return targetID
        on error errMsg
            my writeLog("ERROR", "處理資料夾時發生錯誤：" & errMsg)
            error "找不到資料夾：原始影片"
        end try
    else if targetName is "嵌入影片" then
        try
            set targetID to |嵌入影片| of folderDict
            return targetID
        on error errMsg
            my writeLog("ERROR", "處理資料夾時發生錯誤：" & errMsg)
            error "找不到資料夾：嵌入影片"
        end try
    end if
    
    error "找不到資料夾：" & targetName
end getFolderID

-- Helper 函數：修改創建子資料夾的部分
on createSubFolders(driveFolderID, refreshToken, clientId, clientSecret)
    -- 初始化空字典
    set folderDict to {}
    set subFolders to {"字幕時間軸", "原始影片", "嵌入影片", "截圖"}
    
    -- 創建子資料夾
    repeat with i from 1 to length of subFolders
        set folderName to item i of subFolders
        try
            set subFolderID to my createGoogleDriveFolder(folderName, driveFolderID, refreshToken, clientId, clientSecret)
            
            -- 將新的鍵值對加入字典
            if i = 1 then
                -- 第一個項目
                set folderDict to {|字幕時間軸|:subFolderID}
            else if i = 2 then
                -- 第二個項目
                set folderDict to folderDict & {|原始影片|:subFolderID}
            else if i = 3 then
                -- 第三個項目
                set folderDict to folderDict & {|嵌入影片|:subFolderID}
            else if i = 4 then
                -- 第四個項目
                set folderDict to folderDict & {|截圖|:subFolderID}
            end if
            
        on error errMsg
            my writeLog("ERROR", "創建子資料夾失敗：" & folderName & "，錯誤：" & errMsg)
            error "創建子資料夾失敗：" & errMsg
        end try
    end repeat
    
    return folderDict
end createSubFolders

-- Helper 函數：上傳影片到 Google Drive
on uploadToGoogleDrive(filePath, fileName, folderID, refreshToken, clientId, clientSecret)
    set accessToken to my getGoogleAccessToken(refreshToken, clientId, clientSecret)
    
    -- 獲取父資料夾的 driveId
    set getDriveIdCommand to "curl -s -X GET -H \"Authorization: Bearer " & accessToken & "\" \"https://www.googleapis.com/drive/v3/files/" & folderID & "?fields=driveId&supportsAllDrives=true\""
    set driveIdResponse to do shell script getDriveIdCommand
    set driveId to do shell script "echo " & quoted form of driveIdResponse & " | python3 -c \"import sys, json; print(json.load(sys.stdin).get('driveId', ''))\""
    
    set uploadSessionURL to "https://www.googleapis.com/upload/drive/v3/files?uploadType=resumable&supportsAllDrives=true&includeItemsFromAllDrives=true"
    
    -- 準備檔案詮釋資料，根據是否為共用雲端硬碟添加 driveId
    set fileMetadata to "{\"name\": \"" & fileName & "\", \"parents\": [\"" & folderID & "\"]}"
    if driveId is not "" then
        set fileMetadata to "{\"name\": \"" & fileName & "\", \"parents\": [\"" & folderID & "\"], \"driveId\": \"" & driveId & "\"}"
    end if
    
    set createUploadSessionCommand to "curl -s -X POST -H \"Authorization: Bearer " & accessToken & "\" -H \"Content-Type: application/json\" -H \"X-Upload-Content-Type: video/mp4\" -d " & quoted form of fileMetadata & " -i \"" & uploadSessionURL & "\" | grep -i 'Location: ' | cut -d' ' -f2- | tr -d '\\r'"
    set uploadURL to do shell script createUploadSessionCommand
    do shell script "curl -s -X PUT -H \"Authorization: Bearer " & accessToken & "\" -H \"Content-Type: video/mp4\" --data-binary @" & quoted form of filePath & " \"" & uploadURL & "\""
end uploadToGoogleDrive

-- Helper 函數：取得 Google Drive Access Token
on getGoogleAccessToken(refreshToken, clientId, clientSecret)
    set tokenURL to "https://oauth2.googleapis.com/token"
    set curlCommand to "curl -s -X POST " & quoted form of tokenURL & " -d client_id=" & clientId & " -d client_secret=" & clientSecret & " -d refresh_token=" & refreshToken & " -d grant_type=refresh_token"
    set response to do shell script curlCommand
    return do shell script "echo " & quoted form of response & " | python3 -c \"import sys, json; print(json.load(sys.stdin)['access_token'])\""
end getGoogleAccessToken

-- Helper 函數：創建 Trello 卡片
on createTrelloCard(cardName, apiKey, token, listID, templateCardID)
    set createCardURL to "https://api.trello.com/1/cards"
    set createCardCommand to "curl -X POST " & quoted form of createCardURL & " -d \"key=" & apiKey & "\" -d \"token=" & token & "\" -d \"idList=" & listID & "\" -d \"name=" & cardName & "\" -d \"idCardSource=" & templateCardID & "\""
    do shell script createCardCommand
end createTrelloCard
