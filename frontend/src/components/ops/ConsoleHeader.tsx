import type { ReactNode } from "react";
import { relativeTime } from "../../utils/ops";

// A console page's title, what it shows, whether it is live and how fresh, and its actions.
export default function ConsoleHeader({
  title,
  eyebrow,
  children,
  loadedAt,
  refreshing,
  now,
  actions,
}: Readonly<{
  title: string;
  eyebrow: string;
  children?: ReactNode;
  loadedAt: number | null;
  refreshing: boolean;
  now: number;
  actions?: ReactNode;
}>) {
  return (
    <header className="console-header">
      <div className="console-heading">
        <p className="console-eyebrow">{eyebrow}</p>
        <h1>{title}</h1>
        {children && <p className="muted-paragraph console-intro">{children}</p>}
      </div>
      <div className="console-side">
        <p className="console-live">
          <span className={`live-dot${refreshing ? " live-busy" : ""}`} aria-hidden="true" />
          {loadedAt === null
            ? "Connecting..."
            : `Live · updated ${relativeTime(loadedAt, Math.max(now, loadedAt))}`}
          {refreshing && loadedAt !== null && " · refreshing"}
        </p>
        {actions && <div className="console-actions">{actions}</div>}
      </div>
    </header>
  );
}
