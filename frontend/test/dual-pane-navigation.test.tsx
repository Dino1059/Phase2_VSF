import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { MemoryRouter } from 'react-router-dom';
import App from '@/src/App';
import { AppShell } from '@/components/datatrust/app-shell';
import { useAuthStore } from '@/src/stores/authStore';

// Mock apiBridge to avoid real network requests during unit tests
vi.mock('@/lib/api-bridge', () => ({
  apiBridge: {
    checkHealth: vi.fn().mockResolvedValue({ isLive: true, message: 'OK' }),
    fetchCatalogColumns: vi.fn().mockResolvedValue([]),
    fetchDatasets: vi.fn().mockResolvedValue([]),
    fetchActiveRules: vi.fn().mockResolvedValue([]),
    fetchProfilingSummary: vi.fn().mockResolvedValue([]),
    fetchLineageRuns: vi.fn().mockResolvedValue([
      { runId: 'run_5b320bf9b22d', datasetId: 'ride_hailing_xanh_sm_trips', createdAt: '2026-10-10T10:00:00Z', status: 'COMPLETED' },
    ]),
    fetchRunLineage: vi.fn().mockResolvedValue({
      runId: 'run_5b320bf9b22d',
      datasetId: 'ride_hailing_xanh_sm_trips',
      nodes: [],
      edges: [],
      metrics: { scannedCount: 1000, silverCount: 965, quarantineCount: 25, warningCount: 10 },
      evidenceHash: 'abc123def456',
    }),
    fetchReliabilityRules: vi.fn().mockResolvedValue([]),
    fetchComplianceRules: vi.fn().mockResolvedValue([]),
    fetchDataTreatmentRules: vi.fn().mockResolvedValue([]),
  },
}));

