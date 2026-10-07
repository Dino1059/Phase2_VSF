# DataTrust OS — Component architecture và state management

> Vai trò: **Admin**. Đọc [README.md](README.md) trước khi triển khai.
> Phần tương ứng trong spec gốc: 24, 25. Nội dung các phần này được giữ nguyên.

## Tài liệu liên quan

- [Phạm vi sản phẩm](01-product-scope.md)
- [Thiết kế và tương tác dùng chung](02-design-system-and-interactions.md)
- [Điều hướng](03-app-shell-and-navigation.md)
- [Data model](16-data-models.md)
- [API và realtime](18-api-and-realtime.md)
- [Acceptance và bàn giao](19-acceptance-and-delivery.md)

---

# 24. Component architecture

Đề xuất component hierarchy:

```text
AppShell
├── Sidebar
├── Topbar
└── DualPaneLayout
    ├── AiChatPane (sticky/fixed, persistent)
    └── Workspace (route content)

DashboardPage
├── KPIGrid
├── ComplianceTrendChart
├── FindingsSummary
├── PolicyDistribution
└── RecentRuns

HomePage
└── DatasetSelector

AppliedRulesPage
├── AppliedRulesToolbar
├── AppliedRulesTable
└── RuleDetailDrawer

RunPage
├── RunHeader
├── PipelineStepper
├── RunMetrics
└── RunEventTimeline

RunResultsPage
├── ResultKPIGrid
├── ResultDistribution
├── FindingsSummary
└── TopViolatedRules

FindingsPage
├── FindingsToolbar
├── FindingsTable
└── FindingDetailDrawer

FindingDetail
├── FindingSummary
├── RuleContext
├── AIAnalysisPanel
├── ActionBar
└── RelatedEvidence

LineagePage
├── LineageToolbar
├── LineageCanvas
└── NodeDetailDrawer

QuarantinePage
├── QuarantineSummary
├── QuarantineFilters
├── QuarantineTable
└── QuarantineDetailDrawer

EvidencePage
├── EvidenceSummary
├── EvidenceSections
└── EvidenceActions

AccessControlPage
├── AccessKPIs
├── AccessTrend
├── ResourceDistribution
├── RealTimeAlerts
└── AccessTable
```

---

# 25. Suggested state management

UI state tối thiểu:

```text
selectedWorkspace
selectedDataset
selectedRun
selectedFinding
selectedRule
selectedQuarantineRecord

chatSession
chatMessages
chatContext
isChatOpen

filters
drawerState
modalState

runStatus
pipelineProgress

aiAnalysis
aiRemediationSuggestion
hitlDecision
```

`selectedRule` chỉ dùng để mở chi tiết rule read-only; không đại diện cho việc chọn rule áp dụng cho run.

Không lưu AI suggestion như một rule definition.

AI suggestion là ephemeral/workflow object liên kết với Finding.

---
