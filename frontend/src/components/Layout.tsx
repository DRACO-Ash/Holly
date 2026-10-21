import { type ReactNode, useState } from "react";
import { Link, Outlet, useLocation } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import { EventTimersProvider } from "../context/EventTimersContext";
import DisplayToggles from "./DisplayToggles";
import TimerBanner from "./TimerBanner";
import type { UserRole } from "../types";
import { type DisplayPrefs, loadDisplayPrefs, saveDisplayPrefs } from "../utils/displayPrefs";

interface NavItem {
  to: string;
  label: string;
  requiredRoles?: ReadonlyArray<UserRole>;
}

const NAV_ITEMS: ReadonlyArray<NavItem> = [
  { to: "/", label: "Dashboard" },
  { to: "/notifications", label: "Notifications" },
  { to: "/maneuvers", label: "Maneuvers" },
  { to: "/comms", label: "Comms" },
  { to: "/procedures", label: "Procedures" },
  { to: "/shift-log", label: "Shift log" },
  { to: "/audit", label: "Audit log", requiredRoles: ["operator", "admin"] },
  { to: "/users", label: "Users", requiredRoles: ["admin"] },
  { to: "/password", label: "Password" },
];

// The timers' provider, left out while a password an admin set is still to change: Holly would
// refuse its polls, and nothing reachable then shows timers.
function Timers({ off, children }: Readonly<{ off: boolean; children: ReactNode }>) {
  return off ? <>{children}</> : <EventTimersProvider>{children}</EventTimersProvider>;
}

export default function Layout() {
  const { logout, user } = useAuth();
  const { pathname } = useLocation();
  const [display, setDisplay] = useState<DisplayPrefs>(() => loadDisplayPrefs());

  function changeDisplay(next: DisplayPrefs) {
    setDisplay(next);
    saveDisplayPrefs(next);
  }

  // Until a password an admin set is changed, the password page is the only place to go.
  const changeDue = user?.must_change_password ?? false;
  const visibleItems = NAV_ITEMS.filter((item) => {
    if (changeDue) return item.to === "/password";
    if (!item.requiredRoles) return true;
    if (!user) return false;
    return item.requiredRoles.includes(user.role);
  });

  return (
    <Timers off={changeDue}>
      <div
        className="app-shell"
        data-scanlines={display.scanlines ? "on" : "off"}
        data-flicker={display.flicker ? "on" : "off"}
      >
        <header className="app-header">
          <div className="app-brand">
            <span className="brand-badge" aria-hidden="true">
              [H]
            </span>
            <span className="brand-text">
              <span className="app-title">
                <span aria-hidden="true">[</span>Holly<span aria-hidden="true">]</span>
              </span>
              <span className="brand-sub">Daily operations dashboard</span>
            </span>
          </div>
          <div className="app-header-right">
            <DisplayToggles prefs={display} onChange={changeDisplay} />
            {user && <span className="app-user">{user.username}</span>}
            {!changeDue && (
              <Link
                to="/help"
                className="help-link"
                aria-current={pathname === "/help" ? "page" : undefined}
              >
                Help
              </Link>
            )}
            <button type="button" className="logout-btn" onClick={logout}>
              Sign out
            </button>
          </div>
        </header>
        {!changeDue && <TimerBanner />}
        <div className="app-body">
          <nav className="app-nav">
            {visibleItems.map((item) => (
              <Link
                key={item.to}
                to={item.to}
                className={pathname === item.to ? "nav-link active" : "nav-link"}
                aria-current={pathname === item.to ? "page" : undefined}
              >
                {item.label}
              </Link>
            ))}
          </nav>
          <main className="app-main">
            <span className="screw screw-tl" aria-hidden="true" />
            <span className="screw screw-tr" aria-hidden="true" />
            <span className="screw screw-bl" aria-hidden="true" />
            <span className="screw screw-br" aria-hidden="true" />
            <div className="crt-screen">
              <div className="crt-content">
                <Outlet />
              </div>
            </div>
          </main>
        </div>
      </div>
    </Timers>
  );
}
