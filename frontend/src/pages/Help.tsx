import { useEffect, useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { getManual, listManuals } from "../api/manuals";
import MarkdownBlocks from "../components/Markdown";
import type { Manual, ManualSummary } from "../types";
import { extractErrorMessage } from "../utils/errors";
import { type Block, parseMarkdown } from "../utils/markdown";

interface Entry {
  id: string;
  text: string;
  level: number;
  section: string | null;
}

// The manual's own title and the brand line above it are the page's header, so the body starts
// after the first top-level heading.
function body(blocks: readonly Block[]): Block[] {
  const title = blocks.findIndex((b) => b.kind === "heading" && b.level === 1);
  return title === -1 ? [...blocks] : blocks.slice(title + 1);
}

// The contents: each section and its subsections, a section numbered by the SECTION line above it.
function contents(blocks: readonly Block[]): Entry[] {
  const entries: Entry[] = [];
  let section: string | null = null;
  for (const block of blocks) {
    if (block.kind === "eyebrow") section = block.text.replace("SECTION ", "");
    if (block.kind === "heading" && block.level <= 3) {
      entries.push({ id: block.id, text: block.text, level: block.level, section });
      section = null;
    }
  }
  return entries;
}

function goTo(id: string) {
  const target = document.getElementById(id);
  const still = window.matchMedia?.("(prefers-reduced-motion: reduce)").matches ?? true;
  target?.scrollIntoView?.({ behavior: still ? "auto" : "smooth", block: "start" });
  target?.focus({ preventScroll: true });
}

// Help: the manuals this user may read, each with its contents beside it, to search, read and
// print. Which manuals are offered is the server's decision, by role.
export default function HelpPage() {
  const [params, setParams] = useSearchParams();
  const [manuals, setManuals] = useState<ManualSummary[] | null>(null);
  const [manual, setManual] = useState<Manual | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [find, setFind] = useState("");
  const asked = params.get("manual");
  const slug = manuals?.some((m) => m.slug === asked) ? asked : manuals?.[0]?.slug;

  useEffect(() => {
    listManuals()
      .then(setManuals)
      .catch((err: unknown) => setError(extractErrorMessage(err, "Failed to load the manuals.")));
  }, []);

  useEffect(() => {
    if (!slug) return undefined;
    let cancelled = false;
    setManual(null);
    setError(null);
    getManual(slug)
      .then((loaded) => {
        if (!cancelled) setManual(loaded);
      })
      .catch((err: unknown) => {
        if (!cancelled) setError(extractErrorMessage(err, "Failed to load the manual."));
      });
    return () => {
      cancelled = true;
    };
  }, [slug]);

  const blocks = useMemo(() => (manual ? body(parseMarkdown(manual.markdown)) : []), [manual]);
  const entries = useMemo(() => contents(blocks), [blocks]);
  const needle = find.trim().toLowerCase();
  const shown = needle ? entries.filter((e) => e.text.toLowerCase().includes(needle)) : entries;

  function choose(next: string) {
    setFind("");
    setParams({ manual: next });
  }

  return (
    <div className="help">
      <header className="help-top">
        <div>
          <p className="manual-eyebrow">Help</p>
          <h1>{manual?.title ?? "Manuals"}</h1>
          <p className="muted-paragraph">
            The manuals for this release of Holly. Pick a section to jump to it, or print the
            manual, or save it as a PDF from the print dialogue.
          </p>
        </div>
        <div className="help-actions">
          {manuals && manuals.length > 1 && (
            <div className="segmented" role="group" aria-label="Manual">
              {manuals.map((m) => (
                <button
                  key={m.slug}
                  type="button"
                  aria-pressed={m.slug === slug}
                  onClick={() => choose(m.slug)}
                >
                  {m.title}
                </button>
              ))}
            </div>
          )}
          <button type="button" onClick={() => window.print()} disabled={!manual}>
            Print or save as PDF
          </button>
        </div>
      </header>

      {error && (
        <div className="form-error" role="alert">
          {error}
        </div>
      )}
      {!manual && !error && <p className="muted">Loading the manual...</p>}

      {manual && (
        <div className="help-layout">
          <nav className="help-toc" aria-label="Contents">
            <label className="help-find">
              <span>Find a section</span>
              <input
                type="search"
                value={find}
                onChange={(e) => setFind(e.target.value)}
                maxLength={100}
              />
            </label>
            {shown.length === 0 ? (
              <p className="muted">No section is called that.</p>
            ) : (
              <ol>
                {shown.map((entry) => (
                  <li key={entry.id} className={`toc-level-${entry.level}`}>
                    <a
                      href={`#${entry.id}`}
                      onClick={(event) => {
                        event.preventDefault();
                        goTo(entry.id);
                      }}
                    >
                      {entry.section && <span className="toc-number">{entry.section}</span>}
                      {entry.text}
                    </a>
                  </li>
                ))}
              </ol>
            )}
          </nav>
          <article className="manual" aria-label={manual.title}>
            <MarkdownBlocks blocks={blocks} />
          </article>
        </div>
      )}
    </div>
  );
}
