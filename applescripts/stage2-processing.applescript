-- 定義寫入日誌的函數
on writeLog(level, message)
    set scriptPath to "/Users/Mac/GitHub/automation/scripts/log_bridge.py"
    set stage to "2"
    set component to "processing"
    
    try
        do shell script "python3 " & quoted form of scriptPath & " " & stage & " " & level & " " & quoted form of message & " " & component
    on error errMsg
        -- 如果日誌記錄失敗，使用基本的 stderr 輸出
        do shell script "echo 'Log Error: " & errMsg & "' >&2"
    end try
end writeLog

-- Helper function for face detection and cover generation
on generateCoverImage(videoPath, outputDir)
    try
        my writeLog("INFO", "開始進行封面生成...")
        
        set pythonCmd to "/Library/Frameworks/Python.framework/Versions/3.11/bin/python3"
        set scriptPath to "/Users/Mac/GitHub/automation/scripts/face_center_crop.py"
        
        set videoID to do shell script "basename " & quoted form of videoPath & " | sed 's/\\..*$//'"
        set targetDir to outputDir & "/" & videoID
        
        set shellCommand to pythonCmd & " " & quoted form of scriptPath & " " & quoted form of videoPath & " -o " & quoted form of targetDir
        
        set coverPath to do shell script shellCommand
        return coverPath
    on error errMsg
        my writeLog("ERROR", "封面生成失敗：" & errMsg)
        error "封面生成失敗：" & errMsg
    end try
end generateCoverImage

-- Helper 函數：取得環境變數值
on getEnvValue(envPath, key)
    return do shell script "grep '^" & key & "=' " & quoted form of envPath & " | cut -d '=' -f 2 | tr -d '\"' | tr -d '\\n' | tr -d '\\r'"
end getEnvValue

-- Helper 函數：創建 Trello 卡片
on createTrelloCard(cardName, apiKey, token, listID, templateCardID)
    set maxRetries to 3
    set retryDelay to 5 -- 5 秒延遲
    
    repeat with retryCount from 1 to maxRetries
        try
            my writeLog("INFO", "嘗試創建 Trello 卡片 (" & retryCount & "/" & maxRetries & ")")
            
            set createCardURL to "https://api.trello.com/1/cards"
            set createCardCommand to "curl -X POST " & quoted form of createCardURL & " -d \"key=" & apiKey & "\" -d \"token=" & token & "\" -d \"idList=" & listID & "\" -d \"name=" & cardName & "\" -d \"idCardSource=" & templateCardID & "\""
            
            set response to do shell script createCardCommand
            
            my writeLog("INFO", "Trello 卡片創建成功")
            return response
            
        on error errMsg
            if retryCount is maxRetries then
                my writeLog("ERROR", "創建 Trello 卡片失敗：" & errMsg)
                error "創建 Trello 卡片失敗：" & errMsg
            else
                my writeLog("WARNING", "創建 Trello 卡片失敗，" & retryDelay & " 秒後重試：" & errMsg)
                delay retryDelay
            end if
        end try
    end repeat
