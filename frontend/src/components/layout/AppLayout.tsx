import { Outlet } from 'react-router-dom';
import { Header } from './Header';
import { Sidebar } from './Sidebar';


export function AppLayout() {
  return (
    <>
      <div className="ambient-glow-1"></div>
      <div className="ambient-glow-2"></div>
      <div className="dash-container">
        <Header />

        <div className="dash-layout">
          <Sidebar />

          <main className="dash-main-viewport">
            <Outlet />
          </main>
        </div>
      </div>
    </>
  );
}
