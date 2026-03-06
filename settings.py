from dotenv import load_dotenv
from gemini_engine import GeminiVA
from gemini_engine.handlers import DefaultCameraHandler
from wake_word.detector import WakeWordDetector
import yaml, os

with open("settings.yml", "r", encoding="utf-8") as f:
    settings = yaml.load(f, Loader=yaml.FullLoader)

if settings.get('load_dotenv'):
    load_dotenv()

for env in settings.get('environment_variables', []):
    val = os.environ.get(env)
    if val is not None:
        settings[env] = val

storage_folder = settings.get("storage_folder", "storage")
os.makedirs(storage_folder, exist_ok=True)

va = GeminiVA(
    api_key=settings.get("GEMINI_API_KEY") or "",
    system_prompt=settings.get("prompt"),
    model_name="gemini-2.5-flash-native-audio-preview-12-2025",
    memory_path=os.path.join(storage_folder, "gemini_memory.json"),
    log_messages=False,
    verbose=True,
    use_memory=True,
    proxy=settings.get("GEMINI_PROXY"),
    silence_timeout=settings.get("assistant_settings", {}).get("silence_timeout", None),
    enable_ducking=settings.get("assistant_settings", {}).get("enable_ducking", False),
    media_handler=DefaultCameraHandler()
)

detector = WakeWordDetector(
    wakeword_models=settings.get("wake_word_settings").get("model_name"), 
    threshold=settings.get("wake_word_settings").get("threshold"), 
    cooldown_sec=settings.get("wake_word_settings").get("cooldown_sec"), 
    init_delay_sec=settings.get("wake_word_settings").get("init_delay_sec")
)