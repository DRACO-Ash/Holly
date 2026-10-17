// The bulkhead plate logo from the Holly design document, coloured by the theme's tokens
// (tokens.css, "Brand"). The trace in its screen is decoration, not a reading.
export default function BrandPlate() {
  return (
    <svg
      className="brand-plate"
      role="img"
      aria-label="Holly, daily operations dashboard"
      width="220"
      height="120"
      viewBox="0 0 220 120"
    >
      <rect className="plate-body" x="2" y="2" width="216" height="116" rx="8" />
      <circle className="plate-screw" cx="12" cy="12" r="3" />
      <circle className="plate-screw" cx="208" cy="12" r="3" />
      <circle className="plate-screw" cx="12" cy="108" r="3" />
      <circle className="plate-screw" cx="208" cy="108" r="3" />
      <rect className="plate-screen" x="20" y="20" width="60" height="45" rx="4" />
      <path className="plate-trace" d="M25 42.5H35L40 28L45 52L50 35L55 42.5H75" />
      <circle className="plate-dot" cx="72" cy="58" r="3" />
      <text className="plate-label" x="90" y="32">
        DAILY OPS
      </text>
      <text className="plate-sub" x="90" y="44">
        DASHBOARD
      </text>
      <text className="plate-name" x="20" y="98">
        [HOLLY]
      </text>
    </svg>
  );
}
