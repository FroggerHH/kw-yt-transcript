# TODO.md — kw-yt-transcript

## Фаза 1: Скелет + CLI [ ]
- [ ] pyproject.toml (project kw-yt-transcript 0.1.0, deps yt-dlp, youtube-transcript-api; extra asr faster-whisper; entry kw-yt), пакет kw_yt_transcript/, `kw-yt --help/--version` RU
- [ ] inputs.py (single id/URL, multi split, --from-file, playlist detect) + unit tests (stubs, без сети)
- [ ] Gates: `ruff/black?` → форматтер, `pytest -q` зелёный, `kw-yt --help` работает

## Фаза 2: Метаданные + субтитры [ ]
- [ ] metadata.py (yt-dlp extract_info download=False, sanitize_info, full набор полей) + tests на фикстурах
- [ ] transcript.py + formats.py (fetch ru→en fallback, SRT/VTT/JSON/TXT/MD с абзацами) + tests
- [ ] E2E на фикстуре: одна папка с 5 файлами, таймкоды валидны

## Фаза 3: Batch + Whisper-fallback [ ]
- [ ] outputs.py (папка на видео, index.json, errors.log, exit codes 0/1/2, прогресс)
- [ ] asr.py (lazy faster-whisper, tmp аудио через yt-dlp bestaudio, очистка) + tests со stub-моделью
- [ ] Плейлист N=3 (mock) → N папок + index.json, частичные ошибки не валят всё

## Фаза 4: Качество/упаковка [ ]
- [ ] README.md RU (установка pipx/uv, примеры single/multi/playlist, форматы, Whisper extra) — проверить команды в чистом env (C3)
- [ ] M4 полный прогон: format+lint+type+pytest+реальный --help; M5 изоляция (XDG temp, без сети)
- [ ] Oracle-review x2 до zero-actionable, exhaustion passes 1–8, done check C5

## Future backlog (не делаем)
- Перевод транскрипта, YouTube Data API v3, TUI/Web — причины в SPEC non-goals.
