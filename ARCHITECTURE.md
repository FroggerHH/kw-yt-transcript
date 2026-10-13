# ARCHITECTURE.md — kw-yt-transcript

## Решение (C4): Python-CLI
- **Выбор:** Python 3.11+ (в системе 3.14.7), `pipx`/`uv` установка, entry point `kw-yt`.
- **Runner-up:** Node/Bun-CLI + `youtube-transcript-plus@2.0.0` — отклонён: npm-пакет Node-only, нет плейлистов, метаданные всё равно через yt-dlp (Python-embedding зрелее), Whisper-экосистема Python stronger. Детали в `DECISIONS.md`.
- **Зависимости (pin в pyproject):** `yt-dlp>=2026.8.19`, `youtube-transcript-api==1.2.4`, `faster-whisper==1.2.1` (опциональный extra `asr`), stdlib остальное (argparse, json, re, pathlib).
- **Packaging:** `uv` основной (`uv.lock` в коммите, `uv sync --locked`, dev на 3.14 через `.python-version`, CI на `setup-uv`); `pip`/`pipx`-путь сохранён как альтернатива, `requires-python >=3.11`.

## Слои
```
src/kw_yt_transcript/   (src-layout: пакет в src/, тесты находят его через pythonpath=["src"] в pyproject)
  cli.py         — argparse (RU), коды выхода 0/1/2, прогресс batch
  inputs.py      — входы → список задач: single URL/id | CSV/space/newline | --from-file | playlist URL
  metadata.py    — yt-dlp YoutubeDL.extract_info(download=False); sanitize_info; _type video vs playlist
  transcript.py  — YouTubeTranscriptApi().list() → find_transcript(langs) → fetch() → to_raw_data; is_generated → origin manual/auto
  asr.py         — lazy faster-whisper fallback (WhisperModel small/int8, vad_filter); интерфейс segments(start,duration,text)
  formats.py     — свои сериализаторы SRT/VTT (таймкоды HH:MM:SS,mmm / HH:MM:SS.mmm совместимы с formatters); TXT/MD читаемый (группировка по паузам >2с / ~800 символов в абзац)
  outputs.py     — <out>/<slug>_<id>/meta.json + transcript.{srt,vtt,json,txt,md,jsonl,csv}; index.json {_type, entries, failed}; ошибки — в entries[].error + stderr
tests/           — stubs yt-dlp/transcript/whisper, без сети (M5: XDG temp, PATH stubs, no network)
```

## Поток данных
1. `inputs.parse(args)` → `jobs: list[VideoJob{id, source}]` (playlist → flat extract → expand, full extract per video).
2. `metadata.get(job)` → dict (title, channel, duration, upload_date, view/like, description, chapters, thumbnails, tags, subtitles list).
3. `transcript.get(video_id, langs)` → segments + origin {manual|auto|whisper|none}.
4. `formats.*` → 7 файлов. Нет субтитров → `asr.transcribe(audio via yt-dlp bestaudio tmp)` или понятная ошибка + инструкция.
5. `outputs.write()` → папки + `index.json {_type, entries, failed}`. Частичные ошибки: exit 1, остальные готовы.

## Ключевые решения
- Различие video/playlist по `info['_type']`; flat для оглавления, full для метаданных.
- Fallback языков `ru→en→first available` через `languages=[...]` + `TranscriptList` при `NotAvailableLanguage`.
- Читаемый текст: склейка сегментов, разбивка на абзацы по паузе/д Schlange, MD с header (title/channel/date/origin) + главы если есть.
- Whisper — опциональный extra, lazy import, временное аудио чистится.
  PyAV ≥ 15 + faster-whisper 1.2.1 → TypeError `metadata_errors`: fallback
  `_decode_via_ffmpeg` (системный ffmpeg → wav 16 кГц моно → ndarray float32),
  повтор `model.transcribe` без PyAV; wav чистится. Цепочка VAD: сначала
  `vad_filter=True`, при пустом результате — повтор без VAD (Silero режет
  музыку: live 0 vs 54 сегментов).
- Свои сериализаторы SRT/VTT вместо youtube_transcript_api.formatters: форматтерам нужны FetchedTranscript-объекты, а у нас плоские dict-сегменты {text, start, duration}; таймкоды совпадают.
- Сеть только в `metadata`/`transcript`/`asr` + `cli.expand_playlist` (flat extract оглавления) + `outputs.fetch_thumbnail` (обложки, волна 7); тесты мокают.
- Дедуп входов по ключу (video_id или url) с сохранением порядка; мусорные токены — error-entries, batch идёт дальше (только мусор → exit 2 без index).
- Запись атомарная: `*.tmp` + `os.replace` для meta.json/transcript.*/index.json.
- Отчёт обогащён: `meta.json` — transcript_lang, fetched_at (UTC ISO), tool_version, asr_model (при origin whisper); `index.json` — playlist_url + transcript_lang в entries.

