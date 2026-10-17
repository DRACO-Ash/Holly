import { useState } from "react";
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
];

export default function Layout() {
  const { logout, user } = useAuth();
  const { pathname } = useLocation();
  const [display, setDisplay] = useState<DisplayPrefs>(() => loadDisplayPrefs());

  function changeDisplay(next: DisplayPrefs) {
    setDisplay(next);
    saveDisplayPrefs(next);
  }

  const visibleItems = NAV_ITEMS.filter((item) => {
    if (!item.requiredRoles) return true;
    if (!user) return false;
    return item.requiredRoles.includes(user.role);
  });

  return (
    <EventTimersProvider>
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
            <button type="button" className="logout-btn" onClick={logout}>
              Sign out
            </button>
          </div>
        </header>
        <TimerBanner />
        <div className="app-body">
          <nav className="app-nav">
            {visibleItems.map((item) => (
              <Link
                key={item.to}
                to={item.to}
                className={pathname === item.to ? "nav-link active" : "nav-link"}
              >
                {item.label}
              </Link>
            ))}
          </nav>
          <main className="app-main">
            <div className="crt-screen">
              <div className="crt-content">
                <Outlet />
              </div>
            </div>
          </main>
        </div>
      </div>
    </EventTimersProvider>
  );
}
