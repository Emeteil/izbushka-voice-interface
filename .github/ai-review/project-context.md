# Project context
`izbushka-voice-interface` — сервис голосового ассистента робота «Избушка»: детектирует ключевое слово, ведёт диалог через Gemini Live API, ищет ответы в базе знаний и обменивается статусами с `izbushka-web-core`.

## What to review and what to ignore
Ревьюить: `main.py`, `voice_link.py`, `custom_handlers.py`, `event_session/`, `external_tools/`, `knowledge_base/`, `settings.py`.
Игнорировать: `.github/`, CI-конфиги, сабмодули `gemini_engine` и `wake_word` (независимые репозитории с legacy-кодом), `__pycache__`, `storage/*.json` (рантайм-данные), `wake_word_models/` (бинарные ONNX-модели), `sounds/` (аудиоассеты).
Если в диффе нет ревьюабельного кода — так и напиши в summary, не выдумывай замечания.

## Always read the PR description and comments
Перед ревью прочитай PR DESCRIPTION из PR / GIT CONTEXT и комментарии в pr-comments/others/. Не поднимай повторно то, что там уже решено или объяснено; объяснение снимает придирку, но не отменяет реальный баг.

## Stack
Python, асинхронная модель событий (asyncio/websockets), Google Gemini Live API (через сабмодуль `gemini_engine`), openWakeWord/ONNX (через сабмодуль `wake_word`), sounddevice/scipy для аудио, PyYAML для конфигов.

## Code style
В соседнем `izbushka-web-core` CI использует flake8 с `--max-line-length=120`; в этом репозитории ориентируйся на те же общие правила проекта (PEP8, ограничение длины строки ~120), если явного CI-конфига для flake8 в этом репо нет — не придирайся жёстко к стилю без явного правила.

## Architecture and patterns
- `wake_word/` (сабмодуль) — детектор ключевого слова: ресемплинг аудио в 16 кГц, порог `threshold=0.5`.
- `gemini_engine/` (сабмодуль) — WS-клиент к Gemini Live API (`assistant.py`, `gemini_client.py`, `memory.py`), захват микрофона/динамика, `LoopbackCameraHandler` для передачи кадров с камеры web-core.
- `event_session/event_memory.py` — посессионная память диалога с автосбросом через `session_idle_reset_sec` (45 сек), резюме сохраняется в `storage/event_facts.json`, не подмешивается в следующий системный промпт.
- `knowledge_base/loader.py` — скоринговый поиск по базе знаний (без векторных БД).
- `voice_link.py` — WebSocket-клиент к `izbushka-web-core`, при `production=True` блокирует запуск детектора до подтверждения соединения.

## Dependencies on other parts of the system
- WebSocket VoiceLink к [izbushka-web-core](https://github.com/Emeteil/izbushka-web-core) (`ws://.../api/voice/link?token=...`), события `voice.status_changed`, `voice.message`, `voice.tool_call/result`, `voice.error`, `voice.trigger`, `voice.stop`.
- Получение JPEG-кадров камеры от web-core через loopback для передачи в Gemini.
- Поиск по базе знаний [izbushka-knowledge-base](https://github.com/Emeteil/izbushka-knowledge-base) (YAML + Markdown).
- Сабмодули: [gemini_engine](https://github.com/Emeteil/gemini_engine), [wake_word](https://github.com/Emeteil/wake_word).

## Review checklist
- Изменение состава/формата событий `voice.*`, отправляемых/ожидаемых по WebSocket, без синхронизации с обработчиками в `izbushka-web-core` — отметить явно.
- Изменение структуры карточек знаний/полей скоринга без соответствия формату `sibsutis.yml` в `izbushka-knowledge-base`.
- Новая зависимость в коде без добавления в `requirements.txt`.
- Утечка контекста между сессиями пользователей (нарушение изоляции `EventMemory`) — критично, т.к. на мероприятии разные абитуриенты не должны видеть чужие данные.
- Блокирующие синхронные вызовы (аудио I/O, сеть) в асинхронном коде основного цикла.
- Хардкод API-ключей Gemini/токенов вместо чтения из `.env`/`settings.yml`, либо их логирование.
- Изменения таймаутов (`session_idle_reset_sec`, `production` wait) — проверить, что не ломают договорённость по lifespan с web-core.
