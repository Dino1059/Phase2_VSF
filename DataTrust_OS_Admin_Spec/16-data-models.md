# DataTrust OS — Data model TypeScript tối thiểu

> Vai trò: **Admin**. Đọc [README.md](README.md) trước khi triển khai.
> Phần tương ứng trong spec gốc: 23. Nội dung các phần này được giữ nguyên.

## Tài liệu liên quan

- [Phạm vi sản phẩm](01-product-scope.md)
- [Thiết kế và tương tác dùng chung](02-design-system-and-interactions.md)
- [Điều hướng](03-app-shell-and-navigation.md)
- [Data model](16-data-models.md)
- [API và realtime](18-api-and-realtime.md)
- [Acceptance và bàn giao](19-acceptance-and-delivery.md)

---

# 23. Data model tối thiểu cho UI

## Dataset

```ts
type Dataset = {
  id: string
  name: string
  source: string
  description?: string
  columnCount: number
  hasPII: boolean
  lastUpdated?: string
}
```

## Rule

```ts
type Rule = {
  id: string
  name: string
  policyId: string
  policyName: string
  policyVersion?: string
  target: string
  scope: "dataset" | "column" | "record"
  severity: "critical" | "high" | "medium" | "low"
  condition: string
  requiredTreatment?: string
  status: "active" | "inactive"
}
```

## Run

```ts
type Run = {
  id: string
  datasetId: string
  datasetName: string
  status: "pending" | "running" | "completed" | "failed" | "cancelled"
  startedAt?: string
  finishedAt?: string
  scannedCount: number
  passCount: number
  failCount: number
  warningCount: number
  notEvaluatedCount: number
  quarantineCount: number
}
```

## Finding

```ts
type Finding = {
  id: string
  runId: string
  ruleId: string
  policyId: string
  datasetId: string
  column?: string
  severity: "critical" | "high" | "medium" | "low"
  status: string
  failedRecords: number
  reason: string
  impact?: string
}
```

Jurisdiction fields required on `Finding`:

```ts
subjectZone: 'EU' | 'VN' | 'US' | 'GLOBAL' | string
jurisdictionChain: string[]
policyId?: string
lawRef?: string
```

`lawRef` is an evaluation-time snapshot of the control that failed. It is not a UI fallback.

## Quarantine record

Every quarantine record additionally carries:

```ts
subjectZone: string
jurisdictionChain: string[]
policyId?: string
policyName?: string
lawRef?: string
```

These fields preserve the matched policy decision so downstream aggregation does not re-infer jurisdiction from a generic rule name.
```ts
type QuarantineRecord = {
  id: string
  runId: string
  datasetId: string
  datasetName: string
  column?: string
  reason: string
  ruleId: string
  severity: string
  detectedAt: string
  status: string
  lineageHash?: string
}
```

## AI recommendation

AI recommendation chỉ dùng cho **explanation/RCA/remediation**, không dùng cho rule creation.

```ts
type AIRemediationSuggestion = {
  id: string
  findingId: string
  rootCause: string
  suggestedActions: string[]
  confidence: number
  status: "suggested" | "approved" | "rejected" | "executing" | "completed" | "failed"
}
```

---
