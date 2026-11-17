"""Wire the Object Lens prototype into a scratch copy of Holly's frontend.

Usage: python3 patch.py <copy of frontend/>

Each change is an exact replacement that must match once, so a change to Holly's code that moves
one of these lines stops the build with the file and the text that no longer matches, rather
than building a prototype that silently lacks a link. Holly's own source is never touched.
"""

import sys
from pathlib import Path

SRC = "src"


def lens_import(path: str, names: str) -> str:
    """An import of the lens's Linkify module, relative to the patched file."""
    depth = path.count("/") - 1
    return f'import {{ {names} }} from "{"../" * depth}proto/lens/Linkify";\n'


PATCHES: list[tuple[str, str, str]] = [
    # The stand-in API is installed before the app loads, and the prototype's styles after Holly's.
    (
        "src/main.tsx",
        'import App from "./App";\n',
        'import "./proto/mock";\nimport App from "./App";\n',
    ),
    ("src/main.tsx", 'import "./styles/tokens.css";\n', 'import "./styles/tokens.css";\nimport "./proto/proto.css";\n'),
    # A single offline file has no server to answer deep links, so the prototype routes by hash.
    ("src/App.tsx", "import { BrowserRouter, Routes, Route }", "import { HashRouter, Routes, Route }"),
    (
        "src/App.tsx",
        'import Users from "./pages/Users";\n',
        'import Users from "./pages/Users";\n'
        'import { LensProvider } from "./proto/lens/LensContext";\n'
        'import { LensLayer } from "./proto/lens/Chrome";\n'
        'import TestConsole from "./proto/console/TestConsole";\n',
    ),
    ("src/App.tsx", "<BrowserRouter>\n        <Routes>", "<HashRouter>\n        <LensProvider>\n        <Routes>"),
    (
        "src/App.tsx",
        "</Routes>\n      </BrowserRouter>",
        "</Routes>\n        <LensLayer />\n        <TestConsole />\n        </LensProvider>\n      </HashRouter>",
    ),
    (
        "src/components/Layout.tsx",
        'import { Link',
        'import { FindButton, WatchStrip } from "../proto/lens/Chrome";\nimport { Link',
    ),
    (
        "src/components/Layout.tsx",
        "<DisplayToggles prefs={display} onChange={changeDisplay} />",
        "{!changeDue && <FindButton />}\n            <DisplayToggles prefs={display} onChange={changeDisplay} />",
    ),
    (
        "src/components/Layout.tsx",
        '<div className="crt-content">\n',
        '<div className="crt-content">\n                <WatchStrip />\n',
    ),
    # Numbers become links where Holly shows text that names objects.
    (
        "src/components/comms/MessageList.tsx",
        "<Fragment key={part.start}>{part.text}</Fragment>",
        "<Fragment key={part.start}><Linkify text={part.text} /></Fragment>",
    ),
    (
        "src/components/notice/NoticeHero.tsx",
        '<span className="norad"> #{object.id}</span>',
        '<span className="norad"> #<SatChip id={object.id} /></span>',
    ),
    (
        "src/components/notice/SatelliteCards.tsx",
        '<span className="norad"> #{satId}</span>',
        '<span className="norad"> #<SatChip id={satId} /></span>',
    ),
    (
        "src/components/EventTimersPanel.tsx",
        "<strong>{timer.label}</strong>",
        "<strong><Linkify text={timer.label} /></strong>",
    ),
    (
        "src/components/TimerBanner.tsx",
        '<span className="timer-banner-label">{t.label}</span>',
        '<span className="timer-banner-label"><Linkify text={t.label} /></span>',
    ),
    (
        "src/pages/ShiftLog.tsx",
        '<p className="shift-note-body">{display}</p>',
        '<p className="shift-note-body"><Linkify text={display} /></p>',
    ),
    (
        "src/components/handover/StoryView.tsx",
        '{entry.detail && <p className="story-detail">{entry.detail}</p>}',
        '{entry.detail && <p className="story-detail"><Linkify text={entry.detail} /></p>}',
    ),
    # "Open full story" in the lens lands on the Handover page with that object picked.
    (
        "src/pages/Handover.tsx",
        "        setList(data);\n        setLoadedAt(Date.now());\n",
        "        setList(data);\n        setLoadedAt(Date.now());\n"
        '        const pending = sessionStorage.getItem("holly.proto.openSat");\n'
        "        if (pending) {\n"
        '          sessionStorage.removeItem("holly.proto.openSat");\n'
        "          select(Number(pending));\n"
        "        }\n",
    ),
]

IMPORTS: dict[str, str] = {
    "src/components/comms/MessageList.tsx": "Linkify",
    "src/components/notice/NoticeHero.tsx": "SatChip",
    "src/components/notice/SatelliteCards.tsx": "SatChip",
    "src/components/EventTimersPanel.tsx": "Linkify",
    "src/components/TimerBanner.tsx": "Linkify",
    "src/pages/ShiftLog.tsx": "Linkify",
    "src/components/handover/StoryView.tsx": "Linkify",
}


def main(root: Path) -> None:
    for rel, old, new in PATCHES:
        path = root / rel
        text = path.read_text(encoding="utf-8")
        if text.count(old) != 1:
            sys.exit(f"patch.py: {rel} no longer holds exactly one copy of:\n{old}")
        path.write_text(text.replace(old, new), encoding="utf-8")
    for rel, names in IMPORTS.items():
        path = root / rel
        path.write_text(lens_import(rel, names) + path.read_text(encoding="utf-8"), encoding="utf-8")
    print(f"patch.py: {len(PATCHES)} changes and {len(IMPORTS)} imports applied")


if __name__ == "__main__":
    main(Path(sys.argv[1]))
