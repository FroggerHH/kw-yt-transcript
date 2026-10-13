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

## Волна 9: Аудит README [x] (done 16:38, 181 passed, fix-3)
- [x] Разрывы закрыты: 10 файлов в live-check, обложки в «Что умеет», конфиг-фолбэк дефолтов; маркеры расширены
- [x] Gates: pytest 181, ruff clean; только README + test_readme
- [x] ora-3 fix-list: CHANGELOG волны 4–5; completion ветка export; README exit-коды; валидация сегментов → skipped; atomic-хелпер; ARCH memory-limitation; cli docstring/EXAMPLES; SPEC пп.12–13 + acceptance; тест битых сегментов

## Волна 10: CHANGELOG [x] (done, 181 passed, fix-3)
- [x] Запись 0.2.0: волны 8–9 + review-циклы, счётчик 181; grep «Волна» = 9

## Волна 17: Wiki-зеркало sync [x] (done 17:12, 191 passed, fix-3)
- [x] 6/7 страниц вровень с волнами 12–16 (CI/uv/AI/EN/badges); формат коротких страниц сохранён
- [x] Gates: pytest 191, readme-smoke 9 passed; только docs/wiki/

## Волна 19: Хранилище + report-хаб [x] (done 17:39, 207 passed, fix-3)
- [x] storage.py (library_path XDG, resolve флаг>конфиг>библиотека); config out убран из DEFAULTS
- [x] cli library (таблица/JSON) + clean (ID/--all --yes/--older-than/--cache, --all без --yes → exit 2)
- [x] report-хаб: Текст первым, По времени/Файлы (details, относительные download-ссылки на все файлы), поиск по обеим секциям
- [x] Tests 16 новых (storage 11, report 4, batch 1) + test_speed дефолты; Gates: pytest 207, ruff clean, library exit 0 на XDG-tmp
- [x] 30-минутное обязательство: волна в работе и доведена до зелёных gates + live-библиотека (17:39)
- [ ] storage.py: library_path() (XDG_DATA_HOME/kw-yt/library, fallback ~/.local/share); out по умолчанию = библиотека (--out/конфиг перекрывают)
- [ ] cli library (список: название/id/дата/размер, --json) + clean (--all | ID... | --older-than D, [--cache], подтверждение? нет — явные флаги достаточно)
- [ ] report.html редизайн UX-first: сначала human-readable текст; вкладки Текст/По времени/Файлы (ссылки на ВСЕ артефакты, относительные, file:// ok); поиск по обоим видам
- [ ] tests: дефолт-библиотека (XDG tmp), library/clean unit + CLI exit-коды, report-хаб (порядок: текст раньше таймкодов; ссылки на все файлы), README/ARCH/SPEC-консистентность
- [ ] Gates: pytest зелёный (миграция дефолта --out не должна сломать старые тесты — обновить консистентно), ruff чисто, live: fetch без --out → библиотека, report открывается с текстом первым
- [ ] Live-видео от пользователя (после волны 19): `https://www.youtube.com/watch?v=DbWL6Zs2j_g` — полный прогон + report-хаб + библиотека

## Волна 20: Цветной вывод [ ] (queued, ПОСЛЕ волны 19 — правит cli.py/help)
- [ ] Проблема: `uv tool install` даёт бесцветный --help (argparse без цветов везде). Решение stdlib-ANSI: подсветка help (usage/секции/опции) + прогресс/ok/fail; TTY-детект, NO_COLOR + --no-color, пайп — без цветов
- [ ] tests: цвета на TTY-стабе, тишина на пайпе/NO_COLOR; README-строка; Gates: pytest зелёный

## Волна 21: Фрагменты видео [ ] (queued, ПОСЛЕ волн 19–20 — трогает cli.py/formats/outputs)
- [ ] `--from SEC --to SEC` (mm:ss/секунды) на fetch: обрезка сегментов по диапазону (границы клиппаются), meta-поле section, отдельная папка с суффиксом, пометка в report
- [ ] tests: клиппинг unit + CLI exit-коды; README/ARCH/completion; Gates: pytest зелёный, ruff чисто

## Волна 22: AI-agent skill [ ] (queued, ПОСЛЕ волн 20–21 — README правится многими)
- [ ] SKILL.md (Agent Skills spec: name/description/frontmatter): когда использовать kw-yt (транскрипты для анализа, RAG-корпус, поиск), как (команды, exit-коды, форматы, без API-ключа, origin-маркировка), примеры
- [ ] tests/test_skill.py (файл + frontmatter + ключевые команды); README-ссылка — отдельным коммитом оркестратора после всех волн; Gates: pytest зелёный
- [x] v0.1 → v0.2.0: 18 волн, 191 passed + 2 skipped, ruff чисто, всё запушено (FroggerHH/kw-yt-transcript, PUBLIC)
- [x] Live-доказательства: fetch/batch/resume/export/stats/search/serve/Whisper-tiny(75)/thumbnails/gallery
- [ ] Wiki-remote: not found весь день → user-step (создать первую страницу в web-wiki, контент в docs/wiki/)

## Волна 11: GitHub + wiki [~] (репозиторий PUBLIC + main запушен; wiki — blocked, контент сохранён)
- [x] Аудит секретов чист (только упоминание пути); `gh repo edit --visibility public` → PUBLIC
- [x] `git push -u origin main` — вся история на GitHub (FroggerHH/kw-yt-transcript)
- [x] 7 wiki-страниц готовы (/tmp/opencode/kw-wiki) + зеркало docs/wiki/ запушено в main (d09f4fa)
- [ ] BLOCKED (GitHub): `...wiki.git` not found >20 мин (wiki:true, репо public). User-step: открыть https://github.com/FroggerHH/kw-yt-transcript/wiki → «Create the first page» (текст — docs/wiki/Home.md) → remote появится → следующая сессия пушит остальные
- [x] /tmp/kw-final: pip install . → 0.2.0, 5×--help exit 0, pip check чисто
- [x] Live: fetch exit 0 (10 файлов), export 61/487, stats таблица, search 38, serve 200

## Волна 12: GitHub Actions CI [x] (done 16:56, 188 passed, fix-3)
- [x] .github/workflows/ci.yml (push/PR, matrix 3.11–3.13, pip install + pytest + ruff, YAML валиден)
- [x] README-бейдж CI (строка вне теста флагов — проверено)

## Волна 13: AI-generated warning [x] (done 16:56, 188 passed, fix-3)
- [x] README-плашка (проект + auto/whisper); report.html жёлтый баннер (auto/whisper only); md/txt строки
- [x] Тесты ×3 origin + маркер «распознан ИИ»

## Волна 14: Миграция на uv [x] (done 16:58, 188 passed, fix-3)
- [x] uv.lock (35 пакетов) + .python-version 3.14; CI на setup-uv (matrix 3.11–3.13); README uv-first, pip — альтернатива
- [x] Gates: `uv sync --locked` чисто, pytest 188, ruff чисто; статус — только разрешённые файлы

## Волна 15: Multilanguage README [x] (done 17:03, 189 passed, fix-3)
- [x] README_EN.md 1:1 (73% объёма RU, команды без перевода) + шапки-ссылки + тест EN
- [x] Gates: pytest 189, ruff clean (первая попытка частично записала файлы до rate limit — учтено в retry)
- [x] README_EN.md — полный английский перевод 1:1; RU основной; языковые шапки-ссылки в обоих (done, волна 15 — 189 passed)
- [x] test_readme: EN существует + ключевые секции + та же версия; Gates: pytest зелёный (подтверждено волной 16: 190 passed)

## Review-финал v0.2+ [x] (done 17:10, 191 passed, ora-3 → fix-3 + оркестратор)
- [x] 8 пунктов без блокеров: CI locked+ruff-пин+3.14, SPEC AI-п.11, строгая валидация сегментов, asr-skip, wiki-public, TODO-чекбоксы
- [x] Хвосты оркестратора: classifier 3.14, `uv lock --check` чисто; Gates: pytest 191, ruff clean
- [x] Бейджи (CI/0.2.0/Python/MIT) + Оглавление с якорями + Highlights с demo + FAQ (строго по коду)
- [x] Тест якорей TOC + маркеры; только README + test_readme; Gates: pytest 190, ruff clean
- [ ] Бейджи (CI, версия, Python, лицензия), оглавление, highlights, скриншот-описание report.html, демо-сессия, FAQ; без битых ссылок/флагов (тест флагов должен остаться зелёным)
- [ ] Gates: pytest зелёный (маркеры), `grep` битых якорей

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