## v0.2 Волна 1 (HTML + статистика, аддитивно)
- **stats.py** — `compute_stats(segments, duration_sec, top_n=10) -> {words, chars, reading_time_min (words/180), speaking_wpm (words/span_min по сегментам, None без спанов), top_keywords (TF по `[a-zа-яё]{3,}`, стоп-слова ru/en встроены)}`. Только stdlib.
- **report.py** — `render_report(meta, segments, stats, origin)` (один HTML: meta charset, встроенные style/script, главы `youtu.be/{id}?t=`, реплики `watch?v={id}&t={s}s`, поиск с подсветкой, escape) и `render_index(entries_info, corpus)` (таблица + сводка). Всё на русском.
- **outputs.py** — `write_video` всегда пишет `report.html` + `stats` в `meta.json`; `write_index` всегда пишет `index.html` рядом с `index.json` (ссылки `dir/report.html`). 7 форматов (`srt,vtt,json,txt,md,jsonl,csv`).
- **formats.py `to_md`** — в шапку добавлены строки слов/времени чтения/топ-3 (сигнатура та же).

## v0.2 Волна 2 (поиск + serve + скорость, аддитивно)
- **Субкоманды:** `cli.main` смотрит на argv[1]: `search`/`serve` — свои парсеры
  (`build_search_parser`/`build_serve_parser`), иначе старое fetch-поведение
  (`build_parser` + `--jobs`/`--resume`). Fetch-примеры и флаги не менялись.
- **search.py** — `search_corpus(root, query, context_sec=15, limit=20)`:
  читает `*/transcript.json` (+title из `meta.json`), case-insensitive подстрока,
  контекст — соседние реплики в ±секундах, сортировка видео по числу прямых
  вхождений (desc), лимит — по числу видео. CLI: группы «заголовок + mm:ss»,
  exit 0/1 (нашёл/нет).
- **serve.py** — `make_server(root, port=0)` (ThreadingHTTPServer на 127.0.0.1,
  stdlib) + `serve_dir` (печать URL в stdout, Ctrl+C — чистый выход).
  CLI: `kw-yt serve [DIR] [--port N]` (0 — авто).
- **Скорость batch:** `--jobs N` (default 4, 1–16, иначе exit 2) —
  ThreadPoolExecutor, порядок слотов = порядок входов (index стабилен),
  прогресс в stderr под Lock. `--resume` — пропуск готовых через
  `outputs.find_ready(out_dir, video_id)` (glob `*_<video_id>` + meta.json,
  запись «skip», сеть не вызывается).
- **cache.py** — кэш метаданных `XDG_CACHE_HOME/kw-yt/{id}.json`
  (fallback `~/.cache`), `{saved_at, ttl=86400, meta}`; просрочка/ошибки — тихий
  miss; атомарная запись. `metadata.get_metadata` смотрит в кэш до сети.
- **config.py** — `load_config()` читает `XDG_CONFIG_HOME/kw-yt/config.toml`
  (fallback `~/.config`), stdlib tomllib, секция `[tool.defaults]` (также
  `[defaults]`/корень): langs (строка), out, jobs (int), whisper_model;
  отсутствие файла — молча дефолты, нечитаемый/битый — предупреждение в stderr.
  Приоритет: CLI-флаги > конфиг > дефолты. `requires-python >=3.11` ради tomllib.

## v0.2 Волна 3a (правки Oracle review, аддитивно)
- **config тишина (oracle №1):** отсутствие файла — молча DEFAULTS без stderr;
  предупреждаем только о нечитаемом/битом + guard `sys.version_info < (3,11)`
  («нужен Python 3.11+ (tomllib)»).
- **Сильный resume (№2):** `find_ready` требует комплект
  `meta.json` (со stats и origin) + `transcript.json` + `report.html`;
  неполная папка (только meta.json) — не готова, идёт сеть.
- **search O(n) (№3):** окно контекста — bisect по отсортированным starts
  (границы включительно), вместо вложенного цикла.
- **cli прогресс (№4):** `as_completed` с future→index; все записи
  (видео/skip/ошибки expand) — через слоты плана по порядку входов, index
  стабилен. Мусорные токены без позиций — error-записи первыми (ограничение
  inputs-модуля, зафиксировано).
- **serve (№5):** нет `index.html` в root — предупреждение в stderr, служим дальше.
- **search вывод (№6):** `direct_count` отдельно в выдаче; заголовок группы —
  число прямых совпадений; строки: `>` прямые, пробел — контекст.