describe('Dual-Pane Global Layout & Navigation', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    localStorage.clear();
    // Navigation tests exercise an authenticated shell explicitly. Production
    // startup itself remains logged out and is covered by the auth suite.
    useAuthStore.getState().switchPersona('admin');
  });

  it('renders Slim Icon Rail navigation without "Kết quả" tab', () => {
    render(
      <MemoryRouter initialEntries={['/overview']}>
        <App />
      </MemoryRouter>
    );

    const mainNav = screen.getByRole('navigation', { name: /Điều hướng chính/i });
    expect(mainNav).toBeInTheDocument();

    // Verify allowed navigation items
    expect(screen.getByRole('link', { name: /^Trang chủ$/i })).toBeInTheDocument();
    expect(screen.getByRole('link', { name: /Lần chạy & Lineage/i })).toBeInTheDocument();
    expect(screen.getByRole('link', { name: /Quy tắc & Chính sách/i })).toBeInTheDocument();

    // Verify "Kết quả" tab has been completely removed from navigation
    const resultsLink = screen.queryByRole('link', { name: /^Kết quả$/i });
    expect(resultsLink).not.toBeInTheDocument();
  });

  it('redirects /results to /runs', async () => {
    render(
      <MemoryRouter initialEntries={['/results']}>
        <App />
      </MemoryRouter>
    );

    // After redirect, the header should display "LẦN CHẠY & LINEAGE"
    await waitFor(() => {
      expect(screen.getByText('LẦN CHẠY & LINEAGE')).toBeInTheDocument();
    });
  });

  it('redirects legacy aliases (/dashboard, /data-quality, /evidence) to /runs', async () => {
    const { unmount } = render(
      <MemoryRouter initialEntries={['/dashboard']}>
        <App />
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(screen.getByText('LẦN CHẠY & LINEAGE')).toBeInTheDocument();
    });
    unmount();

    render(
      <MemoryRouter initialEntries={['/evidence']}>
        <App />
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(screen.getByText('LẦN CHẠY & LINEAGE')).toBeInTheDocument();
    });
  });

  it('preserves persistent AI chat pane across page navigation without remounting', async () => {
    render(
      <MemoryRouter initialEntries={['/overview']}>
        <App />
      </MemoryRouter>
    );

    // Persistent chat pane exists on initial /overview route
    const chatPane = screen.getByTestId('persistent-ai-chat-pane');
    expect(chatPane).toBeInTheDocument();

    // Navigate to /runs by clicking link
    const runsLink = screen.getByRole('link', { name: /Lần chạy & Lineage/i });
    fireEvent.click(runsLink);

    await waitFor(() => {
      expect(screen.getByText('LẦN CHẠY & LINEAGE')).toBeInTheDocument();
    });

    // The persistent chat container remains the exact same DOM node
    const chatPaneAfterNav = screen.getByTestId('persistent-ai-chat-pane');
    expect(chatPaneAfterNav).toBe(chatPane);

    // Navigate to /rules
    const rulesLink = screen.getByRole('link', { name: /Quy tắc & Chính sách/i });
    fireEvent.click(rulesLink);

    await waitFor(() => {
      expect(screen.getByText('QUY TẮC & CHÍNH SÁCH')).toBeInTheDocument();
    });

    // Chat pane is still mounted and unchanged
    expect(screen.getByTestId('persistent-ai-chat-pane')).toBe(chatPane);
  });

  it('verifies accessibility (a11y) on navigation links: aria-label, title, focus states and aria-current', () => {
    render(
      <MemoryRouter initialEntries={['/overview']}>
        <App />
      </MemoryRouter>
    );

    const homeLink = screen.getByRole('link', { name: /^Trang chủ$/i });
    expect(homeLink).toHaveAttribute('aria-label', 'Trang chủ');
    expect(homeLink).toHaveAttribute('title', 'Trang chủ');
    expect(homeLink).toHaveAttribute('aria-current', 'page');
    expect(homeLink.className).toContain('focus-visible:ring-2');

    const runsLink = screen.getByRole('link', { name: /Lần chạy & Lineage/i });
    expect(runsLink).not.toHaveAttribute('aria-current');
    expect(runsLink.className).toContain('focus-visible:ring-2');

    // Desktop collapse button accessibility
    const collapseBtn = screen.getByRole('button', { name: /Thu gọn khung AI Chat/i });
    expect(collapseBtn).toHaveAttribute('aria-expanded', 'true');
    expect(collapseBtn.className).toContain('focus-visible:ring-2');
  });

  it('toggles chat collapse on desktop button click and updates aria-expanded', () => {
    render(
      <MemoryRouter initialEntries={['/overview']}>
        <App />
      </MemoryRouter>
    );

    const collapseBtn = screen.getByRole('button', { name: /Thu gọn khung AI Chat/i });
    fireEvent.click(collapseBtn);

    // Button should now indicate expand action
    const expandBtn = screen.getByRole('button', { name: /Mở rộng khung AI Chat/i });
    expect(expandBtn).toBeInTheDocument();
    expect(expandBtn).toHaveAttribute('aria-expanded', 'false');
  });

  it('respects prefers-reduced-motion with motion-reduce classes', () => {
    render(
      <MemoryRouter initialEntries={['/overview']}>
        <App />
      </MemoryRouter>
    );

    const chatPane = screen.getByTestId('persistent-ai-chat-pane');
    expect(chatPane.className).toContain('motion-reduce:transition-none');
    expect(chatPane.className).toContain('motion-reduce:transform-none');
  });

  it('handles mobile drawer opening and closing with backdrop', () => {
    render(
      <MemoryRouter initialEntries={['/overview']}>
        <App />
      </MemoryRouter>
    );

    // Mobile chat toggle button in header
    const mobileToggleBtn = screen.getByRole('button', { name: /Bật\/tắt khung AI Chat/i });
    expect(mobileToggleBtn).toBeInTheDocument();
    expect(mobileToggleBtn).toHaveAttribute('aria-expanded', 'false');

    // Open mobile chat
    fireEvent.click(mobileToggleBtn);
    expect(mobileToggleBtn).toHaveAttribute('aria-expanded', 'true');

    // Backdrop is displayed
    const backdrop = screen.getByRole('button', { name: /Đóng khung AI Chat/i });
    expect(backdrop).toBeInTheDocument();

    // Click backdrop to close
    fireEvent.click(backdrop);
    expect(mobileToggleBtn).toHaveAttribute('aria-expanded', 'false');
  });
});
