# TODO.md — kw-yt-transcript

## Фаза 1: Скелет + CLI [x] (done 2026-10-13, 9ae4d9b)
- [x] pyproject.toml (project kw-yt-transcript 0.1.0, deps yt-dlp, youtube-transcript-api; extra asr faster-whisper; entry kw-yt), пакет kw_yt_transcript/, `kw-yt --help/--version` RU
- [x] inputs.py (single id/URL, multi split, --from-file, playlist detect) + unit tests (stubs, без сети)
- [x] Gates: `python3 -m kw_yt_transcript --help` RU exit 0, `--version` 0.1.0, `pytest -q` 14 passed

## Фаза 2: Метаданные + субтитры [x] (done 2026-10-13)
- [x] metadata.py (yt-dlp extract_info download=False, sanitize_info, full набор полей) + tests на фикстурах
- [x] transcript.py + formats.py (fetch ru→en fallback, SRT/VTT/JSON/TXT/MD с абзацами) + tests
- [x] E2E на фикстуре: 38 passed, SRT таймкоды валидны

## Фаза 3: Batch + Whisper-fallback [x] (done 2026-10-13)
- [x] outputs.py (папка на видео, index.json, errors.log, exit codes 0/1/2, прогресс)
- [x] asr.py (lazy faster-whisper, tmp аудио через yt-dlp bestaudio, очистка) + tests со stub-моделью
- [x] Плейлист N=3 (mock) → N папок + index.json, частичные ошибки не валят всё (61 passed)

## Фаза 4: Качество/упаковка [x] (done 2026-10-13)
- [x] README.md RU (установка pipx/uv, примеры single/multi/playlist, форматы, Whisper extra) — локальные команды проверены (C3), live-check оставлен user-side
- [x] M4 полный прогон: pytest 66 passed + --help/--version exit 0; M5 изоляция (XDG temp, stubs, аудит без сети)
- [x] Oracle-review раунд 1 (ora-1): verdict fix-list, 15 findings, блокеров нет.
- [x] Findings fix (fix-1): все 15 отработаны (п.13 осознанно без изменений), 72 passed.
- [x] Oracle-review раунд 2 (ora-1): nothing actionable.
- [x] Oracle-review раунд 3 (ora-1): nothing actionable (второй consecutive clean — условие exhaustion по review выполнено) + 7 improvement-предложений с верификацией.
- [x] Exhaustion lanes: ora-3 clean (второй consecutive) + 7 предложений; exp-1 10 предложений; live-check находка (английский ModuleNotFoundError без deps).
- [x] Exhaustion fix (fix-1): A–J внедрены, 100 passed (72+28), ruff E/F/W/I/UP чист.
- [x] Packaging smoke: clean venv pip install . → kw-yt 0.1.0, --help exit 0, pip check чисто.
- [x] Live end-to-end: Never Gonna Give You Up → exit 0, 6 файлов, origin manual lang en, индекс ok (evidence в STATUS).
- [x] Oracle-review раунд 4 (final, ora-1): nothing actionable (третий consecutive clean).
- [x] Done check C5: все acceptance SPEC — с доказательствами (см. STATUS Exhaustion reached).
- Принято: A.meta/index enrichment (transcript_lang, fetched_at, tool_version, asr_model, playlist_url); B.дедуп входов; C.атомарная запись; D.нормализация langs; E.мусор→partial entries exit 1; F.hint_id упавших + счёт пропущенных плейлиста; G.ранняя валидация опций/файла; H.русские hints missing-deps + ffmpeg-preflight; I.stderr-консистентность + пустой from-file→index + readonly-тест; J.ruff select + тесты пробелов.
- Rejected: resume-skip готовых папок (меняет семантику без флага); _VIDEO_ID_RE dedup (решено в round1 п.13); новые флаги; перевод/Data API/TUI.

## Future backlog (не делаем)
- Перевод транскрипта, YouTube Data API v3, TUI/Web — причины в SPEC non-goals.
