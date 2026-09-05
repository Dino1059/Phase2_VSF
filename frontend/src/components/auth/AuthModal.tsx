import React, { useState } from 'react';
import { Shield, Eye, KeyRound, X, CheckCircle2, Crown, Sparkles, BarChart3 } from 'lucide-react';
import { useAuthStore, UserRole } from '../../stores/authStore';

export const AuthModal: React.FC = () => {
  const { isAuthModalOpen, setAuthModalOpen, user, isAuthenticated, quickSwitchRole, login } = useAuthStore();
  const required = !isAuthenticated;
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [loadingRole, setLoadingRole] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);


  if (!isAuthModalOpen) return null;

  const handleSwitch = async (role: string) => {
    setLoadingRole(role);
    setError(null);
    try {
      await quickSwitchRole(role);
    } catch (err: any) {
      setError(err.message || 'Role switch failed');
    } finally {
      setLoadingRole(null);
    }
  };

  const handleCustomLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!username.trim()) return;
    setLoadingRole('custom');
    setError(null);
    try {
      await login(username, password);
    } catch (err: any) {
      setError(err.message || 'Login failed');
    } finally {
      setLoadingRole(null);
    }
  };

  const personas: Array<{ role: UserRole; label: string; email: string; department: string; desc: string; icon: any; color: string }> = [
    {
      role: 'Admin',
      label: 'Administrator',
      email: 'admin@datatrust.os',
      department: 'Operations',
      desc: 'Full system control, DB reset, prompt injection, rule execution & config.',
      icon: Crown,
      color: 'var(--alert-magenta, #f43f5e)',
    },
    {
      role: 'Analyst',
      label: 'Fleet Analyst',
      email: 'analyst@datatrust.os',
      department: 'Fleet Analytics',
      desc: 'Profile datasets, propose rules, run eval vs GT. No reset / HITL approve.',
      icon: BarChart3,
      color: '#38bdf8',
    },
    {
      role: 'Steward',
      label: 'Data Steward',
      email: 'steward@datatrust.os',
      department: 'Data Quality',
      desc: 'Rule proposals, HITL approvals, quarantine triage & telemetry inspection.',
      icon: Shield,
      color: 'var(--electric-green, #10b981)',
    },
    {
      role: 'Viewer',
      label: 'Read-Only Viewer',
      email: 'viewer@datatrust.os',
      department: 'Audit',
      desc: 'Observability & audit logs view only. No execution or reset permissions.',
      icon: Eye,
      color: 'var(--text-cyan, #06b6d4)',
    },
  ];

  return (
    <div
      className="modal-overlay"
      style={{
        position: 'fixed',
        inset: 0,
        zIndex: 9999,
        backgroundColor: 'rgba(0, 0, 0, 0.65)',
        backdropFilter: 'blur(8px)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        padding: '16px',
      }}
      onClick={() => { if (!required) setAuthModalOpen(false); }}
    >
      <div
        className="auth-modal-card"
        style={{
          width: '100%',
          maxWidth: '480px',
          backgroundColor: 'var(--bg-card, #121826)',
          border: '1px solid var(--glass-border-bright, rgba(255,255,255,0.15))',
          borderRadius: '16px',
          padding: '24px',
          boxShadow: '0 20px 50px rgba(0,0,0,0.5)',
          color: 'var(--text-main, #ffffff)',
          position: 'relative',
        }}
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '20px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
            <div
              style={{
                width: '36px',
                height: '36px',
                borderRadius: '10px',
                backgroundColor: 'rgba(14, 165, 233, 0.15)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                color: 'var(--neon-cyan, #38bdf8)',
              }}
            >
              <KeyRound size={18} />
            </div>
            <div>
              <div style={{ fontSize: '16px', fontWeight: 600 }}>Role & Identity Access</div>
              <div style={{ fontSize: '12px', color: 'var(--text-muted, #94a3b8)' }} data-testid="auth-active-identity">
                {isAuthenticated && user
                  ? <>Active: <strong style={{ color: 'var(--neon-cyan)' }}>{user.username}</strong> ({user.role})</>
                  : 'Not signed in'}
              </div>
            </div>
          </div>

          {!required && (
          <button
            type="button"
            onClick={() => setAuthModalOpen(false)}
            style={{
              background: 'transparent',
              border: 'none',
              color: 'var(--text-muted)',
              cursor: 'pointer',
              padding: '6px',
              borderRadius: '8px',
            }}
          >
            <X size={18} />
          </button>
          )}
        </div>

        {error && (
          <div
            style={{
              backgroundColor: 'rgba(239, 68, 68, 0.15)',
              border: '1px solid rgba(239, 68, 68, 0.3)',
              color: '#f87171',
              padding: '8px 12px',
              borderRadius: '8px',
              fontSize: '12px',
              marginBottom: '16px',
            }}
          >
            {error}
          </div>
        )}

        {/* 1-Click Persona Quick-Switch */}
        <div style={{ marginBottom: '24px' }}>
          <div
            style={{
              fontSize: '11px',
              fontWeight: 600,
              letterSpacing: '0.05em',
              textTransform: 'uppercase',
              color: 'var(--text-muted, #94a3b8)',
              marginBottom: '10px',
              display: 'flex',
              alignItems: 'center',
              gap: '6px',
            }}
          >
            <Sparkles size={12} style={{ color: 'var(--warning-amber)' }} />
            1-Click Demo Persona Switcher
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
            {personas.map((p) => {
              const Icon = p.icon;
              const isActive = isAuthenticated && user?.role?.toLowerCase() === p.role.toLowerCase();
              return (
                <button
                  key={p.role}
                  type="button"
                  onClick={() => handleSwitch(p.role)}
                  disabled={loadingRole === p.role}
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'space-between',
                    padding: '12px 14px',
                    borderRadius: '12px',
                    backgroundColor: isActive ? 'rgba(255, 255, 255, 0.08)' : 'var(--bg-card-hover, rgba(255,255,255,0.03))',
                    border: `1px solid ${isActive ? p.color : 'var(--glass-border, rgba(255,255,255,0.08))'}`,
                    cursor: 'pointer',
                    textAlign: 'left',
                    transition: 'all 150ms ease',
                  }}
                >
                  <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                    <div
                      style={{
                        width: '32px',
                        height: '32px',
                        borderRadius: '8px',
                        backgroundColor: 'rgba(255, 255, 255, 0.06)',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        color: p.color,
                      }}
                    >
                      <Icon size={16} />
                    </div>
                    <div>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                        <span style={{ fontSize: '13px', fontWeight: 600, color: 'var(--text-main, #ffffff)' }}>
                          {p.label}
                        </span>
                        <span
                          style={{
                            fontSize: '10.5px',
                            padding: '1px 6px',
                            borderRadius: '4px',
                            backgroundColor: 'rgba(255,255,255,0.06)',
                            color: 'var(--text-muted, #94a3b8)',
                          }}
                        >
                          {p.email} · {p.department}
                        </span>
                      </div>
                      <div style={{ fontSize: '11px', color: 'var(--text-muted, #94a3b8)', marginTop: '2px' }}>
                        {p.desc}
                      </div>
                    </div>
                  </div>

                  {isActive ? (
                    <CheckCircle2 size={16} style={{ color: p.color, flexShrink: 0 }} />
                  ) : (
                    <span style={{ fontSize: '11px', color: 'var(--text-muted)', flexShrink: 0 }}>Switch →</span>
                  )}
                </button>
              );
            })}
          </div>
        </div>

        {/* Custom Login Form */}
        <div style={{ borderTop: '1px solid var(--glass-border)', paddingTop: '16px' }}>
          <div style={{ fontSize: '11px', fontWeight: 600, color: 'var(--text-muted)', marginBottom: '10px' }}>
            Or Sign In with Custom Credentials (steward_a / steward_b for ACL demo)
          </div>
          <form onSubmit={handleCustomLogin} style={{ display: 'flex', gap: '8px', flexWrap: 'wrap', alignItems: 'flex-end' }}>
            <div style={{ flex: '1 1 140px', display: 'flex', flexDirection: 'column', gap: 4 }}>
              <label htmlFor="dt-login-user" style={{ fontSize: 11, fontWeight: 600, color: 'var(--text-muted)' }}>Username / Email</label>
              <input
                id="dt-login-user"
                type="text"
                autoComplete="username"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                style={{
                  width: '100%',
                  padding: '8px 12px',
                  borderRadius: '8px',
                  border: '1px solid var(--glass-border)',
                  backgroundColor: 'var(--bg-page, #0b0f19)',
                  color: 'var(--text-main, #ffffff)',
                  fontSize: '12px',
                }}
              />
            </div>
            <div style={{ flex: '1 1 120px', display: 'flex', flexDirection: 'column', gap: 4 }}>
              <label htmlFor="dt-login-pass" style={{ fontSize: 11, fontWeight: 600, color: 'var(--text-muted)' }}>Password (optional)</label>
              <input
                id="dt-login-pass"
                type="password"
                autoComplete="current-password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                style={{
                  width: '100%',
                  padding: '8px 12px',
                  borderRadius: '8px',
                  border: '1px solid var(--glass-border)',
                  backgroundColor: 'var(--bg-page, #0b0f19)',
                  color: 'var(--text-main, #ffffff)',
                  fontSize: '12px',
                }}
              />
            </div>

            <button
              type="submit"
              disabled={loadingRole === 'custom'}
              style={{
                padding: '8px 16px',
                borderRadius: '8px',
                backgroundColor: '#0369a1',
                color: '#ffffff',
                border: 'none',
                fontSize: '12px',
                fontWeight: 700,
                cursor: 'pointer',
                minHeight: 36,
              }}
            >
              Sign In
            </button>
          </form>
        </div>
      </div>
    </div>
  );
};
