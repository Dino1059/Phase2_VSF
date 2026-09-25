'use client';
import { useState, useRef, useEffect } from 'react';
import {
  Bot,
  ChevronLeft,
  ChevronRight,
  Database,
  FileCheck2,
  FileText,
  RotateCcw,
  Send,
  Sparkles,
  User,
} from 'lucide-react';
import { useAgentStore, type ChatMessageItem } from '@/lib/agent-store';

export function AiChatPane() {
  const {
    currentRole,
    isChatCollapsed,
    toggleChatCollapse,
    chatMessages,
    sendUserChatMessage,
    startPipelineRun,
    resetHomepageFlow,
  } = useAgentStore();

  const [inputVal, setInputVal] = useState('');
  const messagesEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [chatMessages]);

  const handleSend = () => {
    if (!inputVal.trim()) return;
    sendUserChatMessage(inputVal.trim());
    setInputVal('');
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter') {
      handleSend();
    }
  };

  const handleActionClick = (action: { label: string; actionType: string; payload?: any }) => {
    if (action.actionType === 'SELECT_AND_RUN') {
      startPipelineRun(action.payload);
    } else if (action.actionType === 'TRIGGER_AUDIT_TESTCASES') {
      sendUserChatMessage('Đề xuất kịch bản kiểm toán cho auditor');
    } else if (action.actionType === 'TRIGGER_POLICY_RULE') {
      sendUserChatMessage('Đề xuất rule mới từ văn bản chính sách');
    } else if (action.actionType === 'RESET_FLOW') {
      resetHomepageFlow();
    }
  };


  // When collapsed: show thin vertical bar with icon & expand button
  if (isChatCollapsed) {
    return (
      <div className="flex h-full w-14 flex-col items-center justify-between rounded-2xl border border-slate-200 bg-white py-4 shadow-xs transition-all">
        <div className="flex flex-col items-center gap-3">
          <button
            onClick={toggleChatCollapse}
            title="Mở rộng khung Chat"
            className="flex size-9 items-center justify-center rounded-xl bg-[#04D3D4]/15 text-slate-900 border border-[#04D3D4]/40 transition hover:bg-[#04D3D4]"
          >
            <ChevronRight size={18} />
          </button>
          <div className="size-8 grid place-items-center rounded-xl bg-slate-950 text-[#04D3D4] border border-[#04D3D4]/30 shadow-xs">
            <Bot size={16} />
          </div>
          <span className="writing-mode-vertical text-[11px] font-bold uppercase tracking-wider text-slate-400 rotate-180 py-4">
            AI Copilot
          </span>
        </div>
        <div className="flex flex-col items-center gap-2 text-slate-400">
          <Sparkles size={16} className="text-[#04D3D4] fill-[#FFC402] animate-pulse" />
        </div>
      </div>
    );
  }

  return (
    <div className="flex h-full flex-col rounded-2xl border border-slate-200 bg-white shadow-xs overflow-hidden">
      {/* Header */}
      <div className="flex items-center justify-between border-b border-slate-100 bg-[#fafcfb] px-4 py-3 shrink-0">
        <div className="flex items-center gap-2.5">
          <div className="grid size-8 place-items-center rounded-xl bg-slate-950 text-[#04D3D4] border border-[#04D3D4]/40 shadow-xs">
            <Sparkles size={16} className="text-[#04D3D4] fill-[#FFC402]" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <span className="text-xs font-bold text-slate-900">AI Orchestrator</span>
              <span className="rounded-full bg-[#04D3D4]/20 border border-[#04D3D4]/40 px-1.5 py-0.2 text-[9px] font-extrabold text-slate-900">
                Online
              </span>
            </div>
          </div>
        </div>

        <button
          onClick={toggleChatCollapse}
          title="Thu gọn khung Chat"
          className="flex size-7 items-center justify-center rounded-lg text-slate-400 hover:bg-slate-100 hover:text-slate-700 transition"
        >
          <ChevronLeft size={16} />
        </button>
      </div>

      {/* Quick Action Navigation Bar */}
      <div className="flex items-center gap-1.5 overflow-x-auto border-b border-slate-100 bg-white px-3 py-2 text-[11px] scrollbar-none shrink-0">
        <button
          onClick={() => sendUserChatMessage('Chọn dataset')}
          className="flex shrink-0 items-center gap-1 rounded-lg border border-slate-200 bg-white px-2 py-1 text-slate-700 hover:border-[#04D3D4] hover:bg-[#04D3D4]/10 transition font-medium"
        >
          <Database size={12} className="text-[#04D3D4]" />
          <span>Chọn dataset</span>
        </button>
        <button
          onClick={() => sendUserChatMessage('Đề xuất kịch bản kiểm toán cho auditor')}
          className="flex shrink-0 items-center gap-1 rounded-lg border border-slate-200 bg-white px-2 py-1 text-slate-700 hover:border-[#04D3D4] hover:bg-[#04D3D4]/10 transition font-medium"
        >
          <FileCheck2 size={12} className="text-[#FFC402]" />
          <span>Test case Auditor</span>
        </button>
        {currentRole === 'admin' && (
          <button
            onClick={() => sendUserChatMessage('Đề xuất rule mới từ văn bản chính sách')}
            className="flex shrink-0 items-center gap-1 rounded-lg border border-slate-200 bg-white px-2 py-1 text-slate-700 hover:border-[#04D3D4] hover:bg-[#04D3D4]/10 transition font-medium"
          >
            <FileText size={12} />
            <span>Rule từ Policy</span>
          </button>
        )}
        <button
          onClick={resetHomepageFlow}
          title="Đặt lại luồng"
          className="flex shrink-0 items-center gap-1 rounded-lg border border-slate-200 bg-white px-2 py-1 text-slate-400 hover:border-red-300 hover:text-red-600 transition"
        >
          <RotateCcw size={11} />
        </button>
      </div>

      {/* Messages Scroll Area with Independent Scrollbar */}
      <div className="flex-1 min-h-0 space-y-3.5 overflow-y-auto p-4 text-xs scroll-smooth">
        {chatMessages.map((msg: ChatMessageItem) => {
          const isAi = msg.sender === 'ai';
          return (
            <div
              key={msg.id}
              className={`flex gap-2.5 ${isAi ? 'items-start' : 'items-end flex-row-reverse'}`}
            >
              {isAi ? (
                <div className="grid size-7 shrink-0 place-items-center rounded-lg bg-slate-950 text-[#04D3D4] border border-[#04D3D4]/30 shadow-2xs">
                  <Bot size={14} />
                </div>
              ) : (
                <div className="grid size-7 shrink-0 place-items-center rounded-lg bg-slate-900 text-white shadow-2xs">
                  <User size={13} />
                </div>
              )}

              <div
                className={`max-w-[86%] rounded-2xl px-3.5 py-2.5 leading-relaxed shadow-2xs ${
                  isAi
                    ? 'border border-slate-200 bg-white text-slate-800'
                    : 'bg-slate-950 text-white font-medium'
                }`}
              >
                <div className="whitespace-pre-line text-xs font-normal">
                  {msg.text.split('\n').map((line, idx) => {
                    const parts = line.split(/(\*\*.*?\*\*)/g);
                    return (
                      <p key={idx} className={idx > 0 ? 'mt-1' : ''}>
                        {parts.map((p, pIdx) => {
                          if (p.startsWith('**') && p.endsWith('**')) {
                            return (
                              <strong key={pIdx} className="font-bold text-slate-950">
                                {p.slice(2, -2)}
                              </strong>
                            );
                          }
                          if (p.startsWith('`') && p.endsWith('`')) {
                            return (
                              <code
                                key={pIdx}
                                className="rounded bg-slate-100 px-1 py-0.5 text-[11px] font-mono text-cyan-900 border border-slate-200"
                              >
                                {p.slice(1, -1)}
                              </code>
                            );
                          }
                          return p;
                        })}
                      </p>
                    );
                  })}
                </div>

                {/* Quick actions chips if available */}
                {msg.quickActions && msg.quickActions.length > 0 && (
                  <div className="mt-2.5 flex flex-wrap gap-1.5 pt-1">
                    {msg.quickActions.map((action, aIdx) => (
                      <button
                        key={aIdx}
                        onClick={() => handleActionClick(action)}
                        className="rounded-lg border border-[#04D3D4]/50 bg-white px-2.5 py-1 text-[11px] font-mono font-bold text-slate-900 hover:bg-[#04D3D4] transition shadow-2xs"
                      >
                        {action.label}
                      </button>
                    ))}
                  </div>
                )}

                <div
                  className={`mt-1.5 text-[10px] ${
                    isAi ? 'text-slate-400' : 'text-slate-400'
                  } text-right`}
                >
                  {msg.timestamp}
                </div>
              </div>
            </div>
          );
        })}
        <div ref={messagesEndRef} />
      </div>

      {/* Input Box */}
      <div className="border-t border-slate-100 bg-[#fafcfb] p-3 shrink-0">
        <div className="flex items-center gap-2 rounded-xl border border-slate-200 bg-white px-3 py-1.5 shadow-2xs focus-within:border-[#04D3D4] focus-within:ring-2 focus-within:ring-[#04D3D4]/20 transition">
          <input
            type="text"
            value={inputVal}
            onChange={(e) => setInputVal(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Nhập lệnh: 'chạy trips', 'test case'..."
            className="flex-1 bg-transparent text-xs text-slate-900 placeholder:text-slate-400 focus:outline-none"
          />
          <button
            onClick={handleSend}
            disabled={!inputVal.trim()}
            className="flex size-7 items-center justify-center rounded-lg bg-[#04D3D4] text-slate-950 font-bold disabled:opacity-40 transition hover:bg-[#03bcbd] cursor-pointer"
          >
            <Send size={13} />
          </button>
        </div>
      </div>
    </div>
  );
}
