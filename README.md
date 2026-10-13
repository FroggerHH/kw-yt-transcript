# kw-yt-transcript

[![CI](https://github.com/FroggerHH/kw-yt-transcript/actions/workflows/ci.yml/badge.svg)](https://github.com/FroggerHH/kw-yt-transcript/actions)
![Version](https://img.shields.io/badge/version-0.2.0-blue)
![Python](https://img.shields.io/badge/python-3.11%2B-blue)
![License](https://img.shields.io/badge/license-MIT-green)

English version: README_EN.md.

> Проект разработан при участии ИИ. Текст с origin auto/whisper распознан ИИ (машинный слух) — возможны ошибки, сверяйте важные места с аудио.

Консольная утилита для скачивания метаданных и полных транскриптов видео YouTube.
Русскоязычный CLI, пакетная обработка, работает **без API-ключа**.

## Оглавление

- [Highlights](#highlights)
- [Требования](#требования)
- [Установка](#установка)
- [Использование](#использование)
- [Конфиг и кэш](#конфиг-и-кэш)
- [Выходная структура](#выходная-структура)
- [Ошибки и коды выхода](#ошибки-и-коды-выхода)
- [FAQ](#faq)
- [Проверка на живом видео](#проверка-на-живом-видео-вручную-нужен-интернет)
- [Разработка](#разработка)

Что умеет:
- одиночное видео по id или URL (включая `youtu.be`, `/shorts/`, `music.youtube.com`);
- несколько видео через запятую/пробел или списком из файла (`--from-file`);
- плейлист целиком (развёртка + сводный `index.json`);
- субтитры YouTube (ручные → авто, языки по приоритету `ru,en`);
- Whisper-fallback, если субтитров нет (опциональный extra `asr`);
- 7 форматов на видео: `srt`, `vtt`, `json`, `txt`, `md` — таймкоды + читаемый текст,
  плюс `jsonl`/`csv` для корпусов и RAG;
- `report.html` на видео (метаданные, обложка, статистика, главы-ссылки, кликабельные таймкоды, поиск с подсветкой) и `index.html` на весь корпус (таблица с миниатюрами обложек) — открываются в браузере без сервера;
- статистика текста: слова, время чтения, темп речи, ключевые слова;
- `kw-yt search` — поиск по сохранённым транскриптам с контекстом;
- `kw-yt serve` — просмотр корпуса в браузере (встроенный HTTP-сервер);
- быстрый batch: `--jobs N` параллельно, `--resume` пропускает готовое, кэш метаданных, конфиг-файл.

## Highlights

- **Без API-ключа.** Всё через публичные механизмы YouTube (yt-dlp + субтитры), ключ не нужен и не предусмотрен.
- **HTML-отчёты без сервера.** `report.html` на видео (главы-ссылки, кликабельные таймкоды, поиск с подсветкой) и `index.html` на корпус открываются двойным кликом.
- **Готовность к RAG.** `jsonl`/`csv` на видео + `kw-yt export` в единый `corpus.jsonl`/`summary.json`.
- **Поиск по корпусу.** `kw-yt search` с контекстом ±секунды и ранжированием по числу вхождений.
- **Скорость batch.** `--jobs 1–16` параллельно (порядок в `index.json` стабильный), `--resume` без повторной сети, кэш метаданных 24ч, конфиг-файл.
- **Честная маркировка.** `origin` (`manual`/`auto`/`whisper`) + AI-предупреждения в отчётах, когда текст распознан машиной.

Мини demo-сессия:

```bash
$ kw-yt dQw4w9WgXcQ --out ./out
[1/1] dQw4w9WgXcQ ... ok
Готово: 1/1, ошибок: 0. Папка: out.

$ kw-yt stats --in ./out
Корпус: ./out — видео 1, реплик 61, слов 487, минут 3.5.
Источники: manual: 1. Языки: en: 1.
```

## Требования

- Python ≥ 3.11 (конфиг читается через stdlib `tomllib`).
- Сеть (YouTube должен быть доступен).
- `ffmpeg` — **только** для Whisper-fallback (скачивание аудио через yt-dlp). Субтитрам ffmpeg не нужен.
- API-ключ YouTube **не нужен** (см. `DECISIONS.md`, D5).

## Установка

```bash
# uv (рекомендуется): клонирование → детерминированное окружение → запуск
git clone https://github.com/FroggerHH/kw-yt-transcript && cd kw-yt-transcript
uv sync                  # зависимости по uv.lock
uv run kw-yt --help      # запуск без установки

# uv как CLI-утилита
uv tool install .

# Альтернативы без uv
pipx install .         # CLI через pipx
pip install -e .       # pip, editable для разработки

# Whisper-fallback (распознавание речи, если субтитров нет)
pipx install ".[asr]"
# или: pip install -e ".[asr]"
```
```

> Если на Python 3.14 faster-whisper падает с `TypeError: ... metadata_errors ...`
> (PyAV ≥ 15 несовместим с faster-whisper 1.2.1) — ничего делать не нужно:
> `kw-yt` сам декодирует аудио системным `ffmpeg` и передаёт модели готовые
> сэмплы. Downgrade PyAV не требуется (под 3.14 у старого PyAV всё равно нет колёс).

Проверка установки:

```bash
kw-yt --help
kw-yt --version
```

Автодополнение bash (опционально):

```bash
source contrib/kw-yt-completion.bash
```

## Использование

```bash
# Одно видео по id
kw-yt dQw4w9WgXcQ

# Одно видео по URL
kw-yt https://www.youtube.com/watch?v=dQw4w9WgXcQ

# Несколько видео через запятую/пробел
kw-yt dQw4w9WgXcQ,9bZkp7q19f0 "https://youtu.be/9bZkp7q19f0"

# Список из файла (по одному входу на строку, пустые и #-строки пропускаются)
kw-yt --from-file links.txt --out ./out

# Плейлист целиком, только читаемый текст
kw-yt "https://www.youtube.com/playlist?list=PLxxxxxxxx" --format txt

# Только английские субтитры, своя папка
kw-yt dQw4w9WgXcQ --langs en --out ./subs

# Без Whisper-fallback (если субтитров нет — ошибка, а не распознавание)
kw-yt dQw4w9WgXcQ --no-fallback-whisper

# Другая модель Whisper (по умолчанию small)
kw-yt dQw4w9WgXcQ --whisper-model medium

# Быстрый batch: 8 параллельных загрузок, пропуск готового
kw-yt --from-file links.txt --jobs 8 --resume

# Поиск по сохранённым транскриптам
kw-yt search "ключевое слово" --in ./out
kw-yt search never --in ./out --context 30 --limit 5

# Просмотр корпуса в браузере (http://127.0.0.1:8000)
kw-yt serve ./out --port 8000

# Сводный экспорт корпуса для RAG/анализа (corpus.jsonl + summary.json)
kw-yt export --in ./out
kw-yt export --in ./out --format csv --out ./all.csv --no-summary

# Сводная статистика корпуса (таблица или JSON)
kw-yt stats --in ./out
kw-yt stats --in ./out --json
```

Все опции:

| Опция | По умолчанию | Что делает |
|---|---|---|
| `inputs` | — | video id / URL видео / URL плейлиста, несколько через `,;` пробел или перенос |
| `--from-file ФАЙЛ` | — | файл со списком входов |
| `--out, -o ПАПКА` | `./out` | папка результатов |
| `--langs ЯЗЫКИ` | `ru,en` | языки субтитров через запятую, по приоритету |
| `--format` | `all` | `srt`/`vtt`/`json`/`txt`/`md`/`jsonl`/`csv`/`all` (`jsonl` — строки для RAG, `csv` — таблица) |
| `--no-fallback-whisper` | выкл | не распознавать речь, если субтитров нет |
| `--whisper-model МОДЕЛЬ` | `small` | модель faster-whisper |
| `--jobs, -j N` | `4` | параллельных загрузок (1–16, порядок в `index.json` стабильный) |
| `--resume` | выкл | пропускать видео, чья папка уже готова (сеть не вызывается; оглавление плейлиста всё равно читается по сети) |
| `--version` | — | показать версию |

Дефолты `--out`, `--langs`, `--whisper-model`, `--jobs` и `--in` (во всех командах)
берутся из конфига, если флаг не задан (см. «Конфиг и кэш»).

`kw-yt search ЗАПРОС`:

| Опция | По умолчанию | Что делает |
|---|---|---|
| `--in ПАПКА` | `./out` | корень корпуса |
| `--context СЕК` | `15` | соседние реплики в ±секундах (`>` — прямое совпадение, пробел — контекст) |
| `--limit N` | `20` | максимум видео в выдаче |

Выход: группы по видео с числом прямых совпадений, exit 0 (нашёл) / 1 (нет).

`kw-yt serve [ПАПКА] [--port N]` (по умолчанию `./out`, порт `8000`, `0` — авто):
раздаёт готовый корпус (`index.html`/`report.html`) на `127.0.0.1`, выход — Ctrl+C.
Без `index.html` в папке — предупреждение, служит дальше (лиcтинг каталога).

`kw-yt export` — склейка всех `*/transcript.json` корпуса в один файл:

| Опция | По умолчанию | Что делает |
|---|---|---|
| `--in ПАПКА` | `./out` | корень корпуса |
| `--format` | `jsonl` | `jsonl` (строки для RAG) или `csv` (таблица) |
| `--out ФАЙЛ` | `<корень>/corpus.{jsonl\|csv}` | куда писать корпус |
| `--summary ФАЙЛ` | `<корень>/summary.json` | куда писать сводку (счётчики, `by_origin`, пропуски) |
| `--no-summary` | выкл | не писать сводку |

Папки без `transcript.json` или с битым JSON — в `summary.skipped`, экспорт не падает.
Выход: строка сводки в stdout, exit 0; пустой корпус — ошибка, exit 1; нет папки — exit 2.

`kw-yt stats` — сводная статистика корпуса без скачивания:

| Опция | По умолчанию | Что делает |
|---|---|---|
| `--in ПАПКА` | `./out` | корень корпуса |
| `--json` | выкл | сводка JSON вместо таблицы (видео, реплики, слова, минуты, `by_origin`/`by_lang`) |

Пустой корпус — ошибка, exit 1; нет папки — exit 2.

## Конфиг и кэш

Конфиг `~/.config/kw-yt/config.toml` (или `$XDG_CONFIG_HOME/kw-yt/config.toml`):

```toml
[tool.defaults]
langs = "ru,en"
out = "./out"
jobs = 4
whisper_model = "small"
```

Приоритет: флаги CLI → конфиг → встроенные дефолты. Отсутствующий файл —
тихо используются дефолты; битый файл — русское предупреждение в stderr (работа продолжается).

Кэш метаданных: `$XDG_CACHE_HOME/kw-yt` (или `~/.cache/kw-yt`), TTL 24 часа.
Устаревшие просмотры/лайки до суток — by design. Ошибки кэша молча ведут в сеть.

## Выходная структура

```
out/
  index.json                        # сводка batch: {_type, playlist_url, entries, failed}
  index.html                        # тот же список таблицей + сводка корпуса (с миниатюрами thumbnail.jpg, lazy)
  testovoe-video_dQw4w9WgXcQ/       # <slug>_<video_id>/
    meta.json                       # метаданные + origin + stats
    thumbnail.jpg                   # обложка (best-effort: если не скачалась — её нет, остальное пишется)
    report.html                     # отчёт: статистика, главы, кликабельные таймкоды, поиск
    transcript.srt                  # таймкоды HH:MM:SS,mmm
    transcript.vtt                  # таймкоды HH:MM:SS.mmm
    transcript.json                 # [{start, duration, text}]
    transcript.jsonl                # строки {video_id, title, start, duration, text} для RAG
    transcript.csv                  # таблица video_id,title,start,duration,text
    transcript.txt                  # читаемый текст, абзацы
    transcript.md                   # заголовок + статистика + главы + абзацы
```

`meta.json`: `video_id`, `url`, `title`, `channel`/`author`/`channel_id`, `duration`,
`upload_date`, `view_count`, `like_count`, `description`, `chapters`, `thumbnails`,
`tags`, `categories`, `subtitles_keys`, `automatic_captions_keys`, `origin`,
`transcript_lang`, `fetched_at`, `tool_version`, `asr_model` (только при `origin: whisper`),
`stats` (`words`, `chars`, `reading_time_min`, `speaking_wpm`, `top_keywords`),
`thumbnail_file` (`thumbnail.jpg`/null, best-effort).

`origin` — источник текста: `manual` (ручные субтитры), `auto` (автосубтитры),
`whisper` (распознавание речи).

## Ошибки и коды выхода

| Код | Когда |
|---|---|
| `0` | всё обработано |
| `1` | частичные ошибки: остальные видео готовы, неуспешные — в `index.json` с текстом ошибки, `failed > 0` |
| `2` | usage/фатальное: нет входных данных, мусорный вход, не создаётся `--out`, не пишется `index.json` |

Частые случаи:
- мусорный вход (`kw-yt "!!!"`) → `Ошибка: Непонятный вход...`, exit 2, сети не касается;
- нет субтитров + `--no-fallback-whisper` → видео в `index.json` с ошибкой, exit 1;
- нет субтитров и нет extra `asr` → понятная ошибка `pip install kw-yt-transcript[asr]`, exit 1;
- плейлист не читается → ошибка-запись в `index.json`, остальные входы обрабатываются.

## FAQ

**У видео нет субтитров — что будет?**
Whisper-fallback (нужен extra `asr` + системный `ffmpeg`): аудио скачивается временно и чистится, `origin` будет `whisper`. С флагом `--no-fallback-whisper` — ошибка-запись в `index.json`, exit 1. Без extra `asr` — русская подсказка `pip install kw-yt-transcript[asr]`.

**Приватное/удалённое видео роняет весь batch?**
Нет. Неуспешное видео пишется в `index.json` с текстом ошибки, остальные обрабатываются; exit 1 при частичных ошибках.

**Как гнать большой плейлист повторно?**
`--jobs 8 --resume`: готовые папки (комплект `meta.json` + `transcript.json` + `report.html`) пропускаются без сети. Учтите: оглавление самого плейлиста всё равно читается по сети.

**Падает `TypeError: ... metadata_errors ...` на Python 3.14?**
Это несовместимость faster-whisper 1.2.1 с PyAV ≥ 15 — `kw-yt` обходит её сам: декодирует аудио системным `ffmpeg` и передаёт модели готовые сэмплы. Дополнительно при пустом результате повтор идёт без VAD-фильтра (Silero режет музыку).

**Как проверяется качество?**
GitHub Actions: матрица Python 3.11–3.13, `uv sync --locked`, полный pytest без сети, `ruff check`. Бейдж — в шапке.

**Работает на Windows/macOS?**
Проверено на Linux. Пути кэша/конфига имеют fallback (`~/.cache`, `~/.config`), код на stdlib переносим, но вне Linux не проверялось — гарантий нет.

## Проверка на живом видео (вручную, нужен интернет)

```bash
kw-yt dQw4w9WgXcQ --out /tmp/kw-live && ls /tmp/kw-live/*/
```

Ожидается: exit 0, папка `*_dQw4w9WgXcQ/` с `meta.json`, `thumbnail.jpg`,
`report.html` и семью `transcript.*` (всего 10 файлов), в `index.json` —
`"failed": 0`. Открой `report.html` в браузере:
таймкоды кликабельны, поиск подсвечивает совпадения.

Дальше на этом корпусе:

```bash
kw-yt search never --in /tmp/kw-live --limit 3   # exit 0, группы с 00:43 Never gonna...
kw-yt serve /tmp/kw-live --port 8000            # http://127.0.0.1:8000, выход Ctrl+C
```

## Разработка

```bash
uv sync                                            # окружение по uv.lock
uv run --locked --with pytest -- python -m pytest -q -p no:cacheprovider
uvx ruff@0.14.5 check kw_yt_transcript tests        # линт (select E/F/W/I/UP в pyproject)
python -m kw_yt_transcript --help
```
