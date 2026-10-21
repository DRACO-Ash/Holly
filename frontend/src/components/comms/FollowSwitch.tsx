// Whether Holly pulls a channel. One shared list: a change here changes it for everyone, and the
// audit log records who made it. While a change saves, the switch keeps its focus and ignores
// presses, so a keyboard user is not sent back to the top of the page.
export default function FollowSwitch({
  label,
  on,
  busy = false,
  describedBy,
  onChange,
}: Readonly<{
  label: string;
  on: boolean;
  busy?: boolean;
  describedBy?: string;
  onChange: (on: boolean) => void;
}>) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={on}
      aria-label={`Follow ${label}`}
      aria-describedby={describedBy}
      aria-disabled={busy || undefined}
      className={on ? "follow-switch on" : "follow-switch"}
      onClick={() => {
        if (!busy) onChange(!on);
      }}
    >
      <span className="follow-switch-knob" aria-hidden="true" />
      <span className="follow-switch-text">{on ? "On" : "Off"}</span>
    </button>
  );
}
