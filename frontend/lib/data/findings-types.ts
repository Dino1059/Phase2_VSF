import type { FindingSeverity, FindingState } from './dashboard-types';

export interface FindingListItem {
  id: string; title: string; domain: string; severity: FindingSeverity; status: FindingState; createdAt: string;
}
export interface FindingEvidence {
  id: string;
  type: string;
  source: string;
  capturedAt: string;
  actor: string;
  linkedObject: string;
  reference: string;
  controlResultId: string;
  rawEvent: unknown;
}
export interface FindingHistoryItem { label: string; detail: string; occurredAt: string; tone: 'blue' | 'amber' | 'green'; }
export interface FindingDetail extends FindingListItem {
  control: { id: string; name: string; evaluationMessage: string; evaluatedAt: string };
  assignedTo: string;
  issueDescription: string;
  impact: string;
  recommendedActions: string[];
  evidence: FindingEvidence[];
  history: FindingHistoryItem[];
  related: FindingListItem[];
}
export interface FindingsDataSource {
  listFindings(): Promise<FindingListItem[]>;
  getFinding(id: string): Promise<FindingDetail | null>;
}
