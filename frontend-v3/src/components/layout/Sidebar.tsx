import { useRef, useState, useEffect } from 'react';
import { Plus, MessageSquare, Trash2, Shield, RefreshCw, Upload, Loader2 } from 'lucide-react';
import { useChatStore } from '../../stores/chatStore';
import { fetchChatSessions, fetchChatHistory, clearChatDatabase, uploadDatasetFile } from '../../services/api';

interface SessionItem {
  session_id: string;
  msg_count: number;
  last_updated: string;
  title: string;
}

export function Sidebar({ onClose }: { onClose?: () => void }) {
  const { setMessages, clearMessages, setWorkspace } = useChatStore();
  const [sessions, setSessions] = useState<SessionItem[]>([]);
  const [activeSession, setActiveSession] = useState<string>('default');
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [uploading, setUploading] = useState(false);

  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setUploading(true);
    try {
      await uploadDatasetFile(file);
    } catch (err) {
      console.error('File upload failed:', err);
    } finally {
      setUploading(false);
      if (fileInputRef.current) fileInputRef.current.value = '';
    }
  };

  const loadSessions = async () => {
    try {
      const data = await fetchChatSessions();
      setSessions(data.sessions || []);
    } catch (e) {
      console.error('Failed to load chat sessions:', e);
    }
  };

  useEffect(() => {
    loadSessions();
  }, []);

  const handleNewChat = () => {
    const newSessionId = `session_${Date.now()}`;
    setActiveSession(newSessionId);
    clearMessages();
    setWorkspace('empty');
    if (onClose) onClose();
  };

  const handleSelectSession = async (sessionId: string) => {
    setActiveSession(sessionId);
    try {
      const data = await fetchChatHistory(sessionId);
      if (data.messages) {
        setMessages(data.messages);
      }
    } catch (e) {
      console.error('Failed to fetch chat history:', e);
    } finally {
      if (onClose) onClose();
    }
  };

  const handleResetDb = async () => {
    if (window.confirm('Are you sure you want to reset all chat history in the database?')) {
      try {
        await clearChatDatabase();
        clearMessages();
        setWorkspace('empty');
        await loadSessions();
      } catch (e) {
        console.error('Failed to reset chat DB:', e);
      }
    }
  };

  return (
    <aside className="flex flex-col h-full w-64 bg-surface border-r border-border shrink-0 select-none">
      {/* Top action button */}
      <div className="p-3 border-b border-border space-y-2">
        <button
          onClick={handleNewChat}
          className="w-full flex items-center justify-center gap-2 px-3 py-2 text-xs font-semibold text-white bg-agent-orchestrator hover:bg-agent-orchestrator/80 rounded-lg transition-colors shadow-sm"
        >
          <Plus className="w-4 h-4" />
          <span>New Agent Chat</span>
        </button>

        <input
          ref={fileInputRef}
          type="file"
          accept=".parquet,.csv,.json,.jsonl,.sqlite,.db"
          className="hidden"
          onChange={handleFileUpload}
        />
        <button
          onClick={() => fileInputRef.current?.click()}
          disabled={uploading}
          className="w-full flex items-center justify-center gap-2 px-3 py-1.5 text-xs font-medium text-text-primary bg-background border border-border hover:bg-surface-hover rounded-lg transition-colors disabled:opacity-50"
        >
          {uploading ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Upload className="w-3.5 h-3.5 text-agent-orchestrator" />}
          <span>Upload DB / Dataset</span>
        </button>
      </div>

      {/* Session List */}
      <div className="flex-1 overflow-y-auto p-2 space-y-1">
        <div className="px-2 py-1.5 text-[10px] font-semibold text-text-muted uppercase tracking-wider flex items-center justify-between">
          <span>Chat History</span>
          <button onClick={loadSessions} className="hover:text-text-primary transition-colors" title="Refresh">
            <RefreshCw className="w-3 h-3" />
          </button>
        </div>

        {sessions.length === 0 ? (
          <div className="px-3 py-4 text-center text-xs text-text-muted opacity-60">
            No past chat sessions.
          </div>
        ) : (
          sessions.map((s) => (
            <button
              key={s.session_id}
              onClick={() => handleSelectSession(s.session_id)}
              className={`w-full flex items-center gap-2.5 px-3 py-2 rounded-lg text-xs text-left transition-colors ${
                activeSession === s.session_id
                  ? 'bg-agent-orchestrator/15 text-agent-orchestrator font-medium border border-agent-orchestrator/30'
                  : 'text-text-secondary hover:bg-surface-hover hover:text-text-primary'
              }`}
            >
              <MessageSquare className="w-3.5 h-3.5 shrink-0 opacity-70" />
              <div className="flex-1 min-w-0">
                <div className="truncate text-xs">{s.title || 'Chat Session'}</div>
                <div className="text-[10px] opacity-60 font-mono">{s.msg_count} messages</div>
              </div>
            </button>
          ))
        )}
      </div>

      {/* Bottom Footer Actions */}
      <div className="p-3 border-t border-border space-y-2">
        <button
          onClick={handleResetDb}
          className="w-full flex items-center gap-2 px-3 py-1.5 text-xs text-status-error hover:bg-status-error/10 rounded-lg transition-colors"
        >
          <Trash2 className="w-3.5 h-3.5" />
          <span>Reset Chat Database</span>
        </button>

        <div className="flex items-center gap-2 pt-1 text-[10px] text-text-muted">
          <Shield className="w-3 h-3 text-agent-rule-proposer" />
          <span>DataTrust OS v3.0</span>
        </div>
      </div>
    </aside>
  );
}
