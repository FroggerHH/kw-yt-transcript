# ARCHITECTURE.md — kw-yt-transcript

## Решение (C4): Python-CLI
- **Выбор:** Python 3.11+ (в системе 3.14.7), `pipx`/`uv` установка, entry point `kw-yt`.
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
