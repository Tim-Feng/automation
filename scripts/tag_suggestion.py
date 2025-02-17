from typing import Dict
import os
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
        
    def wait_for_completion(self, thread_id: str, run_id: str) -> Dict:
        """等待處理完成並返回結果"""
        while True:
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
                        result = json.loads(last_message.content[0].text.value)
                        return result
                    except (json.JSONDecodeError, IndexError, AttributeError) as e:
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
            self.logger.debug("開始處理標籤建議")
            
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
            self.logger.info("設置標籤完成")
            return result
            
        except Exception as e:
            self.logger.error(f"發生錯誤: {str(e)}")
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
