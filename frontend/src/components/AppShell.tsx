import { NavLink, Link, Outlet } from 'react-router-dom';

const NAV_ITEMS = [
  { to: '/genres', label: 'Genres' },
  { to: '/patterns', label: 'Patterns' },
];

function navLinkClass({ isActive }: { isActive: boolean }) {
  const base =
    'text-xs tracking-wider uppercase transition-colors px-2 py-1 rounded ' +
    'focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-[var(--accent-primary)]';
  return isActive
    ? `${base} text-[var(--accent-primary)]`
    : `${base} text-[var(--text-muted)] hover:text-[var(--accent-primary)] focus-visible:text-[var(--accent-primary)]`;
}

export default function AppShell() {
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
            {NAV_ITEMS.map((item) => (
              <li key={item.to}>
                <NavLink to={item.to} className={navLinkClass}>
                  {item.label}
                </NavLink>
              </li>
            ))}
          </ul>
        </nav>
      </header>
      <main id="main" className="flex-1">
        <Outlet />
      </main>
    </div>
  );
}
