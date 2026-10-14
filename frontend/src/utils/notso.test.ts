import { describe, expect, it } from "vitest";
import { parseArtefacts } from "./notso";

function record(metadata: unknown): Record<string, unknown> {
  return { msgBody: { NOTSO_Image_Metadata: metadata } };
}

describe("parseArtefacts", () => {
  it("reads the JSON string UDL sends", () => {
    const metadata = JSON.stringify([
      {
        id: "a-1",
        filename: "TEST-SAT / Lightcurve",
        caption: "",
        url: "https://images.example/1.png",
      },
    ]);
    expect(parseArtefacts(record(metadata))).toEqual([
      {
        id: "a-1",
        filename: "TEST-SAT / Lightcurve",
        caption: "",
        url: "https://images.example/1.png",
        href: "https://images.example/1.png",
      },
    ]);
  });

  it("accepts an array that is already parsed", () => {
    const [artefact] = parseArtefacts(record([{ filename: "plain.txt" }]));
    expect(artefact.filename).toBe("plain.txt");
    expect(artefact.href).toBeNull();
  });

  it("never offers a link for an unsafe URL", () => {
    const [artefact] = parseArtefacts(record([{ url: "javascript:alert(1)" }]));
    expect(artefact.url).toBe("javascript:alert(1)");
    expect(artefact.href).toBeNull();
  });

  it("keeps only text fields and skips entries that are not objects", () => {
    const artefacts = parseArtefacts(record([{ id: 7, filename: { x: 1 } }, "stray", null]));
    expect(artefacts).toEqual([
      { id: undefined, filename: undefined, caption: undefined, url: undefined, href: null },
    ]);
  });

  it.each([
    ["no record", null],
    ["no message body", {}],
    ["a message body that is not an object", { msgBody: "text" }],
    ["malformed JSON", record("[{")],
    ["JSON that is not a list", record('{"url": "https://images.example/1.png"}')],
    ["a number", record(42)],
  ])("finds nothing in %s", (_label, raw) => {
    expect(parseArtefacts(raw as Record<string, unknown> | null)).toEqual([]);
  });
});
