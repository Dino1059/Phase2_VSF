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
  restoreSession: (token: string, user: UserProfile) => void;
  logout: () => void;
  isAdmin: () => boolean;
  isStewardOrAdmin: () => boolean;
}


function profileFromAuth(res: { user?: unknown; user_profile?: UserProfile; role?: string }, fallbackRole?: string): UserProfile {
  const raw = (res.user_profile && typeof res.user_profile === 'object')
    ? res.user_profile
    : (res.user && typeof res.user === 'object' ? res.user as UserProfile : null);
  const roleRaw = String(raw?.role || res.role || fallbackRole || 'steward');
  const role = (roleRaw.charAt(0).toUpperCase() + roleRaw.slice(1).toLowerCase()) as UserRole;
  const username = typeof res.user === 'string'
    ? res.user
    : (raw?.username || `${role.toLowerCase()}@datatrust.os`);
  return {
    user_id: raw?.user_id || `usr_${role.toLowerCase()}_01`,
    username,
    role,
  };
}

const TOKEN_KEY = 'datatrust_jwt_token';
const USER_KEY = 'datatrust_user_profile';

const initialToken = readAuthToken();
const STEWARD_USER: UserProfile = { user_id: 'usr_steward_01', username: 'steward', role: 'Steward' };
const initialUser: UserProfile = (() => {
  try {
    const raw = localStorage.getItem(USER_KEY);
    const parsed = raw ? JSON.parse(raw) : null;
    if (parsed && typeof parsed === 'object' && parsed.role) return parsed as UserProfile;
    const storedRole = String(localStorage.getItem('datatrust-role') || '').toLowerCase();
    if (storedRole === 'admin' || storedRole === 'administrator') {
      return { user_id: 'usr_admin_01', username: 'admin', role: 'Admin' };
    }
    return STEWARD_USER;
  } catch {
    return STEWARD_USER;
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
        const profile = profileFromAuth(res, role);
        persistAuthToken(res.access_token, profile.role.toLowerCase());
        localStorage.setItem(USER_KEY, JSON.stringify(profile));
        set({
          token: res.access_token,
          user: profile,
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
        const profile = profileFromAuth(res, role);
        persistAuthToken(res.access_token, profile.role.toLowerCase());
        localStorage.setItem(USER_KEY, JSON.stringify(profile));
        set({
          token: res.access_token,
          user: profile,
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

  restoreSession: (token, user) => {
    persistAuthToken(token, user.role.toLowerCase());
    localStorage.setItem(USER_KEY, JSON.stringify(user));
    set({
      token,
      user,
      isAuthenticated: true,
    });
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
    const role = String(get().user?.role || '').toLowerCase();
    return role === 'admin' || role === 'administrator';
  },

  isStewardOrAdmin: () => {
    const role = get().user?.role;
    return role === 'Admin' || role === 'Steward' || role === ('admin' as any) || role === ('steward' as any);
  },
}));
