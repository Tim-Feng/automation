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
            
            -- 處理 Keynote
            try
                set movieDirectory to do shell script "dirname " & quoted form of movieFilePath
                set templateFilePath to movieDirectory & "/影片模板 1920*3414.key"

                -- 強制 Keynote 完全退出
                try
                    tell application "Keynote" to quit
                    delay 1
                end try

                my writeLog("INFO", "開始處理模板")

                -- 使用系統預設方式開啟檔案
                do shell script "open " & quoted form of templateFilePath
                delay 3

                tell application "Keynote"
                    -- 等待文件開啟
                    repeat until documents is not {}
                        delay 1
                    end repeat
                    
                    activate -- 確保 Keynote 在最前面
                    delay 1

                    set thisDocument to document 1
                    tell thisDocument
                        set current slide to slide 1
                        delay 1 -- 確保切換完成
                    end tell
                end tell

                -- 使用 Insert 選項來插入影片
                tell application "System Events"
                    tell process "Keynote"
                        set frontmost to true
                        delay 1

                        -- 開啟 "Insert" 菜單並選擇 "Choose..."
                        click menu item "Choose..." of menu "Insert" of menu bar 1
                        delay 2


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
                        delay 1

                        -- 按下回車鍵來確認插入影片
                        keystroke return
                        delay 1

                        -- 等待媒體插入完成（通過檢查 Cancel 按鈕是否存在來判斷）
                        repeat
                            try
                                tell application "System Events"
                                    tell process "Keynote"
                                        -- 檢查 Cancel 按鈕是否還存在
                                        if not (exists button "Cancel" of sheet 1 of window "影片模板 1920*3414.key") then
                                            exit repeat
                                        end if
                                    end tell
                                end tell
                            end try
                            delay 1
                        end repeat

                        -- 額外等待一小段時間確保完全載入
                        delay 2
                    end tell
                end tell

                 -- 切換到 Keynote 文件進行文本更新和影片位置調整
                tell application "Keynote"
                    -- 先啟動 Keynote
                    activate
                    delay 1
                    -- 先檢查所有已開啟的文件
                    repeat with doc in documents
                        if name of doc contains "影片模板" then
                            set targetDocument to doc
                            exit repeat
                        end if
                    end repeat
                    
                    tell targetDocument
                        -- 第一張投影片處理
                        tell slide 1
                            -- 設置插入影片的位置和大小
                            set allMovies to movies
                            if (count of allMovies) > 0 then
                                set newMovie to item 1 of allMovies
                                -- 設置影片的位置和大小
                                set position of newMovie to {0, 1065}
                                set width of newMovie to 1920
                                set height of newMovie to 1340
                            else
                                my writeLog("ERROR", "無法找到影片物件")
                                error "無法找到影片物件"
                            end if
                            
                            tell first group
                                -- 獲取所有文字項目
                                set textItems to every text item
                                
                                tell item 1 of textItems
                                    set object text to firstText
                                end tell
                                
                                tell item 2 of textItems
                                    set object text to secondText
                                end tell
                                
                                tell item 3 of textItems
                                    set object text to thirdText
                                end tell
                            end tell
                        end tell  -- 加入這個 end tell

                        -- 第二張投影片處理
                        tell slide 2
                            -- 直接獲取投影片上的所有文字項目
                            set textItems to every text item
                            
                            tell item 1 of textItems
                                set object text to firstText
                            end tell
                            
                            tell item 2 of textItems
                                set object text to secondText
                            end tell
                        end tell

                        -- 切換到第一張投影片
                        set current slide to slide 1
                    end tell
                end tell

                -- 確保 Build Order 視窗打開並設置動畫順序
                tell application "System Events"
                    tell process "Keynote"
                        set frontmost to true
                        delay 0.5

                        -- 確保 "Build Order" 視窗已打開
                        try
                            click menu item "Show Build Order" of menu "View" of menu bar 1
                        on error
                            -- 如果已經打開，無需做任何動作
                        end try
                        delay 0.5 -- 確保 Build Order 已完全顯示

                        -- 點擊 "Build Order" 視窗中的第一個項目
                        tell window "Build Order"
                            tell scroll area 1
                                tell table 1
                                    -- 點擊第一行，也就是 Group 物件
                                    select row 1
                                end tell
                            end tell
                        end tell

                        -- 找到並點擊 Order pop up button
                        click pop up button 1 of scroll area 1 of window "影片模板 1920*3414.key"
                        delay 0.5
                        -- 選擇數字 2
                        click menu item "2" of menu 1 of pop up button 1 of scroll area 1 of window "影片模板 1920*3414.key"
                    end tell
                end tell

                -- 導出第一張投影片為影片
                my writeLog("INFO", "開始導出影片")
                try
                    tell application "Keynote"
                        tell the front document
                            set current slide to slide 1
                            delay 1 -- 確保窗口已經完全開啟
                            
                            -- 使用 System Events 打開導出菜單
                            tell application "System Events"
                                tell process "Keynote"
                                    -- 點擊 "File" 選單
                                    click menu bar item "File" of menu bar 1
                                    delay 1
                                    
                                    -- 點擊 "Export To"
                                    click menu item "Export To" of menu 1 of menu bar item "File" of menu bar 1
                                    delay 1
                                    
                                    -- 使用方向鍵下移動兩次到 "Movie..."
                                    key code 125 -- 方向鍵下
                                    delay 0.5
                                    key code 125 -- 方向鍵下
                                    delay 0.5
                                    
                                    -- 按下回車以選擇 "Movie..."
                                    key code 36 -- 按下 Enter 鍵
                                    delay 2
                                    
                                    -- 點擊 Resolution pop up button 並選擇 720p
                                    tell application "System Events"
                                        tell process "Keynote"
                                            tell sheet 1 of window "影片模板 1920*3414.key"
                                                -- 直接指定第二個 pop up button
                                                click pop up button 2
                                                delay 0.5
                                                click menu item "Custom..." of menu 1 of pop up button 2
                                            end tell
                                        end tell
                                    end tell
                                    delay 1

                                    -- 設置導出選項
                                    -- 先點擊 "From" radio button
                                    click radio button "From:" of sheet 1 of window "影片模板 1920*3414.key"
                                    delay 0.2

                                    -- 按下 tab 移動到下一個輸入框
                                    keystroke tab
                                    delay 0.2
                                    
                                    -- 輸入第一個值
                                    keystroke "1"
                                    delay 0.2
                                    
                                    -- 按下 tab 移動到下一個輸入框
                                    keystroke tab
                                    delay 0.2
                                    
                                    -- 輸入第二個值
                                    keystroke "1"
                                    delay 0.2
                                    
                                    -- 在 "to" 欄位輸入值
                                    keystroke tab -- 進入"go to next slide after"字段
                                    delay 0.2
                                    keystroke "0"
                                    delay 0.2
                                    keystroke tab -- 進入"go to next build after"字段
                                    delay 0.2
                                    keystroke "0"
                                    delay 0.2

                                    -- 然後繼續執行

                                    keystroke tab -- 進入解析度字段
                                    delay 0.2
                                    keystroke "1920"
                                    delay 0.2
                                    key code 48 -- Tab鍵，進入高度字段
                                    delay 0.2
                                    keystroke "3414"
                                    delay 0.2
                                    -- 最後按下 "Next" 按鈕進入保存頁面
                                    key code 36 -- 按下 Enter 鍵，進入保存對話框
                                    delay 2
                                    
                                    -- 刪除預設檔名
                                    key code 51 -- 按下 delete 鍵清除整個欄位（假設全選狀態）
                                    delay 1 -- 增加延遲以確保欄位被完全清空
                                    
                                    -- 獲取新檔名並加上後置
                                    set newFileName to movieID & "-1920*3414-zh"
                                    
                                    -- 輸入新檔名
                                    keystroke newFileName
                                    delay 1 -- 增加延遲以確保名稱輸入完成
                                    
                                    -- 按下保存按鈕
                                    key code 36 -- 按下 Enter 鍵以確認保存
                                    delay 1

                                    -- 等待 "Creating movie..." 進度視窗消失
                                    repeat
                                        -- 檢查進度指示器是否存在
                                        if not (exists progress indicator 1 of sheet 1 of window "影片模板 1920*3414.key") then
                                            exit repeat
                                        end if
                                        delay 2
                                    end repeat
                                    
                                    -- 為了確保檔案完整寫入，再多等待幾秒
                                    delay 5
                                end tell
                            end tell
                        end tell
                    end tell
                    my writeLog("SUCCESS", "影片導出完成")
                on error errMsg
                    my writeLog("ERROR", "影片導出失敗：" & errMsg)
                    error "影片導出失敗"
                end try

                -- 導出第二張投影片為圖片
                my writeLog("INFO", "開始導出圖片")
                try
                    tell application "Keynote"
                        tell thisDocument
                            set current slide to slide 2
                            delay 2
                            
                            -- 導出圖片
                            tell application "System Events"
                                tell process "Keynote"
                                -- 點擊 "File" 選單
                                    click menu bar item "File" of menu bar 1
                                    delay 2
                                    
                                    -- 點擊 "Export To"
                                    click menu item "Export To" of menu 1 of menu bar item "File" of menu bar 1
                                    delay 2
                                    
                                    -- 使用方向鍵下移動兩次到 "Movie..."
                                    key code 125 -- 方向鍵下
                                    delay 0.5
                                    key code 125 -- 方向鍵下
                                    delay 0.5
                                    key code 125 -- 方向鍵下
                                    delay 0.5
                                    key code 125 -- 方向鍵下
                                    delay 0.5

                                    -- 按下回車以選擇 "Images..."
                                    key code 36 -- 按下 Enter 鍵
                                    delay 3
                                    
                                    -- 設置導出選項
                                    -- 先點擊 "From" radio button
                                    click radio button "From:" of sheet 1 of window "影片模板 1920*3414.key"
                                    delay 0.5

                                    -- 按下 tab 移動到下一個輸入框
                                    keystroke tab
                                    delay 0.5
                                    
                                    -- 輸入第一個值
                                    keystroke "2"
                                    delay 0.5
                                    
                                    -- 按下 tab 移動到下一個輸入框
                                    keystroke tab
                                    delay 0.5
                                    
                                    -- 輸入第二個值
                                    keystroke "2"
                                    delay 0.5
                                    
                                    -- 按下保存按鈕
                                    key code 36 -- 按下 Enter 鍵以確認保存
                                    delay 3

                                    -- 按下輸出按鈕
                                    key code 36 -- 按下 Enter 鍵以確認輸出
                                    delay 3

                                    -- 處理可能出現的提示視窗
                                    repeat 5 times
                                        if exists sheet 1 of window "影片模板 1920*3414.key" then
                                            if exists button "OK" of sheet 1 of window "影片模板 1920*3414.key" then
                                                click button "OK" of sheet 1 of window "影片模板 1920*3414.key"
                                                delay 1
                                            end if
                                        end if
                                        delay 0.5
                                    end repeat
                                    delay 3
                                end tell
                            end tell
                        end tell
                    end tell
                    my writeLog("SUCCESS", "圖片導出完成")
                on error errMsg
                    my writeLog("ERROR", "圖片導出失敗：" & errMsg)
                    error "圖片導出失敗"
                end try
                
                -- 儲存並關閉 Keynote 文件
                tell application "Keynote"
                    save thisDocument
                    delay 2 -- 給予足夠時間儲存
                    close thisDocument
                    delay 2 -- 給予足夠時間關閉
                    -- 完全退出 Keynote
                    quit
                    delay 2
                end tell

                -- 記錄成功
                set successCount to successCount + 1
                my writeLog("SUCCESS", "完成處理：" & movieID)

            on error errMsg
                my writeLog("ERROR", "模板處理失敗：" & errMsg)
                error "模板處理失敗"
            end try

        on error errMsg
            -- 只在最外層記錄失敗的檔案
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