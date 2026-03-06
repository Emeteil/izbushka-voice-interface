from settings import va
from gemini_engine import BaseTool
from datetime import datetime
from typing import Dict, Any

@va.tool
class GetCurrentTime(BaseTool):
    @property
    def name(self) -> str:
        return "get_current_time"
    
    @property
    def description(self) -> str:
        return "Получить текущую дату и системное время."
    
    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "OBJECT",
            "properties": {},
            "required": []
        }
    
    def execute(self) -> Dict[str, Any]:
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        return {"status": "success", "time": now}