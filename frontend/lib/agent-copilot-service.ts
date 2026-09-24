import type { AgentStoreState, ProposedRule } from './agent-store';

export interface ChatMessage {
  id: string;
  sender: 'agent' | 'user' | 'system';
  text: string;
  timestamp: string;
  actionPayload?: {
    type: 'approve_rule' | 'run_agent' | 'view_evidence' | 'select_dataset';
    ruleId?: string;
    datasetId?: string;
    evidenceId?: string;
    label?: string;
  };
  quickPrompts?: string[];
}

export const INITIAL_COPILOT_MESSAGES: ChatMessage[] = [
  {
    id: 'msg-welcome-1',
    sender: 'agent',
    text: `Chào bạn! Tôi là DataTrust Agent.

Tôi có thể giúp bạn **chạy kiểm thử tuân thủ IPO**, **tra cứu bằng chứng băm SHA-256**, hoặc **tự động thích ứng chính sách mới**.`,
    timestamp: 'Vừa xong',
    quickPrompts: [
      '🧪 Chạy test case tuân thủ',
      '🛡️ Bằng chứng SHA-256',
      '⚡ Cho agent chạy kiểm tra',
      '❓ Tại sao đề xuất rule?',
    ],
  },
];

export function generateCopilotResponse(query: string, store: AgentStoreState): ChatMessage {
  const q = query.toLowerCase().trim();
  const currentDs = store.datasets[store.selectedDatasetId] || store.datasets.trips;
  const pendingRules: ProposedRule[] = currentDs.proposedRules.filter(
    (r: ProposedRule) => r.status === 'pending'
  );
  const now = new Date().toLocaleTimeString('vi-VN', { hour: '2-digit', minute: '2-digit' });

  // 1. Hướng dẫn sử dụng Onboarding (Ngắn gọn, dễ hiểu)
  if (
    q.includes('hướng dẫn') ||
    q.includes('cách dùng') ||
    q.includes('làm sao') ||
    q.includes('bắt đầu') ||
    q.includes('onboard')
  ) {
    return {
      id: `agent-${Date.now()}`,
      sender: 'agent',
      timestamp: now,
      text: `🧭 **3 bước làm việc nhanh:**\n1. Chọn bộ dữ liệu trên thanh công cụ.\n2. Bấm **"Cho agent chạy"** để quét bất thường.\n3. Duyệt rule và đối chiếu bằng chứng SHA-256.\n\n*Bạn muốn tôi chạy thử ngay bây giờ không?*`,
      quickPrompts: [
        '⚡ Cho agent chạy kiểm tra',
        '🧪 Chạy test case tuân thủ',
        '🛡️ Bằng chứng SHA-256',
      ],
    };
  }

  // 2. Kích hoạt chạy Agent
  if (
    q.includes('chạy agent') ||
    q.includes('cho agent chạy') ||
    q.includes('bắt đầu chạy') ||
    q.includes('kiểm tra dữ liệu') ||
    q.includes('run')
  ) {
    if (store.agentStatus === 'running') {
      return {
        id: `agent-${Date.now()}`,
        sender: 'agent',
        timestamp: now,
        text: `⏳ Agent đang phân tích **${currentDs.name}**. Bạn có thể theo dõi thanh tiến trình 4 giai đoạn trên màn hình.`,
        quickPrompts: ['❓ Tại sao đề xuất rule?', '🛡️ Bằng chứng SHA-256'],
      };
    }

    setTimeout(() => {
      store.runAgent();
    }, 200);

    return {
      id: `agent-${Date.now()}`,
      sender: 'agent',
      timestamp: now,
      text: `🚀 **Đã khởi chạy phân tích!**\nAgent đang quét ${currentDs.records.toLocaleString('vi-VN')} bản ghi trên ${currentDs.name}. Kết quả sẽ hiển thị ngay khi hoàn tất.`,
      quickPrompts: ['❓ Tại sao đề xuất rule?', '🛡️ Bằng chứng SHA-256'],
    };
  }

  // 3. Giải thích lý do đề xuất Rule
  if (
    q.includes('tại sao') ||
    q.includes('đề xuất rule') ||
    q.includes('lý do') ||
    q.includes('giải thích rule') ||
    q.includes('rule hiện tại')
  ) {
    if (pendingRules.length === 0) {
      return {
        id: `agent-${Date.now()}`,
        sender: 'agent',
        timestamp: now,
        text: `✅ Bộ dữ liệu **${currentDs.name}** hiện đã được thẩm định hết, không còn rule nào chờ duyệt.`,
        quickPrompts: ['⚡ Cho agent chạy kiểm tra', '🧪 Chạy test case tuân thủ'],
      };
    }

    const firstRule = pendingRules[0];
    return {
      id: `agent-${Date.now()}`,
      sender: 'agent',
      timestamp: now,
      text: `🔍 Phát hiện **${currentDs.anomalies} bản ghi bất thường**.\nTôi đề xuất rule: **${firstRule.name}** (${firstRule.affectedRows} dòng ảnh hưởng) để tự động cách ly vào Quarantine.\n\n*Chi tiết đã mở tại bảng Preview.*`,
      actionPayload: {
        type: 'approve_rule',
        ruleId: firstRule.id,
        label: `Phê duyệt ${firstRule.name}`,
      },
      quickPrompts: [
        `Phê duyệt ${firstRule.name}`,
        '🛡️ Bằng chứng SHA-256',
      ],
    };
  }

  // 4. Phê duyệt Rule trực tiếp trong Chat
  if (q.includes('phê duyệt') || q.includes('duyệt rule') || q.includes('approve')) {
    if (pendingRules.length === 0) {
      return {
        id: `agent-${Date.now()}`,
        sender: 'agent',
        timestamp: now,
        text: `👍 Hiện tại không còn rule nào đang chờ duyệt cho bộ dữ liệu này.`,
        quickPrompts: ['⚡ Cho agent chạy kiểm tra'],
      };
    }

    let targetRule = pendingRules.find(
      (r: ProposedRule) => q.includes(r.id.toLowerCase()) || q.includes(r.name.toLowerCase())
    );
    if (!targetRule) targetRule = pendingRules[0];

    store.approveRule(targetRule.id);

    return {
      id: `agent-${Date.now()}`,
      sender: 'agent',
      timestamp: now,
      text: `✅ **Đã duyệt thành công rule "${targetRule.name}"!**\nDữ liệu vi phạm sẽ được tự động cách ly vào làn Quarantine.`,
      quickPrompts: ['📊 Xem kết quả và bằng chứng', '⚡ Cho agent chạy kiểm tra'],
    };
  }

  // 5. Giải thích Bằng chứng SHA-256 & Audit Store
  if (q.includes('sha-256') || q.includes('bằng chứng') || q.includes('evidence') || q.includes('kiểm toán')) {
    return {
      id: `agent-${Date.now()}`,
      sender: 'agent',
      timestamp: now,
      text: `🛡️ Mỗi phát hiện được niêm phong bằng mã băm **SHA-256 bất biến (Tamper-proof)**, phục vụ thẩm định hồ sơ niêm yết IPO độc lập của Big 4.`,
      quickPrompts: ['🧪 Chạy test case tuân thủ', '⚡ Cho agent chạy kiểm tra'],
    };
  }

  // 6. Test case compliance
  if (q.includes('test') || q.includes('kiểm thử')) {
    return {
      id: `agent-${Date.now()}`,
      sender: 'agent',
      timestamp: now,
      text: `🧪 Hệ thống đã dựng sẵn **6 test case giả lập vi phạm** (cước 0đ, CCCD chưa mã hóa, chênh lệch sạc). Bạn có thể bấm nút chạy ở bảng Preview bên cạnh.`,
      quickPrompts: ['⚡ Cho agent chạy kiểm tra', '🛡️ Bằng chứng SHA-256'],
    };
  }

  // 7. Mặc định: Phản hồi ngắn gọn
  return {
    id: `agent-${Date.now()}`,
    sender: 'agent',
    timestamp: now,
    text: `Tôi đã ghi nhận câu hỏi của bạn. Trên bộ dữ liệu **${currentDs.name}**, hiện có **${currentDs.anomalies} phát hiện** và **${pendingRules.length} rule chờ bạn duyệt**.`,
    quickPrompts: [
      '⚡ Cho agent chạy kiểm tra',
      '❓ Tại sao đề xuất rule?',
      '🛡️ Bằng chứng SHA-256',
    ],
  };
}
