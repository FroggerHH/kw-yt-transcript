# STATUS.md — kw-yt-transcript

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
- [ ] Oracle-review раунд 4 (final): zero-new-items подтверждение → done check C5 → `Exhaustion reached`.

## Next
1. Коммит A–J + docs, ora-4 final.
2. Done check C5, финальный отчёт. Whisper-live (скачивание аудио + faster-whisper) — опционально, модель тяжёлая; остаётся user-side.

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
