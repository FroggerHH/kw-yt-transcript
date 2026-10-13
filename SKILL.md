---
name: kw-yt-transcript
description: Скачивание транскриптов YouTube и работа с корпусом текстов (поиск, RAG-экспорт, статистика). Используй, когда нужно получить текст видео, найти фразу в сохранённых транскриптах или собрать корпус для RAG.
---

# kw-yt-transcript

Консольная утилита `kw-yt`: метаданные + полные транскрипты видео YouTube.
Русскоязычный CLI, пакетная обработка, работает **без API-ключа**.

## Когда использовать

- Нужен текст видео (id/URL, несколько видео, плейлист целиком).
- Нужен поиск фразы по уже скачанным транскриптам (`search`).
- Нужен корпус для RAG/анализа (`export` в `corpus.jsonl` + `summary.json`).
- Нужна сводка корпуса без скачивания (`stats`).

## Команды

```bash
kw-yt <URL|ID> [--out ./out] [--langs ru,en] [--format all]
kw-yt --from-file links.txt --jobs 8 --resume
kw-yt dQw4w9WgXcQ --from 01:30 --to 02:45   # только фрагмент
kw-yt search "фраза" --in ./out [--context 15] [--limit 20]
kw-yt serve ./out [--port 8000]
kw-yt export --in ./out [--format jsonl|csv] [--out corpus.jsonl]
kw-yt stats --in ./out [--json]
kw-yt library [--json]
kw-yt clean <ID> [--cache] | kw-yt clean --all --yes
kw-yt completion bash                        # bash-completion в stdout
```

## Правила

- **Коды выхода:** `0` — ок; `1` — частичные ошибки (остальное готово,
  неуспешное — в `index.json` с текстом) / `search` ничего не нашёл /
  пустой корпус для `export`/`stats`; `2` — usage (нет входов, мусорный
  вход, плохой флаг).
- **Форматы:** `srt`/`vtt`/`json` — с таймкодами; `txt`/`md` — читаемый
  текст; `jsonl` (`{video_id,title,start,duration,text}`) и `csv` — для
  корпусов и RAG; `all` — все сразу.
- **Корень по умолчанию — библиотека** (`XDG_DATA_HOME/kw-yt/library`),
  не `./out`. Флаг `--out`/конфиг перекрывают.
- **API-ключ не нужен** и не предусмотрен; сеть — только YouTube
  (yt-dlp + субтитры + опциональный Whisper-fallback).
- **Маркировка машинного текста:** поле `origin` (`manual`/`auto`/`whisper`);
  `auto`/`whisper` — «распознан ИИ», в отчётах помечается ⚠. Сырые данные
  (`jsonl`/`csv`/выдача `search`) — без примесей, только данные.
- **Фрагменты:** `--from` и `--to` задаются только парой (иначе exit 2);
  субтитры/аудио берутся целиком, реплики фильтруются после.
- **Цвета:** авто по TTY; `--color {auto,always,never}` (`--no-color` —
  то же, что `never`), приоритет: флаг > `NO_COLOR` > TTY.

## Примеры

```bash
# Один транскрипт читаемым текстом
kw-yt dQw4w9WgXcQ --format txt --out ./out

# Плейлист параллельно с докачкой
kw-yt "https://www.youtube.com/playlist?list=PLxxxxxxxx" --jobs 8 --resume

# Есть ли фраза в корпусе?
kw-yt search "ключевое слово" --in ./out || echo "не найдено"

# Корпус для RAG
kw-yt export --in ./out && head -1 ./out/corpus.jsonl
```
