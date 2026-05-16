import os
import yaml
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

kb_cfg = settings.get("knowledge_base", {}) or {}
knowledge = init_knowledge_base(
    file_path=kb_cfg.get("yaml_path", "knowledge_base/sibsutis.yml"),
    docs_dir=kb_cfg.get("docs_dir", "knowledge_base/docs"),
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
    system_prompt=settings.get("prompt"),
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
