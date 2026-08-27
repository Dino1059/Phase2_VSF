import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { MessageSquare, Plus, Trash2, Edit2, Check, X } from 'lucide-react';
import { useChatStore } from '../../stores/chatStore';

export function SessionSwitcher() {
  const { i18n } = useTranslation();
  const isVi = i18n.language === 'vi';

  const sessions = useChatStore((s) => s.sessions);
  const activeSessionId = useChatStore((s) => s.activeSessionId);
  const fetchSessions = useChatStore((s) => s.fetchSessions);
  const createSession = useChatStore((s) => s.createSession);
  const switchSession = useChatStore((s) => s.switchSession);
  const renameSession = useChatStore((s) => s.renameSession);
  const deleteSession = useChatStore((s) => s.deleteSession);

  const [isEditing, setIsEditing] = useState(false);
  const [editTitle, setEditTitle] = useState('');

  useEffect(() => {
    void fetchSessions();
  }, [fetchSessions]);

  const activeSession = sessions.find((s) => s.id === activeSessionId) || sessions[0];

  const handleCreate = () => {
    const title = isVi ? 'Phiên Trò Chuyện Mới' : 'New Agent Chat';
    const newId = createSession(title);
    void switchSession(newId);
  };

  const handleStartEdit = () => {
    if (activeSession) {
      setEditTitle(activeSession.title);
      setIsEditing(true);
    }
  };

  const handleSaveRename = () => {
    if (activeSession && editTitle.trim()) {
      renameSession(activeSession.id, editTitle.trim());
    }
    setIsEditing(false);
  };

  const handleDelete = async () => {
    if (activeSession) {
      await deleteSession(activeSession.id);
    }
  };

  return (
    <div
      className="session-switcher"
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        gap: '8px',
        background: 'var(--bg-card, rgba(15, 23, 42, 0.6))',
        border: '1px solid var(--glass-border, rgba(255, 255, 255, 0.1))',
        borderRadius: '8px',
        padding: '3px 10px',
        fontSize: '12px',
      }}
    >
      <MessageSquare size={13} style={{ color: '#0284c7' }} />

      {isEditing ? (
        <div style={{ display: 'inline-flex', alignItems: 'center', gap: '4px' }}>
          <input
            type="text"
            value={editTitle}
            onChange={(e) => setEditTitle(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter') handleSaveRename();
              if (e.key === 'Escape') setIsEditing(false);
            }}
            style={{
              background: 'rgba(0,0,0,0.3)',
              border: '1px solid #0284c7',
              borderRadius: '4px',
              color: '#fff',
              padding: '1px 6px',
              fontSize: '11px',
              outline: 'none',
            }}
            autoFocus
          />
          <button
            type="button"
            onClick={handleSaveRename}
            style={{ color: '#22c55e', background: 'none', border: 'none', cursor: 'pointer', padding: '1px' }}
            title="Save"
          >
            <Check size={13} />
          </button>
          <button
            type="button"
            onClick={() => setIsEditing(false)}
            style={{ color: '#ef4444', background: 'none', border: 'none', cursor: 'pointer', padding: '1px' }}
            title="Cancel"
          >
            <X size={13} />
          </button>
        </div>
      ) : (
        <>
          <select
            data-testid="session-switcher"
            aria-label="Active conversation session"
            value={activeSessionId}
            onChange={(e) => void switchSession(e.target.value)}
            style={{
              background: 'transparent',
              border: 'none',
              color: 'var(--text-main, #f1f5f9)',
              fontSize: '11.5px',
              fontWeight: 600,
              cursor: 'pointer',
              outline: 'none',
              maxWidth: '160px',
            }}
          >
            {sessions.map((s) => (
              <option
                key={s.id}
                value={s.id}
                style={{ background: '#0f172a', color: '#f1f5f9' }}
              >
                {s.title} ({s.messages?.length || 0})
              </option>
            ))}
          </select>

          <button
            type="button"
            onClick={handleStartEdit}
            style={{ color: 'var(--text-muted)', background: 'none', border: 'none', cursor: 'pointer', padding: '2px' }}
            title={isVi ? 'Đổi tên phiên' : 'Rename Session'}
          >
            <Edit2 size={12} />
          </button>

          {sessions.length > 1 && (
            <button
              type="button"
              onClick={() => void handleDelete()}
              style={{ color: '#ef4444', background: 'none', border: 'none', cursor: 'pointer', padding: '2px' }}
              title={isVi ? 'Xóa phiên này' : 'Delete Session'}
            >
              <Trash2 size={12} />
            </button>
          )}
        </>
      )}

      <button
        type="button"
        onClick={handleCreate}
        style={{
          display: 'inline-flex',
          alignItems: 'center',
          gap: '3px',
          background: 'rgba(2, 132, 199, 0.15)',
          color: '#38bdf8',
          border: '1px solid rgba(2, 132, 199, 0.3)',
          borderRadius: '6px',
          padding: '2px 7px',
          fontSize: '11px',
          fontWeight: 600,
          cursor: 'pointer',
          marginLeft: '4px',
        }}
        title={isVi ? 'Tạo phiên mới' : 'New Session'}
      >
        <Plus size={12} />
        <span>{isVi ? 'Mới' : 'New'}</span>
      </button>
    </div>
  );
}
