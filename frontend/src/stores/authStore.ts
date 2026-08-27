import { create } from 'zustand';
import { authApi, persistAuthToken, readAuthToken } from '../services/api';

export type UserRole = 'Admin' | 'Steward' | 'Viewer' | 'Analyst' | 'Auditor';

export interface UserProfile {
  user_id: string;
  username: string;
  role: UserRole;
}

export const ROLE_PERMISSIONS: Record<UserRole, ReadonlySet<string>> = {
  Admin: new Set(['read', 'profile', 'propose_rules', 'review_rules', 'execute_transform', 'manage_schedule', 'clear_alerts', 'reset']),
  Analyst: new Set(['read', 'profile', 'propose_rules', 'execute_transform']),
  Auditor: new Set(['read', 'review_rules']),
  Steward: new Set(['read', 'profile', 'propose_rules', 'review_rules', 'execute_transform', 'manage_schedule', 'create_alert']),
  Viewer: new Set(['read']),
};

export function normalizeUserRole(raw?: string | null): UserRole | null {
  const s = String(raw || '').trim().toLowerCase().replace(/[\s_-]+/g, ' ');
  if (!s) return null;
  if (s === 'admin' || s === 'administrator') return 'Admin';
  if (s === 'steward' || s === 'data steward') return 'Steward';
  if (s === 'analyst') return 'Analyst';
  if (s === 'auditor') return 'Auditor';
  if (s === 'viewer' || s === 'read only viewer' || s === 'read-only viewer') return 'Viewer';
  return null;
}

export function roleCan(raw: string | null | undefined, action: string): boolean {
  const role = normalizeUserRole(raw);
  return !!role && ROLE_PERMISSIONS[role].has(action);
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
  hasPermission: (action: string) => boolean;
  canReviewRules: () => boolean;
  canPropose: () => boolean;
  canExecute: () => boolean;
}


function profileFromAuth(res: { user?: unknown; user_profile?: UserProfile; role?: string }, fallbackRole?: string): UserProfile {
  const raw = (res.user_profile && typeof res.user_profile === 'object')
    ? res.user_profile
    : (res.user && typeof res.user === 'object' ? res.user as UserProfile : null);
  const roleRaw = String(raw?.role || res.role || fallbackRole || 'steward');
  const roleNorm = normalizeUserRole(roleRaw) || 'Steward';
  const username = typeof res.user === 'string'
    ? res.user
    : (raw?.username || `${roleNorm.toLowerCase()}@datatrust.os`);
  return {
    user_id: raw?.user_id || `usr_${roleNorm.toLowerCase()}_01`,
    username,
    role: roleNorm,
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
    if (parsed && typeof parsed === 'object' && parsed.role) {
      const role = normalizeUserRole(parsed.role) || 'Steward';
      return { ...(parsed as UserProfile), role };
    }
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
      const fallbackRole = normalizeUserRole(role) || 'Steward';
      const fallbackUser: UserProfile = {
        user_id: `usr_${fallbackRole.toLowerCase()}_01`,
        username: `${fallbackRole.toLowerCase()}@datatrust.os`,
        role: fallbackRole,
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

  hasPermission: (action) => roleCan(get().user?.role, action),

  canReviewRules: () => get().hasPermission('review_rules'),
  canPropose: () => get().hasPermission('propose_rules'),
  canExecute: () => get().hasPermission('execute_transform'),
}));
