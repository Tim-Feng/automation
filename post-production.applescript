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

        -- 關閉 Aegisub
        tell application "Aegisub"
            quit
        end tell
        delay 5 -- 確保Aegisub完全關閉

        -- 使用 ffmpeg 來處理影片和字幕
        set videoPath to subtitleDirectory & "/" & trimmedName & "-1920*1340." & videoExtension
        set subtitlePath to subtitleDirectory & "/" & newSubtitleName & ".ass"
        set outputPath to subtitleDirectory & "/" & trimmedName & "-1920*1340-zh.mp4"

        -- 執行 ffmpeg 指令
        set ffmpegCommand to "/usr/local/bin/ffmpeg -i " & quoted form of videoPath & " -vf \"ass=" & quoted form of subtitlePath & "\" -c:a copy " & quoted form of outputPath

        try
            do shell script ffmpegCommand
        on error errMsg
            display dialog errMsg buttons {"OK"} default button "OK"
        end try
    end repeat
end run
