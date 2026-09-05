import { useEffect, useState } from 'react';
import { Outlet, useLocation } from 'react-router-dom';
import { Header } from './Header';
import { Sidebar } from './Sidebar';
import { useAuthStore } from '../../stores/authStore';

export function AppLayout() {
  const [navOpen, setNavOpen] = useState(false);
  const loc = useLocation();
  const isAuthenticated = useAuthStore((s) => s.isAuthenticated);
  const setAuthModalOpen = useAuthStore((s) => s.setAuthModalOpen);

  useEffect(() => { setNavOpen(false); }, [loc.pathname, loc.search, loc.hash]);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => { if (e.key === 'Escape') setNavOpen(false); };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, []);

  useEffect(() => {
    if (!isAuthenticated) setAuthModalOpen(true);
  }, [isAuthenticated, setAuthModalOpen]);

  return (
    <>
      <div className="ambient-glow-1"></div>
      <div className="ambient-glow-2"></div>
      <div className="dash-container">
        <Header navOpen={navOpen} onToggleNav={() => setNavOpen((v) => !v)} />
        <div className={`dash-layout ${navOpen ? 'nav-open' : ''}`}>
          <div
            className="nav-backdrop"
            onClick={() => setNavOpen(false)}
            aria-hidden={!navOpen}
          />
          <Sidebar onNavigate={() => setNavOpen(false)} />
          <main className="dash-main-viewport">
            <Outlet />
          </main>
        </div>
      </div>
    </>
  );
}
