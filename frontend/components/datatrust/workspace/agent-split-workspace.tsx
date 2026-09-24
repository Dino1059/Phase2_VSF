'use client';
import { useState, useRef, useEffect } from 'react';
import { useSearchParams } from 'react-router-dom';
import {
  Sparkles,
  Send,
  ShieldCheck,
  CheckCircle2,
  Bot,
  User,
  Zap,
  Activity,
  FileText,
  Play,
  Copy,
  Check,
  RotateCw,
  Lock,
  Layers,
  Upload,
} from 'lucide-react';
import {
  useAgentStore,
  type TestCaseItem,
  type PolicyAdaptationItem,
} from '@/lib/agent-store';
import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils';

export function AgentSplitWorkspace() {
  const [searchParams, setSearchParams] = useSearchParams();
  const store = useAgentStore();
  const {
    activePersona,
    setActivePersona,
    workspacePreviewTab,
    setWorkspacePreviewTab,
    testCases,
    runTestCase,
    runAllTestCases,
    policies,
    adaptPolicy,
    deployPolicyRule,
    workspaceInitialMessage,
    setWorkspaceInitialMessage,
  } = store;

  // Initialize from URL params if present
  useEffect(() => {
    const personaParam = searchParams.get('persona');
    if (personaParam === 'auditor' || personaParam === 'admin') {
      setActivePersona(personaParam);
    }
    const tabParam = searchParams.get('tab');
    if (tabParam === 'tests' || tabParam === 'evidence' || tabParam === 'telemetry' || tabParam === 'adaptation') {
      setWorkspacePreviewTab(tabParam);
    }
  }, [searchParams, setActivePersona, setWorkspacePreviewTab]);

  // Chat message interface
  interface WorkspaceMessage {
    id: string;
    sender: 'agent' | 'user';
    text: string;
    timestamp: string;
    actionButtons?: {
      label: string;
      onClick: () => void;
      variant?: 'default' | 'xanhsm' | 'outline';
    }[];
  }

  const getInitialMessages = (persona: 'auditor' | 'admin'): WorkspaceMessage[] => {
    const time = 'Vừa xong';
    if (persona === 'auditor') {
      return [
        {
          id: 'auditor-init-1',
          sender: 'agent',
          timestamp: time,
          text: `Chào anh Hoàng! Tôi đã chuẩn bị **6 test case giả lập** và **kho bằng chứng SHA-256** ở bảng Preview bên cạnh.\n\nAnh muốn chạy thử nghiệm ngay hay tra cứu chứng chỉ băm?`,
          actionButtons: [
            {
              label: '▶ Chạy 6 Test Case',
              variant: 'xanhsm',
              onClick: () => {
                runAllTestCases();
                appendSystemReply('Đã hoàn tất 6 test case [6/6 PASS ✓]. Kết quả đã cập nhật ở bảng Preview bên cạnh.');
              },
            },
            {
              label: '🛡️ Xem Bằng chứng SHA-256',
              variant: 'outline',
              onClick: () => setWorkspacePreviewTab('evidence'),
            },
          ],
        },
      ];
    }

    return [
      {
        id: 'admin-init-1',
        sender: 'agent',
        timestamp: time,
        text: `Chào anh Bảo! Bảng Preview bên cạnh đang hiển thị **Live Telemetry (2.450 TPS)** và **Động cơ Thích ứng Chính sách**.\n\nAnh muốn kiểm tra SLA hay thích ứng chính sách mới?`,
        actionButtons: [
          {
            label: '📊 Xem Telemetry',
            variant: 'xanhsm',
            onClick: () => setWorkspacePreviewTab('telemetry'),
          },
          {
            label: '📜 Thích ứng Chính sách',
            variant: 'outline',
            onClick: () => setWorkspacePreviewTab('adaptation'),
          },
        ],
      },
    ];
  };

  const [chatMessages, setChatMessages] = useState<WorkspaceMessage[]>(() =>
    getInitialMessages(store.currentUser.id)
  );

  // Sync when account changes globally
  useEffect(() => {
    setChatMessages(getInitialMessages(store.currentUser.id));
  }, [store.currentUser.id]);
  const [chatInput, setChatInput] = useState('');
  const [isTyping, setIsTyping] = useState(false);
  const [copiedHash, setCopiedHash] = useState<string | null>(null);
  const [selectedPolicyId, setSelectedPolicyId] = useState('POL-01');
  const [customPolicyInput, setCustomPolicyInput] = useState('');

  const chatEndRef = useRef<HTMLDivElement>(null);

  // When initial message from landing is present, auto trigger it
  useEffect(() => {
    if (workspaceInitialMessage) {
      handleUserSubmit(workspaceInitialMessage);
      setWorkspaceInitialMessage(null);
    }
  }, [workspaceInitialMessage]);

  // When persona changes, reset welcoming context if empty or switched
  const handlePersonaChange = (newPersona: 'auditor' | 'admin') => {
    setActivePersona(newPersona);
    setSearchParams({
      persona: newPersona,
      tab: newPersona === 'auditor' ? 'tests' : 'telemetry',
    });
    setChatMessages(getInitialMessages(newPersona));
  };

  const handleCopyHash = (hash: string) => {
    navigator.clipboard.writeText(hash);
    setCopiedHash(hash);
    setTimeout(() => setCopiedHash(null), 2000);
  };

  const handleUserSubmit = (customText?: string) => {
    const text = (customText || chatInput).trim();
    if (!text) return;

    const now = new Date().toLocaleTimeString('vi-VN', { hour: '2-digit', minute: '2-digit' });
    const userMsg: WorkspaceMessage = {
      id: `usr-${Date.now()}`,
      sender: 'user',
      text,
      timestamp: now,
    };

    setChatMessages((prev) => [...prev, userMsg]);
    setChatInput('');
    setIsTyping(true);

    setTimeout(() => {
      const q = text.toLowerCase();
      let reply = '';
      let actions: WorkspaceMessage['actionButtons'] = undefined;

      if (q.includes('test case') || q.includes('chạy test') || q.includes('kiểm thử')) {
        setWorkspacePreviewTab('tests');
        reply = `Đã mở **Compliance Test Lab**. Mời anh bấm chạy để xem hệ thống phát hiện và cách ly vi phạm:`;
        actions = [
          {
            label: '▶ Chạy 6 Test Case',
            variant: 'xanhsm',
            onClick: () => {
              runAllTestCases();
              appendSystemReply('Đã hoàn tất 6 test case [6/6 PASS ✓]. Kết quả đã cập nhật ở bảng Preview bên cạnh.');
            },
          },
          {
            label: 'Xem chứng chỉ SHA-256',
            variant: 'outline',
            onClick: () => setWorkspacePreviewTab('evidence'),
          },
        ];
      } else if (q.includes('bằng chứng') || q.includes('evidence') || q.includes('sha-256')) {
        setWorkspacePreviewTab('evidence');
        reply = `Đã mở **Kho Bằng chứng SHA-256**. Toàn bộ 602 chứng chỉ băm bất biến đã sẵn sàng đối soát.`;
      } else if (q.includes('thích ứng') || q.includes('chính sách') || q.includes('policy') || q.includes('luật')) {
        setWorkspacePreviewTab('adaptation');
        reply = `Đã mở **Auto-Adaptation Engine**. Đã chuyển đổi văn bản sang SQL/PySpark ở bảng bên cạnh.`;
      } else if (q.includes('telemetry') || q.includes('sức khỏe') || q.includes('giám sát')) {
        setWorkspacePreviewTab('telemetry');
        reply = `Đang theo dõi **2.450 TPS**, độ trễ 34ms, 99.9% bản ghi vào Silver sạch.`;
      } else {
        reply = `Đã ghi nhận yêu cầu. Mời anh xem bảng Preview cập nhật bên cạnh.`;
      }

      setChatMessages((prev) => [
        ...prev,
        {
          id: `agt-${Date.now()}`,
          sender: 'agent',
          text: reply,
          timestamp: new Date().toLocaleTimeString('vi-VN', { hour: '2-digit', minute: '2-digit' }),
          actionButtons: actions,
        },
      ]);
      setIsTyping(false);
    }, 600);
  };

  const appendSystemReply = (msg: string) => {
    setChatMessages((prev) => [
      ...prev,
      {
        id: `sys-${Date.now()}`,
        sender: 'agent',
        text: msg,
        timestamp: new Date().toLocaleTimeString('vi-VN', { hour: '2-digit', minute: '2-digit' }),
      },
    ]);
  };

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [chatMessages, isTyping]);

  const currentPolicy = policies.find((p) => p.id === selectedPolicyId) || policies[0];
  const passedTestsCount = testCases.filter((tc) => tc.status === 'passed').length;

  return (
    <div className="page-enter -mx-4 -my-4 md:-mx-8 md:-my-8 flex min-h-[calc(100vh-4rem)] flex-col lg:flex-row bg-[#f4f8f7]">
      {/* ======================================================== */}
      {/* CỘT TRÁI (~38%): CONVERSATIONAL COPILOT CHAT (Screenshot 2) */}
      {/* ======================================================== */}
      <div className="flex w-full flex-col border-b border-[#e2ece8] bg-white lg:w-[400px] xl:w-[440px] lg:border-b-0 lg:border-r shrink-0">
        {/* Agent Header */}
        <div className="flex items-center justify-between border-b border-[#e2ece8] bg-[#0f3834] px-4 py-3.5 text-white">
          <div className="flex items-center gap-2.5">
            <div className="relative grid size-9 place-items-center rounded-xl border border-amber-400 bg-[#164a44] shadow-xs">
              <Sparkles className="size-4.5 text-amber-400" />
              <span className="absolute -top-0.5 -right-0.5 size-2.5 rounded-full border-2 border-[#0f3834] bg-emerald-400" />
            </div>
            <div>
              <div className="flex items-center gap-1.5">
                <h3 className="text-xs font-bold text-white">DataTrust Agent</h3>
              </div>
            </div>
          </div>
        </div>


        {/* Message Thread */}
        <div className="flex-1 space-y-3.5 overflow-y-auto p-4 bg-[#f8faf9] text-xs">
          {chatMessages.map((msg) => {
            const isAgent = msg.sender === 'agent';
            return (
              <div
                key={msg.id}
                className={cn('flex flex-col', isAgent ? 'items-start' : 'items-end')}
              >
                <div className="flex items-start gap-2 max-w-[92%]">
                  {isAgent && (
                    <div className="grid size-7 shrink-0 place-items-center rounded-lg border border-amber-300/60 bg-[#0f3834] text-amber-400 shadow-2xs mt-0.5">
                      <Bot size={13} />
                    </div>
                  )}

                  <div className="space-y-2">
                    <div
                      className={cn(
                        'rounded-2xl p-3.5 shadow-xs leading-relaxed',
                        isAgent
                          ? 'border border-[#dcebe6] bg-white text-slate-800'
                          : 'rounded-tr-xs border border-[#bfe7dc] bg-[#e6f6f2] text-[#005b4c] font-medium'
                      )}
                    >
                      <div className="whitespace-pre-wrap">{msg.text}</div>
                    </div>

                    {/* Action buttons inside message bubble */}
                    {msg.actionButtons && (
                      <div className="flex flex-wrap gap-1.5 pt-1">
                        {msg.actionButtons.map((btn, bIdx) => (
                          <Button
                            key={bIdx}
                            size="sm"
                            variant={btn.variant || 'default'}
                            onClick={btn.onClick}
                            className="h-7 px-2.5 text-[11px] font-semibold"
                          >
                            {btn.label}
                          </Button>
                        ))}
                      </div>
                    )}

                    <span className="block text-[10px] text-slate-400 pl-1">
                      {msg.timestamp}
                    </span>
                  </div>

                  {!isAgent && (
                    <div className="grid size-7 shrink-0 place-items-center rounded-lg bg-[#008b74] text-white shadow-2xs mt-0.5">
                      <User size={13} />
                    </div>
                  )}
                </div>
              </div>
            );
          })}

          {isTyping && (
            <div className="flex items-center gap-2 text-xs text-slate-400 pl-9">
              <span className="size-1.5 rounded-full bg-amber-500 animate-bounce" />
              <span className="size-1.5 rounded-full bg-emerald-500 animate-bounce [animation-delay:0.2s]" />
              <span className="size-1.5 rounded-full bg-[#008b74] animate-bounce [animation-delay:0.4s]" />
              <span className="text-[11px]">Agent đang phân tích...</span>
            </div>
          )}

          <div ref={chatEndRef} />
        </div>

        {/* Quick prompt pills at bottom */}
        <div className="border-t border-[#e2ece8] bg-white px-3 py-2">
          <div className="flex items-center gap-1.5 overflow-x-auto pb-1 text-slate-600 no-scrollbar">
            {activePersona === 'auditor' ? (
              <>
                <button
                  onClick={() => handleUserSubmit('Chạy tất cả test case tuân thủ IPO')}
                  className="shrink-0 rounded-full border border-slate-200 bg-slate-50 px-2.5 py-0.8 text-[10px] font-medium text-slate-700 hover:border-amber-300 hover:bg-amber-50"
                >
                  🧪 Chạy 6 test case
                </button>
                <button
                  onClick={() => handleUserSubmit('Kiểm tra chứng thực mã băm SHA-256')}
                  className="shrink-0 rounded-full border border-slate-200 bg-slate-50 px-2.5 py-0.8 text-[10px] font-medium text-slate-700 hover:border-amber-300 hover:bg-amber-50"
                >
                  🛡️ Xem bằng chứng SHA-256
                </button>
                <button
                  onClick={() => handleUserSubmit('Tải hồ sơ kiểm toán IPO')}
                  className="shrink-0 rounded-full border border-slate-200 bg-slate-50 px-2.5 py-0.8 text-[10px] font-medium text-slate-700 hover:border-amber-300 hover:bg-amber-50"
                >
                  📑 Xuất Audit Pack
                </button>
              </>
            ) : (
              <>
                <button
                  onClick={() => handleUserSubmit('Xem telemetry luồng dữ liệu thời gian thực')}
                  className="shrink-0 rounded-full border border-slate-200 bg-slate-50 px-2.5 py-0.8 text-[10px] font-medium text-slate-700 hover:border-amber-300 hover:bg-amber-50"
                >
                  📊 Giám sát Telemetry
                </button>
                <button
                  onClick={() => handleUserSubmit('Thích ứng chính sách cước phí mới GSM')}
                  className="shrink-0 rounded-full border border-slate-200 bg-slate-50 px-2.5 py-0.8 text-[10px] font-medium text-slate-700 hover:border-amber-300 hover:bg-amber-50"
                >
                  📜 Thích ứng chính sách
                </button>
                <button
                  onClick={() => handleUserSubmit('Ước tính số dòng bị cách ly vào Quarantine')}
                  className="shrink-0 rounded-full border border-slate-200 bg-slate-50 px-2.5 py-0.8 text-[10px] font-medium text-slate-700 hover:border-amber-300 hover:bg-amber-50"
                >
                  ⚠️ Mô phỏng cách ly
                </button>
              </>
            )}
          </div>
        </div>

        {/* Chat Input */}
        <div className="border-t border-[#e2ece8] bg-white p-3">
          <form
            onSubmit={(e) => {
              e.preventDefault();
              handleUserSubmit();
            }}
            className="flex items-center gap-2"
          >
            <input
              type="text"
              value={chatInput}
              onChange={(e) => setChatInput(e.target.value)}
              placeholder={
                activePersona === 'auditor'
                  ? 'Yêu cầu kiểm thử test case hoặc tra cứu evidence...'
                  : 'Hỏi về telemetry hoặc dán chính sách mới để thích ứng...'
              }
              className="h-10 flex-1 rounded-xl border border-[#d2e2dc] bg-white px-3.5 text-xs text-slate-800 placeholder:text-slate-400 focus:border-[#008b74] focus:outline-none focus:ring-1 focus:ring-[#008b74]"
            />
            <Button
              type="submit"
              disabled={!chatInput.trim() || isTyping}
              className="size-10 rounded-xl bg-[#008b74] hover:bg-[#007460] text-white p-0 shrink-0 shadow-xs"
            >
              <Send size={15} />
            </Button>
          </form>
        </div>
      </div>

      {/* ======================================================== */}
      {/* CỘT PHẢI (~62%): DYNAMIC SYNCHRONIZED PREVIEW (Screenshot 2) */}
      {/* ======================================================== */}
      <div className="flex-1 flex flex-col min-w-0 overflow-y-auto p-4 md:p-6 space-y-5">
        {/* Preview Top Control Bar */}
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 rounded-2xl border border-[#e2ece8] bg-white p-4 shadow-xs">
          <div className="flex items-center gap-2">
            <span className="flex items-center gap-1 rounded-lg bg-[#0f3834] px-2.5 py-1 text-xs font-bold text-amber-400">
              <Layers size={13} />
              PREVIEW
            </span>
            <span className="text-xs font-semibold text-slate-700">
              {activePersona === 'auditor'
                ? 'Không gian Kiểm thử & Bằng chứng IPO'
                : 'Giám sát Pipeline & Động cơ Thích ứng'}
            </span>
          </div>

          {/* Tab Switcher for Preview */}
          <div className="flex items-center gap-1.5 rounded-xl border border-slate-200 bg-slate-50 p-1 text-xs">
            {activePersona === 'auditor' ? (
              <>
                <button
                  onClick={() => setWorkspacePreviewTab('tests')}
                  className={cn(
                    'flex items-center gap-1.5 rounded-lg px-3 py-1 font-semibold transition cursor-pointer',
                    workspacePreviewTab === 'tests'
                      ? 'bg-white text-[#008b74] shadow-xs'
                      : 'text-slate-600 hover:text-slate-900'
                  )}
                >
                  <ShieldCheck size={13} />
                  Compliance Test Lab ({testCases.length})
                </button>
                <button
                  onClick={() => setWorkspacePreviewTab('evidence')}
                  className={cn(
                    'flex items-center gap-1.5 rounded-lg px-3 py-1 font-semibold transition cursor-pointer',
                    workspacePreviewTab === 'evidence'
                      ? 'bg-white text-[#008b74] shadow-xs'
                      : 'text-slate-600 hover:text-slate-900'
                  )}
                >
                  <Lock size={13} />
                  Kho Bằng chứng SHA-256
                </button>
              </>
            ) : (
              <>
                <button
                  onClick={() => setWorkspacePreviewTab('telemetry')}
                  className={cn(
                    'flex items-center gap-1.5 rounded-lg px-3 py-1 font-semibold transition cursor-pointer',
                    workspacePreviewTab === 'telemetry'
                      ? 'bg-white text-[#008b74] shadow-xs'
                      : 'text-slate-600 hover:text-slate-900'
                  )}
                >
                  <Activity size={13} />
                  Pipeline Telemetry
                </button>
                <button
                  onClick={() => setWorkspacePreviewTab('adaptation')}
                  className={cn(
                    'flex items-center gap-1.5 rounded-lg px-3 py-1 font-semibold transition cursor-pointer',
                    workspacePreviewTab === 'adaptation'
                      ? 'bg-white text-amber-700 shadow-xs'
                      : 'text-slate-600 hover:text-slate-900'
                  )}
                >
                  <FileText size={13} />
                  Auto-Adaptation Engine
                </button>
              </>
            )}
          </div>
        </div>

        {/* ======================================================== */}
        {/* VIEW 1: AUDITOR TEST CASES RUNNER LAB */}
        {/* ======================================================== */}
        {activePersona === 'auditor' && workspacePreviewTab === 'tests' && (
          <div className="space-y-4">
            {/* Summary Bar */}
            <div className="rounded-2xl border border-emerald-200 bg-gradient-to-r from-emerald-50/70 via-white to-amber-50/50 p-4 sm:p-5 shadow-xs flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
              <div>
                <div className="flex items-center gap-2">
                  <h3 className="text-base font-bold text-slate-900">
                    Phòng Thử nghiệm Tuân thủ Độc lập (Compliance Lab)
                  </h3>
                  <span className="rounded-full bg-emerald-100 border border-emerald-300 px-2 py-0.2 text-[10px] font-bold text-emerald-800">
                    IPO Readiness
                  </span>
                </div>
                <p className="mt-1 text-xs text-slate-600">
                  Kiểm toán viên giả lập nạp dữ liệu vi phạm. Agent sẽ tự động phát hiện, chặn cách ly và sinh mã băm SHA-256 bất biến.
                </p>
              </div>

              <div className="flex items-center gap-3 shrink-0">
                <div className="text-right">
                  <span className="block text-xs font-semibold text-slate-500">Đạt chuẩn:</span>
                  <span className="block text-lg font-extrabold text-[#008b74]">
                    {passedTestsCount} / {testCases.length} Tests
                  </span>
                </div>
                <Button
                  variant="xanhsm"
                  size="default"
                  onClick={runAllTestCases}
                  className="gap-2 shadow-xs bg-[#008b74] hover:bg-[#007460] font-bold text-xs"
                >
                  <Play size={13} className="fill-current" />
                  Chạy tất cả 6 Test Cases
                </Button>
              </div>
            </div>

            {/* Test Case Cards */}
            <div className="space-y-3">
              {testCases.map((tc: TestCaseItem) => {
                const isPassed = tc.status === 'passed';
                const isRunning = tc.status === 'running';

                return (
                  <div
                    key={tc.id}
                    className="rounded-2xl border border-[#e2ece8] bg-white p-4 shadow-xs transition hover:border-[#bfe7dc]"
                  >
                    <div className="flex flex-col sm:flex-row sm:items-start sm:justify-between gap-3">
                      <div className="space-y-1.5 flex-1">
                        <div className="flex flex-wrap items-center gap-2">
                          <span className="rounded-md bg-slate-100 px-2 py-0.5 font-mono text-[11px] font-bold text-slate-700">
                            {tc.code}
                          </span>
                          <h4 className="text-xs font-bold text-slate-900">{tc.name}</h4>
                          <span className="rounded border border-slate-200 bg-slate-50 px-2 py-0.2 text-[10px] font-semibold text-slate-600">
                            {tc.domain}
                          </span>
                        </div>

                        <p className="text-xs text-slate-600">{tc.description}</p>

                        {/* Injected Anomaly Code */}
                        <div className="mt-2 flex flex-col gap-1 rounded-xl border border-slate-200 bg-[#fbfdfc] p-2.5 font-mono text-[11px]">
                          <span className="text-[10px] font-bold uppercase tracking-wider text-slate-400">
                            Payload dữ liệu giả lập vi phạm được bơm:
                          </span>
                          <code className="text-red-700 font-semibold">{tc.injectedAnomaly}</code>
                          <span className="text-[10px] font-bold uppercase tracking-wider text-slate-400 mt-1">
                            Rule tuân thủ kỳ vọng kích hoạt:
                          </span>
                          <code className="text-[#007460] font-semibold">{tc.expectedRule}</code>
                        </div>
                      </div>

                      {/* Right Action & Status */}
                      <div className="flex flex-col items-end gap-2 shrink-0">
                        {isPassed ? (
                          <span className="inline-flex items-center gap-1.5 rounded-lg border border-emerald-300 bg-emerald-50 px-3 py-1 text-xs font-bold text-emerald-800">
                            <CheckCircle2 size={14} className="text-emerald-600" />
                            ĐẠT CHUẨN PASS ✓
                          </span>
                        ) : isRunning ? (
                          <span className="inline-flex items-center gap-1.5 rounded-lg border border-amber-300 bg-amber-50 px-3 py-1 text-xs font-bold text-amber-800 animate-pulse">
                            <RotateCw size={13} className="animate-spin" />
                            Đang kiểm thử...
                          </span>
                        ) : (
                          <Button
                            variant="outline"
                            size="sm"
                            onClick={() => runTestCase(tc.id)}
                            className="gap-1.5 text-xs font-semibold hover:border-[#008b74] hover:text-[#008b74]"
                          >
                            <Play size={12} />
                            Chạy kiểm thử
                          </Button>
                        )}

                        <span className="text-[10px] text-slate-400">
                          Chuẩn: {tc.lawStandard}
                        </span>
                      </div>
                    </div>

                    {/* Evidence Hash Receipt when passed */}
                    {isPassed && tc.evidenceHash && (
                      <div className="mt-3 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2 border-t border-slate-100 pt-2 text-[11px]">
                        <div className="flex items-center gap-2">
                          <span className="font-semibold text-emerald-800">
                            ✓ Đã cách ly {tc.quarantinedCount} bản ghi vi phạm
                          </span>
                          <span className="text-slate-300">·</span>
                          <span className="text-slate-500">Độ trễ: {tc.executionTimeMs}ms</span>
                        </div>

                        <div className="flex items-center gap-1.5">
                          <code className="rounded border border-slate-200 bg-slate-50 px-2 py-0.5 font-mono text-[10px] text-slate-700">
                            {tc.evidenceHash.slice(0, 32)}...
                          </code>
                          <button
                            onClick={() => handleCopyHash(tc.evidenceHash || '')}
                            className="grid size-6 place-items-center rounded text-slate-400 hover:text-slate-700 hover:bg-slate-100"
                            title="Sao chép mã băm chứng chỉ"
                          >
                            {copiedHash === tc.evidenceHash ? (
                              <Check size={12} className="text-emerald-600" />
                            ) : (
                              <Copy size={12} />
                            )}
                          </button>
                        </div>
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          </div>
        )}

        {/* ======================================================== */}
        {/* VIEW 2: AUDITOR SHA-256 EVIDENCE INSPECTOR */}
        {/* ======================================================== */}
        {activePersona === 'auditor' && workspacePreviewTab === 'evidence' && (
          <div className="space-y-4">
            <div className="rounded-2xl border border-[#e2ece8] bg-white p-5 shadow-xs flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
              <div>
                <h3 className="text-base font-bold text-slate-900">
                  Kho Bằng Chứng Kiểm Toán Bất Biến (Cryptographic Evidence Store)
                </h3>
                <p className="text-xs text-slate-500">
                  602 bằng chứng được niêm phong bằng chuỗi băm SHA-256 phục vụ đối soát độc lập Big 4.
                </p>
              </div>

              <Button
                variant="xanhsm"
                size="sm"
                onClick={() =>
                  appendSystemReply(
                    'Đã kết xuất trọn bộ Evidence Pack IPO (SHA-256 Merkle Proof) bao gồm 602 bản ghi chứng thực số.'
                  )
                }
                className="gap-1.5 font-semibold text-xs"
              >
                <Lock size={12} /> Tải Audit Evidence Pack (JSON)
              </Button>
            </div>

            {/* Evidence items */}
            <div className="space-y-3">
              {[
                {
                  id: 'EV-TRIP-VAL-01',
                  source: 'trips · Pipeline Run #42',
                  desc: 'Bằng chứng phát hiện 1.240 chuyến đi cước 0đ hoặc km âm bị cách ly.',
                  hash: 'sha256:7f83b1657ff1fc53b92dc18148a1d65dfc2d4b1fa3d677284addd200126d9069',
                  time: '10:14:22 · Hôm nay',
                },
                {
                  id: 'EV-PII-TRIP-02',
                  source: 'customers · Pipeline Run #41',
                  desc: 'Bằng chứng mã hóa và che mờ 3.420 số CCCD & SĐT theo Nghị định 13.',
                  hash: 'sha256:9b12a832f09c64b5849547d2d14b4344d57a2f588c26786a345bf94821a81234',
                  time: '09:30:15 · Hôm nay',
                },
                {
                  id: 'EV-CHG-POLE-03',
                  source: 'charging · Pipeline Run #39',
                  desc: 'Bằng chứng 56 phiên sạc chênh lệch kWh công tơ được chuyển đối soát.',
                  hash: 'sha256:3a77d4c2b98e1f0a245582d90875c7e1124fa682e44d320984baacdd20485671',
                  time: 'Hôm qua',
                },
              ].map((ev) => (
                <div
                  key={ev.id}
                  className="rounded-xl border border-[#e2ece8] bg-white p-4 shadow-xs flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3"
                >
                  <div className="space-y-1">
                    <div className="flex items-center gap-2">
                      <span className="font-mono text-xs font-bold text-slate-800">{ev.id}</span>
                      <span className="rounded bg-emerald-50 text-emerald-700 px-2 py-0.2 text-[10px] font-bold">
                        Bất biến ✓
                      </span>
                      <span className="text-[11px] text-slate-400">· {ev.source}</span>
                    </div>
                    <p className="text-xs text-slate-600">{ev.desc}</p>
                    <code className="block rounded bg-slate-50 border border-slate-200 px-2.5 py-1 font-mono text-[10px] text-slate-600">
                      {ev.hash}
                    </code>
                  </div>

                  <div className="flex sm:flex-col items-center sm:items-end gap-2 shrink-0">
                    <span className="text-[10px] text-slate-400">{ev.time}</span>
                    <button
                      onClick={() => handleCopyHash(ev.hash)}
                      className="inline-flex items-center gap-1 rounded-md border border-slate-200 px-2.5 py-1 text-xs font-semibold text-slate-700 hover:bg-slate-50 cursor-pointer"
                    >
                      <Copy size={11} /> Sao chép Hash
                    </button>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* ======================================================== */}
        {/* VIEW 3: SYSTEM ADMIN TELEMETRY & HEALTH STREAM */}
        {/* ======================================================== */}
        {activePersona === 'admin' && workspacePreviewTab === 'telemetry' && (
          <div className="space-y-4">
            {/* 4 Metric Cards */}
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
              <div className="rounded-2xl border border-[#e2ece8] bg-white p-4 shadow-xs">
                <span className="text-[11px] font-bold uppercase text-slate-400">Throughput</span>
                <strong className="block text-2xl font-extrabold text-slate-900 mt-1">
                  2.450 <small className="text-xs font-normal text-slate-500">TPS</small>
                </strong>
                <span className="mt-1 flex items-center gap-1 text-[11px] font-semibold text-emerald-600">
                  <CheckCircle2 size={12} /> Đạt chuẩn SLA (99.8%)
                </span>
              </div>

              <div className="rounded-2xl border border-[#e2ece8] bg-white p-4 shadow-xs">
                <span className="text-[11px] font-bold uppercase text-slate-400">Silver Clean Lane</span>
                <strong className="block text-2xl font-extrabold text-[#008b74] mt-1">
                  1.248.760
                </strong>
                <span className="mt-1 block text-[11px] text-slate-400">99.9% bản ghi đạt chuẩn</span>
              </div>

              <div className="rounded-2xl border border-[#e2ece8] bg-white p-4 shadow-xs">
                <span className="text-[11px] font-bold uppercase text-slate-400">Quarantine Lane</span>
                <strong className="block text-2xl font-extrabold text-amber-600 mt-1">
                  1.240
                </strong>
                <span className="mt-1 block text-[11px] text-amber-700 font-medium">Bản ghi vi phạm cách ly</span>
              </div>

              <div className="rounded-2xl border border-[#e2ece8] bg-white p-4 shadow-xs">
                <span className="text-[11px] font-bold uppercase text-slate-400">P99 Latency</span>
                <strong className="block text-2xl font-extrabold text-slate-900 mt-1">
                  34 <small className="text-xs font-normal text-slate-500">ms</small>
                </strong>
                <span className="mt-1 block text-[11px] text-emerald-600 font-medium">Thời gian thực</span>
              </div>
            </div>

            {/* Pipeline Architecture Topology */}
            <div className="rounded-2xl border border-[#e2ece8] bg-white p-5 shadow-xs">
              <h4 className="text-xs font-bold uppercase tracking-wider text-slate-400 mb-3">
                Cấu trúc Luồng Dữ liệu Đa tầng (Multi-layer L1-L4 Pipeline)
              </h4>

              <div className="grid grid-cols-1 sm:grid-cols-4 gap-2 text-xs">
                <div className="rounded-xl border border-slate-200 bg-slate-50 p-3">
                  <span className="block font-bold text-slate-800">1. Ingestion Stage</span>
                  <span className="text-[11px] text-slate-500">IoT Telemetry & Kafka Stream</span>
                  <span className="mt-2 block font-mono text-[10px] text-emerald-600">● 2.450 msg/s</span>
                </div>
                <div className="rounded-xl border border-[#bfe7dc] bg-[#e6f6f2] p-3">
                  <span className="block font-bold text-[#007460]">2. L1-L4 Anomaly Detection</span>
                  <span className="text-[11px] text-slate-600">Dynamic Rule & ML Filter</span>
                  <span className="mt-2 block font-mono text-[10px] text-emerald-700">● 14 Active Rules</span>
                </div>
                <div className="rounded-xl border border-emerald-200 bg-emerald-50 p-3">
                  <span className="block font-bold text-emerald-800">3. Silver Clean Stream</span>
                  <span className="text-[11px] text-slate-600">Đưa vào hồ dữ liệu phân tích</span>
                  <span className="mt-2 block font-mono text-[10px] text-emerald-700">● 99.9% Pass</span>
                </div>
                <div className="rounded-xl border border-amber-300 bg-amber-50 p-3">
                  <span className="block font-bold text-amber-900">4. Quarantine Lane</span>
                  <span className="text-[11px] text-slate-600">Cách ly đối soát & Audit log</span>
                  <span className="mt-2 block font-mono text-[10px] text-amber-700 font-bold">● SHA-256 Proof</span>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* ======================================================== */}
        {/* VIEW 4: SYSTEM ADMIN POLICY AUTO-ADAPTATION ENGINE */}
        {/* ======================================================== */}
        {activePersona === 'admin' && workspacePreviewTab === 'adaptation' && (
          <div className="space-y-4">
            <div className="rounded-2xl border border-amber-300 bg-gradient-to-r from-amber-50/70 via-white to-emerald-50/50 p-5 shadow-xs flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
              <div>
                <div className="flex items-center gap-2">
                  <h3 className="text-base font-bold text-slate-900">
                    Động cơ Tự Thích Ứng Rule từ Chính Sách (Auto-Adaptation Engine)
                  </h3>
                  <span className="rounded-full bg-amber-100 border border-amber-300 px-2 py-0.2 text-[10px] font-bold text-amber-800">
                    Agent NLP & Code Gen
                  </span>
                </div>
                <p className="mt-1 text-xs text-slate-600">
                  Khi nhà nước ra luật mới hoặc GSM đổi chính sách giá, dán văn bản vào đây để Agent tự động sinh Rule SQL/PySpark và chạy thử nghiệm.
                </p>
              </div>
            </div>

            {/* Policy Selector Tabs */}
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
              {policies.map((pol: PolicyAdaptationItem) => (
                <button
                  key={pol.id}
                  onClick={() => setSelectedPolicyId(pol.id)}
                  className={cn(
                    'rounded-xl border p-3 text-left transition shadow-2xs cursor-pointer',
                    selectedPolicyId === pol.id
                      ? 'border-amber-400 bg-amber-50/60 ring-1 ring-amber-400'
                      : 'border-slate-200 bg-white hover:border-slate-300'
                  )}
                >
                  <div className="flex items-center justify-between text-[10px] text-slate-400 mb-1">
                    <span className="font-mono font-bold text-slate-700">{pol.id}</span>
                    <span
                      className={cn(
                        'rounded px-1.5 py-0.2 font-semibold',
                        pol.status === 'deployed'
                          ? 'bg-emerald-100 text-emerald-800'
                          : pol.status === 'simulated'
                          ? 'bg-amber-100 text-amber-800'
                          : 'bg-slate-100 text-slate-600'
                      )}
                    >
                      {pol.status === 'deployed'
                        ? 'Đã Deploy'
                        : pol.status === 'simulated'
                        ? 'Đã Mô Phỏng'
                        : 'Bản Thảo'}
                    </span>
                  </div>
                  <h5 className="text-xs font-bold text-slate-900 line-clamp-2">{pol.title}</h5>
                  <span className="mt-2 block text-[10px] text-slate-500">Hiệu lực: {pol.effectiveDate}</span>
                </button>
              ))}
            </div>

            {/* Active Policy Sandbox Detail */}
            <div className="rounded-2xl border border-[#e2ece8] bg-white p-5 shadow-xs space-y-4">
              <div className="space-y-1">
                <span className="text-[10px] font-bold uppercase tracking-wider text-amber-700">
                  VĂN BẢN CHÍNH SÁCH / THÔNG TƯ NGUỒN
                </span>
                <h4 className="text-sm font-bold text-slate-900">{currentPolicy.title}</h4>
                <p className="rounded-xl border border-slate-200 bg-slate-50 p-3 text-xs text-slate-700 leading-relaxed italic">
                  "{currentPolicy.rawText}"
                </p>
              </div>

              {/* Generated Code Sandbox */}
              <div className="space-y-1.5">
                <div className="flex items-center justify-between">
                  <span className="text-[10px] font-bold uppercase tracking-wider text-[#008b74]">
                    BIỂU THỨC LOGIC ĐƯỢC AGENT TỰ SINH
                  </span>
                  <span className="text-[10px] font-semibold text-slate-500">
                    Target: <strong className="text-slate-800">{currentPolicy.compiledTarget}</strong>
                  </span>
                </div>
                <code className="block rounded-xl border border-[#d2e2dc] bg-[#fbfdfc] p-3 font-mono text-xs font-bold text-[#007460]">
                  {currentPolicy.generatedExpression}
                </code>
              </div>

              {/* Simulated Impact Metrics */}
              <div className="rounded-xl border border-[#e2ece8] bg-slate-50/50 p-3.5 space-y-2">
                <span className="block text-[11px] font-bold uppercase text-slate-400">
                  Mô phỏng tác động trên dữ liệu thực tế (Dry-run Simulation):
                </span>
                <div className="grid grid-cols-3 gap-3 text-xs">
                  <div>
                    <span className="text-slate-500 block text-[11px]">Bản ghi quét</span>
                    <strong className="text-slate-900 font-bold">
                      {currentPolicy.simulatedImpact.scannedRows.toLocaleString('vi-VN')}
                    </strong>
                  </div>
                  <div>
                    <span className="text-slate-500 block text-[11px]">Đưa vào Silver sạch</span>
                    <strong className="text-emerald-700 font-bold">
                      {currentPolicy.simulatedImpact.silverCleanRows.toLocaleString('vi-VN')}
                    </strong>
                  </div>
                  <div>
                    <span className="text-slate-500 block text-[11px]">Bị cách ly Quarantine</span>
                    <strong className="text-amber-700 font-bold">
                      {currentPolicy.simulatedImpact.quarantinedRows.toLocaleString('vi-VN')} dòng
                    </strong>
                  </div>
                </div>
              </div>

              {/* Action Buttons */}
              <div className="flex flex-wrap items-center justify-between gap-3 pt-2 border-t border-slate-100">
                <span className="text-[11px] text-slate-500">
                  Độ tin cậy biên dịch AI: <strong className="text-slate-800">{currentPolicy.confidence}%</strong>
                </span>

                <div className="flex items-center gap-2">
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => adaptPolicy(currentPolicy.id)}
                    className="text-xs"
                  >
                    Mô phỏng lại Dry-run
                  </Button>

                  {currentPolicy.status === 'deployed' ? (
                    <span className="inline-flex items-center gap-1.5 rounded-lg border border-emerald-300 bg-emerald-50 px-3 py-1 text-xs font-bold text-emerald-800">
                      <Check size={13} /> Đã kích hoạt trong Production
                    </span>
                  ) : (
                    <Button
                      variant="xanhsm"
                      size="sm"
                      onClick={() => {
                        deployPolicyRule(currentPolicy.id);
                        appendSystemReply(
                          `🚀 **Đã triển khai thành công rule thích ứng ${currentPolicy.generatedRuleName} vào Pipeline Production!** Rule này hiện đã tự động kiểm soát và cách ly các bản ghi vi phạm.`
                        );
                      }}
                      className="gap-1.5 font-bold text-xs bg-[#008b74] hover:bg-[#007460]"
                    >
                      <Zap size={13} /> 1-Click Triển khai vào Pipeline
                    </Button>
                  )}
                </div>
              </div>
            </div>

            {/* Custom Policy Box */}
            <div className="rounded-2xl border border-dashed border-slate-300 bg-white p-4 space-y-2">
              <span className="block text-xs font-bold text-slate-800">
                + Thêm văn bản chính sách mới để Agent tự thích ứng:
              </span>
              <div className="flex gap-2">
                <input
                  type="text"
                  value={customPolicyInput}
                  onChange={(e) => setCustomPolicyInput(e.target.value)}
                  placeholder="Dán nội dung quy định hoặc thông tư mới (VD: Giới hạn tốc độ xe taxi trời mưa < 70km/h)..."
                  className="flex-1 rounded-xl border border-slate-200 px-3 text-xs focus:border-[#008b74] focus:outline-none"
                />
                <Button
                  size="sm"
                  variant="outline"
                  onClick={() => {
                    if (customPolicyInput.trim()) {
                      handleUserSubmit(`Tôi muốn hệ thống thích ứng với chính sách mới này: "${customPolicyInput}"`);
                      setCustomPolicyInput('');
                    }
                  }}
                  className="gap-1 text-xs font-semibold shrink-0"
                >
                  <Upload size={12} /> Agent phân tích
                </Button>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
