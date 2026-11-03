import type { EventKind, Regime, Urgency } from "../../utils/ops";
import { KIND_LABELS, URGENCY_LABELS } from "../../utils/ops";

// A kind's mark has its own shape as well as its hue, so the kinds never part by colour alone.
export function KindGlyph({ kind }: Readonly<{ kind: EventKind }>) {
  return <span className={`kind-glyph kind-${kind}`} aria-hidden="true" />;
}

export function KindBadge({ kind, label }: Readonly<{ kind: EventKind; label?: string }>) {
  return (
    <span className={`kind-badge kind-${kind}`}>
      <KindGlyph kind={kind} />
      {label ?? KIND_LABELS[kind]}
    </span>
  );
}

const REGIME_SOURCE = {
  notice: "as the notice states",
  elset: "from the latest element set's period and eccentricity",
} as const;

export function RegimeBadge({
  regime,
  from,
}: Readonly<{ regime: Regime | null; from?: "notice" | "elset" | null }>) {
  if (!regime) return null;
  const title = from ? `${regime}, ${REGIME_SOURCE[from]}` : regime;
  return (
    <span className={`regime-badge regime-${regime.toLowerCase()}`} title={title}>
      {regime}
      {from === "elset" && (
        <span className="regime-derived">
          <span aria-hidden="true">*</span>
          <span className="visually-hidden">, derived from the element set</span>
        </span>
      )}
    </span>
  );
}

export function UrgencyBadge({ urgency }: Readonly<{ urgency: Urgency }>) {
  if (urgency === "none") return null;
  return <span className={`urgency-pill urgency-${urgency}`}>{URGENCY_LABELS[urgency]}</span>;
}

export function StatusBadge({ status }: Readonly<{ status: string | null }>) {
  if (!status) return null;
  return <span className={`status-pill status-${status.toLowerCase()}`}>{status}</span>;
}

export function SourceBadge({ source, slot }: Readonly<{ source: string; slot: number }>) {
  return (
    <span className={`source-badge source-${slot}`}>
      <span className="source-dot" aria-hidden="true" />
      {source}
    </span>
  );
}
