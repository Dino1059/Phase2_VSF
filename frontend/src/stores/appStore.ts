import { create } from 'zustand';
import type { UserRole } from '../types';

interface AppState {
  role: UserRole;
  sidebarCollapsed: boolean;
  workspacePanelVisible: boolean;

  setRole: (role: UserRole) => void;
  toggleSidebar: () => void;
  setWorkspacePanelVisible: (visible: boolean) => void;
}

export const useAppStore = create<AppState>((set) => ({
  role: (localStorage.getItem('datatrust-role') as UserRole) || 'steward',
  sidebarCollapsed: false,
  workspacePanelVisible: true,

  setRole: (role) => {
    localStorage.setItem('datatrust-role', role);
    set({ role });
  },
  toggleSidebar: () => set((state) => ({ sidebarCollapsed: !state.sidebarCollapsed })),
  setWorkspacePanelVisible: (visible) => set({ workspacePanelVisible: visible }),
}));
