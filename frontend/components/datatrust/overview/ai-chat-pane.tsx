'use client';

import { useState, useRef, useEffect, useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  ArrowUp,
  Sparkles,
} from 'lucide-react';
import { useAgentStore, type ChatMessageItem } from '@/lib/agent-store';
import { StartRunModal } from '@/components/datatrust/pipeline/start-run-modal';

export function AiChatPane() {
  const navigate = useNavigate();
  const {
    currentRole,
    homepageViewMode,
    selectedDatasetId,
    datasets,
    pipelineLevels,
    chatMessages,
    sendUserChatMessage,
    selectDataset,
    startPipelineRun,
    resetHomepageFlow,
    viewLatestCompletedResults,
  } = useAgentStore();

  const [inputVal, setInputVal] = useState('');
  const [showStartModal, setShowStartModal] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const activeRunId = pipelineLevels.activeRunId || 'RUN-20261007-021';
  const dataset = datasets[selectedDatasetId] || {
    id: selectedDatasetId || 'ride_hailing_xanh_sm_trips',
    title: selectedDatasetId || 'ride_hailing_xanh_sm_trips',
    filename: 'ride_hailing_xanh_sm_trips.csv',
  };

  // Header Subtitle according to mockup
  const headerSubtitle = useMemo(() => {
    if (homepageViewMode === 'results_dashboard') {
      return `Ngữ cảnh: ${activeRunId}`;
    }
    if (homepageViewMode === 'running_pipeline') {
      return `Dataset: ${(dataset.filename || dataset.title || dataset.id || 'ride_hailing_xanh_sm_trips').replace('.csv', '')}`;
    }
    return 'Trạng thái: Sẵn sàng';
  }, [homepageViewMode, activeRunId, dataset]);

  // Input placeholder according to mockup
  const inputPlaceholder = useMemo(() => {
    if (homepageViewMode === 'results_dashboard') {
      return 'Hỏi về kết quả lần chạy...';
    }
    if (homepageViewMode === 'running_pipeline') {
      return 'Hỏi về lần chạy này...';
    }
    return 'Hỏi AI đồng hành...';
  }, [homepageViewMode]);

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
    <div className="flex h-full flex-col rounded-2xl border border-slate-200 bg-white shadow-xs overflow-hidden">
      {/* Header matching example/run.png & example/run_result.png */}
      <div className="border-b border-slate-100 bg-[#fafcfb] px-4 py-3 shrink-0">
        <div className="flex items-center gap-1.5">
          <Sparkles size={14} className="text-[#04D3D4] fill-[#04D3D4]" />
          <span className="text-sm font-bold text-slate-900">AI đồng hành</span>
          <span className="size-2 rounded-full bg-[#04D3D4] inline-block ml-0.5" />
        </div>
        <div className="text-xs text-slate-500 mt-0.5 font-medium">
          {headerSubtitle}
        </div>
      </div>

      {/* Messages Scroll Area */}
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
                <div className="whitespace-pre-line text-xs font-normal">
                  {msg.text.split('\n').map((line, idx) => {
                    const parts = line.split(/(\*\*.*?\*\*|`.*?`)/g);
                    return (
                      <p key={idx} className={idx > 0 ? 'mt-1' : ''}>
                        {parts.map((p, pIdx) => {
                          if (p.startsWith('**') && p.endsWith('**')) {
                            return (
                              <strong
                                key={pIdx}
                                className="font-bold text-slate-950"
                              >
                                {p.slice(2, -2)}
                              </strong>
                            );
                          }
                          if (p.startsWith('`') && p.endsWith('`')) {
                            return (
                              <code
                                key={pIdx}
                                className="rounded px-1 py-0.5 text-[11px] font-mono border bg-slate-100 text-slate-800 border-slate-200"
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

        <div ref={messagesEndRef} />
      </div>

      {/* Input Box with Teal send button matching mockup */}
      <div className="border-t border-slate-100 bg-[#fafcfb] p-3 shrink-0">
        <div className="flex items-center gap-2 rounded-xl border border-slate-200 bg-white px-3 py-1.5 shadow-2xs focus-within:border-[#04D3D4] focus-within:ring-2 focus-within:ring-[#04D3D4]/20 transition">
          <input
            type="text"
            value={inputVal}
            onChange={(e) => setInputVal(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder={inputPlaceholder}
            className="flex-1 bg-transparent text-xs text-slate-900 placeholder:text-slate-400 focus:outline-none"
          />
          <button
            onClick={handleSend}
            disabled={!inputVal.trim()}
            className="flex size-7 items-center justify-center rounded-lg bg-[#2dd4bf] hover:bg-[#14b8a6] text-white font-bold disabled:opacity-40 transition cursor-pointer shadow-2xs"
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
