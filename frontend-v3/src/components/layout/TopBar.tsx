import { useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Brain, Globe, Bell, PanelRightClose, PanelRightOpen, PanelLeftClose, PanelLeftOpen, Upload, Loader2 } from 'lucide-react';
import { useAppStore } from '../../stores/appStore';
import { useChatStore } from '../../stores/chatStore';
import { uploadDatasetFile } from '../../services/api';
import { AGENTS } from '../../types';
import type { AgentId, UserRole } from '../../types';

const ROLE_OPTIONS: UserRole[] = ['admin', 'steward', 'viewer'];

export function TopBar() {
  const { t, i18n } = useTranslation();
  const { role, setRole, workspacePanelVisible, setWorkspacePanelVisible, sidebarCollapsed, toggleSidebar } = useAppStore();
  const { agentStatuses } = useChatStore();
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [uploading, setUploading] = useState(false);

  const toggleLang = () => {
    const newLang = i18n.language === 'en' ? 'vi' : 'en';
    i18n.changeLanguage(newLang);
    localStorage.setItem('datatrust-lang', newLang);
  };

  const handleFileChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
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

  return (
    <header className="flex items-center justify-between px-4 h-12 bg-surface border-b border-border shrink-0">
      {/* Left: Sidebar toggle + Logo + Agent dots */}
      <div className="flex items-center gap-3">
        <button
          onClick={toggleSidebar}
          className="p-1.5 text-text-secondary hover:text-text-primary hover:bg-surface-hover rounded-md transition-colors"
          title={sidebarCollapsed ? 'Expand sidebar' : 'Collapse sidebar'}
        >
          {sidebarCollapsed ? <PanelLeftOpen className="w-4 h-4" /> : <PanelLeftClose className="w-4 h-4" />}
        </button>

        <div className="flex items-center gap-2">
          <Brain className="w-5 h-5 text-agent-orchestrator" />
          <span className="font-semibold text-sm text-text-primary tracking-tight">
            {t('appName')}
          </span>
          <span className="text-[10px] text-text-muted bg-surface-hover px-1.5 py-0.5 rounded-full font-mono">
            {t('appVersion')}
          </span>
        </div>

        {/* Agent status dots */}
        <div className="flex items-center gap-1.5 ml-4 max-sm:hidden">
          {(Object.keys(AGENTS) as AgentId[]).map((id) => {
            const agent = AGENTS[id];
            const status = agentStatuses[id];
            const statusStr = status ? status.charAt(0).toUpperCase() + status.slice(1) : 'Idle';
            return (
              <div
                key={id}
                className={`w-2 h-2 rounded-full transition-all duration-300 ${
                  status === 'active' || status === 'working'
                    ? 'animate-agent-glow'
                    : status === 'done'
                    ? 'opacity-80'
                    : status === 'error'
                    ? 'bg-status-error animate-agent-pulse'
                    : 'opacity-30'
                }`}
                style={{ backgroundColor: agent.color }}
                title={`${t(agent.nameKey)}: ${statusStr}`}
              />
            );
          })}
        </div>
      </div>

      {/* Right: Controls */}
      <div className="flex items-center gap-2">
        {/* Hidden File Input */}
        <input
          ref={fileInputRef}
          type="file"
          accept=".parquet,.csv,.json,.jsonl,.sqlite,.db"
          className="hidden"
          onChange={handleFileChange}
        />

        {/* Upload Dataset Button */}
        <button
          onClick={() => fileInputRef.current?.click()}
          disabled={uploading}
          className="flex items-center gap-1.5 px-2.5 py-1 text-xs font-medium text-white bg-agent-orchestrator hover:bg-agent-orchestrator/80 rounded-md transition-colors disabled:opacity-50"
        >
          {uploading ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Upload className="w-3.5 h-3.5" />}
          <span className="max-sm:hidden">Upload DB</span>
        </button>

        {/* Language toggle */}
        <button
          onClick={toggleLang}
          className="flex items-center gap-1 px-2 py-1 text-xs text-text-secondary hover:text-text-primary hover:bg-surface-hover rounded-md transition-colors"
        >
          <Globe className="w-3.5 h-3.5" />
          <span className="font-medium">{i18n.language.toUpperCase()}</span>
        </button>

        {/* Role selector */}
        <select
          value={role}
          onChange={(e) => setRole(e.target.value as UserRole)}
          className="bg-surface-hover text-text-secondary text-xs px-2 py-1 rounded-md border border-border cursor-pointer hover:border-text-muted transition-colors appearance-none"
        >
          {ROLE_OPTIONS.map((r) => (
            <option key={r} value={r}>
              {t(r)}
            </option>
          ))}
        </select>

        {/* Workspace toggle */}
        <button
          onClick={() => setWorkspacePanelVisible(!workspacePanelVisible)}
          className="p-1.5 text-text-secondary hover:text-text-primary hover:bg-surface-hover rounded-md transition-colors max-lg:hidden"
          title={workspacePanelVisible ? 'Hide workspace' : 'Show workspace'}
        >
          {workspacePanelVisible ? (
            <PanelRightClose className="w-4 h-4" />
          ) : (
            <PanelRightOpen className="w-4 h-4" />
          )}
        </button>

        {/* Notifications */}
        <button className="relative p-1.5 text-text-secondary hover:text-text-primary hover:bg-surface-hover rounded-md transition-colors">
          <Bell className="w-4 h-4" />
        </button>
      </div>
    </header>
  );
}
