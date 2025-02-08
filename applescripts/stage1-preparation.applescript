-- 日誌記錄函數
on writeLog(level, message)
    set scriptPath to "/Users/Mac/GitHub/automation/scripts/log_bridge.py"
    set stage to "1"
    set component to "preparation"
    
    try
        do shell script "python3 " & quoted form of scriptPath & " " & stage & " " & level & " " & quoted form of message & " " & component
    on error errMsg
        -- 如果日誌記錄失敗，使用基本的 stderr 輸出
        do shell script "echo 'Log Error: " & errMsg & "' >&2"
    end try
end writeLog

-- 檢查必要的環境變數
on checkEnvironment()
    try
        set envPath to "/Users/Mac/Library/Mobile Documents/com~apple~Automator/Documents/.env"
        
        -- 檢查 Google Sheets API 相關
        set requiredVars to {"GOOGLE_APPLICATION_CREDENTIALS", "REFRESH_TOKEN", "CLIENT_ID", "CLIENT_SECRET"}
        
        -- 檢查 WordPress API 相關
        set end of requiredVars to "WP_SITE_URL"
        set end of requiredVars to "WP_USERNAME"
        set end of requiredVars to "WP_APP_PASSWORD"
        
        repeat with varName in requiredVars
            set checkCommand to "grep '^" & varName & "=' " & quoted form of envPath
            try
                do shell script checkCommand
            on error
                error "找不到必要的環境變數：" & varName
            end try
        end repeat
        
        return true
    on error errMsg
        my writeLog("ERROR", "環境檢查失敗：" & errMsg)
        return false
    end try
end checkEnvironment

on run {input, parameters}
    -- 開始執行
    my writeLog("INFO", "開始執行內容處理流程")
    
    -- 檢查環境變數
    if not my checkEnvironment() then
        display dialog "環境變數檢查失敗，請確認設定" buttons {"確定"} default button "確定" with icon stop
        return
    end if
    
    try
        set pythonPath to "/Library/Frameworks/Python.framework/Versions/3.11/bin/python3"
        set scriptPath to "/Users/Mac/GitHub/automation/scripts/pre_production_pipeline.py"
        
        set shellCommand to quoted form of pythonPath & " " & quoted form of scriptPath
        
        set pipelineOutput to do shell script shellCommand
        
        my writeLog("SUCCESS", "Pipeline 執行完成")
        
        display notification "內容處理完成" with title "成功"
        
        return input
    on error errMsg
        my writeLog("ERROR", "Pipeline 執行失敗：" & errMsg)
        display dialog "處理過程發生錯誤，請查看日誌了解詳情" buttons {"確定"} default button "確定" with icon stop
        error errMsg
    end try
end run