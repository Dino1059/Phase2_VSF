'use client';

import { useState, useRef, useEffect, useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  ArrowUp,
  Sparkles,
  AlertTriangle,
  Plus,
  Clock,
  Trash2,
  X,
  MessageSquare,
  ShieldAlert,
} from 'lucide-react';
import { useAgentStore, type ChatMessageItem, type ChatSession } from '@/lib/agent-store';
import { StartRunModal } from '@/components/datatrust/pipeline/start-run-modal';

function formatSessionTime(iso: string) {
  try {
    const d = new Date(iso);
    const now = new Date();
    const diffMs = now.getTime() - d.getTime();
    const diffMins = Math.floor(diffMs / (60 * 1000));
    if (diffMins < 1) return 'Vừa xong';
    if (diffMins < 60) return `${diffMins} phút trước`;
    const diffHours = Math.floor(diffMins / 60);
    if (diffHours < 24) return `${diffHours} giờ trước`;
    return d.toLocaleDateString('vi-VN', { day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit' });
  } catch {
    return 'Gần đây';
  }
}

function renderMarkdownContent(text: string) {
  const lines = text.split('\n');
  return (
    <div className="space-y-1.5 text-xs font-normal leading-relaxed">
      {lines.map((line, idx) => {
        const trimmed = line.trim();
        if (!trimmed) {
          return <div key={idx} className="h-1" />;
        }

        const isBullet = /^[•\-\*]\s+/.test(trimmed);
        const isNumbered = /^[0-9]+\.\s+/.test(trimmed);

        const content = isBullet
          ? trimmed.replace(/^[•\-\*]\s+/, '')
          : isNumbered
          ? trimmed.replace(/^[0-9]+\.\s+/, '')
          : line;

        const parts = content.split(/(\*\*.*?\*\*|`.*?`)/g);

        const renderedLine = parts.map((p, pIdx) => {
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
                className="rounded px-1 py-0.5 text-[11px] font-mono border bg-slate-100 text-teal-800 border-slate-200"
              >
                {p.slice(1, -1)}
              </code>
            );
          }
          return p;
        });

        if (isBullet) {
          return (
            <div key={idx} className="flex items-start gap-1.5 pl-1">
              <span className="text-teal-600 font-bold leading-tight select-none">•</span>
              <div className="flex-1">{renderedLine}</div>
            </div>
          );
        }

        if (isNumbered) {
          const numMatch = trimmed.match(/^([0-9]+)\./);
          const num = numMatch ? numMatch[1] : '1';
          return (
            <div key={idx} className="flex items-start gap-1.5 pl-1">
              <span className="font-semibold text-slate-600 select-none text-[11px] leading-tight min-w-[14px]">
                {num}.
              </span>
              <div className="flex-1">{renderedLine}</div>
            </div>
          );
        }

        return (
          <p key={idx} className="text-slate-800">
            {renderedLine}
          </p>
        );
      })}
    </div>
  );
}

