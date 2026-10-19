import type { DisplayPrefs } from "../utils/displayPrefs";

interface DisplayTogglesProps {
  prefs: DisplayPrefs;
  onChange: (prefs: DisplayPrefs) => void;
}

// The two screen effects of the Holly design document, switched per analyst. When the operating
// system asks for reduced motion, flicker is off and its box is greyed out, saying why.
export default function DisplayToggles({ prefs, onChange }: Readonly<DisplayTogglesProps>) {
  const reduceMotion =
    typeof window !== "undefined" &&
    window.matchMedia?.("(prefers-reduced-motion: reduce)").matches === true;
  return (
    <fieldset className="display-toggles">
      <legend className="visually-hidden">Screen effects</legend>
      <label className="display-toggle">
        <input
          type="checkbox"
          checked={prefs.scanlines}
          onChange={(e) => onChange({ ...prefs, scanlines: e.target.checked })}
        />
        <span>Scanlines</span>
      </label>
      <label
        className="display-toggle"
        title={reduceMotion ? "Off: your system reduces motion" : undefined}
      >
        <input
          type="checkbox"
          checked={prefs.flicker && !reduceMotion}
          disabled={reduceMotion}
          aria-describedby={reduceMotion ? "flicker-off-note" : undefined}
          onChange={(e) => onChange({ ...prefs, flicker: e.target.checked })}
        />
        <span>CRT flicker</span>
      </label>
      {reduceMotion && (
        <span id="flicker-off-note" hidden>
          Off: your system reduces motion
        </span>
      )}
    </fieldset>
  );
}