- **Версии (№7, done оркестратором):** везде Python 3.11+ (ARCH:3, pyproject
  requires-python/classifiers, ruff target py311, ruff select E/F/W/I/UP).
- **resume+плейлист (№8):** `--resume` не избавляет от чтения оглавления
  плейлиста — flat expand всегда идёт по сети; пропускаются только видео.
- **timefmt.py (№9):** общий `mmss` (`MM:SS`, часы `H:MM:SS`) для
  formats/report/search; форматные тесты не менялись.
- **Whisper-семафор (№10):** `threading.Semaphore(2)` вокруг whisper-ветки
  `_process_video`, остальной batch параллелен.
- **№11:** keep-as-is, без действий.

## v0.2 Волна 5 (сводный экспорт, аддитивно, оркестратор напрямую)
- `export.py`: `collect_corpus` (детерминированный порядок по имени папки,
  папки без/битых `transcript.json` → `skipped` с ошибкой) + `export_corpus`
  (jsonl — конкат `formats.to_jsonl` по видео, csv — одна шапка + строки;
  атомарная запись `*.tmp` + `os.replace`) + `write_summary` (счётчики,
  `by_origin`, `videos`, `skipped`).
- CLI `export`: `--in/--format/--out/--summary/--no-summary`; пустой корпус →
  exit 1, нет папки → exit 2; итоговая строка в stdout (как search).
- **Limitation (честно):** `export_corpus` держит сегменты всех видео + склейку
  в памяти (×2–3 от корпуса). До ~100 видео (~5–15 МБ) незаметно; для 1000+
  (~100 МБ) — стримить построчно в `*.tmp` (пока не сделано, см. Future).

## v0.2 Волна 6 (статистика корпуса, аддитивно, оркестратор напрямую)
- `export.summarize` (счётчики + `by_origin`/`by_lang`, длительность — спан
  сегментов) + CLI `stats` (`--in/--json`, таблица или JSON, exit 0/1/2);
  тест: таблица, JSON-разбор, пустой/нет папки.

## v0.2 Волна 8 (галерея обложек в index.html, аддитивно)
- `outputs.write_index`/`_write_index_html`: `thumbnail_file` читается из
  `meta.json` папок (best-effort, нет файла → null); схема index.json обратно
  совместима (только новое опциональное поле). `render_index`: в начале ячейки
  названия — `<img src="{dir}/thumbnail.jpg" loading="lazy">` (120px, отступ
  справа) при наличии обложки, иначе старое поведение без img.
  `_entry_thumb` возвращает имя только если файл физически существует
  (защита от битого `<img>` после ручного удаления thumbnail.jpg).

