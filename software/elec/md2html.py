"""Convert a docs/*.md report to the project's .html style (same CSS as the earlier reports). Run: py software/elec/md2html.py docs/<name>.md"""
import re
import sys

import markdown

CSS = ("body{font-family:Georgia,'Times New Roman',serif;max-width:860px;margin:40px auto;padding:0 24px;line-height:1.55;color:#1a1a1a}\n"
       "h1{font-size:1.9em;border-bottom:2px solid #333;padding-bottom:.3em}h2{margin-top:1.8em;border-bottom:1px solid #ccc;padding-bottom:.2em}\n"
       "table{border-collapse:collapse;margin:1em 0;font-size:.9em;width:100%}th,td{border:1px solid #bbb;padding:5px 8px;text-align:left;vertical-align:top}th{background:#f0f0f0}\n"
       "code{font-family:Consolas,monospace;background:#f4f4f4;padding:1px 4px;font-size:.9em}pre{background:#f4f4f4;padding:10px;overflow-x:auto}\n"
       "img{max-width:100%;height:auto;display:block;margin:1em auto;border:1px solid #ddd}\n"
       "blockquote{border-left:3px solid #999;margin-left:0;padding-left:14px;color:#444}")


def _inline_images(html, base_dir):
    """--inline: embed every relative <img src> as a base64 data URI, so the .html is self-contained."""
    import base64
    import mimetypes
    import os

    def sub(m):
        src = m.group(2)
        if src.startswith(("data:", "http:", "https:")):
            return m.group(0)
        path = os.path.join(base_dir, src)
        if not os.path.exists(path):
            return m.group(0)
        mime = mimetypes.guess_type(path)[0] or "image/png"
        data = base64.b64encode(open(path, "rb").read()).decode("ascii")
        return '%s"data:%s;base64,%s"' % (m.group(1), mime, data)

    return re.sub(r'(<img[^>]*?\ssrc=)"([^"]+)"', sub, html)


def convert(md_path, inline=False):
    import os
    text = open(md_path, encoding="utf-8").read()
    title = re.search(r"^#\s+(.+)$", text, re.M).group(1).strip()
    body = markdown.markdown(text, extensions=["tables", "fenced_code", "toc", "sane_lists"])
    if inline:
        body = _inline_images(body, os.path.dirname(os.path.abspath(md_path)))
    html = ("<!DOCTYPE html><html><head><meta charset='utf-8'><title>%s</title><style>%s</style></head><body>%s</body></html>" % (title, CSS, body))
    out = md_path[:-3] + ".html"
    open(out, "w", encoding="utf-8").write(html)
    print("wrote", out, len(html), "bytes")


if __name__ == "__main__":
    # py software/elec/md2html.py [--inline] docs/<name>.md ...   (--inline embeds the images: a self-contained .html)
    args = sys.argv[1:]
    inline = "--inline" in args
    for p in [a for a in args if a != "--inline"]:
        convert(p, inline=inline)
