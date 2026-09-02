import { useEffect, useRef, useState } from 'react'
import { Link, NavLink, Outlet, useLocation } from 'react-router-dom'

import { useAuth } from '../context/AuthContext'
import { ChartIcon, FolderIcon, LayoutIcon, LogoutIcon, MenuIcon, ShieldIcon, XIcon } from '../components/Icons'

/**
 * Root application layout: brand header, primary navigation, routed content.
 *
 * Step 10 changes:
 *  - the four-item Command Center navigation (Dashboard / Verify Identity /
 *    My Cases / Reports);
 *  - a real mobile menu. Before this step everything below `sm` simply lost
 *    the navigation with no replacement; now a hamburger disclosure takes
 *    over until `lg`, closes after navigation and on Escape, and offers logout.
 *
 * Premium light identity: white / light-gray surfaces with green accents.
 */

const NAV_ITEMS = [
  { to: '/', label: 'Dashboard', end: true },
  { to: '/verify', label: 'Verify Identity', end: false },
  { to: '/verifications', label: 'My Cases', end: false },
  { to: '/reports', label: 'Reports', end: false },
]

const MOBILE_ICONS = {
  '/': LayoutIcon,
  '/verify': ShieldIcon,
  '/verifications': FolderIcon,
  '/reports': ChartIcon,
} as const

