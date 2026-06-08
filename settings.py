import os
import yaml
import requests
from dotenv import load_dotenv

from gemini_engine import GeminiVA
from custom_handlers import LoopbackCameraHandler
from wake_word.detector import WakeWordDetector
from knowledge_base import init_knowledge_base
from event_session import EventMemory


with open("settings.yml", "r", encoding="utf-8") as f:
    settings = yaml.load(f, Loader=yaml.FullLoader)

if settings.get("load_dotenv"):
    load_dotenv()

for env in settings.get("environment_variables", []):
    val = os.environ.get(env)
    if val is not None:
        settings[env] = val

storage_folder = settings.get("storage_folder", "storage")
os.makedirs(storage_folder, exist_ok=True)


def _fetch_text(url: str) -> str:
    response = requests.get(url, timeout=10)
    response.raise_for_status()
    return response.text


def _load_remote_knowledge(base_url: str, cache_dir: str):
    base_url = base_url.rstrip("/")
    os.makedirs(os.path.join(cache_dir, "docs"), exist_ok=True)

    yaml_text = _fetch_text(f"{base_url}/sibsutis.yml")
    yaml_path = os.path.join(cache_dir, "sibsutis.yml")

    try:
        yaml.safe_load(yaml_text)
    except yaml.YAMLError as e:
        if os.path.exists(yaml_path):
            print(f"[KB] Скачанный sibsutis.yml невалиден ({e}), используется кэш")
        else:
            raise RuntimeError(f"Скачанный sibsutis.yml невалиден и кэша нет: {e}")
    else:
        with open(yaml_path, "w", encoding="utf-8") as f:
            f.write(yaml_text)

    manifest_text = _fetch_text(f"{base_url}/docs_manifest.txt")
    doc_names = [line.strip() for line in manifest_text.splitlines() if line.strip()]
    for name in doc_names:
        doc_text = _fetch_text(f"{base_url}/docs/{name}")
        with open(os.path.join(cache_dir, "docs", name), "w", encoding="utf-8") as f:
            f.write(doc_text)

    prompt_text = _fetch_text(f"{base_url}/prompt.txt")

    return yaml_path, os.path.join(cache_dir, "docs"), prompt_text


kb_cfg = settings.get("knowledge_base", {}) or {}
repo_url = settings.get("knowledge_base_repo", "").strip()

if repo_url:
    cache_dir = os.path.join(storage_folder, "kb_cache")
    try:
        kb_yaml_path, kb_docs_dir, system_prompt = _load_remote_knowledge(repo_url, cache_dir)
        print(f"[KB] Загружено из GitHub: {repo_url}")
    except Exception as e:
        print(f"[KB] Ошибка загрузки из GitHub ({e}), используются локальные файлы")
        repo_url = ""

if not repo_url:
    kb_yaml_path = kb_cfg.get("yaml_path", "knowledge_base/sibsutis.yml")
    kb_docs_dir = kb_cfg.get("docs_dir", "knowledge_base/docs")
    local_prompt_path = kb_cfg.get("prompt_path", "knowledge_base/prompt.txt")
    if os.path.exists(local_prompt_path):
        with open(local_prompt_path, "r", encoding="utf-8") as f:
            system_prompt = f.read()
    else:
        system_prompt = settings.get("prompt", "")

knowledge = init_knowledge_base(
    file_path=kb_yaml_path,
    docs_dir=kb_docs_dir,
    missing_log_path=kb_cfg.get("missing_log_path", os.path.join(storage_folder, "missing_info.json")),
)

mem_cfg = settings.get("event_memory", {}) or {}
event_memory = EventMemory(
    facts_path=mem_cfg.get("facts_path", os.path.join(storage_folder, "event_facts.json")),
    session_idle_reset_sec=mem_cfg.get("session_idle_reset_sec", 45),
    max_history_messages=mem_cfg.get("max_history_messages", 40),
    log_messages=True,
)

va = GeminiVA(
    api_key=settings.get("GEMINI_API_KEY") or "",
    system_prompt=system_prompt,
    model_name="gemini-2.5-flash-native-audio-preview-12-2025",
    memory_path=os.path.join(storage_folder, "_unused_legacy_memory.json"),
    log_messages=False,
    verbose=True,
    use_memory=True,
    proxy=settings.get("GEMINI_PROXY"),
    silence_timeout=settings.get("assistant_settings", {}).get("silence_timeout", None),
    enable_ducking=settings.get("assistant_settings", {}).get("enable_ducking", False),
    media_handler=LoopbackCameraHandler(
        url=f"http://127.0.0.1:80/api/webcam/stream?token={settings.get('MASTER_TOKEN')}"
    ),
)

va.memory = event_memory

detector = WakeWordDetector(
    wakeword_models=settings.get("wake_word_settings").get("model_name"),
    threshold=settings.get("wake_word_settings").get("threshold"),
    cooldown_sec=settings.get("wake_word_settings").get("cooldown_sec"),
    init_delay_sec=settings.get("wake_word_settings").get("init_delay_sec"),
)