## v0.2 Волна 7 (обложки, аддитивно, оркестратор напрямую)
- `outputs.fetch_thumbnail` (stdlib urllib, только image/*, лимит 5 МБ,
  атомарно, `opener`-инъекция) + `_best_thumbnail_url` (max width);
  `write_video(..., thumb_opener=None)`: best-effort, неудача — тихо
  (`thumbnail_file: null`), `paths["thumb"]` при успехе; ready-критерий
  не менялся (обложка опциональна).
- `report.render_report`: `<img src="thumbnail.jpg">` при наличии файла.
- **Limitation (info):** скачивание обложки — timeout 20 с/видео в воркере пула batch (остальные видео не блокируются); флага `--no-thumb` нет — обложка всегда best-effort.

## v0.2 Волна 19 (библиотека + report-хаб, аддитивно)
- `storage.py`: `library_path()` (`XDG_DATA_HOME/kw-yt/library`, fallback
  `~/.local/share`), `resolve_root` (флаг > конфиг > библиотека),
  `iter_library`/`find_video_dirs` (точное `_<id>`) / `remove_dirs`/`clear_cache`.
  `config.DEFAULTS` без `out` (None = библиотека); mkdir в fetch отложен
  до реальной работы (ошибочные прогоны диск не трогают).
- CLI `library` (таблица/JSON, пустая → exit 0) и `clean`
  (ID/`--all --yes`/`--older-than`/`--cache`; `--all` без `--yes` → exit 2).
- `report.render_report(..., files=None)`: header как есть → «Текст» (абзацы,
  крупно) → Поиск → «По времени»/«Файлы» (details, относительные ссылки
  с download на фактические файлы) → главы; поиск подсвечивает обе секции.

## v0.2 Волна 20 (цветной вывод, аддитивно)
- Только stdlib ANSI в `cli.py`: `_supports_color` (TTY + нет --no-color/
  NO_COLOR/TERM=dumb), `_ColorHelpFormatter` (usage/заголовки/опции;
  на 3.14 гасит и stdlib-тему через `color=`/`_set_color`), красный
  «Ошибка:», зелёный ok / красный FAIL в прогрессе, сводки — plain.

## v0.2 Волна 21 (фрагменты --from/--to, аддитивно)
- `sections.py`: `parse_ts` (mm:ss/hh:mm:ss/секунды → float, мусор — ValueError),
  `clip_segments` (пересечение [frm, to), реплики как есть), `section_key`
  (part0130-0245). CLI: обе границы сразу (иначе exit 2), фильтр после получения
  (Whisper качает всё аудио — честно). Папка `<slug>_part{frm}-{to}_<id>`,
  `meta.section`, пометка «Фрагмент» в report; `find_ready(..., section_key)` —
  полный и фрагмент не матчат друг друга (slug без подчёркиваний).

## v0.2 Волна 23 (навык + completion + --color + демо, аддитивно)
- **SKILL.md** (корень, Agent Skills): frontmatter `name: kw-yt-transcript` +
  `description` (транскрипты/корпус/RAG/поиск); инструкции — команды всех
  субкоманд, exit-коды, форматы, библиотека-дефолт, без API-ключа,
  origin-маркировка, `--from/--to`; покрытие проверяет `tests/test_skill.py`.
- **completion из кода:** `cli.render_bash_completion()` генерирует скрипт из
  argparse-парсеров (`_completion_parsers` — единственный источник: все
  субкоманды search/serve/export/stats/library/clean/completion + флаги fetch
  incl. `--no-color/--color/--from/--to/--jobs/--resume`; значения `--format`
  и `--color` — из `choices` парсеров). `kw-yt completion [bash]` печатает его
  в stdout; `contrib/kw-yt-completion.bash` — зафиксированный вывод той же
  функции (регенерация: `kw-yt completion bash > contrib/...`, руками не
  править; расхождение ловит `test_completion_matches_contrib`).
- **--color:** `_COLOR_MODE` (`_init_color` по сырым argv: `--color X` /
  `--color=X` / `--no-color`=never; мусор — auto, дальше отвергнет argparse).
  Приоритет: флаг > NO_COLOR > TTY; `always` красит даже в pipe.
  Флаг добавлен во все 8 парсеров через `_add_color_args` (completion тоже,
  там игнорируется).
- **docs/demo/:** захваты настоящего вывода без сети (`COLUMNS=80`):
  `version.txt`, `help*.txt` всех подкоманд, `quickstart-*.txt` + синтетический
  `corpus/` (1 видео, помечено демо). Quick start в README цитирует захваты
  дословно (проверяет `test_readme_quotes_demo_outputs`).
- **mypy:** чисто под
  `uvx mypy@1.18.2 src --ignore-missing-imports --follow-imports=skip`
  (пин как у ruff). Правки точечные (≤5 строк на ошибку): `Any`-аннотации
  локалок в sections/report, `assert isinstance` после `type()`-гарда в export
  (bool по-прежнему отсекается `type()`), переименование `item→entry` в
  resume-цикле cli (mypy склеивал тип счётчика с первым `for item` по dict).

## v0.2 Волна 25 (serve --host, аддитивно)
- `serve.serve_dir(root, port, host="127.0.0.1")` / `make_server(..., host)`:
  бинд на host, URL печатает host; не-loopback host (всё кроме
  `127.0.0.1`/`localhost`/`::1`) — русское предупреждение в stderr
  «сервер виден всей локальной сети» (без автоопределения LAN-IP).
- CLI `--host HOST` в serve-парсере (дефолт 127.0.0.1); валидация через
  `socket.getaddrinfo` до бинда (мусор → exit 2).

## v0.2 Волна 26 (kw-yt update, аддитивно)
- `update.py`: `detect_install()` (порядок pipx → uv-tool → source → pip →
  unknown; source — pyproject+.git вверх от `__file__`, pip — метаданные
  importlib с dist-info в site-packages), `remote_version()` (pyproject с main
  через urllib+tomllib, таймаут 20, fetcher-инъекция, ошибки → UpdateError),
  свой tuple-парсинг версий (несравнимые — обновление доступно, с причиной),
  `build_command`/`run_update` (runner-инъекция; fallback upgrade→install
  из git для pipx/uv-tool; source — `git -C <root> pull --ff-only` + hint
  `uv sync`; unknown — инструкция, exit 1).
- CLI `update [--check]`: check — детект + сравнение, exit 0 при успехе;
  полный — уже свежее 0, обновлено 0, ошибка 1. Сеть только в remote_version.
- Безопасность: никаких скачиваний бинарей, кроме официальных каналов
  (pipx/uv/pip из git-источника, git pull из своего репо).
