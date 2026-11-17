"""Fold the prototype's built page, script, styles and icon into one offline HTML file.

Usage: python3 inline.py <vite dist folder> <output html>
"""

import base64
import re
import sys
from pathlib import Path


def main(dist: Path, out: Path) -> None:
    html = (dist / "index.html").read_text(encoding="utf-8")
    scripts = re.findall(r'<script type="module" crossorigin src="\./(assets/[^"]+)"></script>', html)
    styles = re.findall(r'<link rel="stylesheet" crossorigin href="\./(assets/[^"]+)">', html)
    if len(scripts) != 1 or len(styles) != 1:
        sys.exit(f"inline.py: expected one script and one stylesheet, found {scripts} and {styles}")
    js = (dist / scripts[0]).read_text(encoding="utf-8").replace("</script", "<\\/script")
    css = (dist / styles[0]).read_text(encoding="utf-8").replace("</style", "<\\/style")
    html = html.replace(
        f'<script type="module" crossorigin src="./{scripts[0]}"></script>', ""
    ).replace(f'<link rel="stylesheet" crossorigin href="./{styles[0]}">', f"<style>{css}</style>")
    icon = dist / "favicon.svg"
    if icon.exists():
        uri = "data:image/svg+xml;base64," + base64.b64encode(icon.read_bytes()).decode()
        html = html.replace('href="./favicon.svg"', f'href="{uri}"')
    html = html.replace("<title>Holly</title>", "<title>Holly Object Lens prototype</title>")
    notice = (
        "<!-- Holly Object Lens prototype for the hallway test. Bluestaq Limited. Every object, notice,"
        " record, message, timer and note in it is synthetic; it makes no network call. -->\n"
    )
    html = html.replace("</body>", f'<script type="module">{js}</script>\n</body>')
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(notice + html, encoding="utf-8")
    print(f"inline.py: wrote {out} ({out.stat().st_size // 1024} KB)")


if __name__ == "__main__":
    main(Path(sys.argv[1]), Path(sys.argv[2]))
