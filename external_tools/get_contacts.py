from typing import Any, Dict

from gemini_engine import BaseTool
from knowledge_base import get_knowledge_base
from settings import va


@va.tool
class GetContacts(BaseTool):
    @property
    def name(self) -> str:
        return "get_contacts"

    @property
    def description(self) -> str:
        return (
            "Контакты приёмной комиссии СибГУТИ: телефон, email, адрес, сайт. "
            "Вызывай, если абитуриент просит контакты или ты не можешь ответить и нужно "
            "перенаправить к живому сотруднику."
        )

    @property
    def parameters(self) -> Dict[str, Any]:
        return {"type": "OBJECT", "properties": {}, "required": []}

    def execute(self) -> Dict[str, Any]:
        contacts = get_knowledge_base().contacts()
        return {"status": "success", "contacts": contacts}
