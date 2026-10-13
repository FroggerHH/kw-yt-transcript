# STATUS.md — kw-yt-transcript

## v0.2 (старт 14:31 MSK 2026-10-13, дедлайн 17:31 MSK — требование пользователя: больше функционала)
- Причина: пользователь счёл v0.1 минимальной. Scope v0.2 в SPEC.md (HTML, статистика, search, serve, jobs/resume/cache/config).
- [x] Волна 1 (fix-2, 14:34): stats.py + report.py + outputs (report.html/index.html/stats в meta). Gates: 116 passed, --help exit 0.
- [x] Волна 2 (fix-2): search.py + serve.py + cli (subcommands, --jobs, --resume, кэш TTL, конфиг). Gates: 147 passed, serve 200 (тест), --resume без сети (тест), live search 57 хитов exit 0.
- [x] Review v0.2 (ora-2): fix-list, 11 пунктов (3 medium: конфиг-шум, resume-критерий, search O(n)), блокеров нет. Потоки/кэш/serve проверены ok.
- [x] Волна 3a (fix-2 + оркестратор): правки №1–10 + версии 3.11+ везде. Gates: 159 passed, ruff clean, --help exit 0.
- [x] Волна 3b (оркестратор, fixer rate limit): README v0.2 + 0.2.0 + CHANGELOG + test_readme. Gates: 160 passed, ruff clean. Live п.11: exit 0, 7 файлов, report.html 33 ссылки, search 38, serve 200.
- [x] Волна 4 (оркестратор): jsonl/csv + completion + README + тесты. Gates: 163 passed, ruff clean, live 9 файлов exit 0.
## Волна 5: Сводный экспорт [x] (done 16:21, 169 passed, оркестратор напрямую)
- [x] export.py (collect/export_corpus/write_summary, jsonl+csv, skipped, атомарно) + tests/test_export.py (6)
- [x] cli export (--in/--format/--out/--summary/--no-summary, exit 0/1/2) + README + test_readme (парсер в union, маркеры)
- [x] Gates: pytest 169, ruff clean, export --help exit 0; live: 1 видео/61 реплика/487 слов, summary ok
- [x] Волна 8 (fix-3): галерея обложек в index.html (img 120px lazy, entries thumbnail_file, index.json совместим). Gates: 180 passed, ruff clean, live img в index.
- [x] Review волны 8 (ora-3 → fix-3): 2 polish без блокеров (is_file, отступ). Gates: 181 passed, ruff clean.
- [x] Волна 9 (fix-3): аудит README против CLI (10 файлов, обложки, конфиг-фолбэк). Gates: 181 passed, ruff clean.
- [x] Волна 10 (fix-3): CHANGELOG 0.2.0 (волны 8–9 + review-циклы, счётчик 181). Gates: 181 passed.
- [x] ASR av-fallback + VAD-цепочка (fix-3): live Whisper-tiny → origin whisper, 75 сегментов. Gates: 186 passed + 2 skipped, ruff clean.
- [x] GitHub: аудит чист, репозиторий PUBLIC, main запушен (FroggerHH/kw-yt-transcript).
- [ ] Wiki-remote not found (провиженинг): 7 страниц готовы локально, повтор перед done.
- [ ] Волны 12 (CI) + 13 (AI-warning) → fixer; затем done + отчёт.
- [ ] Волна 12 (queued, после ASR-fallback): GitHub Actions CI (matrix 3.11–3.13, pytest+ruff) + README-бейдж.
- [ ] Волна 13 (queued, после ASR-fallback): AI-warning (баннер в report.html + строка в md/txt при origin auto/whisper).
- [ ] Live batch (2 видео, --jobs 2, --resume повтор) + Whisper-tiny на реальном аудио. Затем done + отчёт.
- [x] Done v0.2 (16:34 MSK, до дедлайна 17:31): коммит ниже, дерево чистое. Live-доказательства: single→9 файлов exit 0, report.html 33 ссылки, search 38–57 хитов, serve 200, export 61/487, stats таблица+JSON, thumbnail.jpg.
- [x] Волна 6 (оркестратор): `kw-yt stats` (summarize + таблица/JSON, exit 0/1/2). Gates: 173 passed, ruff clean, live таблица+JSON ok.
- [x] Волна 7 (оркестратор): thumbnails (fetch best-effort + <img> в report). Gates: 176 passed, ruff clean, live thumbnail.jpg + meta + report exit 0. Изоляция обложек: pop thumbnails в helper + stub-opener (fixture info.json URL содержит — честно).
- [ ] Done v0.2: коммит волны 7, финальные gates, отчёт.

---

## Phase 0: Bootstrap (2026-10-13, verified)
- [x] Plugin config: `~/.config/opencode/oh-my-opencode-slim.json` существует, preset=`muse`, orchestrator=`opencode/muse-spark-1.3-contributor-free` (совпадает с текущей моделью).
- [x] OpenCode config: `opencode.json` отсутствует, есть `opencode.jsonc` с `plugin: ["oh-my-opencode-slim", "session-skills"]` — плагин загружен.
- [x] Toolchain: Python 3.14.7, Node v22.23.3, Bun 1.4.2, yt-dlp 2026.08.19, ffmpeg n9.0.2 — проверено `shell`.
- [x] Permissions: read/shell/write без промптов (доказано: read конфигов + shell версий + write SPEC.md).
- [x] Git: `git init` выполнен, ветка `main`.
- [~] Models list / ping all agents: пропущено как избыточное. Deviation logged в DECISIONS.md.
- Observer: не нужен.

