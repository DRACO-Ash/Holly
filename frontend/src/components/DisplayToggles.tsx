import type { DisplayPrefs } from "../utils/displayPrefs";

interface DisplayTogglesProps {
  prefs: DisplayPrefs;
  onChange: (prefs: DisplayPrefs) => void;
}

// The two screen effects of the Holly design document, switched per analyst. Flicker also stops
// whenever the operating system asks for reduced motion.
export default function DisplayToggles({ prefs, onChange }: DisplayTogglesProps) {
  return (
    <fieldset className="display-toggles">
      <legend className="visually-hidden">Screen effects</legend>
      <label className="display-toggle">
        <input
          type="checkbox"
          checked={prefs.scanlines}
          onChange={(e) => onChange({ ...prefs, scanlines: e.target.checked })}
        />
        Scanlines
      </label>
      <label className="display-toggle">
        <input
          type="checkbox"
          checked={prefs.flicker}
          onChange={(e) => onChange({ ...prefs, flicker: e.target.checked })}
        />
        CRT flicker
      </label>
    </fieldset>
  );
}
