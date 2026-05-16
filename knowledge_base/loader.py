from __future__ import annotations

import json
import os
import re
import threading
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

import yaml


@dataclass(frozen=True)
class KnowledgeFragment:
    section: str
    title: str
    text: str
    keywords: Tuple[str, ...]
    payload: Dict[str, Any]


@dataclass(frozen=True)
class DocumentEntry:
    name: str
    title: str
    path: str
    size_bytes: int

    def to_dict(self) -> Dict[str, Any]:
        return {"name": self.name, "title": self.title, "size_bytes": self.size_bytes}


class KnowledgeBase:
    def __init__(
        self,
        file_path: str,
        docs_dir: Optional[str] = None,
        missing_log_path: Optional[str] = None,
        max_doc_chars: int = 8000,
    ) -> None:
        self._file_path = file_path
        self._docs_dir = docs_dir or os.path.join(os.path.dirname(file_path), "docs")
        self._missing_log_path = missing_log_path
        self._max_doc_chars = max_doc_chars

        self._lock = threading.RLock()
        self._data: Dict[str, Any] = {}
        self._fragments: List[KnowledgeFragment] = []
        self._documents: Dict[str, DocumentEntry] = {}
        self.reload()

    @property
    def file_path(self) -> str:
        return self._file_path

    @property
    def docs_dir(self) -> str:
        return self._docs_dir

    def reload(self) -> None:
        with self._lock:
            with open(self._file_path, "r", encoding="utf-8") as f:
                self._data = yaml.safe_load(f) or {}
            self._fragments = list(self._build_fragments(self._data))
            self._documents = self._scan_documents()

    @property
    def raw(self) -> Dict[str, Any]:
        with self._lock:
            return self._data

    @property
    def university_name(self) -> str:
        return self._data.get("university", {}).get("short_name", "ВУЗ")

    @property
    def university_full_name(self) -> str:
        return self._data.get("university", {}).get("full_name", "")

    def list_programs(self) -> List[Dict[str, Any]]:
        return list(self._data.get("programs", []))

    def list_faculties(self) -> List[Dict[str, Any]]:
        return list(self._data.get("faculties", []))

    def get_program(self, program_id: str) -> Optional[Dict[str, Any]]:
        for p in self.list_programs():
            if p.get("id") == program_id:
                return p
        return None

    def admission_info(self) -> Dict[str, Any]:
        return dict(self._data.get("admission", {}))

    def scores(self, program_id: Optional[str] = None) -> Dict[str, Any]:
        scores = self._data.get("scores", {}) or {}
        if program_id:
            return {program_id: scores.get(program_id)}
        return dict(scores)

    def dormitory(self) -> Dict[str, Any]:
        return dict(self._data.get("dormitory", {}))

    def scholarship(self) -> Dict[str, Any]:
        return dict(self._data.get("scholarship", {}))

    def benefits(self) -> List[str]:
        return list(self._data.get("benefits", []))

    def contacts(self) -> Dict[str, Any]:
        return dict(self._data.get("admission", {}).get("contacts", {}))

    def faq(self) -> List[Dict[str, str]]:
        return list(self._data.get("frequently_asked", []))

    def search(self, query: str, limit: int = 5) -> List[KnowledgeFragment]:
        tokens = _normalize_tokens(query)
        if not tokens:
            return []
        scored: List[Tuple[float, KnowledgeFragment]] = []
        for frag in self._fragments:
            score = _score_fragment(frag, tokens)
            if score > 0:
                scored.append((score, frag))
        scored.sort(key=lambda x: x[0], reverse=True)
        return [f for _, f in scored[:limit]]

    def list_documents(self) -> List[DocumentEntry]:
        with self._lock:
            return list(self._documents.values())

    def read_document(self, name: str) -> Optional[str]:
        with self._lock:
            entry = self._documents.get(self._normalize_doc_name(name))
        if not entry:
            return None
        try:
            with open(entry.path, "r", encoding="utf-8") as f:
                text = f.read()
        except OSError:
            return None
        if len(text) > self._max_doc_chars:
            text = text[: self._max_doc_chars] + "\n\n[...документ обрезан...]"
        return text

    def log_missing(self, question: str, note: Optional[str] = None) -> Dict[str, Any]:
        if not self._missing_log_path:
            return {"logged": False, "reason": "missing_log_path is not configured"}

        entry = {
            "question": (question or "").strip(),
            "note": (note or "").strip() or None,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        if not entry["question"]:
            return {"logged": False, "reason": "empty question"}

        os.makedirs(os.path.dirname(self._missing_log_path) or ".", exist_ok=True)
        with self._lock:
            try:
                with open(self._missing_log_path, "r", encoding="utf-8") as f:
                    items = json.load(f)
                if not isinstance(items, list):
                    items = []
            except (FileNotFoundError, json.JSONDecodeError):
                items = []
            items.append(entry)
            tmp = self._missing_log_path + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(items, f, ensure_ascii=False, indent=2)
            os.replace(tmp, self._missing_log_path)
        return {"logged": True, "entry": entry}

    def _scan_documents(self) -> Dict[str, DocumentEntry]:
        result: Dict[str, DocumentEntry] = {}
        if not os.path.isdir(self._docs_dir):
            return result

        for filename in sorted(os.listdir(self._docs_dir)):
            if not filename.endswith(".md") or filename.startswith("_") or filename.lower() == "readme.md":
                continue
            full_path = os.path.join(self._docs_dir, filename)
            if not os.path.isfile(full_path):
                continue
            name = filename[:-3]
            title = _extract_title(full_path) or name
            result[name] = DocumentEntry(
                name=name,
                title=title,
                path=full_path,
                size_bytes=os.path.getsize(full_path),
            )
        return result

    def _normalize_doc_name(self, name: str) -> str:
        n = (name or "").strip().lower()
        if n.endswith(".md"):
            n = n[:-3]
        return n

    def _build_fragments(self, data: Dict[str, Any]):
        for program in data.get("programs", []) or []:
            kws = tuple(k.lower() for k in program.get("keywords", []))
            text = (
                f"{program.get('title', '')}. "
                f"Степень: {program.get('degree', '')}. "
                f"Срок: {program.get('duration_years', '?')} лет. "
                f"Формы: {', '.join(program.get('forms', []))}. "
                f"Экзамены: {', '.join(program.get('exams', []))}. "
                f"{program.get('description', '')}"
            )
            yield KnowledgeFragment(
                section="program",
                title=program.get("title", program.get("id", "")),
                text=text,
                keywords=kws + (str(program.get("title", "")).lower(),),
                payload=program,
            )

        for item in data.get("frequently_asked", []) or []:
            yield KnowledgeFragment(
                section="faq",
                title=item.get("q", ""),
                text=f"{item.get('q', '')} {item.get('a', '')}",
                keywords=(),
                payload=item,
            )

        for benefit in data.get("benefits", []) or []:
            yield KnowledgeFragment(
                section="benefit",
                title="Льгота",
                text=str(benefit),
                keywords=("льгота", "льготы", "целевое", "олимпиада"),
                payload={"text": benefit},
            )

        adm = data.get("admission", {}) or {}
        if adm:
            schedule = adm.get("schedule", {}) or {}
            contacts = adm.get("contacts", {}) or {}
            yield KnowledgeFragment(
                section="admission",
                title="Приёмная кампания",
                text=(
                    f"Приём документов: с {schedule.get('documents_start', '?')} "
                    f"до {schedule.get('documents_end_budget_no_exams', '?')}. "
                    f"Контакты: {contacts.get('phone', '')}, {contacts.get('email', '')}."
                ),
                keywords=("приём", "сроки", "документы", "поступление"),
                payload=adm,
            )

        dorm = data.get("dormitory", {}) or {}
        if dorm:
            yield KnowledgeFragment(
                section="dormitory",
                title="Общежитие",
                text=(
                    f"Общежитие. Стоимость: {dorm.get('monthly_fee_rub', '?')} руб/мес. "
                    + " ".join(str(n) for n in dorm.get("notes", []))
                ),
                keywords=("общежитие", "общага", "жильё", "иногородним"),
                payload=dorm,
            )

        sch = data.get("scholarship", {}) or {}
        if sch:
            yield KnowledgeFragment(
                section="scholarship",
                title="Стипендии",
                text=(
                    f"Академическая: {sch.get('academic_base', '?')} руб. "
                    f"Социальная: {sch.get('social_base', '?')} руб. "
                    f"Повышенная для первокурсников: {sch.get('enhanced_first_year', '?')} руб. "
                    + " ".join(str(n) for n in sch.get("notes", []))
                ),
                keywords=("стипендия", "стипендии", "выплаты"),
                payload=sch,
            )


_WORD_RE = re.compile(r"[A-Za-zА-Яа-яЁё0-9]+", re.UNICODE)


def _normalize_tokens(text: str) -> List[str]:
    return [t.lower() for t in _WORD_RE.findall(text or "") if len(t) >= 2]


def _score_fragment(frag: KnowledgeFragment, tokens: List[str]) -> float:
    haystack = (frag.title + " " + frag.text).lower()
    score = 0.0
    for tok in tokens:
        if any(tok == kw or tok in kw for kw in frag.keywords):
            score += 3.0
        if tok in haystack:
            score += 1.0
    if frag.section in {"faq", "admission"} and score > 0:
        score += 0.5
    return score


def _extract_title(path: str) -> Optional[str]:
    try:
        with open(path, "r", encoding="utf-8") as f:
            for raw in f:
                line = raw.strip()
                if not line:
                    continue
                if line.startswith("#"):
                    return line.lstrip("#").strip()
                return line[:100]
    except OSError:
        return None
    return None


_INSTANCE_LOCK = threading.Lock()
_INSTANCE: Optional[KnowledgeBase] = None


def init_knowledge_base(
    file_path: str,
    docs_dir: Optional[str] = None,
    missing_log_path: Optional[str] = None,
) -> KnowledgeBase:
    global _INSTANCE
    with _INSTANCE_LOCK:
        _INSTANCE = KnowledgeBase(
            file_path=file_path,
            docs_dir=docs_dir,
            missing_log_path=missing_log_path,
        )
        return _INSTANCE


def get_knowledge_base() -> KnowledgeBase:
    if _INSTANCE is None:
        raise RuntimeError("KnowledgeBase is not initialized. Call init_knowledge_base() first.")
    return _INSTANCE
