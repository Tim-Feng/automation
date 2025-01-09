-- 首先定義寫入日誌的函數
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

on run {input, parameters}
-- 獲取機密資訊從環境變數
  set envPath to "/Users/Mac/Library/Mobile Documents/com~apple~Automator/Documents/.env"

  set refreshToken to do shell script "grep '^REFRESH_TOKEN=' " & quoted form of envPath & " | cut -d '=' -f 2 | tr -d '\"' | tr -d '\\n' | tr -d '\\r'"
  set clientId to do shell script "grep '^CLIENT_ID=' " & quoted form of envPath & " | cut -d '=' -f 2 | tr -d '\"' | tr -d '\\n' | tr -d '\\r'"
  set clientSecret to do shell script "grep '^CLIENT_SECRET=' " & quoted form of envPath & " | cut -d '=' -f 2 | tr -d '\"' | tr -d '\\n' | tr -d '\\r'"
  set parentID to do shell script "grep '^GOOGLE_DRIVE_PARENT_ID=' " & quoted form of envPath & " | cut -d '=' -f 2 | tr -d '\"' | tr -d '\\n' | tr -d '\\r'"
  set trelloAPIKey to do shell script "grep '^TRELLO_API_KEY=' " & quoted form of envPath & " | cut -d '=' -f 2 | tr -d '\"' | tr -d '\\n' | tr -d '\\r'"
  set trelloToken to do shell script "grep '^TRELLO_TOKEN=' " & quoted form of envPath & " | cut -d '=' -f 2 | tr -d '\"' | tr -d '\\n' | tr -d '\\r'"
  set trelloListID to do shell script "grep '^TRELLO_LIST_ID=' " & quoted form of envPath & " | cut -d '=' -f 2 | tr -d '\"' | tr -d '\\n' | tr -d '\\r'"
  set templateCardID to do shell script "grep '^TEMPLATE_CARD_ID=' " & quoted form of envPath & " | cut -d '=' -f 2 | tr -d '\"' | tr -d '\\n' | tr -d '\\r'"

  -- 循環處理每個影片
  repeat with movieFile in input
    set movieFilePath to POSIX path of movieFile

    -- 使用 refresh token 來獲取新的 access token
    set refreshURL to "https://oauth2.googleapis.com/token"
    set refreshCommand to "curl -X POST " & quoted form of refreshURL & " -d client_id=" & clientId & " -d client_secret=" & clientSecret & " -d refresh_token=" & refreshToken & " -d grant_type=refresh_token"
    set refreshResponse to do shell script refreshCommand

    -- 使用 shell script 解析 JSON 中的 access_token
    set accessToken to do shell script "echo " & quoted form of refreshResponse & " | python3 -c \"import sys, json; print(json.load(sys.stdin)['access_token'])\""

    -- 找到模板的 POSIX 路徑，假設模板名稱是 "影片模板 1920*1340.key"
    set movieDirectory to do shell script "dirname " & quoted form of movieFilePath
    set templateFilePath to movieDirectory & "/影片模板 1920*1340.key"

    -- 打開 Keynote 並加載模板
    tell application "Keynote"
      activate
      set thisDocument to open (POSIX file templateFilePath)
      delay 3 -- 延遲一段時間確保模板打開
    end tell

    -- 清空模板中的影片
    tell application "Keynote"
      tell the front document
        set thisSlide to the first slide
        tell thisSlide
          delete (every movie)
        end tell
      end tell
    end tell

    -- 使用 Insert 選項來插入影片
    tell application "System Events"
      tell process "Keynote"
        set frontmost to true
        delay 3

        -- 開啟 "Insert" 菜單並選擇 "Choose..."
        click menu item "Choose..." of menu "Insert" of menu bar 1
        delay 3

        -- 使用逐字鍵入影片路徑
        repeat with i from 1 to (count of characters of movieFilePath)
          if i ≤ 5 then
            -- 對於前五個字符增加延遲
            keystroke (character i of movieFilePath)
            delay 0.3 -- 增加延遲，確保系統接受開頭字符
          else
            -- 後續字符正常輸入
            keystroke (character i of movieFilePath)
          end if
        end repeat
        delay 2

        -- 按下回車鍵來確認影片路徑
        keystroke return
        delay 3

        -- 確認輸入影片
        keystroke return
        delay 3

        -- 等待插入過程完成
        set maxWaitTime to 300 -- 最多等待 5 分鐘
        set waitCount to 0
        
        repeat
            delay 1
            set waitCount to waitCount + 1
            
            -- 檢查是否存在 "Cancel" 按鈕
            try
                if exists sheet 1 then
                    if exists button "Cancel" of sheet 1 then
                        -- 還在插入中，繼續等待
                        if waitCount > maxWaitTime then
                            display dialog "影片插入時間過長，請檢查影片檔案。" buttons {"OK"} default button "OK"
                            error "插入超時"
                        end if
                    else
                        -- 沒有 Cancel 按鈕，可能已完成
                        delay 3 -- 等待一下確保完全完成
                        exit repeat
                    end if
                else
                    -- 沒有 sheet，應該已完成
                    delay 3 -- 等待一下確保完全完成
                    exit repeat
                end if
            on error errMsg
                if errMsg is not "插入超時" then
                    -- 如果是其他錯誤，假設已完成
                    delay 3
                    exit repeat
                else
                    -- 如果是超時錯誤，向外拋出
                    error errMsg
                end if
            end try
        end repeat
      end tell
    end tell

    -- 調整影片大小和位置
    tell application "Keynote"
      tell the front document
        set thisSlide to the first slide
        tell thisSlide
          set allMovies to movies
          if (count of allMovies) > 0 then
            set theMovie to item 1 of allMovies
            -- 確保影片高度為 1080 並進行相應的水平調整
            set height of theMovie to 1080
            -- 計算影片的寬度與幻燈片寬度的差異，以確保影片水平居中
            set slideWidth to 1920
            set movieWidth to width of theMovie
            if movieWidth < slideWidth then
              set xOffset to (slideWidth - movieWidth) / 2
            else
              set xOffset to 0
              set width of theMovie to slideWidth -- 如果影片比幻燈片寬，則縮放至幻燈片寬度
            end if
            -- 設定影片的位置，確保高度貼齊上方，水平居中
            set position of theMovie to {xOffset, 0} -- Y座標為0，貼齊上方；X座標為偏移量
          else
            display dialog "找不到影片，請確認影片已經成功插入到幻燈片中。" buttons {"OK"} default button "OK"
            return input
          end if
        end tell
      end tell
    end tell
    
    -- 創建輸出目錄在桌面指定路徑下
    set outputDirectory to "/Users/Mac/Desktop/Video Production/2. To be Translated"
    set originalName to name of (info for movieFile)
    set trimmedName to do shell script "basename " & quoted form of originalName & " | sed 's/\\.[^.]*$//'"
    set subDirectory to outputDirectory & "/" & trimmedName
    do shell script "mkdir -p " & quoted form of subDirectory
    
    -- 複製指定的檔案到新資料夾
    set templateToCopyPath to "/Users/Mac/Movies/影片模板 1920*3414.key"
    do shell script "cp " & quoted form of templateToCopyPath & " " & quoted form of subDirectory
    
    -- 複製指定的影片檔案到新資料夾
    do shell script "cp " & quoted form of movieFilePath & " " & quoted form of subDirectory
    
    -- 導出為影片
    tell application "Keynote"
      tell the front document
        activate
        delay 2 -- 確保窗口成功開啟
        
        -- 使用 System Events 打開導出選單
        tell application "System Events"
          tell process "Keynote"
            -- 先點擊 "File" 選單
            click menu bar item "File" of menu bar 1
            delay 2
            
            -- 再點擊 "Export To"
            click menu item "Export To" of menu 1 of menu bar item "File" of menu bar 1
            delay 2
            
            -- 使用方向鍵下移動兩次到 "Movie..."
            key code 125 -- 方向鍵下
            delay 0.5
            key code 125 -- 方向鍵下
            delay 0.5
            
            -- 最後按下回車以選擇 "Movie..."
            key code 36 -- 按下 Enter 鍵
            delay 3
            
            -- 設置導出選項
            keystroke tab -- 進入"go to next slide after"字段
            delay 0.5
            keystroke "0"
            delay 0.5
            keystroke tab -- 進入"go to next build after"字段
            delay 0.5
            keystroke "0"
            delay 0.5
            keystroke tab -- 進入解析度字段
            delay 0.5
            keystroke "1920"
            delay 0.5
            key code 48 -- Tab鍵，進入高度字段
            delay 0.5
            keystroke "1340"
            delay 0.5
            
            -- 最後，按下 "Next" 按鈕進入保存頁面
            key code 36 -- 按下 Enter 鍵，進入保存對話框
            delay 3
            
            -- 刪除預設檔名
            key code 51 -- 按下 delete 鍵清除整個欄位（假設全選狀態）
            delay 2 -- 增加延遲以確保欄位被完全清空
            
            -- 獲取新檔名並加上後置
            set newFileName to trimmedName & "-1920*1340"
            
            -- 輸入新檔名
            keystroke newFileName
            delay 1 -- 增加延遲以確保名稱輸入完成
            
            -- 修改保存路徑至新創建的資料夾
            keystroke "g" using {command down, shift down} -- 打開前往文件夾窗口
            delay 1
            key code 51 -- 刪除之前可能的錯誤路徑
            delay 0.5
            keystroke subDirectory
            delay 2
            key code 36 -- 按下 Enter 確認路徑
            delay 1
            
            -- 按下保存按鈕
            key code 36 -- 按下 Enter 鍵以確認保存
            delay 3
          end tell
        end tell
      end tell
    end tell
    
    -- 等待影片輸出完成
    set outputFilePath to subDirectory & "/" & newFileName & ".m4v"
    repeat until (do shell script "test -e " & quoted form of outputFilePath & " && echo yes || echo no") is "yes"
      delay 5
    end repeat
    
    -- 確保轉檔完成後，清空模板中的影片
    tell application "Keynote"
      tell the front document
        set thisSlide to the first slide
        tell thisSlide
          delete (every movie)
        end tell
      end tell
    end tell

    delay 3
    -- 確保轉檔完成後，關閉當前文檔
    tell application "Keynote"
      close the front document saving yes
    end tell
    
    try
        my writeLog("INFO", "開始處理 Google Drive 上傳流程")
        set createFolderUrl to "https://www.googleapis.com/drive/v3/files?supportsAllDrives=true"
        set createFolderJson to "{\"name\": \"" & trimmedName & "\", \"mimeType\": \"application/vnd.google-apps.folder\", \"parents\": [\"" & parentID & "\"]}"
        
        set curlCommand to "curl -s -X POST -H \"Authorization: Bearer " & accessToken & "\" -H \"Content-Type: application/json\" -d " & quoted form of createFolderJson & " \"" & createFolderUrl & "\""
        set googleDriveResponse to do shell script curlCommand
        
        set driveFolderID to do shell script "echo " & quoted form of googleDriveResponse & " | python3 -c \"import sys, json; print(json.load(sys.stdin)['id'])\""
        
        -- 創建子資料夾
        set originalVideoFolderID to ""
        set subFolders to {"字幕時間軸", "原始影片", "嵌入影片", "截圖"}
        
        repeat with subFolder in subFolders
            try
                set currentFolderName to contents of subFolder
                set createSubFolderJson to "{\"name\": \"" & currentFolderName & "\", \"mimeType\": \"application/vnd.google-apps.folder\", \"parents\": [\"" & driveFolderID & "\"]}"
                
                set subFolderCommand to "curl -s -X POST -H \"Authorization: Bearer " & accessToken & "\" -H \"Content-Type: application/json\" -d " & quoted form of createSubFolderJson & " \"" & createFolderUrl & "\""
                set subFolderResponse to do shell script subFolderCommand
                
                set currentFolderID to do shell script "echo " & quoted form of subFolderResponse & " | python3 -c 'import sys, json; print(json.load(sys.stdin)[\"id\"])'"
                
                if currentFolderName is "原始影片" then
                    set originalVideoFolderID to currentFolderID
                end if
                
            on error errMsg
                my writeLog("ERROR", "創建子資料夾 " & currentFolderName & " 失敗：" & errMsg)
                return input
            end try
        end repeat
        
        -- 上傳原始影片
        try
            set createFileUrl to "https://www.googleapis.com/upload/drive/v3/files?uploadType=resumable&supportsAllDrives=true"
            set createFileJson to "{\"name\": \"" & originalName & "\", \"parents\": [\"" & originalVideoFolderID & "\"]}"
            
            set uploadUrlCommand to "curl -s -X POST -H \"Authorization: Bearer " & accessToken & "\" -H \"Content-Type: application/json\" -H \"X-Upload-Content-Type: video/mp4\" -d " & quoted form of createFileJson & " -i \"" & createFileUrl & "\""
            set uploadUrlResponse to do shell script uploadUrlCommand & " | grep -i 'Location: ' | cut -d' ' -f2- | tr -d '\\r'"
            
            if uploadUrlResponse contains "http" then
                set uploadCommand to "curl -s -X PUT -H \"Authorization: Bearer " & accessToken & "\" -H \"Content-Type: video/mp4\" --data-binary @" & quoted form of movieFilePath & " \"" & uploadUrlResponse & "&supportsAllDrives=true\""
                set uploadResponse to do shell script uploadCommand
                
                if uploadResponse contains "\"kind\": \"drive#file\"" and uploadResponse contains "\"id\":" then
                    set tid to offset of "\"id\": \"" in uploadResponse
                    set tmp to text (tid + 7) thru -1 of uploadResponse
                    set fileID to text 1 thru ((offset of "\"" in tmp) - 1) of tmp
                else
                    my writeLog("ERROR", "上傳失敗")
                    error "上傳失敗：無效的回應"
                end if
            else
                my writeLog("ERROR", "獲取上傳 URL 失敗")
                error "無效的上傳 URL"
            end if
            
        on error errMsg
            my writeLog("ERROR", "上傳失敗：" & errMsg)
            return input
        end try
        
        my writeLog("SUCCESS", "Google Drive 處理流程完成")
        
    on error errMsg
        my writeLog("ERROR", "整體處理失敗：" & errMsg)
        return input
    end try

    -- 創建 Google Doc 文件
    set createDocUrl to "https://www.googleapis.com/drive/v3/files?supportsAllDrives=true"
    set createDocJson to "{\"name\": \"" & trimmedName & "\", \"mimeType\": \"application/vnd.google-apps.document\", \"parents\": [\"" & driveFolderID & "\"]}"
    do shell script "curl -X POST -H \"Authorization: Bearer " & accessToken & "\" -H \"Content-Type: application/json\" -d " & quoted form of createDocJson & " " & createDocUrl
    
    -- 使用 Trello API 建立卡片
    set trelloCardName to trimmedName
    do shell script "curl -X POST \"https://api.trello.com/1/cards\" " & ¬
      "-d \"key=" & trelloAPIKey & "\" " & ¬
      "-d \"token=" & trelloToken & "\" " & ¬
      "-d \"idList=" & trelloListID & "\" " & ¬
      "-d \"name=" & trelloCardName & "\" " & ¬
      "-d \"idCardSource=" & templateCardID & "\""
    
  end repeat
  
  return input
end run
