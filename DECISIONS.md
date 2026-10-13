# DECISIONS.md — kw-yt-transcript

## D1: Стек Python-CLI (C4, accepted 2026-10-13)
- **Claim:** Достаточно Python-CLI; Node не нужен несмотря на совет youtube-transcript-plus.
- **Checked:** `python3 --version` → 3.14.7; `yt-dlp --version` → 2026.08.19; librarian lib-1: youtube-transcript-plus = npm-only v2.0.0 Node≥20, нет на PyPI; Python-аналог youtube-transcript-api 1.2.4 (MIT, deps requests+defusedxml).
- **Result:** Совет пользователя частично отклонён по доказательствам (C2): идея «субтитры быстро/бесплатно» принята, конкретная библиотека заменена на Python-эквивалент.
- **Outcome:** accepted — Python, runner-up Node/Bun проиграл (два рантайма, нет плейлистов, yt-dlp embedding Python зрелее).

## D2: Источник транскрипта (accepted)
- **Claim:** Субтитры YouTube primary, Whisper fallback.
- **Checked:** lib-1: ytt-api fetch(languages=['ru','en']) + find_manually_created→generated; formatters SRT/VTT встроены; faster-whisper 1.2.1 CPU int8 без ffmpeg, openai-whisper требует ffmpeg+torch и Python ≤3.11 заявлено.
- **Outcome:** accepted — primary `youtube-transcript-api`, fallback `faster-whisper` (extra `asr`), openai-whisper rejected.
- **Поправка (Python 3.14, live):** faster-whisper 1.2.1 + PyAV ≥ 15 падает (`av.open(metadata_errors=...)` → TypeError); на 3.14 у старого PyAV нет колёс — downgrade не вариант. Обход: системный ffmpeg декодирует аудио в ndarray (float32, 16 кГц), модель принимает его штатно. Пин `av` не требуется.

## D3: Форматы вывода (accepted)
- **Claim:** 5 файлов на видео покрывают «таймкоды + читаемый».
- **Checked:** ytt-api formatters SRT/WebVTT/JSON/Text; whisper сегменты (start,end,text) → те же сериализаторы + своя группировка в абзацы.
- **Outcome:** accepted — `meta.json, transcript.srt/vtt/json/txt/md`.

## D4: Входы широко (accepted)
- **Claim:** Один парсер покрывает single/multi/file/playlist.
- **Checked:** yt-dlp `_type` video vs playlist/multi_video, `extract_flat` True/False; inputs: URL/id regex, split по `[,;\s\n]+`, `--from-file`, playlist expand.
- **Outcome:** accepted.

## D5: Работа без YouTube Data API-ключа (accepted 2026-10-13)
- **Claim:** Утилита не требует API-ключа; файл `~/Рабочий стол/yt-api-key.txt` не читаем и не используем.
- **Checked:** Архитектура (yt-dlp + youtube-transcript-api + faster-whisper) ключа не требует; пользователь явно предпочёл работу без ключа, файл упомянут лишь как запасной.
- **Outcome:** accepted — ключ остаётся опциональным fallback на будущее (SPEC non-goals: Data API v3 опционально позже); секрет-файл нетронут.

## D6: Публичность репозитория (accepted 2026-10-13)
- **Claim:** Навык требует private по умолчанию, но пользователь явно приказал «make public» ради Wiki (ей нужен public/upgrade).
- **Checked:** секрет-аудит перед открытием чист (только упоминание пути к ключу, без значений); `gh repo edit --visibility public --accept-visibility-change-consequences` → PUBLIC.
- **Outcome:** accepted — отклонение от дефолта навыка по явному указанию пользователя, зафиксировано здесь.
