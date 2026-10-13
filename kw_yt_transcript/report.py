"""HTML-отчёты: report.html на видео и index.html на корпус (v0.2, Волна 1).

Только stdlib (html.escape). Все CSS/JS — встроенные, внешних URL
в <link>/<script src> нет (ссылки на YouTube в теле — контентные).
Весь пользовательский текст экранируется. Язык интерфейса — русский.
"""

from __future__ import annotations

import html
from typing import Any

from kw_yt_transcript.timefmt import mmss as _mmss

_ORIGIN_LABELS = {"manual": "ручные субтитры", "auto": "автосубтитры", "whisper": "Whisper ASR"}

_CSS = (
    "body{font-family:sans-serif;max-width:900px;margin:0 auto;padding:16px;line-height:1.5}"
    "header{border-bottom:1px solid #ccc;margin-bottom:16px}"
    ".meta{color:#444}.stats{background:#f6f6f6;padding:12px;border-radius:8px}"
    "table{border-collapse:collapse;width:100%}"
    "th,td{border:1px solid #ccc;padding:6px 8px;text-align:left}"
    "mark{background:yellow}.seg{margin:6px 0}.ts{white-space:nowrap}"
    "#search{width:100%;padding:8px;font-size:1em;margin:12px 0}"
)

_JS_SEARCH = """(function(){
var input=document.getElementById("search");
if(!input){return;}
var blocks=Array.prototype.slice.call(document.querySelectorAll(".seg-text"));
var originals=blocks.map(function(el){return el.textContent;});
function esc(s){return s.replace(/[.*+?^${}()|[\\]\\\\]/g,"\\\\$&");}
input.addEventListener("input",function(){
  var q=input.value.trim();
  var countEl=document.getElementById("search-count");
  var n=0;
  blocks.forEach(function(el,i){
    var orig=originals[i];
    el.textContent=orig;
    if(!q){return;}
    var re=new RegExp("("+esc(q)+")","gi");
    var m=orig.match(re);
    if(m){n+=m.length;el.innerHTML=orig.replace(re,"<mark>$1</mark>");}
  });
  if(countEl){countEl.textContent=q?("Найдено совпадений: "+n):"";}
});
})();"""


def _origin_label(origin: str | None) -> str:
    return _ORIGIN_LABELS.get(str(origin or ""), str(origin or "—"))


def render_report(
    meta: dict[str, Any] | None,
    segments: list[dict[str, Any]],
    stats: dict[str, Any] | None,
    origin: str | None,
) -> str:
    """Один HTML-отчёт на видео."""
    meta = dict(meta or {})
    stats = dict(stats or {})
    video_id = str(meta.get("video_id") or "")
    title = str(meta.get("title") or "Транскрипт")
    author = str(meta.get("channel") or meta.get("author") or "—")
    date = str(meta.get("upload_date") or "—")
    duration = meta.get("duration")
    lang = meta.get("transcript_lang") or "—"
    words = stats.get("words", 0)
    chars = stats.get("chars", 0)
    reading = stats.get("reading_time_min", 0.0)
    try:
        reading_s = f"{float(reading):.1f}"
    except Exception:
        reading_s = "0.0"
    wpm = stats.get("speaking_wpm")
    try:
        wpm_s = f"{float(wpm):.0f}" if wpm is not None else "—"
    except Exception:
        wpm_s = "—"
    top = stats.get("top_keywords") or []
    top_s = ", ".join(
        f"{html.escape(str(k.get('word', '')), quote=True)} ({int(k.get('count', 0))})"
        for k in top
        if isinstance(k, dict) and k.get("word")
    ) or "—"

    chapters = meta.get("chapters") or []
    ch_rows: list[str] = []
    for ch in chapters:
        if not isinstance(ch, dict):
            continue
        try:
            sec = int(ch.get("start_time") or 0)
        except Exception:
            sec = 0
        ctitle = html.escape(str(ch.get("title") or "—"), quote=True)
        if video_id:
            ch_rows.append(
                f'<li><a href="https://youtu.be/{html.escape(video_id, quote=True)}'
                f"?t={sec}\">{_mmss(sec)}</a> {ctitle}</li>"
            )
        else:
            ch_rows.append(f"<li>{_mmss(sec)} {ctitle}</li>")

    seg_rows: list[str] = []
    for seg in segments or []:
        try:
            text = seg.get("text", "") if isinstance(seg, dict) else ""
            start = float(seg.get("start", 0.0)) if isinstance(seg, dict) else 0.0
        except Exception:
            continue
        s = max(0, int(start))
        ts = _mmss(start)
        t_esc = html.escape(str(text), quote=False)
        if video_id:
            link = (
                f"https://www.youtube.com/watch?v={html.escape(video_id, quote=True)}"
                f"&t={s}s"
            )
            seg_rows.append(
                f'<p class="seg"><a class="ts" href="{link}">{ts}</a> '
                f'<span class="seg-text">{t_esc}</span></p>'
            )
        else:
            seg_rows.append(
                f'<p class="seg"><span class="ts">{ts}</span> '
                f'<span class="seg-text">{t_esc}</span></p>'
            )

    chapters_html = (
        "<section><h2>Главы</h2><ul>" + "".join(ch_rows) + "</ul></section>"
        if ch_rows
        else ""
    )
    transcript_html = (
        "<section><h2>Транскрипт</h2>" + "".join(seg_rows) + "</section>"
        if seg_rows
        else "<section><h2>Транскрипт</h2><p>Транскрипт пуст.</p></section>"
    )
    watch = (
        f'<p><a href="https://www.youtube.com/watch?v='
        f'{html.escape(video_id, quote=True)}">Смотреть на YouTube</a></p>'
        if video_id
        else ""
    )

    thumb = ""
    if meta.get("thumbnail_file"):
        thumb = (
            '<img src="thumbnail.jpg" alt="Обложка видео" '
            'style="max-width:100%;border-radius:8px">\n'
        )

    return (
        "<!DOCTYPE html>\n<html lang=\"ru\">\n<head>\n<meta charset=\"utf-8\">\n"
        f"<title>{html.escape(title, quote=True)}</title>\n"
        f"<style>{_CSS}</style>\n</head>\n<body>\n"
        f"<header><h1>{html.escape(title, quote=False)}</h1>\n{thumb}"
        f"<p class=\"meta\">Автор: {html.escape(author, quote=False)} | "
        f"Дата: {html.escape(date, quote=False)} | "
        f"Длительность: {_mmss(duration)} | "
        f"Источник: {html.escape(_origin_label(origin), quote=False)} | "
        f"Язык: {html.escape(str(lang), quote=False)}</p>\n{watch}</header>\n"
        f"<section class=\"stats\"><h2>Статистика</h2>\n"
        f"<p>Слов: {words} | Символов: {chars} | "
        f"Время чтения: {reading_s} мин | Темп речи: {wpm_s} слов/мин</p>\n"
        f"<p>Ключевые слова: {top_s}</p></section>\n"
        f"{chapters_html}\n"
        "<section><h2>Поиск</h2>\n"
        '<input type="search" id="search" placeholder="Поиск по транскрипту…">\n'
        '<p id="search-count"></p></section>\n'
        f"{transcript_html}\n"
        f"<script>{_JS_SEARCH}</script>\n</body>\n</html>\n"
    )


