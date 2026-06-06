import { NavLink, Link, Outlet } from 'react-router-dom';
import { useCapabilitiesStore } from '../stores/capabilitiesStore';

interface NavItem {
  to: string;
  label: string;
  // Feature flag gating this entry; omitted entries are always shown.
  feature?: string;
}

const NAV_ITEMS: NavItem[] = [
  { to: '/genres', label: 'Genres' },
  { to: '/patterns', label: 'Patterns', feature: 'pattern_library' },
];

function navLinkClass({ isActive }: { isActive: boolean }) {
  const base =
    'text-xs tracking-wider uppercase transition-colors px-2 py-1 rounded ' +
    'focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-[var(--accent-primary)]';
  return isActive
    ? `${base} text-[var(--accent-primary)]`
    : `${base} text-[var(--text-muted)] hover:text-[var(--accent-primary)] focus-visible:text-[var(--accent-primary)]`;
}

function LimitedModeBanner() {
  return (
    <div
      role="status"
      data-testid="limited-mode-banner"
      className="px-6 py-2 text-xs text-center"
      style={{
        background: 'var(--score-mid-faint)',
        borderBottom: '1px solid var(--score-mid)',
        color: 'var(--score-mid)',
      }}
    >
      <span style={{ color: 'var(--text-secondary)' }}>
        <strong style={{ color: 'var(--score-mid)' }}>Limited mode</strong>
        {' — long-term memory is off (pattern library, history, lineage, and learning are '}
        disabled). Generation works normally.
      </span>
    </div>
  );
}

export default function AppShell() {
  const can = useCapabilitiesStore((s) => s.can);
  const isMemoryMode = useCapabilitiesStore((s) => s.isMemoryMode);
  const visibleNav = NAV_ITEMS.filter((item) => !item.feature || can(item.feature));

  return (
    <div className="min-h-dvh flex flex-col">
      <header
        className="flex items-center justify-between px-6 py-3"
        style={{
          background: 'var(--surface-1)',
          borderBottom: '1px solid var(--border-subtle)',
        }}
      >
        <Link
          to="/"
          aria-label="Explorator — back to dashboard"
          className="text-sm font-semibold tracking-tight text-[var(--accent-primary)] focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-[var(--accent-primary)] rounded px-1"
        >
          Explorator
        </Link>
        <nav aria-label="Primary">
          <ul className="flex items-center gap-2">
            {visibleNav.map((item) => (
              <li key={item.to}>
                <NavLink to={item.to} className={navLinkClass}>
                  {item.label}
                </NavLink>
              </li>
            ))}
          </ul>
        </nav>
      </header>
      {isMemoryMode() && <LimitedModeBanner />}
      <main id="main" className="flex-1">
        <Outlet />
      </main>
    </div>
  );
}
