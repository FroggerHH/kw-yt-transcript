# CHANGELOG — kw-yt-transcript

## 0.2.0 (2026-10-13)

- **Волна 1 — HTML + статистика:** `stats.py` (слова, время чтения, wpm,
  топ ключевых слов ru/en), `report.py` (`report.html` на видео: главы,
  кликабельные `?t=`, поиск с подсветкой; `index.html` на batch), `stats`
  в `meta.json`, статистика в шапке MD, Python только stdlib.
- **Волна 2 — поиск + serve + скорость:** `kw-yt search` (контекст,
  ранжирование, exit 0/1), `kw-yt serve` (stdlib HTTP на 127.0.0.1),
  `--jobs 1–16` (порядок index стабильный), `--resume`, кэш метаданных
  (XDG, TTL 24ч), конфиг `~/.config/kw-yt/config.toml`.
- **Волна 3a — hardening по review:** тихий отсутствующий конфиг, сильный
  resume-комплект, search за O(n log n), `as_completed`-прогресс, общий
  `timefmt.py`, whisper-семафор (2), версии Python 3.11+ везде.
- Тестов 176 (было 100 в v0.1), ruff `E/F/W/I/UP` чисто.
- **Волна 4 — экспорт форматов + completion:** `jsonl` (строки для RAG)
  и `csv` (таблица) в `--format`/`FORMATS`, `contrib/kw-yt-completion.bash`.
- **Волна 5 — сводный экспорт:** `kw-yt export` (один `corpus.jsonl/csv` +
  `summary.json` со счётчиками, `by_origin` и `skipped`).
- **Волна 6 — статистика корпуса:** `kw-yt stats` (таблица/JSON: видео,
  реплики, слова, минуты, `by_origin`/`by_lang`) без скачивания.
- **Волна 7 — обложки:** `thumbnail.jpg` best-effort в папке видео + `<img>`
  в `report.html` (`thumbnail_file` в meta.json).

## 0.1.0 (2026-10-13)

- **Фаза 1 — скелет + CLI:** `pyproject.toml` (`kw-yt-transcript 0.1.0`, `yt-dlp`,
  `youtube-transcript-api`, extra `asr` с `faster-whisper`, entry point `kw-yt`),
  пакет `kw_yt_transcript/`, русскоязычный argparse (`--help` с примерами,
  `--version`), `inputs.py` (single id/URL, multi split `[,;\\s]`, `--from-file`,
  detect плейлистов), 14 unit-тестов.
- **Фаза 2 — метаданные + субтитры:** `metadata.py` (yt-dlp `extract_info`,
  полный набор полей, `MetadataError`), `transcript.py` (`fetch ru→en`,
  fallback на первый доступный, origin `manual`/`auto`, `NoTranscriptError`),
  `formats.py` (SRT/VTT/JSON/TXT/MD, абзацы по паузе >2с / длине >800),
  фикстуры `tests/fixtures/`, +24 теста (всего 38).
- **Фаза 3 — batch + Whisper-fallback:** `outputs.py` (slug с транслитом,
  папка `<slug>_<id>/`, `meta.json`, `index.json {_type, entries, failed}`),
  `asr.py` (ленивый faster-whisper, bestaudio tmp mp3, чистка в `finally`,
  `ASRError` с русской подсказкой про `.[asr]`), wiring `cli.py` (expand
  плейлистов, прогресс `[i/N]` в stderr, exit-коды 0/1/2), +23 теста (всего 61).
- **Фаза 4 — упаковка:** `README.md` (RU), `CHANGELOG.md`, classifiers/keywords
  в `pyproject.toml`, `tests/test_readme.py` (консистентность README ↔ CLI),
  M4/M5-прогоны (pytest зелёный, `--help`/`--version` exit 0, изоляция без
  сети/HOME/бинарей). Живой прогон на YouTube — user-side шаг из README.
