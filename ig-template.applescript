on run {input, parameters}
    -- 循環處理每個影片
    repeat with movieFile in input
        -- 獲取影片路徑
        set movieFilePath to POSIX path of movieFile
        
        -- 使用 shell 命令提取影片 ID
        set movieID to do shell script "basename " & quoted form of movieFilePath & " | sed 's/-1920\\*1340.*$//'"

        -- 獲取機密資訊從環境變數
        set envPath to "/Users/Mac/Library/Mobile Documents/com~apple~Automator/Documents/.env"

        set refreshToken to do shell script "grep '^REFRESH_TOKEN=' " & quoted form of envPath & " | cut -d '=' -f 2 | tr -d '\"' | tr -d '\n' | tr -d '\r'"
        set clientId to do shell script "grep '^CLIENT_ID=' " & quoted form of envPath & " | cut -d '=' -f 2 | tr -d '\"' | tr -d '\n' | tr -d '\r'"
        set clientSecret to do shell script "grep '^CLIENT_SECRET=' " & quoted form of envPath & " | cut -d '=' -f 2 | tr -d '\"' | tr -d '\n' | tr -d '\r'"

        -- 使用 refresh token 來獲取新的 access token
        set refreshURL to "https://oauth2.googleapis.com/token"
        set refreshCommand to "curl -X POST " & quoted form of refreshURL & " -d client_id=" & clientId & " -d client_secret=" & clientSecret & " -d refresh_token=" & refreshToken & " -d grant_type=refresh_token"
        set refreshResponse to do shell script refreshCommand

        -- 使用 shell script 解析 JSON 中的 access_token
        set accessToken to do shell script "echo " & quoted form of refreshResponse & " | python3 -c \"import sys, json; print(json.load(sys.stdin)['access_token'])\""

        -- 使用 access token 來從 Google Sheets 獲取數據
        set sheetID to "1EE5tphRzOLvCclDMPpg0SxY8Zfq1zWBu4010yBKw9xc"
        set sheetRange to "Sheet1!A:D"
        set sheetURL to "https://sheets.googleapis.com/v4/spreadsheets/" & sheetID & "/values/" & sheetRange
        set sheetCommand to "curl -X GET " & quoted form of sheetURL & " -H \"Authorization: Bearer " & accessToken & "\""
        set sheetValues to do shell script sheetCommand

        -- 定義 Python 腳本來解析匹配行
        set pythonScript to "import sys, json; data = json.loads(sys.stdin.read()); movie_id = '" & movieID & "'; result = [line for line in data['values'] if line[0] == movie_id]; print(result[0] if result else '[]')"

        -- 使用 shell 執行該腳本
        set pythonScriptCommand to "echo " & quoted form of sheetValues & " | python3 -c " & quoted form of pythonScript
        set matchingRow to do shell script pythonScriptCommand

        -- 檢查結果
        if matchingRow is equal to "[]" then
            return input
        end if

        -- 使用 Python 解析 JSON 並獲取文本數據
        set pythonExtractScript to "import sys, ast; data = ast.literal_eval(sys.stdin.read()); print(data[1], data[2], data[3], sep='|')"
        set parsedTextCommand to "echo " & quoted form of matchingRow & " | python3 -c " & quoted form of pythonExtractScript
        set parsedText to do shell script parsedTextCommand

        -- 拆分獲取到的文本
        set textItems to splitString(parsedText, "|")
        set firstText to item 1 of textItems
        set secondText to item 2 of textItems
        set thirdText to item 3 of textItems

         -- 打開 Keynote 並加載模板
        set movieDirectory to do shell script "dirname " & quoted form of movieFilePath
        set templateFilePath to movieDirectory & "/影片模板 1920*3414.key"

        -- 強制 Keynote 完全退出（加入錯誤處理）
        try
            do shell script "killall Keynote"
        on error
            -- Keynote 沒有執行，不需要做任何事
        end try
        delay 2

        -- 使用系統預設方式開啟檔案
        do shell script "open " & quoted form of templateFilePath
        delay 3

        tell application "Keynote"
            -- 等待文件開啟
            repeat until documents is not {}
                delay 1
            end repeat
            
            set thisDocument to document 1
            tell thisDocument
                set current slide to slide 1
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

                -- 按下回車鍵來確認插入影片
                keystroke return
                delay 3

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
                delay 5
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
                        return input
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
                delay 1

                -- 確保 "Build Order" 視窗已打開
                try
                    click menu item "Show Build Order" of menu "View" of menu bar 1
                on error
                    -- 如果已經打開，無需做任何動作
                end try
                delay 1 -- 確保 Build Order 已完全顯示

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
        tell application "Keynote"
            tell the front document
                set current slide to slide 1
                delay 2 -- 確保窗口已經完全開啟
                
                -- 使用 System Events 打開導出菜單
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
                        
                        -- 按下回車以選擇 "Movie..."
                        key code 36 -- 按下 Enter 鍵
                        delay 3
                        
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
                        delay 0.5

                        -- 按下 tab 移動到下一個輸入框
                        keystroke tab
                        delay 0.5
                        
                        -- 輸入第一個值
                        keystroke "1"
                        delay 0.5
                        
                        -- 按下 tab 移動到下一個輸入框
                        keystroke tab
                        delay 0.5
                        
                        -- 輸入第二個值
                        keystroke "1"
                        delay 0.5
                        
                        -- 在 "to" 欄位輸入值
                        keystroke tab -- 進入"go to next slide after"字段
                        delay 0.5
                        keystroke "0"
                        delay 0.5
                        keystroke tab -- 進入"go to next build after"字段
                        delay 0.5
                        keystroke "0"
                        delay 0.5

                        -- 然後繼續執行

                        keystroke tab -- 進入解析度字段
                        delay 0.5
                        keystroke "1920"
                        delay 0.5
                        key code 48 -- Tab鍵，進入高度字段
                        delay 0.5
                        keystroke "3414"
                        delay 0.5
                        -- 最後按下 "Next" 按鈕進入保存頁面
                        key code 36 -- 按下 Enter 鍵，進入保存對話框
                        delay 3
                        
                        -- 刪除預設檔名
                        key code 51 -- 按下 delete 鍵清除整個欄位（假設全選狀態）
                        delay 2 -- 增加延遲以確保欄位被完全清空
                        
                        -- 獲取新檔名並加上後置
                        set newFileName to movieID & "-1920*3414-zh"
                        
                        -- 輸入新檔名
                        keystroke newFileName
                        delay 1 -- 增加延遲以確保名稱輸入完成
                        
                        -- 按下保存按鈕
                        key code 36 -- 按下 Enter 鍵以確認保存
                        delay 3

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

                        -- 處理可能出現的提示視窗
                        repeat 10 times
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
        
        -- 導出第二張投影片為圖片
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
    end repeat
    
    return input
end run

-- Helper function to split a string by a delimiter
on splitString(theString, theDelimiter)
    set oldDelimiters to AppleScript's text item delimiters
    set AppleScript's text item delimiters to theDelimiter
    set theArray to every text item of theString
    set AppleScript's text item delimiters to oldDelimiters
    return theArray
end splitString
