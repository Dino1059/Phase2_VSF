import { create } from 'zustand';
import { authApi, persistAuthToken, readAuthToken } from '../services/api';

export type UserRole = 'Admin' | 'Steward' | 'Viewer' | 'Analyst' | 'Auditor';

export interface UserProfile {
  user_id: string;
  username: string;
  role: UserRole;
}

interface AuthState {
  token: string | null;
  user: UserProfile | null;
  isAuthenticated: boolean;
  isAuthModalOpen: boolean;
  setAuthModalOpen: (open: boolean) => void;
  login: (username: string, password?: string, role?: string) => Promise<void>;
  quickSwitchRole: (role: string) => Promise<void>;
  logout: () => void;
  isAdmin: () => boolean;
  isStewardOrAdmin: () => boolean;
}

const TOKEN_KEY = 'datatrust_jwt_token';
const USER_KEY = 'datatrust_user_profile';

const initialToken = readAuthToken();
const initialUser: UserProfile = (() => {
  try {
    const raw = localStorage.getItem(USER_KEY);
    return raw ? JSON.parse(raw) : { user_id: 'usr_admin_01', username: 'admin@datatrust.os', role: 'Admin' };
  } catch {
    return { user_id: 'usr_admin_01', username: 'admin@datatrust.os', role: 'Admin' };
  }
})();

export const useAuthStore = create<AuthState>((set, get) => ({
  token: initialToken,
  user: initialUser,
  isAuthenticated: !!initialToken,
  isAuthModalOpen: false,

  setAuthModalOpen: (open) => set({ isAuthModalOpen: open }),

  login: async (username, password, role) => {
    try {
      const res = await authApi.login({ username, password, role });
      if (res && res.access_token) {
        persistAuthToken(res.access_token, (res.user?.role || role || 'steward').toString().toLowerCase());
        localStorage.setItem(USER_KEY, JSON.stringify(res.user));
        set({
          token: res.access_token,
          user: res.user as UserProfile,
          isAuthenticated: true,
          isAuthModalOpen: false,
        });
      }
    } catch (err) {
      console.error('Login failed:', err);
      throw err;
    }
  },

  quickSwitchRole: async (role: string) => {
    try {
      const res = await authApi.quickSwitch(role);
      if (res && res.access_token) {
        persistAuthToken(res.access_token, (res.user?.role || role || 'steward').toString().toLowerCase());
        localStorage.setItem(USER_KEY, JSON.stringify(res.user));
        set({
          token: res.access_token,
          user: res.user as UserProfile,
          isAuthenticated: true,
          isAuthModalOpen: false,
        });
      }
    } catch (err) {
      console.error('Quick switch failed:', err);
      // Fallback local role update
      const fallbackUser: UserProfile = {
        user_id: `usr_${role.toLowerCase()}_01`,
        username: `${role.toLowerCase()}@datatrust.os`,
        role: (role.charAt(0).toUpperCase() + role.slice(1).toLowerCase()) as UserRole,
      };
      set({ user: fallbackUser, isAuthModalOpen: false });
    }
  },

  logout: () => {
    localStorage.removeItem(TOKEN_KEY);
    localStorage.removeItem('datatrust-token');
    localStorage.removeItem(USER_KEY);
    set({
      token: null,
      user: null,
      isAuthenticated: false,
    });
  },

  isAdmin: () => {
    const role = get().user?.role;
    return role === 'Admin' || role === ('admin' as any);
  },

  isStewardOrAdmin: () => {
    const role = get().user?.role;
    return role === 'Admin' || role === 'Steward' || role === ('admin' as any) || role === ('steward' as any);
  },
}));
