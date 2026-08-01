import { TopBar } from './TopBar';
import { ChatPanel } from '../chat/ChatPanel';
import { WorkspacePanel } from '../workspace/WorkspacePanel';
import { AgentStatusBar } from './AgentStatusBar';
import { useAppStore } from '../../stores/appStore';

export function AppShell() {
  const { workspacePanelVisible } = useAppStore();

  return (
    <div className="flex flex-col h-screen bg-background overflow-hidden">
      <TopBar />
      <div className="flex flex-1 overflow-hidden">
        {/* Chat Panel */}
        <div
          className={`flex flex-col border-r border-border transition-all duration-300 ${
            workspacePanelVisible ? 'w-[35%] min-w-[320px]' : 'w-full'
          } max-lg:w-full`}
        >
          <ChatPanel />
        </div>

        {/* Workspace Panel - hidden on mobile, toggleable */}
        {workspacePanelVisible && (
          <div className="flex-1 flex flex-col max-lg:hidden">
            <WorkspacePanel />
          </div>
        )}
      </div>
      <AgentStatusBar />
    </div>
  );
}