export default function AppLayout() {
  const { user, logout } = useAuth()
  const location = useLocation()
  const [isMenuOpen, setIsMenuOpen] = useState(false)
  const menuButtonRef = useRef<HTMLButtonElement>(null)

  // A new page means the menu has done its job - close it (requirement 11).
  useEffect(() => {
    setIsMenuOpen(false)
  }, [location.pathname])

  // Escape closes the menu and hands focus back to the hamburger button.
  useEffect(() => {
    if (!isMenuOpen) return
    function handleKeyDown(event: KeyboardEvent) {
      if (event.key === 'Escape') {
        setIsMenuOpen(false)
        menuButtonRef.current?.focus()
      }
    }
    document.addEventListener('keydown', handleKeyDown)
    return () => document.removeEventListener('keydown', handleKeyDown)
  }, [isMenuOpen])

  const desktopLinkClasses = ({ isActive }: { isActive: boolean }) =>
    `rounded-lg px-3 py-1.5 text-sm font-medium transition duration-200 ease-out ${
      isActive
        ? 'bg-brand-50 text-brand-700 ring-1 ring-brand-200'
        : 'text-gray-600 hover:bg-gray-100 hover:text-gray-900'
    }`

  return (
    <div className="flex min-h-screen flex-col bg-gray-50">
      <a
        href="#main-content"
        className="sr-only focus:not-sr-only focus:absolute focus:top-2 focus:left-2 focus:z-50 focus:rounded-lg focus:bg-white focus:px-4 focus:py-2 focus:text-sm focus:font-medium focus:text-brand-700 focus:shadow-md"
      >
        Skip to main content
      </a>

      <header className="sticky top-0 z-40 border-b border-gray-200 bg-white/90 backdrop-blur">
        <div className="mx-auto flex h-16 w-full max-w-7xl items-center justify-between gap-3 px-4 sm:px-6">
          <Link to="/" className="flex min-w-0 items-center gap-3 rounded-xl focus-visible:outline-2">
            <span
              className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-gradient-to-br from-brand-500 to-brand-700 text-sm font-bold text-white shadow-sm"
              aria-hidden="true"
            >
              GV
            </span>
            <span className="min-w-0 leading-tight">
              <span className="block truncate text-sm font-semibold tracking-tight text-gray-900">
                GeneVerify AI
              </span>
              <span className="hidden truncate text-xs text-gray-500 sm:block">
                AI-Powered Identity Verification
              </span>
            </span>
          </Link>

          <nav className="hidden items-center gap-1 lg:flex" aria-label="Primary">
            {NAV_ITEMS.map((item) => (
              <NavLink key={item.to} to={item.to} end={item.end} className={desktopLinkClasses}>
                {item.label}
              </NavLink>
            ))}
          </nav>

          <div className="flex min-w-0 items-center gap-2 sm:gap-3">
            <span className="gv-badge hidden bg-brand-50 text-brand-700 ring-brand-200 xl:inline-flex">
              Prototype · Synthetic data only
            </span>
            {user && (
              <div className="hidden items-center gap-2 border-l border-gray-200 pl-3 lg:flex">
                <div className="text-right leading-tight">
                  <p className="max-w-[10rem] truncate text-xs font-semibold text-gray-800">
                    {user.username}
                  </p>
                  <p className="gv-eyebrow">{user.role}</p>
                </div>
                <button
                  type="button"
                  onClick={() => void logout()}
                  className="gv-btn gv-btn-sm gv-btn-secondary"
                >
                  <LogoutIcon size={14} />
                  Log out
                </button>
              </div>
            )}

            <button
              ref={menuButtonRef}
              type="button"
              onClick={() => setIsMenuOpen((open) => !open)}
              aria-expanded={isMenuOpen}
              aria-controls="mobile-navigation"
              className="gv-btn gv-btn-secondary lg:hidden"
            >
              {isMenuOpen ? <XIcon size={16} /> : <MenuIcon size={16} />}
              <span>{isMenuOpen ? 'Close menu' : 'Menu'}</span>
            </button>
          </div>
        </div>

        {/* Mobile / tablet menu: rendered only while open, so it is absent
            from the accessibility tree when closed. */}
        {isMenuOpen && (
          <div
            id="mobile-navigation"
            className="animate-gv-menu border-t border-gray-200 bg-white lg:hidden"
          >
            <nav className="mx-auto flex w-full max-w-7xl flex-col gap-1 px-4 py-3 sm:px-6" aria-label="Mobile">
              {NAV_ITEMS.map((item) => {
                const Icon = MOBILE_ICONS[item.to as keyof typeof MOBILE_ICONS] ?? LayoutIcon
                return (
                  <NavLink
                    key={item.to}
                    to={item.to}
                    end={item.end}
                    className={({ isActive }) =>
                      `flex items-center gap-3 rounded-xl px-3 py-2.5 text-sm font-medium transition ${
                        isActive
                          ? 'bg-brand-50 text-brand-700 ring-1 ring-brand-200'
                          : 'text-gray-700 hover:bg-gray-100'
                      }`
                    }
                  >
                    <span className="text-brand-600" aria-hidden="true">
                      <Icon size={16} />
                    </span>
                    {item.label}
                  </NavLink>
                )
              })}
            </nav>
            <div className="mx-auto flex w-full max-w-7xl flex-col gap-3 border-t border-gray-100 px-4 py-3 sm:px-6">
              <div className="flex items-center justify-between gap-3">
                <div className="min-w-0 leading-tight">
                  <p className="truncate text-sm font-semibold text-gray-900">
                    {user?.username ?? 'Not signed in'}
                  </p>
                  <p className="gv-eyebrow">{user?.role ?? 'guest'}</p>
                </div>
                <button
                  type="button"
                  onClick={() => void logout()}
                  className="gv-btn gv-btn-sm gv-btn-secondary shrink-0"
                >
                  <LogoutIcon size={14} />
                  Log out
                </button>
              </div>
              <p className="gv-badge self-start bg-brand-50 text-brand-700 ring-brand-200">
                Prototype · Synthetic data only
              </p>
            </div>
          </div>
        )}
      </header>

      <main id="main-content" className="mx-auto w-full max-w-7xl flex-1 px-4 py-8 sm:px-6 sm:py-10">
        <Outlet />
      </main>

      <footer className="border-t border-gray-200 bg-white">
        <div className="mx-auto flex w-full max-w-7xl flex-col items-center justify-between gap-2 px-4 py-6 text-xs text-gray-500 sm:flex-row sm:px-6">
          <p className="text-center sm:text-left">
            GeneVerify is a prototype and is not a legally valid forensic identity system.
          </p>
          <p className="flex items-center gap-3">
            <Link to="/overview" className="rounded font-medium text-gray-500 transition hover:text-brand-700">
              About GeneVerify
            </Link>
            <span aria-hidden="true">·</span>
            <Link to="/lookup" className="rounded font-medium text-gray-500 transition hover:text-brand-700">
              CNIC lookup (test tool)
            </Link>
            <span aria-hidden="true">·</span>
            <span>FastAPI · React · TypeScript · Tailwind CSS</span>
          </p>
        </div>
      </footer>
    </div>
  )
}
