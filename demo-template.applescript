-- 寫入日誌函數
on writeLog(message, logFile)
    do shell script "echo \"$(date '+%Y-%m-%d %H:%M:%S') " & message & "\" >> " & quoted form of logFile
end writeLog

-- 移除表情符號的函數
on removeEmoji(theText)
    return do shell script "echo " & quoted form of theText & " | perl -CS -pe 's/[^[:ascii:]]//g'"
end removeEmoji

on run {input, parameters}
    -- 設定日誌檔案路徑
    set logFile to "/Users/Mac/GitHub/automation/logs/demo_template.log"
    
    try
        writeLog("開始執行 Demo 模板處理", logFile)
        writeLog("輸入參數: " & input, logFile)
        
        -- 檢查輸入參數
        if input is equal to current application then
            writeLog("錯誤: 沒有輸入檔案", logFile)
            return input
        end if
        
        -- 循環處理每個影片
        repeat with movieFile in input
            -- 轉換為 POSIX 路徑
            set movieFilePath to (POSIX path of movieFile) as string
            writeLog("POSIX 路徑: " & movieFilePath, logFile)
            
            -- 使用 shell 命令提取影片 ID
            set movieID to do shell script "basename " & quoted form of movieFilePath & " | sed -E 's/-1920\\*[0-9]+.*$//'"
            writeLog("影片 ID: " & movieID, logFile)

            -- 準備模板檔案
            set movieDirectory to do shell script "dirname " & quoted form of movieFilePath
            set templatePath to "/Users/Mac/GitHub/automation/keynote-templates/影片模板 1920*3414.key"
            set newFileName to movieDirectory & "/" & movieID & "-1920*3414.key"
            set templateFilePath to quoted form of newFileName
            writeLog("模板路徑: " & templateFilePath, logFile)
            
            -- 複製模板檔案
            do shell script "cp " & quoted form of templatePath & " " & quoted form of templateFilePath
            writeLog("已複製模板檔案", logFile)
            
            -- 強制 Keynote 完全退出
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
                        keystroke (character i of movieFilePath)
                    end repeat
                    delay 2
                    
                    -- 按下回車鍵來確認影片路徑
                    keystroke return
                    delay 3
                    
                    -- 按下回車鍵來確認插入影片
                    keystroke return
                    delay 3
                    
                    -- 等待媒體插入完成
                    delay 5
                end tell
            end tell
            
            -- 調整影片位置和大小
            tell application "Keynote"
                tell thisDocument
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
                    end tell
                end tell
            end tell
            
            -- 導出第一張投影片為影片
            tell application "Keynote"
                tell thisDocument
                    set current slide to slide 1
                    delay 2
                    
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
                            
                            -- 設置導出選項
                            tell sheet 1 of window "影片模板 1920*3414.key"
                                -- 設置解析度
                                click pop up button 2
                                delay 0.5
                                click menu item "Custom..." of menu 1 of pop up button 2
                                delay 1
                                
                                -- 設置幀數
                                click radio button "From:"
                                delay 0.5
                                keystroke tab
                                delay 0.5
                                keystroke "1"
                                delay 0.5
                                keystroke tab
                                delay 0.5
                                keystroke "1"
                                delay 0.5
                                
                                -- 設置解析度
                                keystroke tab
                                delay 0.5
                                keystroke "1920"
                                delay 0.5
                                keystroke tab
                                delay 0.5
                                keystroke "3414"
                                delay 0.5
                                
                                -- 按下 Next
                                keystroke return
                                delay 3
                            end tell
                            
                            -- 設置輸出檔名
                            keystroke (movieID & "-1920*3414-zh")
                            delay 1
                            
                            -- 按下保存按鈕
                            keystroke return
                            delay 3
                            
                            -- 等待導出完成
                            repeat 30 times
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
            
            -- 儲存並關閉 Keynote 文件
            tell application "Keynote"
                save thisDocument
                delay 2
                close thisDocument
                delay 2
                quit
                delay 2
            end tell
        end repeat
        
        writeLog("處理完成", logFile)
        return input
    on error errMsg
        writeLog("錯誤: " & errMsg, logFile)
        return input
    end try
end run
