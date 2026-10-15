import { render, screen, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { MemoryRouter, Routes, Route } from 'react-router-dom';
import { useAuthStore, getSystemAccess } from '@/src/stores/authStore';
import { AuthGuard } from '@/src/components/auth/AuthGuard';
import { LoginPage } from '@/src/components/auth/LoginPage';
import { AppShell } from '@/components/datatrust/app-shell';
import { SodWorkspace } from '@/src/components/sod/SodWorkspace';

// Mock apiBridge to avoid network calls during tests
vi.mock('@/lib/api-bridge', () => ({
  apiBridge: {
    checkHealth: vi.fn().mockResolvedValue({ isLive: true, message: 'OK' }),
    fetchCatalogColumns: vi.fn().mockResolvedValue([]),
    fetchDatasets: vi.fn().mockResolvedValue([]),
    fetchActiveRules: vi.fn().mockResolvedValue([]),
    fetchProfilingSummary: vi.fn().mockResolvedValue([]),
    fetchLineageRuns: vi.fn().mockResolvedValue([]),
    fetchRunLineage: vi.fn().mockResolvedValue({ nodes: [], edges: [], metrics: {} }),
    fetchReliabilityRules: vi.fn().mockResolvedValue([]),
    fetchComplianceRules: vi.fn().mockResolvedValue([]),
    fetchDataTreatmentRules: vi.fn().mockResolvedValue([]),
  },
}));

describe('Phase 1: Unified Auth & Role-Based Routing Tests', () => {
  beforeEach(() => {
    localStorage.clear();
    // Default to ADMIN before each test
    useAuthStore.getState().switchPersona('admin');
  });

  describe('1. RBAC & Multi-Role System Access Resolution (getSystemAccess)', () => {
    it('classifies single roles correctly across the 3 access domains', () => {
      // Both (4 roles)
      expect(getSystemAccess(['ADMIN'])).toBe('both');
      expect(getSystemAccess(['AUDITOR'])).toBe('both');
      expect(getSystemAccess(['DPO'])).toBe('both');
      expect(getSystemAccess(['SO'])).toBe('both');

      // SoD Only (7 roles)
      expect(getSystemAccess(['REQ'])).toBe('sod_only');
      expect(getSystemAccess(['LM'])).toBe('sod_only');
      expect(getSystemAccess(['IAM'])).toBe('sod_only');
      expect(getSystemAccess(['DEV'])).toBe('sod_only');
      expect(getSystemAccess(['REL'])).toBe('sod_only');
      expect(getSystemAccess(['OPS'])).toBe('sod_only');
      expect(getSystemAccess(['CISO'])).toBe('sod_only');

      // DataTrust Only (3 roles)
      expect(getSystemAccess(['DATA_STEWARD'])).toBe('datatrust_only');
      expect(getSystemAccess(['ANALYST'])).toBe('datatrust_only');
      expect(getSystemAccess(['VIEWER'])).toBe('datatrust_only');
    });

    it('resolves multi-role combinations cleanly to "both"', () => {
      // When user holds both SoD and DataTrust roles
      expect(getSystemAccess(['DEV', 'DATA_STEWARD'])).toBe('both');
      expect(getSystemAccess(['OPS', 'ANALYST'])).toBe('both');

      // When user holds an elevated role among others
      expect(getSystemAccess(['VIEWER', 'ADMIN'])).toBe('both');
      expect(getSystemAccess(['REQ', 'AUDITOR'])).toBe('both');

      // When all roles belong to same domain
      expect(getSystemAccess(['DEV', 'OPS', 'REL'])).toBe('sod_only');
      expect(getSystemAccess(['ANALYST', 'VIEWER'])).toBe('datatrust_only');
    });
  });

  describe('2. Persona Switching and State Hygiene', () => {
    it('switches persona, updates user attributes, and resets session state', () => {
      // Switch to SoD Requester (an.nguyen / req)
      useAuthStore.getState().switchPersona('req');
      let state = useAuthStore.getState();
      expect(state.user?.username).toBe('an.nguyen');
      expect(state.user?.role).toBe('REQ');
      expect(state.systemAccess).toBe('sod_only');
      expect(state.currentPersona?.defaultRoute).toBe('/sod');

      // Switch to Data Steward (steward.le / steward)
      useAuthStore.getState().switchPersona('steward');
      state = useAuthStore.getState();
      expect(state.user?.username).toBe('steward.le');
      expect(state.user?.role).toBe('DATA_STEWARD');
      expect(state.systemAccess).toBe('datatrust_only');
      expect(state.currentPersona?.defaultRoute).toBe('/overview');

      // Logout resets user and isAuthenticated
      useAuthStore.getState().logout();
      state = useAuthStore.getState();
      expect(state.isAuthenticated).toBe(false);
      expect(state.user).toBeNull();
    });
  });

  describe('3. Login Page UI & Persona Switcher', () => {
    it('renders Quick Switcher with 3 visual groups and 14 personas', () => {
      useAuthStore.getState().logout();

      render(
        <MemoryRouter>
          <LoginPage />
        </MemoryRouter>
      );

      // Verify headings and groups
      expect(screen.getByText(/Cổng Đăng nhập Tập trung/i)).toBeInTheDocument();
      expect(screen.getByText(/Cả hai hệ thống/i)).toBeInTheDocument();
      expect(screen.getByText(/Chỉ SoD/i)).toBeInTheDocument();
      expect(screen.getByText(/Chỉ DataTrust/i)).toBeInTheDocument();

      // Verify representative persona cards
      expect(screen.getByText('Nguyễn Quốc Bảo')).toBeInTheDocument(); // ADMIN
      expect(screen.getByText('Nguyễn An')).toBeInTheDocument(); // REQ
      expect(screen.getByText('Lê Nam')).toBeInTheDocument(); // DATA_STEWARD
      expect(screen.getByText('Hoàng Giang')).toBeInTheDocument(); // CISO
    });
  });

  describe('4. AuthGuard Boundary Enforcement (403 Screens)', () => {
    it('blocks sod_only user from accessing DataTrust pages and shows 403', () => {
      // Set to REQ (sod_only)
      useAuthStore.getState().switchPersona('req');

      render(
        <MemoryRouter initialEntries={['/overview']}>
          <Routes>
            <Route
              path="/overview"
              element={
                <AuthGuard requiredAccess="datatrust">
                  <div>DataTrust Protected Content</div>
                </AuthGuard>
              }
            />
          </Routes>
        </MemoryRouter>
      );

      // Must NOT show DataTrust protected content
      expect(screen.queryByText('DataTrust Protected Content')).not.toBeInTheDocument();
      // Must show 403 screen with guidance to SoD
      expect(screen.getByText(/403 · Ranh giới Phân quyền/i)).toBeInTheDocument();
      expect(screen.getByText(/Không có quyền truy cập DataTrust OS/i)).toBeInTheDocument();
      expect(screen.getByRole('button', { name: /Quay lại SoD Flow Workspace/i })).toBeInTheDocument();
    });

    it('blocks datatrust_only user from accessing SoD pages and shows 403', () => {
      // Set to DATA_STEWARD (datatrust_only)
      useAuthStore.getState().switchPersona('steward');

      render(
        <MemoryRouter initialEntries={['/sod']}>
          <Routes>
            <Route
              path="/sod"
              element={
                <AuthGuard requiredAccess="sod">
                  <div>SoD Protected Content</div>
                </AuthGuard>
              }
            />
          </Routes>
        </MemoryRouter>
      );

      // Must NOT show SoD protected content
      expect(screen.queryByText('SoD Protected Content')).not.toBeInTheDocument();
      // Must show 403 screen with guidance to DataTrust
      expect(screen.getByText(/403 · Ranh giới Phân quyền/i)).toBeInTheDocument();
      expect(screen.getByText(/Không có quyền truy cập SoD Flow/i)).toBeInTheDocument();
      expect(screen.getByRole('button', { name: /Quay lại DataTrust OS/i })).toBeInTheDocument();
    });

    it('allows users with "both" access to enter both DataTrust and SoD routes', () => {
      // Set to ADMIN (both)
      useAuthStore.getState().switchPersona('admin');

      const { unmount } = render(
        <MemoryRouter initialEntries={['/overview']}>
          <Routes>
            <Route
              path="/overview"
              element={
                <AuthGuard requiredAccess="datatrust">
                  <div>DataTrust Protected Content</div>
                </AuthGuard>
              }
            />
          </Routes>
        </MemoryRouter>
      );
      expect(screen.getByText('DataTrust Protected Content')).toBeInTheDocument();
      unmount();

      render(
        <MemoryRouter initialEntries={['/sod']}>
          <Routes>
            <Route
              path="/sod"
              element={
                <AuthGuard requiredAccess="sod">
                  <div>SoD Protected Content</div>
                </AuthGuard>
              }
            />
          </Routes>
        </MemoryRouter>
      );
      expect(screen.getByText('SoD Protected Content')).toBeInTheDocument();
    });
  });

  describe('5. DataTrust AppShell Dynamic 4th Tab Rendering', () => {
    it('renders the 4th tab "Phân quyền & SoD" when user has "both" access', () => {
      useAuthStore.getState().switchPersona('admin'); // ADMIN -> both

      render(
        <MemoryRouter initialEntries={['/overview']}>
          <AppShell>
            <div>Overview Inner</div>
          </AppShell>
        </MemoryRouter>
      );

      // All 4 tabs must be in navigation
      expect(screen.getByRole('link', { name: /^Trang chủ$/i })).toBeInTheDocument();
      expect(screen.getByRole('link', { name: /Lần chạy & Lineage/i })).toBeInTheDocument();
      expect(screen.getByRole('link', { name: /Quy tắc & Chính sách/i })).toBeInTheDocument();
      expect(screen.getByRole('link', { name: /Phân quyền & SoD/i })).toBeInTheDocument();
    });

    it('hides the 4th tab "Phân quyền & SoD" when user has "datatrust_only" access', () => {
      useAuthStore.getState().switchPersona('steward'); // DATA_STEWARD -> datatrust_only

      render(
        <MemoryRouter initialEntries={['/overview']}>
          <AppShell>
            <div>Overview Inner</div>
          </AppShell>
        </MemoryRouter>
      );

      // Base 3 tabs exist
      expect(screen.getByRole('link', { name: /^Trang chủ$/i })).toBeInTheDocument();
      expect(screen.getByRole('link', { name: /Lần chạy & Lineage/i })).toBeInTheDocument();
      expect(screen.getByRole('link', { name: /Quy tắc & Chính sách/i })).toBeInTheDocument();
      // 4th tab MUST NOT exist
      expect(screen.queryByRole('link', { name: /Phân quyền & SoD/i })).not.toBeInTheDocument();
    });
  });

  describe('6. SoD Workspace Dual Mode & Subtabs', () => {
    it('renders embedded mode cleanly without standalone top header', () => {
      render(
        <MemoryRouter>
          <SodWorkspace mode="embedded" />
        </MemoryRouter>
      );

      // Navigation tab for matrix exists
      expect(screen.getByRole('button', { name: /Ma trận SoD \(RACIX\)/i })).toBeInTheDocument();
      // Default view is Matrix
      expect(screen.getByText(/Ma trận Phân tách Trách nhiệm/i)).toBeInTheDocument();
      // Standalone header should NOT be present
      expect(screen.queryByText('Standalone Workspace')).not.toBeInTheDocument();
    });

    it('renders standalone mode with dedicated header and allows subtab switching', () => {
      render(
        <MemoryRouter>
          <SodWorkspace mode="standalone" />
        </MemoryRouter>
      );

      // Standalone header bar exists
      expect(screen.getByText('SoD Flow')).toBeInTheDocument();
      expect(screen.getByText('Standalone Workspace')).toBeInTheDocument();

      // Switch to "Phiếu Yêu cầu" subtab
      const ticketsTab = screen.getByRole('button', { name: /Phiếu Yêu cầu/i });
      fireEvent.click(ticketsTab);

      // Check for tickets view content
      expect(screen.getByText(/Tất cả Phiếu Yêu cầu/i)).toBeInTheDocument();
    });
  });
});
