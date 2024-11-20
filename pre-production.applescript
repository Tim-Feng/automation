on run {input, parameters}
-- 獲取機密資訊從環境變數
  set refreshToken to do shell script "grep '^REFRESH_TOKEN=' .env | cut -d '=' -f 2"
  set clientId to do shell script "grep '^CLIENT_ID=' .env | cut -d '=' -f 2"
  set clientSecret to do shell script "grep '^CLIENT_SECRET=' .env | cut -d '=' -f 2"
  set parentID to do shell script "grep '^GOOGLE_DRIVE_PARENT_ID=' .env | cut -d '=' -f 2"
  set trelloAPIKey to do shell script "grep '^TRELLO_API_KEY=' .env | cut -d '=' -f 2"
  set trelloToken to do shell script "grep '^TRELLO_TOKEN=' .env | cut -d '=' -f 2"
  set trelloListID to do shell script "grep '^TRELLO_LIST_ID=' .env | cut -d '=' -f 2"
  set templateCardID to do shell script "grep '^TEMPLATE_CARD_ID=' .env | cut -d '=' -f 2"

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

        -- 更精確地查找 "Insert" 按鈕
        try
          tell window 1
            tell sheet 1
              click button "Insert"
            end tell
          end tell
          delay 6
        on error
          -- 如果按鈕無法點擊，則顯示錯誤信息
          display dialog "找不到插入按鈕，請手動嘗試。" buttons {"OK"} default button "OK"
          return input
        end try
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
        delay 2 -- 確保窗口已經完全激活
        
        -- 使用 System Events 打開導出菜單
        tell application "System Events"
          tell process "Keynote"
            -- 先點擊 "File" 菜單
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
    -- 確保轉檔完成後，關閉當前文檔
    tell application "Keynote"
      close the front document saving yes
    end tell
    
    -- 創建 Google Drive 主資料夾
    set createFolderUrl to "https://www.googleapis.com/drive/v3/files?supportsAllDrives=true"
    set createFolderJson to "{\"name\": \"" & trimmedName & "\", \"mimeType\": \"application/vnd.google-apps.folder\", \"parents\": [\"" & parentID & "\"]}"
    set googleDriveResponse to do shell script "curl -X POST -H \"Authorization: Bearer " & accessToken & "\" -H \"Content-Type: application/json\" -d " & quoted form of createFolderJson & " " & createFolderUrl
    
    -- 解析返回的 JSON 以獲取主資料夾 ID
    set driveFolderID to do shell script "echo " & quoted form of googleDriveResponse & " | python3 -c \"import sys, json; print(json.load(sys.stdin)['id'])\""
    
    -- 創建四個子資料夾
    set subFolders to {"字幕時間軸", "原始影片", "嵌入影片", "截圖"}
    repeat with subFolder in subFolders
      set createSubFolderJson to "{\"name\": \"" & subFolder & "\", \"mimeType\": \"application/vnd.google-apps.folder\", \"parents\": [\"" & driveFolderID & "\"]}"
      do shell script "curl -X POST -H \"Authorization: Bearer " & accessToken & "\" -H \"Content-Type: application/json\" -d " & quoted form of createSubFolderJson & " " & createFolderUrl
    end repeat
    
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
