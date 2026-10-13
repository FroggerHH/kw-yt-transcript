# kw-yt-transcript

Консольная утилита для скачивания метаданных и полных транскриптов видео YouTube.
Русскоязычный CLI, пакетная обработка, работает **без API-ключа**.

Что умеет:
- одиночное видео по id или URL (включая `youtu.be`, `/shorts/`, `music.youtube.com`);
- несколько видео через запятую/пробел или списком из файла (`--from-file`);
- плейлист целиком (развёртка + сводный `index.json`);
- субтитры YouTube (ручные → авто, языки по приоритету `ru,en`);
- Whisper-fallback, если субтитров нет (опциональный extra `asr`);
- 5 форматов на видео: `srt`, `vtt`, `json`, `txt`, `md` — таймкоды + читаемый текст с абзацами.

## Требования

- Python ≥ 3.10.
- Сеть (YouTube должен быть доступен).
- `ffmpeg` — **только** для Whisper-fallback (скачивание аудио через yt-dlp). Субтитрам ffmpeg не нужен.
- API-ключ YouTube **не нужен** (см. `DECISIONS.md`, D5).

## Установка

```bash
# pipx (рекомендуется для CLI)
pipx install .

# uv
uv tool install .

# pip, editable для разработки
pip install -e .

# Whisper-fallback (распознавание речи, если субтитров нет)
pipx install ".[asr]"
# или: pip install -e ".[asr]"
```

Проверка установки:

```bash
kw-yt --help
kw-yt --version
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
```

Все опции:

| Опция | По умолчанию | Что делает |
|---|---|---|
| `inputs` | — | video id / URL видео / URL плейлиста, несколько через `,;` пробел или перенос |
| `--from-file ФАЙЛ` | — | файл со списком входов |
| `--out, -o ПАПКА` | `./out` | папка результатов |
| `--langs ЯЗЫКИ` | `ru,en` | языки субтитров через запятую, по приоритету |
| `--format` | `all` | `srt`/`vtt`/`json`/`txt`/`md`/`all` |
| `--no-fallback-whisper` | выкл | не распознавать речь, если субтитров нет |
| `--whisper-model МОДЕЛЬ` | `small` | модель faster-whisper |
| `--version` | — | показать версию |

## Выходная структура

```
out/
  index.json                        # сводка batch: {_type, entries, failed}
  testovoe-video_dQw4w9WgXcQ/       # <slug>_<video_id>/
    meta.json                       # метаданные + origin
    transcript.srt                  # таймкоды HH:MM:SS,mmm
    transcript.vtt                  # таймкоды HH:MM:SS.mmm
    transcript.json                 # [{start, duration, text}]
    transcript.txt                  # читаемый текст, абзацы
    transcript.md                   # заголовок + главы + абзацы
```

`meta.json`: `video_id`, `url`, `title`, `channel`/`author`/`channel_id`, `duration`,
`upload_date`, `view_count`, `like_count`, `description`, `chapters`, `thumbnails`,
`tags`, `categories`, `subtitles_keys`, `automatic_captions_keys`, `origin`.

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

## Проверка на живом видео (вручную, нужен интернет)

```bash
kw-yt dQw4w9WgXcQ --out /tmp/kw-live && ls /tmp/kw-live/*/
```

Ожидается: exit 0, папка `*_dQw4w9WgXcQ/` с `meta.json` и пятью `transcript.*`,
в `index.json` — `"failed": 0`.

## Разработка

```bash
python -m pytest -q          # все тесты (без сети: stubs + tmp_path + tests/fixtures)
python -m kw_yt_transcript --help
```
