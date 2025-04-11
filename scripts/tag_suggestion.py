from typing import Dict
import os
import re
from openai import OpenAI
from dotenv import load_dotenv
import json
import time
from logger import get_workflow_logger

class TagSuggester:
    def __init__(self):
        """初始化 TagSuggester"""
        self.logger = get_workflow_logger('1', 'tag_suggester')
        self.logger.debug("初始化 TagSuggester...")
        
        # 取得專案根目錄
        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        
        # 載入 .env 檔案
        load_dotenv(os.path.join(project_root, 'config', '.env'))
        self.logger.debug("已載入環境變數檔案")
        
        # 檢查環境變數
        api_key = os.getenv("OPENAI_API_KEY")
        assistant_id = os.getenv("ASSISTANT_ID")
        
        if not api_key:
            raise ValueError("請設置 OPENAI_API_KEY 環境變數")
        if not assistant_id:
            raise ValueError("請設置 ASSISTANT_ID 環境變數")
            
        self.logger.debug(f"使用 Assistant ID: {assistant_id}")
        
        self.client = OpenAI(api_key=api_key)
        self.assistant_id = assistant_id
        
    def handle_required_action(self, thread_id: str, run_id: str) -> Dict:
        """處理 requires_action 狀態"""
        # 獲取需要執行的功能
        run = self.client.beta.threads.runs.retrieve(
            thread_id=thread_id,
            run_id=run_id
        )
        
        if not hasattr(run, 'required_action') or not run.required_action:
            self.logger.warning("沒有找到需要執行的動作")
            return {}
            
        tool_calls = run.required_action.submit_tool_outputs.tool_calls
        outputs = []
        
        for tool_call in tool_calls:
            # 根據功能名稱執行對應的操作
            if tool_call.function.name == "suggest_tags":
                outputs.append({
                    "tool_call_id": tool_call.id,
                    "output": tool_call.function.arguments
                })
            else:
                self.logger.warning(f"未知的功能: {tool_call.function.name}")
                outputs.append({
                    "tool_call_id": tool_call.id,
                    "output": "{}"
                })
        
        # 提交功能執行結果
        run = self.client.beta.threads.runs.submit_tool_outputs(
            thread_id=thread_id,
            run_id=run_id,
            tool_outputs=outputs
        )
        
        return self.wait_for_completion(thread_id, run.id)
        
    def wait_for_completion(self, thread_id: str, run_id: str, timeout: int = 60) -> Dict:
        """等待處理完成並返回結果
        
        Args:
            thread_id: 對話的 thread ID
            run_id: 處理的 run ID
            timeout: 超時時間，預設 60 秒
            
        Returns:
            處理結果字典
        """
        start_time = time.time()
        
        while True:
            # 檢查是否超時
            if time.time() - start_time > timeout:
                self.logger.error(f"標籤生成超時，已等待 {timeout} 秒")
                # 返回一個預設的標籤結構，而不是空字典，確保即使超時也能繼續處理
                return {"existing_tags": {"tags": {"general": ["video"]}}}
                
            run = self.client.beta.threads.runs.retrieve(
                thread_id=thread_id,
                run_id=run_id
            )
            
            self.logger.debug(f"目前狀態: {run.status}")
            
            if run.status == "completed":
                messages = self.client.beta.threads.messages.list(
                    thread_id=thread_id
                )
                
                last_message = messages.data[0]
                if last_message.role == "assistant":
                    try:
                        # 記錄原始回應內容以便調試
                        raw_content = last_message.content[0].text.value
                        self.logger.debug(f"原始回應內容: {raw_content}")
                        
                        # 嘗試解析 JSON
                        try:
                            result = json.loads(raw_content)
                            self.logger.debug(f"成功解析 JSON 回應")
                            return result
                        except json.JSONDecodeError:
                            # 如果不是有效的 JSON，嘗試尋找和提取 JSON 部分
                            self.logger.warning("回應不是有效的 JSON，嘗試尋找 JSON 部分")
                            
                            # 尋找可能的 JSON 部分（在 ``` 或 {} 之間）
                            json_pattern = r'```json\s*(.+?)\s*```|\{(.+?)\}'
                            matches = re.findall(json_pattern, raw_content, re.DOTALL)
                            
                            if matches:
                                for match in matches:
                                    json_str = match[0] if match[0] else '{' + match[1] + '}'
                                    try:
                                        result = json.loads(json_str)
                                        self.logger.debug(f"成功從文本中提取和解析 JSON")
                                        return result
                                    except json.JSONDecodeError:
                                        continue
                            
                            # 如果仍然無法解析，創建一個預設的標籤結構
                            self.logger.warning("無法解析任何 JSON，使用預設結構")
                            
                            # 嘗試從文本中提取標籤
                            tags = re.findall(r'["\']([^"\',]+)["\']', raw_content)
                            if tags:
                                self.logger.debug(f"從文本中提取到標籤")
                                return {"existing_tags": {"tags": {"general": tags}}}
                            
                            return {"existing_tags": {"tags": {"general": ["video"]}}}
                    except (IndexError, AttributeError) as e:
                        self.logger.error(f"解析回應時發生錯誤: {str(e)}")
                        return {}
                        
            elif run.status == "requires_action":
                return self.handle_required_action(thread_id, run_id)
                
            elif run.status in ["failed", "expired", "cancelled"]:
                self.logger.error(f"處理失敗，狀態為 {run.status}")
                return {}
                
            time.sleep(1)
        
    def suggest_tags(self, title: str, content: str) -> Dict:
        """根據影片標題和內容生成標籤建議"""
        try:
            self.logger.info("開始生成標籤建議...")
            
            # 建立新的 thread
            thread = self.client.beta.threads.create()
            self.logger.debug(f"Thread ID: {thread.id}")
            
            # 添加訊息
            message = self.client.beta.threads.messages.create(
                thread_id=thread.id,
                role="user",
                content=f"標題：{title}\n內容：{content}"
            )
            self.logger.debug("已添加訊息")
            
            # 開始運行 assistant
            self.logger.debug("開始運行 assistant")
            run = self.client.beta.threads.runs.create(
                thread_id=thread.id,
                assistant_id=self.assistant_id
            )
            
            result = self.wait_for_completion(thread.id, run.id)
            
            # 檢查是否有標籤結果
            if result and "existing_tags" in result:
                tag_count = 0
                # 計算所有標籤數量
                if "tags" in result["existing_tags"]:
                    for category in result["existing_tags"]["tags"].values():
                        if isinstance(category, dict):
                            for subcategory in category.values():
                                if isinstance(subcategory, list):
                                    tag_count += len(subcategory)
                        elif isinstance(category, list):
                            tag_count += len(category)
                
                self.logger.info(f"標籤生成完成，共產生 {tag_count} 個標籤")
            else:
                self.logger.info("標籤生成完成，但沒有產生標籤")
                
            return result
            
        except Exception as e:
            self.logger.error(f"生成標籤時發生錯誤: {str(e)}")
            return {}

if __name__ == "__main__":
    # 測試用例
    suggester = TagSuggester()
    result = suggester.suggest_tags(
        "True To Texas - Let's Bring Productions Home",
        "這是一支由多位德州出身的知名演員共同參與的影片，希望推動德州成為電影和電視製作的新中心。影片中，馬修·麥康納（Matthew McConaughey）與伍迪·哈里森（Woody Harrelson）重現他們在《無間警探（True Detective）》中的角色，兩人駕車穿越德州，討論將影視製作帶回家鄉的可能性。丹尼斯·奎德（Dennis Quaid）也在影片中出現，強調德州擁有豐富的天賦和資源，適合發展影視產業。此外，比利·鮑伯·松頓（Billy Bob Thornton）和芮妮·齊薇格（Renée Zellweger）也透過電話連線的方式參與，表達他們對在德州拍攝的支持。這支影片由《無間警探》創作者尼克·皮佐拉托（Nic Pizzolatto）執導，鼓勵德州立法機構提供新的激勵措施，吸引更多影視製作在德州進行。"
    )
    suggester.logger.info("\n最終結果:")
    suggester.logger.info(json.dumps(result, ensure_ascii=False, indent=2))
