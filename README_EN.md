# kw-yt-transcript

[![CI](https://github.com/FroggerHH/kw-yt-transcript/actions/workflows/ci.yml/badge.svg)](https://github.com/FroggerHH/kw-yt-transcript/actions)

Russian version: README.md.

> This project was developed with AI assistance. Text with origin auto/whisper was machine-transcribed — errors are possible, double-check important parts against the audio.

A console utility for downloading YouTube video metadata and full transcripts.
Russian-language CLI, batch processing, works **without an API key**.

Features:
- single video by id or URL (including `youtu.be`, `/shorts/`, `music.youtube.com`);
- multiple videos via comma/space or a file list (`--from-file`);
- whole playlists (expansion + summary `index.json`);
- YouTube subtitles (manual → auto, languages by priority `ru,en`);
- Whisper fallback when no subtitles exist (optional `asr` extra);
- 7 formats per video: `srt`, `vtt`, `json`, `txt`, `md` — timestamps + readable text,
  plus `jsonl`/`csv` for corpora and RAG;
- per-video `report.html` (metadata, thumbnail, stats, chapter links, clickable timestamps, highlighted search) and corpus-wide `index.html` (table with thumbnail gallery) — open in a browser, no server needed;
- text stats: words, reading time, speaking rate, keywords;
- `kw-yt search` — search saved transcripts with context;
- `kw-yt serve` — browse the corpus in a browser (built-in HTTP server);
- `kw-yt library` / `kw-yt clean` — own storage: list with sizes, delete videos and cache;
- fast batch: `--jobs N` in parallel, `--resume` skips finished items, metadata cache, config file.

## Requirements

- Python ≥ 3.11 (config is read via stdlib `tomllib`).
- Network (YouTube must be reachable).
- `ffmpeg` — **only** for the Whisper fallback (audio download via yt-dlp). Subtitles don't need ffmpeg.
- No YouTube API key needed (see `DECISIONS.md`, D5).

## Installation

```bash
# uv (recommended): clone → deterministic environment → run
git clone https://github.com/FroggerHH/kw-yt-transcript && cd kw-yt-transcript
uv sync                  # dependencies from uv.lock
uv run kw-yt --help      # run without installing

# uv as a CLI tool
uv tool install .

# Alternatives without uv
pipx install .         # CLI via pipx
pip install -e .       # pip, editable for development

# Whisper fallback (speech recognition when no subtitles exist)
pipx install ".[asr]"
# or: pip install -e ".[asr]"
```

## Updating

```bash
pipx upgrade kw-yt-transcript            # was pipx install .
uv tool upgrade kw-yt-transcript        # was uv tool install .
pip install -U .                        # was pip install . (from the repo dir)
```

Same check after updating: `kw-yt --version` shows the new version
(compare with CHANGELOG.md).

> If on Python 3.14 faster-whisper crashes with `TypeError: ... metadata_errors ...`
> (PyAV ≥ 15 is incompatible with faster-whisper 1.2.1) — nothing to do:
> `kw-yt` decodes audio with system `ffmpeg` itself and passes ready samples
> to the model. No PyAV downgrade needed (old PyAV has no wheels for 3.14 anyway).

Verify the installation:

```bash
kw-yt --help
kw-yt --version
```

Bash completion (optional) — generated from the code:

```bash
eval "$(kw-yt completion bash)"
```

The file `contrib/kw-yt-completion.bash` is a pinned snapshot of the same
command's output (don't edit by hand, see `ARCHITECTURE.md`). Without eval:

```bash
source contrib/kw-yt-completion.bash
```

## Quick start

Everything below is real tool output, no network (synthetic demo corpus in
`docs/demo/corpus`, captured outputs live in `docs/demo/`):

```bash
$ kw-yt --version
kw-yt 0.2.0

$ kw-yt stats --in docs/demo/corpus
Корпус: docs/demo/corpus — видео 1, реплик 6, слов 48, минут 0.5.
Источники: manual: 1. Языки: ru: 1.
- Демо-видео (синтетический офлайн-корпус) [DEMOdemo011]: 6 реплик, 48 слов, 27.2 с.

$ kw-yt search "привет" --in docs/demo/corpus
Результаты поиска «привет»: видео 1, вхождений 2.

Видео: Демо-видео (синтетический офлайн-корпус) [DEMOdemo011] — совпадений: 2
  > 00:00 Привет! Это демонстрационный корпус для офлайн-проверки kw-yt.
    00:04 Здесь лежат несколько реплик, чтобы показать поиск и статистику.
  > 00:09 Поиск находит слово привет даже в середине предложения.
    00:13 Статистика считает слова и минуты без единого запроса в сеть.
    00:19 Экспорт склеивает такие реплики в единый файл для RAG.
    00:24 Конец демонстрации, спасибо за внимание.
```

`docs/demo/` also holds `--help` outputs of all subcommands (`help*.txt`) —
tests compare them against the real CLI. First real download (needs internet):

```bash
kw-yt dQw4w9WgXcQ --out ./out
```

## Usage

```bash
# Single video by id
kw-yt dQw4w9WgXcQ

# Single video by URL
kw-yt https://www.youtube.com/watch?v=dQw4w9WgXcQ

# Multiple videos via comma/space
kw-yt dQw4w9WgXcQ,9bZkp7q19f0 "https://youtu.be/9bZkp7q19f0"

# List from a file (one entry per line, empty and #-lines skipped)
kw-yt --from-file links.txt --out ./out

# Whole playlist, readable text only
kw-yt "https://www.youtube.com/playlist?list=PLxxxxxxxx" --format txt

# English subtitles only, custom folder
kw-yt dQw4w9WgXcQ --langs en --out ./subs

# No Whisper fallback (error instead of recognition when no subtitles)
kw-yt dQw4w9WgXcQ --no-fallback-whisper

# Different Whisper model (default small)
kw-yt dQw4w9WgXcQ --whisper-model medium

# Video fragment 01:30–02:45 (subtitles fetched whole, then lines clipped)
kw-yt dQw4w9WgXcQ --from 01:30 --to 02:45

# Fast batch: 8 parallel downloads, skip finished items
kw-yt --from-file links.txt --jobs 8 --resume

# Search saved transcripts
kw-yt search "keyword" --in ./out
kw-yt search never --in ./out --context 30 --limit 5

# Browse the corpus in a browser (http://127.0.0.1:8000)
kw-yt serve ./out --port 8000

# Summary corpus export for RAG/analysis (corpus.jsonl + summary.json)
kw-yt export --in ./out
kw-yt export --in ./out --format csv --out ./all.csv --no-summary

# Summary corpus stats (table or JSON)
kw-yt stats --in ./out
kw-yt stats --in ./out --json

# Default library (no --out — into own storage)
kw-yt dQw4w9WgXcQ
kw-yt library
kw-yt library --json

# Delete from the library
kw-yt clean dQw4w9WgXcQ
kw-yt clean --older-than 30 --cache
kw-yt clean --all --yes

# Bash completion (generated from the code: all subcommands and flags)
eval "$(kw-yt completion bash)"
```

All options:

| Option | Default | What it does |
|---|---|---|
| `inputs` | — | video id / video URL / playlist URL, several via `,;` space or newline |
| `--from-file FILE` | — | file with an entry list |
| `--out, -o DIR` | `library` | results folder (own storage when unset) |
| `--langs LANGS` | `ru,en` | subtitle languages, comma-separated, by priority |
| `--format` | `all` | `srt`/`vtt`/`json`/`txt`/`md`/`jsonl`/`csv`/`all` (`jsonl` — RAG lines, `csv` — table) |
| `--from SEC` | — | fragment start (`mm:ss` or seconds; `--to` also required) |
| `--to SEC` | — | fragment end (`mm:ss` or seconds; `--from` also required) |
| `--no-fallback-whisper` | off | don't run speech recognition when no subtitles exist |
| `--whisper-model MODEL` | `small` | faster-whisper model |
| `--jobs, -j N` | `4` | parallel downloads (1–16, order in `index.json` is stable) |
| `--resume` | off | skip videos whose folder is already finished (no network calls; playlist table of contents is still read over the network) |
| `--color` | `auto` | colors: `auto` (by TTY), `always`, `never` |
| `--version` | — | show version |

Defaults of `--out`, `--langs`, `--whisper-model`, `--jobs` and `--in` (in all commands)
come from the config file when the flag is not given (see "Config and cache").
Colors: `--color {auto,always,never}` (default `auto` — by TTY),
`--no-color` is the same as `--color never`; priority: flag > `NO_COLOR` > TTY.
The `--color` flag exists on all subcommands.

`kw-yt search QUERY`:

| Option | Default | What it does |
|---|---|---|
| `--in DIR` | `library` | corpus root |
| `--context SEC` | `15` | neighbouring lines within ±seconds (`>` — direct hit, space — context) |
| `--limit N` | `20` | max videos in output |

Output: groups per video with direct-hit counts, exit 0 (found) / 1 (not found).

`kw-yt serve [DIR] [--port N]` (default library, port `8000`, `0` — auto):
serves the finished corpus (`index.html`/`report.html`) on `127.0.0.1`, exit with Ctrl+C.
No `index.html` in the folder — warning, keeps serving (directory listing).

`kw-yt export` — merges all `*/transcript.json` of the corpus into one file:

| Option | Default | What it does |
|---|---|---|
| `--in DIR` | `library` | corpus root |
| `--format` | `jsonl` | `jsonl` (RAG lines) or `csv` (table) |
| `--out FILE` | `<root>/corpus.{jsonl\|csv}` | where to write the corpus |
| `--summary FILE` | `<root>/summary.json` | where to write the summary (counters, `by_origin`, skips) |
| `--no-summary` | off | don't write the summary |

Folders without `transcript.json` or with broken JSON go to `summary.skipped`, export doesn't fail.
Output: summary line on stdout, exit 0; empty corpus — error, exit 1; missing folder — exit 2.

`kw-yt stats` — summary corpus stats without downloading:

| Option | Default | What it does |
|---|---|---|
| `--in DIR` | `library` | corpus root |
| `--json` | off | JSON summary instead of a table (videos, lines, words, minutes, `by_origin`/`by_lang`) |

Empty corpus — error, exit 1; missing folder — exit 2.

`kw-yt completion [bash]` — prints bash completion to stdout (single source —
the argparse parsers in `cli.py`; `contrib/kw-yt-completion.bash` is a pinned
snapshot of the same command's output). One-line setup:

```bash
eval "$(kw-yt completion bash)"
```

## Config and cache

Config `~/.config/kw-yt/config.toml` (or `$XDG_CONFIG_HOME/kw-yt/config.toml`):

```toml
[tool.defaults]
langs = "ru,en"
out = "./out"
jobs = 4
whisper_model = "small"
```

Priority: CLI flags → config → built-in defaults. Missing file —
defaults are used silently; broken file — Russian warning on stderr (work continues).
Without `out` (flag and config) the root of all commands is the library (see "Library and cleanup").

Metadata cache: `$XDG_CACHE_HOME/kw-yt` (or `~/.cache/kw-yt`), TTL 24 hours.
Stale views/likes up to a day — by design. Cache errors silently fall back to network.

## Output structure

Default root is the library (see above); layout inside the root
(`--from/--to` fragment — `<slug>_part0130-0245_<id>/` folder + `section` field in `meta.json`):

```
out/
  index.json                        # batch summary: {_type, playlist_url, entries, failed}
  index.html                        # same list as a table + corpus summary (with thumbnail.jpg thumbnails, lazy)
  testovoe-video_dQw4w9WgXcQ/       # <slug>_<video_id>/
    meta.json                       # metadata + origin + stats
    thumbnail.jpg                   # thumbnail (best-effort: if not downloaded — missing, rest is written)
    report.html                     # report: stats, chapters, clickable timestamps, search
    transcript.srt                  # timestamps HH:MM:SS,mmm
    transcript.vtt                  # timestamps HH:MM:SS.mmm
    transcript.json                 # [{start, duration, text}]
    transcript.jsonl                # {video_id, title, start, duration, text} lines for RAG
    transcript.csv                  # video_id,title,start,duration,text table
    transcript.txt                  # readable text, paragraphs
    transcript.md                   # heading + stats + chapters + paragraphs
```

`meta.json`: `video_id`, `url`, `title`, `channel`/`author`/`channel_id`, `duration`,
`upload_date`, `view_count`, `like_count`, `description`, `chapters`, `thumbnails`,
`tags`, `categories`, `subtitles_keys`, `automatic_captions_keys`, `origin`,
`transcript_lang`, `fetched_at`, `tool_version`, `asr_model` (only with `origin: whisper`),
`stats` (`words`, `chars`, `reading_time_min`, `speaking_wpm`, `top_keywords`),
`thumbnail_file` (`thumbnail.jpg`/null, best-effort).

`origin` — text source: `manual` (manual subtitles), `auto` (auto subtitles),
`whisper` (speech recognition).

## Errors and exit codes

| Code | When |
|---|---|
| `0` | everything processed |
| `1` | partial errors: other videos are ready, failed ones are in `index.json` with error text, `failed > 0` |
| `2` | usage/fatal: no inputs, garbage input, can't create `--out`, can't write `index.json` |

Common cases:
- garbage input (`kw-yt "!!!"`) → `Ошибка: Непонятный вход...` (Russian CLI message), exit 2, no network touched;
- no subtitles + `--no-fallback-whisper` → video in `index.json` with an error, exit 1;
- no subtitles and no `asr` extra → helpful error `pip install kw-yt-transcript[asr]`, exit 1;
- unreadable playlist → error entry in `index.json`, other inputs still processed.

## Library and cleanup

Without `--out` everything goes to own storage: `XDG_DATA_HOME/kw-yt/library`
(or `~/.local/share/kw-yt/library`). Priority: `--out` flag → config `out` → library.

`kw-yt library` — video list (title, id, date, size, origin):

| Option | Default | What it does |
|---|---|---|
| `--json` | off | JSON list instead of a table |

Empty library — Russian hint line, exit 0.

`kw-yt clean` — delete from the library:

| Option | Default | What it does |
|---|---|---|
| `ID [ID...]` | — | video id (exact `*_<id>` folder match) |
| `--all --yes` | off | delete everything (`--all` without `--yes` is refused, exit 2) |
| `--older-than DAYS` | — | delete videos older than N days |
| `--cache` | off | also clear the XDG metadata cache |

Report of what was deleted + bytes; nothing found — exit 1.

## Live video check (manually, needs internet)

```bash
kw-yt dQw4w9WgXcQ --out /tmp/kw-live && ls /tmp/kw-live/*/
```

Expected: exit 0, a `*_dQw4w9WgXcQ/` folder with `meta.json`, `thumbnail.jpg`,
`report.html` and seven `transcript.*` (10 files total), `"failed": 0` in `index.json`.
Open `report.html` in a browser: timestamps are clickable, search highlights matches.

Then on this corpus:

```bash
kw-yt search never --in /tmp/kw-live --limit 3   # exit 0, groups with 00:43 Never gonna...
kw-yt serve /tmp/kw-live --port 8000            # http://127.0.0.1:8000, exit with Ctrl+C
```

## Contributing

Current version: 0.2.0 (`kw-yt --version`).

```bash
uv sync                                            # environment from uv.lock (+ editable install of src/)
uv run --locked --with pytest -- python -m pytest -q -p no:cacheprovider
uvx ruff@0.14.5 check src tests                     # lint (select E/F/W/I/UP in pyproject)
uvx ruff@0.14.5 format --check src tests            # format
uvx mypy@1.18.2 src --ignore-missing-imports --follow-imports=skip
uv run kw-yt --help                               # entry point (bare python -m can't see src/ from root)
```

Rules: tests run without network (stubs in `tests/`; live YouTube runs are
manual, see above); never edit `contrib/kw-yt-completion.bash` by hand —
regenerate it with `kw-yt completion bash > contrib/kw-yt-completion.bash`;
`docs/demo/*.txt` are captures of real output (`COLUMNS=80`), the quick start
quotes them verbatim (checked by `tests/test_readme.py`); the agent skill lives
in `SKILL.md`.
