-- 假設 Automator 開始時取得的字幕檔案路徑
on run {input, parameters}
    -- 依次處理每一個字幕檔案
    repeat with currentSubtitlePath in input
        set subtitlePath to POSIX path of currentSubtitlePath
        set subtitleDirectory to do shell script "dirname " & quoted form of subtitlePath
        -- 使用單步處理，直接去掉結尾的 -zh.srt
        set trimmedName to do shell script "basename " & quoted form of subtitlePath & " | sed 's/-zh\\.srt$//'"


        -- 動態獲取影片副檔名
        set videoExtension to do shell script "ls " & quoted form of subtitleDirectory & "/" & trimmedName & "-1920*1340.* | head -n 1 | awk -F'.' '{print $NF}'"

        -- Aegisub 操作部分
        tell application "Aegisub"
            activate
            delay 5 -- 等待應用程式打開和檔案加載
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
                    delay 3 -- 等待字幕檔案加載完成

                    -- 全選字幕
                    click menu item "Select All" of menu "Edit" of menu bar 1
                    delay 1 -- 給它一些時間來完成全選操作

                    -- 使用鼠標點擊特定的 XY 座標來展開下拉選單
                    set mouseX to 387
                    set mouseY to 98
                    do shell script "/usr/bin/env osascript -e 'tell application \"System Events\" to click at {" & mouseX & ", " & mouseY & "}'"
                    delay 1 -- 等待選單展開

                    -- 使用鍵盤箭頭向下鍵選擇 "蘋方 1340"
                    key code 125 -- 按下向下箭頭
                    delay 0.5 -- 等待選擇完成
                    key code 36 -- 按下 Enter 鍵選擇模板
                    delay 2 -- 等待模板套用完成

                    -- 儲存檔案時修改檔名
                    keystroke "s" using {command down} -- 模擬 Command+S 來保存文件
                    delay 3

                    -- 刪除預設檔名
                    key code 51 -- 按下 delete 鍵清除整個欄位（假設全選狀態）
                    delay 0.5 -- 增加延遲以確保欄位被完全清空

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
                    delay 3 -- 等待影片加載完成

                    -- 再次儲存檔案
                    keystroke "s" using {command down} -- 模擬 Command+S 來保存影片與字幕的關聯
                    delay 2 -- 等待保存完成
                end if
            end tell
        end tell

        -- 關閉 Aegisub
        tell application "Aegisub"
            quit
        end tell
        delay 5 -- 確保Aegisub完全關閉

        -- 開啟 MacX Video Converter Pro 並載入影片
        tell application "MacX Video Converter Pro"
            activate
            delay 5 -- 等待應用程式完全打開
        end tell

        tell application "System Events"
            tell process "MacX Video Converter Pro"
                -- 清除工作區中的所有影片，確保工作區是空的
                set mouseX to 616
                set mouseY to 146
                do shell script "/usr/local/bin/cliclick m:" & mouseX & "," & mouseY
                delay 1 -- 增加延遲以模擬滑鼠停留的效果

                -- 點擊垃圾桶符號來清除所有影片
                do shell script "/usr/local/bin/cliclick c:" & mouseX & "," & mouseY
                delay 2 -- 等待清除完成

                -- 點擊 "Video" 按鈕來選擇影片
                click button "Video" of group 1 of group 1 of window 1
                delay 3 -- 等待新窗口或對話框打開

                -- 按下 Command+Shift+G 來打開 "前往文件夾" 的輸入框
                keystroke "g" using {command down, shift down}
                delay 2 -- 等待 "前往文件夾" 的輸入框出現

                -- 使用逐字鍵入影片路徑的方式來避免輸入錯誤
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
                delay 2 -- 等待路徑跳轉

                -- 第二次按下回車鍵來打開影片檔案
                keystroke return
                delay 5 -- 增加延遲，等待影片加入完成

                -- 點擊 "Done" 按鈕
                click button "Done" of sheet 1 of window 1
                delay 2

                -- 設定 Load Subtitle 下拉選單的操作
                -- 獲取窗口的大小和位置
                set windowBounds to size of window 1
                set windowPosition to position of window 1
                
                -- 計算 Load Subtitle 下拉選單的絕對位置
                set targetX to (item 1 of windowPosition) + 164
                set targetY to (item 2 of windowPosition) + 164
                
                -- 使用 cliclick 來移動滑鼠到 Load Subtitle 下拉選單的位置
                do shell script "/usr/local/bin/cliclick m:" & targetX & "," & targetY
                delay 1 -- 增加延遲以模擬滑鼠停留的效果
                
                -- 點擊 Load Subtitle 下拉選單
                do shell script "/usr/local/bin/cliclick c:" & targetX & "," & targetY
                delay 1 -- 等待選單展開
                
                -- 移動滑鼠到 Load Subtitle 的選項（向下移動一些）
                set targetY to targetY + 30 -- 向下移動 30 點（可以根據需要調整）
                do shell script "/usr/local/bin/cliclick m:" & targetX & "," & targetY
                delay 1 -- 增加延遲以模擬滑鼠停留的效果
                
                -- 點擊 Load Subtitle 選項
                do shell script "/usr/local/bin/cliclick c:" & targetX & "," & targetY
                delay 2 -- 等待選項被選中
                
                -- 按下 Command+Shift+G 來打開 "前往文件夾" 的輸入框
                keystroke "g" using {command down, shift down}
                delay 2 -- 等待 "前往文件夾" 輸入框出現
                
                -- 定義字幕檔的完整路徑（這次是 `.ass` 檔案）
                set fullSubtitlePath to subtitleDirectory & "/" & newSubtitleName & ".ass"
                
                -- 使用逐字鍵入字幕檔的路徑
                repeat with i from 1 to (count of characters of fullSubtitlePath)
                    if i ≤ 5 then
                        -- 對於前五個字符增加延遲
                        keystroke (character i of fullSubtitlePath)
                        delay 0.3 -- 增加延遲，確保系統接受開頭字符
                    else
                        -- 後續字符正常輸入
                        keystroke (character i of fullSubtitlePath)
                    end if
                end repeat
                delay 2 -- 等待輸入完成
                
                -- 按下回車鍵來確認輸入的路徑
                keystroke return
                delay 3 -- 等待跳轉到指定目錄
                
                -- 按下回車鍵來選擇字幕檔並確認
                keystroke return
                delay 3 -- 等待字幕檔加入完成

                -- 點擊右下角 "RUN" 按鈕開始轉檔
                -- 計算 RUN 按鈕的絕對位置
                set targetX to (item 1 of windowPosition) + 963
                set targetY to (item 2 of windowPosition) + 568
                
                -- 使用 cliclick 來移動滑鼠到 RUN 按鈕的位置
                do shell script "/usr/local/bin/cliclick m:" & targetX & "," & targetY
                delay 1 -- 增加延遲以模擬滑鼠停留的效果
                
                -- 點擊 RUN 按鈕
                do shell script "/usr/local/bin/cliclick c:" & targetX & "," & targetY
                delay 3 -- 等待點擊完成並讓轉碼開始
                
                -- 使用一個 loop 來等待轉檔窗口的消失，表示轉檔完成
                repeat until not (exists (sheet 1 of window 1))
                    delay 5 -- 每隔 5 秒檢查一次轉檔進度窗口是否還存在
                end repeat
                
                -- 移動滑鼠到更大的垃圾桶符號並點擊（位於 616,146）
                set mouseX to 616
                set mouseY to 146
                do shell script "/usr/local/bin/cliclick m:" & mouseX & "," & mouseY
                delay 1 -- 增加延遲以模擬滑鼠停留的效果
                
                -- 點擊垃圾桶符號來清除所有影片
                do shell script "/usr/local/bin/cliclick c:" & mouseX & "," & mouseY
                delay 2 -- 等待清除完成
            end tell
        end tell

        -- 重命名轉檔完成的影片並移動到與字幕相同的目錄
        set originalDir to "/Users/Mac/Movies/Mac Video Library/"
        set originalFileName to trimmedName & "-1920*1340.mp4"
        set originalPath to originalDir & originalFileName
        set newFileName to trimmedName & "-1920*1340-zh.mp4"
        set newFilePath to subtitleDirectory & "/" & newFileName

        do shell script "mv " & quoted form of originalPath & " " & quoted form of newFilePath
    end repeat
end run
