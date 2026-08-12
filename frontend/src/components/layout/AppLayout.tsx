import { Outlet, useLocation } from 'react-router-dom';
import { Header } from './Header';
import { Sidebar } from './Sidebar';

export function AppLayout() {
  const location = useLocation();
  const isWorkspace = location.pathname.includes('/workspace') || location.pathname.includes('/chat');

  return (
    <>
      <div className="ambient-glow-1"></div>
      <div className="ambient-glow-2"></div>
      <div className="dash-container">
        <Header />

        <div className="dash-layout">
          <Sidebar />

          <main className={isWorkspace ? 'main-chat-panel' : 'dash-main-container'} style={isWorkspace ? { flex: 1 } : {}}>
            <Outlet />
          </main>
        </div>
      </div>
    </>
  );
}
