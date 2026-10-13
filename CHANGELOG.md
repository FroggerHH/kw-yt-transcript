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
- **Волна 3b — релиз 0.2.0:** README v0.2, версия 0.2.0, CHANGELOG,
  `test_readme` (консистентность README ↔ CLI).
- Тестов 191 (было 100 в v0.1), ruff `E/F/W/I/UP` чисто.
- **Волна 4 — экспорт форматов + completion:** `jsonl` (строки для RAG)
  и `csv` (таблица) в `--format`/`FORMATS`, `contrib/kw-yt-completion.bash`.
- **Волна 5 — сводный экспорт:** `kw-yt export` (один `corpus.jsonl/csv` +
  `summary.json` со счётчиками, `by_origin` и `skipped`).
- **Волна 6 — статистика корпуса:** `kw-yt stats` (таблица/JSON: видео,
  реплики, слова, минуты, `by_origin`/`by_lang`) без скачивания.
- **Волна 7 — обложки:** `thumbnail.jpg` best-effort в папке видео + `<img>`
  в `report.html` (`thumbnail_file` в meta.json).
- **ASR av/VAD-fallback (live-находка):** faster-whisper 1.2.1 + PyAV ≥ 15
  (`TypeError metadata_errors`) — обход через системный ffmpeg (wav 16 кГц
  моно → ndarray float32, PyAV не задействуется); цепочка VAD (пусто
  с фильтром → повтор без, live: 0 против 54); live-proof: Whisper-tiny →
  origin whisper, 75 сегментов.
- **Волна 8 — галерея в index.html:** миниатюры обложек (120px, lazy)
  в ячейке названия, `thumbnail_file` в entries (`index.json` совместим,
  is_file-защита от битого `<img>`).
- **Волна 9 — аудит README против CLI:** все команды/флаги с корректными
  дефолтами, 10 файлов в live-check, обложки в «Что умеет», конфиг-фолбэк.
- **Волна 10 — CHANGELOG 0.2.0:** запись покрыла волны 1–9 + review-циклы.
- **Волна 11 — GitHub + wiki:** репозиторий PUBLIC, main запушен;
  wiki-контент (7 страниц) зеркалится в `docs/wiki/` (web-wiki — user-step).
- **Волна 12 — CI:** GitHub Actions (push/PR, matrix 3.11–3.14),
  `uv sync --locked` + pytest + ruff-пин `0.14.5`, бейдж в README.
- **Волна 13 — AI-warning:** плашка в README, ⚠-баннер в `report.html`
  + строки в MD/TXT при origin auto/whisper; `jsonl`/`csv`/search — без примесей.
- **Волна 14 — uv-миграция:** `uv.lock` (35 пакетов), `.python-version` 3.14,
  CI на setup-uv, README uv-first (pip — альтернатива).
- **Волна 15 — EN README:** `README_EN.md` 1:1 + языковые шапки-ссылки + тест.
- **Волна 16 — rich README:** бейджи, оглавление с якорями, highlights + demo,
  FAQ строго по коду.
- **Волна 17 — wiki-зеркало:** sync 6/7 страниц `docs/wiki/` с волнами 12–16.
- **Волна 19 — библиотека + report-хаб:** собственное хранилище
  (`XDG_DATA_HOME/kw-yt/library`, дефолт всех команд; `out` убран из DEFAULTS),
  `kw-yt library`/`clean` (размеры, точные id, `--all --yes`, `--older-than`,
  `--cache`); `report.html` — хаб папки (Текст → По времени/Файлы → главы).
- **Review-циклы без блокеров:** ora-2 (конфиг-тишина, resume, search O(n));
  ora-3 волн 4–5 (валидация сегментов → skipped, atomic, acceptance);
  финал волн 6–7 (span/минуты в `export.summarize`, 7 форматов в ARCH/SPEC,
  acceptance п.15, `thumbnail_file` в README); review-финал v0.2+
  (8 пунктов, classifier 3.14, LICENSE MIT).

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
