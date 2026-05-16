from typing import Any, Dict

from gemini_engine import BaseTool
from knowledge_base import get_knowledge_base
from settings import va


@va.tool
class ListDocuments(BaseTool):
    @property
    def name(self) -> str:
        return "list_documents"

    @property
    def description(self) -> str:
        return (
            "Список дополнительных markdown-документов с неструктурированной информацией о СибГУТИ "
            "(например: военный учебный центр, аккредитация, партнёры, студенческая жизнь). "
            "Возвращает имена файлов и их заголовки. Используй, если search_knowledge не дал результата."
        )

    @property
    def parameters(self) -> Dict[str, Any]:
        return {"type": "OBJECT", "properties": {}, "required": []}

    def execute(self) -> Dict[str, Any]:
        docs = get_knowledge_base().list_documents()
        return {
            "status": "success",
            "documents": [d.to_dict() for d in docs],
        }


@va.tool
class ReadDocument(BaseTool):
    @property
    def name(self) -> str:
        return "read_document"

    @property
    def description(self) -> str:
        return (
            "Прочитать полное содержимое одного из дополнительных markdown-документов по имени "
            "(имя без расширения .md, как в list_documents)."
        )

    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "OBJECT",
            "properties": {
                "name": {
                    "type": "STRING",
                    "description": "Имя файла без расширения (например, military-department).",
                }
            },
            "required": ["name"],
        }

    def execute(self, name: str) -> Dict[str, Any]:
        text = get_knowledge_base().read_document(name)
        if text is None:
            return {"status": "not_found", "name": name}
        return {"status": "success", "name": name, "content": text}


@va.tool
class LogMissingInfo(BaseTool):
    @property
    def name(self) -> str:
        return "log_missing_info"

    @property
    def description(self) -> str:
        return (
            "Зафиксировать пробел в базе знаний: задай этот инструмент, если на содержательный "
            "вопрос абитуриента не удалось найти ответ ни через search_knowledge, ни через "
            "list_documents/read_document. Сотрудники приёмной потом пополнят базу."
        )

    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "OBJECT",
            "properties": {
                "question": {
                    "type": "STRING",
                    "description": "Дословный вопрос абитуриента (то, на что не нашлось ответа).",
                },
                "note": {
                    "type": "STRING",
                    "description": "Что именно искал ассистент и какого фрагмента не хватило.",
                },
            },
            "required": ["question"],
        }

    def execute(self, question: str, note: str = "") -> Dict[str, Any]:
        result = get_knowledge_base().log_missing(question=question, note=note)
        return {"status": "success" if result.get("logged") else "skipped", **result}