def render_index(
    entries_info: list[dict[str, Any]],
    corpus: dict[str, Any] | None,
) -> str:
    """Сводный index.html: таблица видео + сводка корпуса."""
    corpus = dict(corpus or {})
    n = corpus.get("n_videos", len(entries_info or []))
    tw = corpus.get("total_words", 0)
    tm = corpus.get("total_min", 0.0)
    try:
        tm_s = f"{float(tm):.1f}"
    except Exception:
        tm_s = "0.0"

    rows: list[str] = []
    for e in entries_info or []:
        if not isinstance(e, dict):
            continue
        title = str(e.get("title") or e.get("video_id") or "—")
        d = str(e.get("dir") or "")
        author = str(e.get("author") or "—")
        dur = e.get("duration")
        words = e.get("words", "—")
        origin = _origin_label(e.get("origin"))
        href = f"{html.escape(d, quote=True)}/report.html" if d else "#"
        thumb = ""
        thumb_file = e.get("thumbnail_file")
        if d and isinstance(thumb_file, str) and thumb_file:
            src = f"{html.escape(d, quote=True)}/{html.escape(thumb_file, quote=True)}"
            thumb = (
                f'<img src="{src}" loading="lazy" alt="" '
                f'style="width:120px;margin-right:8px;vertical-align:middle">'
            )
        rows.append(
            f"<tr><td>{thumb}<a href=\"{href}\">{html.escape(title, quote=False)}</a></td>"
            f"<td>{html.escape(author, quote=False)}</td>"
            f"<td>{_mmss(dur)}</td>"
            f"<td>{html.escape(str(words), quote=False)}</td>"
            f"<td>{html.escape(origin, quote=False)}</td></tr>"
        )
    body = (
        "<table><thead><tr><th>Название</th><th>Автор</th>"
        "<th>Длительность</th><th>Слов</th><th>Источник</th></tr></thead>"
        "<tbody>" + "".join(rows) + "</tbody></table>"
        if rows
        else "<p>Видео нет.</p>"
    )
    return (
        "<!DOCTYPE html>\n<html lang=\"ru\">\n<head>\n<meta charset=\"utf-8\">\n"
        "<title>Каталог транскриптов</title>\n"
        f"<style>{_CSS}</style>\n</head>\n<body>\n"
        "<header><h1>Каталог транскриптов</h1>\n"
        f"<p class=\"meta\">Всего видео: {n} | Всего слов: {tw} | "
        f"Общая длительность: {tm_s} мин</p></header>\n"
        f"{body}\n</body>\n</html>\n"
    )
