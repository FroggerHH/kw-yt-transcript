# SPEC.md — kw-yt-transcript

## Цель
Консольная утилита для получения данных о видео с YouTube + полного транскрипта.
Пользователь: русскоязычный разработчик/исследователь, пакетная обработка видео для анализа.

## Scope (must-have)
1. **Входы (широко):**
   - одиночное видео (URL или video id)
   - несколько видео через разделитель (запятая/пробел/новая строка, файл со списком)
   - плейлист / канал (URL плейлиста, batch-режим)
2. **Метаданные (полный набор):** title, channel/author, videoId, URL, duration, upload_date/published, view/like counts (если доступны), description, chapters, thumbnails, tags/categories, субтитры-список.
3. **Транскрипт:**
   - источник 1: субтитры YouTube (ручные → автогенерированные, выбор языка, fallback ru→en→первые доступные)
   - источник 2 (fallback): Whisper ASR по аудиодорожке, если субтитров нет
   - форматы вывода: с таймкодами (SRT/VTT/JSON) + читаемый текст с абзацами (TXT/Markdown)
4. **CLI на русском:** `--help`, понятные ошибки, коды выхода, пакетный прогон с прогрессом.
5. **Выходная структура:** папка на видео (slug/id), `meta.json`, `transcript.srt`, `transcript.vtt`, `transcript.json`, `transcript.jsonl`, `transcript.csv`, `transcript.txt`, `transcript.md`, `thumbnail.jpg` (best-effort).

## Non-goals
- Скачивание видео/аудио как цель (только временное аудио для Whisper, с очисткой).
- TUI/Web UI, paid API (YouTube Data API v3 — опционально позже).
- Перевод транскрипта (deferred в Future backlog).

## v0.2 Scope (расширение, 2026-10-13, по требованию пользователя)
6. **HTML-отчёты:** на видео — один `report.html` (метаданные, обложка `thumbnail.jpg` best-effort, статистика, главы-ссылки, транскрипт с кликабельными таймкодами `?t=`, поиск по тексту с подсветкой); на batch/плейлист — `index.html` со списком видео и общей статистикой. Только stdlib (встроенные CSS/JS), без внешних CDN.
7. **Статистика текста:** words, chars, reading_time_min, speaking_wpm, top_keywords (TF + встроенные стоп-слова ru/en) — в `meta.json` + шапку HTML/MD.
8. **Поиск по корпусу:** `kw-yt search <запрос> --in ./out` — вхождения с контекстом `±N сек`, ранжирование по числу вхождений, RU-вывод, exit 0/1 (нашёл/нет).
9. **Просмотр корпуса:** `kw-yt serve ./out [--port]` — stdlib HTTP-сервер по готовым index.html/report.html.
10. **Скорость/надёжность batch:** `--jobs N` (параллельно, порядок в index стабильный), `--resume` (пропуск готовых папок), кэш метаданных с TTL, конфиг `~/.config/kw-yt/config.toml` (langs, out, jobs, whisper-model).
11. **AI-маркировка машинного текста:** `origin` auto/whisper маркируется ⚠ в `report.html`/MD/TXT («распознан ИИ»); `jsonl`/`csv`/search-выдача — без примесей, только данные.
12. **Экспортные форматы:** `jsonl` (строки `{video_id,title,start,duration,text}` для RAG) и `csv` (таблица) в `--format`/`FORMATS` + `contrib/kw-yt-completion.bash`.
13. **Сводный экспорт:** `kw-yt export` — склейка `*/transcript.json` в один `corpus.jsonl/csv` + `summary.json` (счётчики, `by_origin`, `skipped`); пустой корпус → exit 1.
14. **Сводная статистика:** `kw-yt stats` — таблица/JSON по корпусу (видео, реплики, слова, минуты, `by_origin`/`by_lang`) без скачивания; пустой корпус → exit 1.
17. **Собственное хранилище:** дефолтная папка — библиотека утилиты (`XDG_DATA_HOME/kw-yt/library`, fallback `~/.local/share/kw-yt/library`), а не `./out`; `--out`/конфиг перекрывают. Управление: `kw-yt library` (список с размерами), `kw-yt clean` (удаление видео/кэша).
18. **report.html как хаб:** доступны ВСЕ артефакты видео (скачивание/просмотр каждого формата + meta + обложка, относительные ссылки, работает с file://); первым показан human-readable текст, таймкод-вид — второй вкладкой.
15. **Acceptance v0.2:** live single → report.html открывается и содержит таймкоды; search находит слово из живого транскрипта; serve отдаёт 200 на index; повторный прогон с --resume не зовёт сеть (тест); конфиг читается; export склеивает корпус в corpus.jsonl + summary.json (тест + live); stats показывает минуты, обложки best-effort (`thumbnail.jpg`/`thumbnail_file: null`); весь набор тестов зелёный.
## Acceptance criteria (v0.1)
- `kw-yt --help` работает, `--version` показывает версию.
- Одиночное видео с субтитрами → все 5 файлов, таймкоды корректны.
- Видео без субтитров → Whisper fallback (или понятный `blocked` + инструкция).
- Плейлист из N видео → N папок, сводный `index.json`, неупавшие элементы залогированы, exit code ≠ 0 при частичных ошибках, но остальные готовы.
- Несколько URL через запятую/файл → то же, что плейлист.
- Тесты изолированы (без сети), полный набор зелёный.

## Assumptions
- Стек решает оркестратор (ответ «Решай сам»), обоснование в DECISIONS.md (C4).
- Рекомендация пользователя: библиотека youtube-transcript-plus — проверить, принять/отклонить по доказательствам.
- Сеть доступна; YouTube не блокирует IP; Python/Node/Bun/yt-dlp/ffmpeg уже стоят (проверено 2026-10-13).
- Язык CLI и README — русский.

## Constraints
- quality-contract: ARCHITECTURE.md, TODO.md, DECISIONS.md, STATUS.md, git-чеки, верификация исполнением, изолированные тесты, README.
- Не выдумывать версии/флаги — проверять через --help/docs.
- Лицензия: MIT (дефолт, меняется по просьбе).