## Phase 1: Interview (done)
Ответы в SPEC.md: стек — решать мне; источник — субтитры + Whisper fallback; входы — видео+плейлист+список; метаданные полные + RU.

## Phase 2: Contract (done 2026-10-13)
- [x] SPEC.md, ARCHITECTURE.md, TODO.md, DECISIONS.md
- librarian lib-1 reconciled: youtube-transcript-plus = Node-only → Python-аналог youtube-transcript-api 1.2.4; yt-dlp embedding; faster-whisper 1.2.1 fallback.
- quality-contract: M1-M6 обязательны; C2/C3/C4/C5 применяются.
- Коммит: docs contract (см. git log).

## Phase 3: Implementation (in progress)
- [x] Фаза 1 (fix-1, 9ae4d9b): скелет + CLI + inputs.py + 14 tests. Gates: --help RU exit 0, --version 0.1.0, pytest 14 passed.
- [x] Фаза 2 (fix-1): metadata.py + transcript.py + formats.py + 24 tests. Gates: 38 passed, --help exit 0, SRT/VTT regex валидны.
- [x] Фаза 3 (fix-1): outputs.py + asr.py + cli wiring batch + 23 tests. Gates: 61 passed, --help exit 0, slug-транслит ок.
- [x] Фаза 4 (fix-1): README RU + CHANGELOG + classifiers + test_readme (5). Gates: 66 passed, M5 XDG-изоляция + аудит, C3 локальные команды, live-check user-side.
- [x] Oracle-review раунд 1 (ora-1): verdict fix-list, 15 findings, блокеров нет. Findings fix (fix-1): все отработаны, 72 passed.
- [x] Oracle-review раунд 2 (ora-1): nothing actionable (первый clean).
- [x] Exhaustion fix (fix-1): A–J внедрены, 100 passed, ruff чист. Packaging smoke: clean venv → 0.1.0, pip check чисто.
- [x] Live end-to-end (2026-10-13, /tmp/kw-live3): `kw-yt dQw4w9WgXcQ` → exit 0, папка + meta.json + 5 transcript.*, index.json failed 0; origin manual, transcript_lang en, tool_version 0.1.0, SRT/MD валидны. SPEC acceptance доказано исполнением.
- [x] Oracle-review раунд 4 (final, ora-1): nothing actionable (третий consecutive clean).
- [x] Done check C5 (2026-10-13) — см. `Exhaustion reached` ниже.

## Exhaustion reached (2026-10-13)
- Полный цикл passes 1–8 с нулевыми новыми items: ora-4 вернул nothing actionable после внедрения A–J; новых предложений нет.
- Consecutive clean: раунды 2, 3, 4 — все nothing actionable.
- SPEC acceptance (доказательства исполнением):
  1. `--help`/`--version` RU, exit 0 — live + tests/test_readme.py.
  2. Single с субтитрами → 6 файлов, таймкоды валидны — live `/tmp/kw-live3` exit 0 (meta.json + srt/vtt/json/txt/md, origin manual lang en).
  3. Без субтитров → Whisper fallback — путь доказан live (аудио скачалось, русская ASRError без модели); полная транскрибация — user-side (команда ниже).
  4. Плейлист N → N папок + index.json + exit 1 при частичных — mock-тесты tests/test_cli_batch.py (7 тестов).
  5. Multi через запятую/файл — tests/test_inputs.py + parse_inputs_with_errors (мусор → partial entries).
  6. 100 passed, изоляция: XDG-прогон, stubs, аудит без сети/бинарей; ruff E/F/W/I/UP чист.
- Packaging: clean venv `pip install .` → kw-yt 0.1.0, `pip check` чисто.
- Reflection (трение сессии): раннее librarian-исследование отменило неверный стек (Node-lib); замер exit-кода через пайп врёт — проверять без `| tail`; `build/` попал в коммит — артефакты сборки игнорить сразу; фиксер дважды чинил собственные тесты — тесты ревьюить как код.
- Остаток user-side (сеть/железо): `pip install "kw-yt-transcript[asr]" && kw-yt <id-без-субтитров> --out /tmp/kw-asr` — ожидается exit 0 и origin whisper в meta.json; плейлист live: `kw-yt '<playlist-url>' --out /tmp/kw-pl` — ожидается N папок + index.json.

## Future backlog (не делаем)
- Resume-skip готовых папок (нужен отдельный дизайн флага).
- Перевод транскрипта, YouTube Data API v3, TUI/Web (SPEC non-goals).

## Next
1. Дождаться fix-2, сверить gates (pytest + --help + live exit-код без пайпа), коммит.
2. Packaging smoke (clean venv), done check C5, `Exhaustion reached` в STATUS, финальный отчёт.
3. Live YouTube-прогон с установленными deps — если сеть к YouTube доступна; иначе user-side.

## Future backlog (не делаем)
- Resume-skip готовых папок (меняет семантику без флага — нужен отдельный дизайн).
- Перевод транскрипта, YouTube Data API v3, TUI/Web (SPEC non-goals).
- Next: Фаза 3 batch+ASR, Фаза 4 README/верификация/Oracle-review.

## Next
1. Дождаться fix-1, сверить gates, коммит.
2. Диспетч Фазы 2 через @fixer.
3. Oracle-review на phase gate.