export function AiChatPane() {
  const navigate = useNavigate();
  const {
    currentRole,
    homepageViewMode,
    selectedDatasetId,
    datasets,
    pipelineLevels,
    chatMessages,
    chatSessions,
    activeSessionId,
    isBackendLive,
    isSyncing,
    isChatLoading,
    chatError,
    sendUserChatMessage,
    selectDataset,
    startPipelineRun,
    resetHomepageFlow,
    viewLatestCompletedResults,
    startNewChatSession,
    switchChatSession,
    deleteChatSession,
    clearAllChatSessions,
  } = useAgentStore();

  const [inputVal, setInputVal] = useState('');
  const [showStartModal, setShowStartModal] = useState(false);
  const [showHistory, setShowHistory] = useState(false);
  const [filterAllRuns, setFilterAllRuns] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  // Strict Run Isolation: Do NOT use hard-coded fallback!
  const activeRunId = pipelineLevels.activeRunId;
  const dataset = datasets[selectedDatasetId] || {
    id: selectedDatasetId || 'ride_hailing_xanh_sm_trips',
    title: selectedDatasetId || 'ride_hailing_xanh_sm_trips',
    filename: 'ride_hailing_xanh_sm_trips.csv',
  };

  // Chat sessions for current run
  const currentRunSessions = useMemo(() => {
    if (!activeRunId) return [];
    return chatSessions.filter((s) => s.runId === activeRunId);
  }, [chatSessions, activeRunId]);

  const displayedSessions = useMemo(() => {
    if (filterAllRuns) return chatSessions;
    return currentRunSessions;
  }, [filterAllRuns, chatSessions, currentRunSessions]);

  // Header Subtitle according to run status
  const headerSubtitle = useMemo(() => {
    if (!activeRunId) {
      return 'Chưa có Run (Vui lòng chọn hoặc chạy pipeline)';
    }
    if (homepageViewMode === 'results_dashboard') {
      return `Ngữ cảnh: ${activeRunId}`;
    }
    if (homepageViewMode === 'running_pipeline') {
      return `Run: ${activeRunId} • Dataset: ${(dataset.filename || dataset.title || dataset.id || '').replace('.csv', '')}`;
    }
    return `Ngữ cảnh: ${activeRunId}`;
  }, [homepageViewMode, activeRunId, dataset]);

  // Input placeholder according to run availability
  const inputPlaceholder = useMemo(() => {
    if (!activeRunId) {
      return 'Chưa chọn Run. Vui lòng chạy hoặc chọn một lần chạy để trò chuyện...';
    }
    if (homepageViewMode === 'results_dashboard') {
      return 'Hỏi về kết quả lần chạy (VD: giải thích nguyên nhân finding)...';
    }
    if (homepageViewMode === 'running_pipeline') {
      return 'Hỏi về tiến độ và trạng thái lần chạy...';
    }
    return 'Hỏi AI trong lần chạy này...';
  }, [homepageViewMode, activeRunId]);

  useEffect(() => {
    if (!showHistory) {
      messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
    }
  }, [chatMessages, showHistory]);

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

  const handleStartNewChat = () => {
    if (!activeRunId) return;
    startNewChatSession(activeRunId);
    setShowHistory(false);
  };

  const handleSelectSession = (sessionId: string) => {
    switchChatSession(sessionId);
    setShowHistory(false);
  };

  const handleDeleteSession = (e: React.MouseEvent, sessionId: string) => {
    e.stopPropagation();
    deleteChatSession(sessionId);
  };

  const handleClearAll = () => {
    if (window.confirm('Bạn có chắc chắn muốn xóa toàn bộ lịch sử các đoạn chat? Thao tác này không thể hoàn tác.')) {
      clearAllChatSessions();
      setShowHistory(false);
    }
  };

  const handleActionClick = (action: { label: string; actionType: string; payload?: any }) => {
    if (action.actionType === 'NAVIGATE_RESULTS' && action.payload) {
      navigate(action.payload);
    } else if (action.actionType === 'NAVIGATE_FINDINGS' && action.payload) {
      navigate(action.payload);
    } else if (action.actionType === 'OPEN_START_RUN_MODAL') {
      setShowStartModal(true);
    } else if (action.actionType === 'VIEW_RESULTS') {
      viewLatestCompletedResults();
    } else if (action.actionType === 'SCROLL_TO_CRITICAL') {
      const el = document.getElementById('finding-remediation-section');
      if (el) el.scrollIntoView({ behavior: 'smooth' });
    } else if (action.actionType === 'ASK_AI_STEP') {
      sendUserChatMessage('Bước này đang làm gì? Hãy giải thích chi tiết tác vụ đang diễn ra.');
    } else if (action.actionType === 'SELECT_AND_RUN' || action.actionType === 'SELECT_DATASET') {
      if (action.payload) {
        selectDataset(action.payload);
      }
      if (currentRole === 'admin' && action.actionType === 'SELECT_AND_RUN') {
        startPipelineRun(action.payload);
      }
    } else if (action.actionType === 'RESET_FLOW') {
      resetHomepageFlow();
    }
  };

  return (
    <div className="flex h-full flex-col rounded-2xl border border-slate-200 bg-white shadow-xs overflow-hidden relative">
      {/* Header with Title and Session Controls */}
      <div className="border-b border-slate-100 bg-[#fafcfb] px-4 py-3 shrink-0">
        <div className="flex items-center justify-between gap-2">
          <div className="flex items-center gap-1.5 min-w-0">
            <Sparkles size={14} className="text-[#04D3D4] fill-[#04D3D4] shrink-0" />
            <span className="text-sm font-bold text-slate-900 truncate">DataTrust Agent</span>
            <span
              className={`size-2 rounded-full inline-block ml-0.5 shrink-0 ${
                isSyncing ? 'bg-amber-400 animate-pulse' : isBackendLive ? 'bg-[#04D3D4]' : 'bg-slate-300'
              }`}
              title={isSyncing ? 'Đang kiểm tra kết nối' : isBackendLive ? 'Backend online' : 'Backend offline'}
            />
          </div>

          {/* Action buttons: New Chat and History */}
          <div className="flex items-center gap-1.5 shrink-0">
            <button
              onClick={handleStartNewChat}
              disabled={!activeRunId}
              className="flex items-center gap-1 rounded-lg border border-slate-200 bg-white px-2 py-1 text-[11px] font-medium text-slate-700 hover:bg-slate-50 disabled:opacity-40 disabled:cursor-not-allowed transition shadow-2xs cursor-pointer"
              title="Tạo đoạn chat mới cho lần chạy này"
            >
              <Plus size={12} className="text-teal-600" />
              <span>Đoạn chat mới</span>
            </button>

            <button
              onClick={() => setShowHistory((prev) => !prev)}
              className={`flex items-center gap-1 rounded-lg border px-2 py-1 text-[11px] font-medium transition shadow-2xs cursor-pointer ${
                showHistory
                  ? 'bg-teal-50 border-teal-300 text-teal-800'
                  : 'bg-white border-slate-200 text-slate-700 hover:bg-slate-50'
              }`}
              title="Xem lịch sử các đoạn chat"
            >
              <Clock size={12} className="text-slate-500" />
              <span>Lịch sử ({currentRunSessions.length})</span>
            </button>
          </div>
        </div>

        <div className="text-xs text-slate-500 mt-0.5 font-medium flex items-center justify-between">
          <span className="truncate">{headerSubtitle}</span>
          {activeRunId && (
            <span className="font-mono text-[10px] bg-slate-100 text-slate-600 px-1.5 py-0.5 rounded border border-slate-200 shrink-0 ml-2">
              Run Scoped
            </span>
          )}
        </div>
      </div>

      {/* Error banner if chat error occurred */}
      {chatError && (
        <div className="bg-red-50 border-b border-red-200 px-3.5 py-2 flex items-center gap-2 text-[11px] text-red-700 shrink-0">
          <AlertTriangle size={13} className="text-red-600 shrink-0" />
          <span className="flex-1 truncate">{chatError}</span>
        </div>
      )}

      {/* History Drawer / Slide-over Overlay */}
      {showHistory ? (
        <div className="flex-1 flex flex-col min-h-0 bg-slate-50/70 p-3 overflow-hidden">
          <div className="flex items-center justify-between pb-2 border-b border-slate-200">
            <div className="flex items-center gap-2">
              <MessageSquare size={14} className="text-teal-600" />
              <span className="text-xs font-bold text-slate-900">Lịch sử hội thoại</span>
            </div>
            <div className="flex items-center gap-2">
              <button
                onClick={() => setFilterAllRuns((prev) => !prev)}
                className="text-[10px] px-2 py-0.5 rounded-full border border-slate-200 bg-white hover:bg-slate-100 text-slate-600 transition"
              >
                {filterAllRuns ? 'Tất cả Run' : `Chỉ Run này (${currentRunSessions.length})`}
              </button>
              <button
                onClick={() => setShowHistory(false)}
                className="rounded p-1 text-slate-400 hover:text-slate-700 hover:bg-slate-200/60 transition"
                title="Đóng lịch sử"
              >
                <X size={14} />
              </button>
            </div>
          </div>

          {/* Session List */}
          <div className="flex-1 overflow-y-auto py-2 space-y-2 min-h-0">
            {displayedSessions.length === 0 ? (
              <div className="h-full flex flex-col items-center justify-center text-center p-4 text-slate-400 text-xs">
                <Clock size={24} className="mb-2 text-slate-300" />
                <p>Chưa có đoạn chat nào được lưu cho lần chạy này.</p>
                {activeRunId && (
                  <button
                    onClick={handleStartNewChat}
                    className="mt-3 text-xs font-semibold text-teal-600 hover:text-teal-700 underline"
                  >
                    + Tạo đoạn chat mới
                  </button>
                )}
              </div>
            ) : (
              displayedSessions.map((s: ChatSession) => {
                const isActive = s.id === activeSessionId;
                return (
                  <div
                    key={s.id}
                    onClick={() => handleSelectSession(s.id)}
                    className={`group relative rounded-xl border p-2.5 transition cursor-pointer text-left ${
                      isActive
                        ? 'border-teal-400 bg-teal-50/60 shadow-2xs'
                        : 'border-slate-200 bg-white hover:border-slate-300 hover:bg-slate-50'
                    }`}
                  >
                    <div className="flex items-start justify-between gap-2">
                      <div className="min-w-0 flex-1">
                        <div className="flex items-center gap-1.5">
                          <p className="text-xs font-semibold text-slate-900 truncate">
                            {s.title}
                          </p>
                          {isActive && (
                            <span className="size-1.5 rounded-full bg-teal-500 shrink-0" title="Đang mở" />
                          )}
                        </div>
                        <div className="mt-1 flex items-center gap-2 text-[10px] text-slate-500">
                          <span className="font-mono bg-slate-100 px-1 rounded text-slate-600">
                            {s.runId}
                          </span>
                          <span>•</span>
                          <span>{formatSessionTime(s.updatedAt || s.createdAt)}</span>
                          <span>•</span>
                          <span>{s.messages.length} tin</span>
                        </div>
                      </div>
                      <button
                        onClick={(e) => handleDeleteSession(e, s.id)}
                        className="opacity-0 group-hover:opacity-100 p-1 text-slate-400 hover:text-red-600 hover:bg-red-50 rounded transition"
                        title="Xóa đoạn chat này"
                      >
                        <Trash2 size={13} />
                      </button>
                    </div>
                  </div>
                );
              })
            )}
          </div>

          {/* Drawer Footer & Security Notice */}
          <div className="pt-2 border-t border-slate-200 shrink-0 space-y-2">
            {chatSessions.length > 0 && (
              <div className="flex items-center justify-between">
                <span className="text-[11px] text-slate-500">
                  Tổng cộng: {chatSessions.length} phiên đã lưu
                </span>
                <button
                  onClick={handleClearAll}
                  className="text-[11px] text-red-600 hover:text-red-700 font-medium transition cursor-pointer"
                >
                  Xóa tất cả lịch sử
                </button>
              </div>
            )}
            <div className="rounded-lg bg-amber-50/70 border border-amber-200/50 p-2 text-[10.5px] text-amber-800 leading-tight flex items-start gap-1.5">
              <ShieldAlert size={12} className="text-amber-600 shrink-0 mt-0.5" />
              <span>
                Dữ liệu chat được lưu tạm trên trình duyệt cục bộ. Vui lòng xóa lịch sử nếu dùng chung thiết bị.
              </span>
            </div>
          </div>
        </div>
      ) : (
        /* Messages Scroll Area */
        <div className="flex-1 min-h-0 space-y-3 overflow-y-auto p-4 text-xs scroll-smooth">
          {chatMessages.map((msg: ChatMessageItem) => {
            const isAi = msg.sender === 'ai';
            return (
              <div
                key={msg.id}
                className={`flex flex-col ${isAi ? 'items-start' : 'items-end'}`}
              >
                <div
                  className={`max-w-[92%] rounded-2xl px-3.5 py-2.5 leading-relaxed shadow-2xs ${
                    isAi
                      ? 'border border-slate-100 bg-slate-50/90 text-slate-800'
                      : 'bg-[#ecfdf5] border border-[#bbf7d0]/50 text-slate-900 font-medium'
                  }`}
                >
                  {renderMarkdownContent(msg.text)}

                  {/* Quick actions chips inside bubble */}
                  {msg.quickActions && msg.quickActions.length > 0 && (
                    <div className="mt-2.5 flex flex-wrap gap-1.5 pt-1">
                      {msg.quickActions.map((action, aIdx) => (
                        <button
                          key={aIdx}
                          onClick={() => handleActionClick(action)}
                          className="rounded-xl border border-slate-200 bg-white px-3 py-1 text-[11px] font-semibold text-slate-800 hover:bg-slate-100 transition shadow-2xs cursor-pointer"
                        >
                          {action.label}
                        </button>
                      ))}
                    </div>
                  )}
                </div>
              </div>
            );
          })}

          {/* Dynamic Context Helpers when in running_pipeline mode */}
          {homepageViewMode === 'running_pipeline' && (
            <div className="pt-1">
              <button
                onClick={() => handleActionClick({ label: 'Bước này đang làm gì?', actionType: 'ASK_AI_STEP' })}
                className="rounded-xl border border-slate-200 bg-white px-3 py-1.5 text-xs font-semibold text-slate-800 hover:bg-slate-50 transition shadow-2xs cursor-pointer"
              >
                Bước này đang làm gì?
              </button>
            </div>
          )}

          {isChatLoading && (
            <div className="flex items-center gap-2 text-xs text-slate-500" role="status">
              <span className="size-2 animate-pulse rounded-full bg-[#04D3D4]" />
              AI đang phân tích…
            </div>
          )}

          <div ref={messagesEndRef} />
        </div>
      )}

      {/* Input Box with Teal send button */}
      <div className="border-t border-slate-100 bg-[#fafcfb] p-3 shrink-0">
        <div className="flex items-center gap-2 rounded-xl border border-slate-200 bg-white px-3 py-1.5 shadow-2xs focus-within:border-[#04D3D4] focus-within:ring-2 focus-within:ring-[#04D3D4]/20 transition">
          <input
            type="text"
            value={inputVal}
            onChange={(e) => setInputVal(e.target.value)}
            onKeyDown={handleKeyDown}
            disabled={isChatLoading || !activeRunId}
            placeholder={inputPlaceholder}
            className="flex-1 bg-transparent text-xs text-slate-900 placeholder:text-slate-400 focus:outline-none disabled:opacity-50 disabled:cursor-not-allowed"
          />
          <button
            onClick={handleSend}
            disabled={!inputVal.trim() || isChatLoading || !activeRunId}
            className="flex size-7 items-center justify-center rounded-lg bg-[#2dd4bf] hover:bg-[#14b8a6] text-white font-bold disabled:opacity-40 disabled:cursor-not-allowed transition cursor-pointer shadow-2xs"
            title="Gửi câu hỏi"
          >
            <ArrowUp size={14} className="stroke-[2.5]" />
          </button>
        </div>
      </div>

      <StartRunModal
        isOpen={showStartModal}
        onClose={() => setShowStartModal(false)}
      />
    </div>
  );
}
