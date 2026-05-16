from typing import Any, Dict

from gemini_engine import BaseTool
from knowledge_base import get_knowledge_base
from settings import va


@va.tool
class SearchKnowledge(BaseTool):
    @property
    def name(self) -> str:
        return "search_knowledge"

    @property
    def description(self) -> str:
        return (
            "Поиск по структурированной базе знаний СибГУТИ: направления, проходные баллы, "
            "сроки приёма, общежитие, стипендии, льготы, контакты, FAQ. "
            "Вызывай этот инструмент первым, прежде чем отвечать на любой содержательный вопрос абитуриента. "
            "Если результата нет — обратись к list_documents."
        )

    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "OBJECT",
            "properties": {
                "query": {
                    "type": "STRING",
                    "description": "Свободный запрос — то, что спросил абитуриент или ключевые слова темы.",
                },
                "limit": {
                    "type": "INTEGER",
                    "description": "Максимум фрагментов в ответе (по умолчанию 5).",
                },
            },
            "required": ["query"],
        }

    def execute(self, query: str, limit: int = 5) -> Dict[str, Any]:
        kb = get_knowledge_base()
        fragments = kb.search(query=query, limit=max(1, min(int(limit or 5), 10)))
        if not fragments:
            return {"status": "empty", "results": [], "hint": "Попробуй list_documents и read_document."}
        return {
            "status": "success",
            "results": [
                {
                    "section": f.section,
                    "title": f.title,
                    "text": f.text,
                    "payload": f.payload,
                }
                for f in fragments
            ],
        }
