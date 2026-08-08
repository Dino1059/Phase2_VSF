import { BrowserRouter, Routes, Route } from 'react-router-dom';
import { AppShell } from './components/layout/AppShell';
import { ErrorBoundary } from './components/ErrorBoundary';
import { DashboardPage } from './pages/DashboardPage';

export default function App() {
  return (
    <ErrorBoundary>
      <BrowserRouter basename="/v3">
        <Routes>
          <Route path="/" element={<AppShell />} />
          <Route path="/dashboard" element={<DashboardPage />} />
        </Routes>
      </BrowserRouter>
    </ErrorBoundary>
  );
}