end createTrelloCard

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
                my writeLog("SUCCESS", "封面圖片已生成")
            on error errMsg
                my writeLog("ERROR", "生成封面圖片失敗：" & errMsg)
            end try
            
            -- 更新輸出檔案路徑到子資料夾中
            set outputFilePath to subDirectory & "/" & trimmedName & "-1920*1340.mp4"
            
            -- 轉檔（加黑色方塊）
            try
                -- 構建 FFmpeg 命令
                set ffmpegCommand to "/usr/local/bin/ffmpeg -i " & quoted form of movieFilePath & ¬
                    " -vf \"pad=width=1920:height=1340:x=0:y=0:color=black\" " & ¬
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
                
                my writeLog("SUCCESS", "影片轉檔完成")
                
            on error errMsg
                my writeLog("ERROR", "FFmpeg 轉檔失敗：" & errMsg)
                error "FFmpeg 轉檔失敗，中止處理"
            end try
            
            -- 建立 Google Drive 資料夾結構
            my writeLog("INFO", "開始建立資料夾結構：" & fileBaseName)
            set pythonPath to "/Library/Frameworks/Python.framework/Versions/3.11/bin/python3"
            set driveScriptPath to "/Users/Mac/GitHub/automation/scripts/google_drive.py"
            
            -- 創建主資料夾
            set createFolderCommand to quoted form of pythonPath & " " & quoted form of driveScriptPath & ¬
                " --create-folder " & quoted form of fileBaseName & " " & quoted form of parentID
            
            set driveFolderID to do shell script createFolderCommand
            
            -- 在主資料夾中創建同名的 Google Docs
            set createDocsCommand to quoted form of pythonPath & " " & quoted form of driveScriptPath & ¬
                " --create-docs " & quoted form of fileBaseName & " " & quoted form of driveFolderID
            
            do shell script createDocsCommand
            
            -- 初始化變數
            set originalFolderID to ""
            set embeddedFolderID to ""
            
            -- 建立子資料夾
            set subFolders to {"字幕時間軸", "原始影片", "嵌入影片", "截圖"}
            
            repeat with folderName in subFolders
                try
                    set createSubFolderCommand to quoted form of pythonPath & " " & quoted form of driveScriptPath & ¬
                        " --create-folder " & quoted form of folderName & " " & quoted form of driveFolderID
                    
                    set subFolderID to do shell script createSubFolderCommand
                    
                    if folderName as string is equal to "原始影片" then
                        set originalFolderID to subFolderID
                    else if folderName as string is equal to "嵌入影片" then
                        set embeddedFolderID to subFolderID
                    end if
                    
                on error errMsg
                    my writeLog("ERROR", "建立子資料夾失敗：" & errMsg)
                    error "建立子資料夾失敗：" & errMsg
                end try
            end repeat
            
            my writeLog("SUCCESS", "資料夾結構建立完成")
            
            -- 上傳檔案
            my writeLog("INFO", "開始上傳影片檔案...")
            
            -- 上傳原始影片
            if originalFolderID is "" then
                error "原始影片資料夾 ID 未設定"
            end if
            
            try
                set uploadOriginalCommand to quoted form of pythonPath & " " & quoted form of driveScriptPath & ¬
                    " --upload-file " & quoted form of movieFilePath & ¬
                    " " & quoted form of fileName & ¬
                    " " & quoted form of originalFolderID
                
                do shell script uploadOriginalCommand
                
            on error errMsg
                my writeLog("ERROR", "原始影片上傳失敗：" & errMsg)
                error "原始影片上傳失敗：" & errMsg
            end try
            
            -- 上傳轉檔影片
            if embeddedFolderID is "" then
                error "嵌入影片資料夾 ID 未設定"
            end if
            
            set uploadSuccess to false
            try
                set uploadConvertedCommand to quoted form of pythonPath & " " & quoted form of driveScriptPath & ¬
                    " --upload-file " & quoted form of outputFilePath & ¬
                    " " & quoted form of (trimmedName & "-1920*1340.mp4") & ¬
                    " " & quoted form of embeddedFolderID
                
                do shell script uploadConvertedCommand
                set uploadSuccess to true
                my writeLog("SUCCESS", "轉檔影片上傳成功")
                
            on error errMsg
                my writeLog("ERROR", "轉檔影片上傳失敗：" & errMsg)
                -- 不再直接拋出錯誤，繼續執行
            end try
            
            -- 無論上傳是否成功，都嘗試創建 Trello 卡片
            try
                my createTrelloCard(fileBaseName, trelloAPIKey, trelloToken, trelloListID, templateCardID)
            on error errMsg
                my writeLog("ERROR", "創建 Trello 卡片失敗：" & errMsg)
            end try
            
            -- 如果上傳失敗，最後才拋出錯誤
            if not uploadSuccess then
                error "轉檔影片上傳失敗"
            end if
            
            my writeLog("SUCCESS", "所有影片檔案上傳完成")
            
            my writeLog("SUCCESS", "影片處理完成：" & fileName)
            
        on error errMsg
            my writeLog("ERROR", "處理影片 " & fileName & " 時發生錯誤：" & errMsg)
        end try
    end repeat
    
    my writeLog("INFO", "所有影片處理完成")
    return input
end run