export type UserRole = 'Admin' | 'Steward' | 'Viewer';

export interface ColumnProfile {
  column_name: string;
  data_type: string;
  null_count: number;
  null_percentage: number;
  distinct_count: number;
  min_value?: any;
  max_value?: any;
  sample_values?: any[];
  health_status?: 'Good' | 'Drifting' | 'Warning';
}

export interface ProfileReport {
  snapshot_id: string;
  row_count: number;
  column_count: number;
  duplicate_count: number;
  columns: ColumnProfile[];
}

export interface RuleSchema {
  rule_id: string;
  rule_type: string;
  target_column: string;
  action: string;
  parameters: Record<string, any>;
  severity: 'High' | 'Medium' | 'Low';
  description: string;
  status?: 'Proposed' | 'Approved' | 'Rejected';
  confidence_score?: number;
  evidence?: string;
}

export interface ProposeRulesResponse {
  variant: string;
  rules: RuleSchema[];
  reasoning: string;
}

export interface ExecuteTransformRequest {
  data: Record<string, any>[];
  rules: RuleSchema[];
}

export interface ExecuteTransformResponse {
  initial_rows: number;
  clean_rows: number;
  quarantine_rows: number;
  execution_time_sec: number;
  quarantine_summary: Record<string, number>;
}

export interface CronSchedule {
  id: string;
  name: string;
  dataset_source: string;
  cron_expression: string;
  variant: string;
  notification_email: string;
  active: boolean;
  next_run: string;
  last_status: 'Success' | 'Failed' | 'Pending';
}

export interface AnomalyEvent {
  id: string;
  timestamp: string;
  target_column: string;
  metric: string;
  severity: 'Critical' | 'Warning' | 'Info';
  detected_value: string | number;
  expected_range: string;
  root_cause: string;
  remediation_suggestion: string;
  impact_summary: string;
  status: 'Open' | 'Investigating' | 'Resolved';
}

export interface NotificationAlert {
  id: string;
  timestamp: string;
  title: string;
  message: string;
  severity: 'Critical' | 'Warning' | 'Info';
  read: boolean;
  category: 'Schema Drift' | 'Data Quality' | 'Governance' | 'System';
}

export interface AuditRecord {
  timestamp: string;
  event_type: string;
  role?: string;
  details: Record<string, any>;
  hash?: string;
}

export interface TargetSchemaField {
  name: string;
  type: string;
  nullable: boolean;
  primaryKey: boolean;
  description: string;
}
