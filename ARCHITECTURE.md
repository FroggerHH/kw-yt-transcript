# ARCHITECTURE.md — kw-yt-transcript

## Решение (C4): Python-CLI
- **Выбор:** Python 3.10+ (в системе 3.14.7), `pipx`/`uv` установка, entry point `kw-yt`.
- **Runner-up:** Node/Bun-CLI + `youtube-transcript-plus@2.0.0` — отклонён: npm-пакет Node-only, нет плейлистов, метаданные всё равно через yt-dlp (Python-embedding зрелее), Whisper-экосистема Python stronger. Детали в `DECISIONS.md`.
- **Зависимости (pin в pyproject):** `yt-dlp>=2026.8.19`, `youtube-transcript-api==1.2.4`, `faster-whisper==1.2.1` (опциональный extra `asr`), stdlib остальное (argparse, json, re, pathlib).

## Слои
```
kw_yt_transcript/
  cli.py         — argparse (RU), коды выхода 0/1/2, прогресс batch
  inputs.py      — входы → список задач: single URL/id | CSV/space/newline | --from-file | playlist URL
  metadata.py    — yt-dlp YoutubeDL.extract_info(download=False); sanitize_info; _type video vs playlist
  transcript.py  — YouTubeTranscriptApi().list() → find_transcript(langs) → fetch() → to_raw_data; is_generated → origin manual/auto
  asr.py         — lazy faster-whisper fallback (WhisperModel small/int8, vad_filter); интерфейс segments(start,duration,text)
  formats.py     — свои сериализаторы SRT/VTT (таймкоды HH:MM:SS,mmm / HH:MM:SS.mmm совместимы с formatters); TXT/MD читаемый (группировка по паузам >2с / ~800 символов в абзац)
  outputs.py     — <out>/<slug>_<id>/meta.json + transcript.{srt,vtt,json,txt,md}; index.json {_type, entries, failed}; ошибки — в entries[].error + stderr
tests/           — stubs yt-dlp/transcript/whisper, без сети (M5: XDG temp, PATH stubs, no network)
```

## Поток данных
1. `inputs.parse(args)` → `jobs: list[VideoJob{id, source}]` (playlist → flat extract → expand, full extract per video).
2. `metadata.get(job)` → dict (title, channel, duration, upload_date, view/like, description, chapters, thumbnails, tags, subtitles list).
3. `transcript.get(video_id, langs)` → segments + origin {manual|auto|whisper|none}.
4. `formats.*` → 5 файлов. Нет субтитров → `asr.transcribe(audio via yt-dlp bestaudio tmp)` или понятная ошибка + инструкция.
5. `outputs.write()` → папки + `index.json {_type, entries, failed}`. Частичные ошибки: exit 1, остальные готовы.

## Ключевые решения
- Различие video/playlist по `info['_type']`; flat для оглавления, full для метаданных.
- Fallback языков `ru→en→first available` через `languages=[...]` + `TranscriptList` при `NotAvailableLanguage`.
- Читаемый текст: склейка сегментов, разбивка на абзацы по паузе/д Schlange, MD с header (title/channel/date/origin) + главы если есть.
- Whisper — опциональный extra, lazy import, временное аудио чистится.
- Свои сериализаторы SRT/VTT вместо youtube_transcript_api.formatters: форматтерам нужны FetchedTranscript-объекты, а у нас плоские dict-сегменты {text, start, duration}; таймкоды совпадают.
- Сеть только в `metadata`/`transcript`/`asr` + `cli.expand_playlist` (flat extract оглавления); тесты мокают.
