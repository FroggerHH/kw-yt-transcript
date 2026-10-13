# TODO.md — kw-yt-transcript

## v0.2 Волны (старт 14:31 MSK, дедлайн 17:31 MSK)
## Волна 1: HTML + статистика [x] (done 14:34, 116 passed)
- [x] stats.py (words/chars/reading_time/wpm/top_keywords ru/en стоп-слова) + tests
- [x] report.py (report.html на видео + index.html на batch, кликабельные ?t=, поиск с подсветкой, только stdlib) + tests
- [x] outputs write_video → +report.html +stats в meta.json; write_index → +index.html; MD-шапка со статистикой
- [x] Gates: pytest 116 зелёный, --help exit 0 (stale test_format_filter починен оркестратором)

## Волна 2: Поиск + serve + скорость [x] (done, 147 passed)
- [x] search.py (`kw-yt search <q> --in --context`, ранжирование, exit 0/1) + tests — live: 57 хитов по корпусу
- [x] serve.py (`kw-yt serve DIR [--port]`, stdlib http) + tests (200 на index)
- [x] cli: subcommands search/serve, --jobs N (порядок стабильный), --resume, кэш метаданных TTL, конфиг ~/.config/kw-yt/config.toml
- [x] Gates: pytest 147, serve 200 локально (тест), --resume без сети (тест)
- [ ] Замечание оркестратора в волну 3: warning «конфиг не найден» шумит каждый запуск → молчать при отсутствии, предупреждать только о битом

## Волна 3a: Правки review v0.2 [x] (done 14:46, 159 passed, ruff clean)
- [x] №1–10 oracle fix-list (конфиг-тишина, сильный resume, search O(n), as_completed, serve-warn, direct_count, версии 3.11, resume-дока, общий _mmss, whisper-семафор). №11 keep-as-is.
- [x] Версии унифицированы оркестратором (3.11+ везде, ruff select E/F/W/I/UP, guard с noqa, datetime.UTC). Gates: pytest 159, ruff clean, --help exit 0

## Волна 3b: Релиз 0.2.0 [x] (done, 160 passed, сделано оркестратором напрямую — fixer rate limit)
- [x] README v0.2 (search/serve/jobs/resume/кэш/конфиг/HTML/stats), версия 0.2.0, CHANGELOG
- [x] test_readme: 3 парсера, новые маркеры, тест версии; Gates: pytest 160, ruff clean, --help/search --help exit 0
- [x] Live acceptance п.11: single → exit 0, 7 файлов, report.html 33 таймкод-ссылки; search 38 хитов; serve 200 (1237 bytes)

## Волна 5: Сводный экспорт [x] (done 16:21, 169 passed, оркестратор напрямую)
- [x] export.py + tests/test_export.py (6); cli export; README + test_readme; Gates + live (61 реплика/487 слов)

## Волна 6: Сводная статистика [x] (done 16:27, 173 passed, оркестратор напрямую)
- [x] export.summarize + cli stats (--in/--json, таблица/JSON, exit 0/1/2) + tests/test_stats_cmd.py (3)
- [x] README + SPEC п.14 + ARCH + completion + test_readme (парсер, маркеры); Gates + live (таблица и JSON ok)

## Волна 7: Обложки [x] (done, 176 passed, оркестратор напрямую)
- [x] outputs.fetch_thumbnail + _best_thumbnail_url + write_video (best-effort, thumbnail_file, paths thumb) + report <img>
- [x] Тесты stub/fail/no-thumbs + изоляция обложек: pop thumbnails в helper + stub-opener (fixture info.json URL содержит — честно); README/ARCH/SPEC/CHANGELOG; live: thumbnail.jpg + meta + report exit 0

## Финал review волн 6–7 [x] (done 16:33, 176 passed: span fix, минуты, CHANGELOG, ARCH 7 файлов, SPEC 15, README thumbnail_file — частично оркестратор, доки — fix-3)
- [x] ora-3 fix-list без блокеров отработан полностью; Gates: pytest 176, ruff clean

## Волна 8: Галерея в index.html [x] (done 16:35, 180 passed, fix-3)
- [x] report.render_index: img-колонка 120px lazy при наличии обложки; outputs thumbnail_file в entries (index.json совместим)
- [x] Тесты галереи (4) + ARCH + README; Gates + live: img в index.html корпуса
- [x] Review волны 8 (ora-3 → fix-3): 2 polish без блокеров (is_file-защита, отступ img) — 181 passed, ruff clean

## v0.2 DONE (16:35 MSK, до дедлайна 17:31 — резерв на review волны 8)
- [x] ora-3 fix-list: CHANGELOG волны 4–5; completion ветка export; README exit-коды; валидация сегментов → skipped; atomic-хелпер; ARCH memory-limitation; cli docstring/EXAMPLES; SPEC пп.12–13 + acceptance; тест битых сегментов

## Волна 4: Экспорт + completion [x] (done 16:18, 163 passed, оркестратор напрямую)
- [x] formats jsonl/csv (+реестр FORMATS, filenames, --format choices), тесты round-trip/quoting/empty/header
- [x] contrib/kw-yt-completion.bash + README + тест покрытия; README «7 форматов», live «семью»
- [x] Gates: pytest 163, ruff clean, bash -n ok; live --format all → exit 0, 9 файлов, jsonl/csv валидны

## v0.1 (done)

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
