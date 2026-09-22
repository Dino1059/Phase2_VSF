import { humanize, parseCsv, type CsvRow } from './csv';
import type { FindingSeverity, FindingState } from './dashboard-types';
import type { FindingDetail, FindingListItem, FindingsDataSource } from './findings-types';
import findingsCsv from '../../../data/datatrust_audit_demo_csv/findings.csv?raw';
import controlsCsv from '../../../data/datatrust_audit_demo_csv/control_results.csv?raw';
import evidenceCsv from '../../../data/datatrust_audit_demo_csv/evidence.csv?raw';
import dbAuditCsv from '../../../data/datatrust_audit_demo_csv/db_audit_events.csv?raw';
import exportsCsv from '../../../data/datatrust_audit_demo_csv/export_events.csv?raw';
import accessCsv from '../../../data/datatrust_audit_demo_csv/access_requests.csv?raw';
import approvalsCsv from '../../../data/datatrust_audit_demo_csv/approvals.csv?raw';
import hrCsv from '../../../data/datatrust_audit_demo_csv/hr_events.csv?raw';
import cicdCsv from '../../../data/datatrust_audit_demo_csv/cicd_events.csv?raw';

const sources:Record<string,string>={'findings.csv':findingsCsv,'control_results.csv':controlsCsv,'evidence.csv':evidenceCsv,'db_audit_events.csv':dbAuditCsv,'export_events.csv':exportsCsv,'access_requests.csv':accessCsv,'approvals.csv':approvalsCsv,'hr_events.csv':hrCsv,'cicd_events.csv':cicdCsv};

export class LocalCsvFindingsDataSource implements FindingsDataSource {
  async listFindings(): Promise<FindingListItem[]> {
    const [findings, controls] = await Promise.all([this.read('findings.csv'), this.read('control_results.csv')]);
    const controlMap = new Map(controls.map(control => [control.control_result_id, control]));
    return findings.map(finding => this.toListItem(finding, controlMap.get(finding.control_result_id))).sort((a, b) => b.createdAt.localeCompare(a.createdAt));
  }

  async getFinding(id: string): Promise<FindingDetail | null> {
    const [findings, controls, evidenceRows, dbEvents, exportEvents, accessRequests, approvals, hrEvents, cicdEvents] = await Promise.all([
      this.read('findings.csv'), this.read('control_results.csv'), this.read('evidence.csv'),
      this.read('db_audit_events.csv'), this.read('export_events.csv'), this.read('access_requests.csv'),
      this.read('approvals.csv'), this.read('hr_events.csv'), this.read('cicd_events.csv'),
    ]);
    const finding = findings.find(item => item.finding_id.toLowerCase() === id.toLowerCase());
    if (!finding) return null;
    const control = controls.find(item => item.control_result_id === finding.control_result_id);
    const base = this.toListItem(finding, control);
    const sourceRows: Record<string, CsvRow[]> = { DB_AUDIT:dbEvents, EXPORT:exportEvents, ACCESS_REQUEST:accessRequests, APPROVAL:approvals, HR:hrEvents, CICD:cicdEvents };
    const rawFor = (item:CsvRow): unknown => {
      const rows=sourceRows[item.evidence_type] ?? [];
      if(item.evidence_type==='APPROVAL') return rows.filter(row=>row.request_id===item.source_event_id || row.request_id===item.request_id);
      const key:Record<string,string>={DB_AUDIT:'event_id',EXPORT:'export_id',ACCESS_REQUEST:'request_id',HR:'hr_event_id',CICD:'cicd_event_id'};
      return rows.find(row=>row[key[item.evidence_type]]===item.source_event_id) ?? { message:'Raw source event not found', source_event_id:item.source_event_id };
    };
    const linkedObjectFor = (item:CsvRow, raw:unknown) => {
      const record=Array.isArray(raw)?raw[0]:raw as CsvRow|undefined;
      return item.request_id || item.run_id || item.trip_id || record?.object_name || record?.dataset || record?.change_request_id || item.source_event_id;
    };
    const evidence = evidenceRows.filter(item => item.evidence_id === control?.evidence_id).map(item => { const rawEvent=rawFor(item); return {
      id:item.evidence_id, type:humanize(item.evidence_type), source:humanize(item.source_system), capturedAt:item.captured_at,
      actor:item.actor_user_id || (Array.isArray(rawEvent)?rawEvent[0]?.approver_user_id:(rawEvent as CsvRow)?.actor_user_id) || 'System',
      linkedObject:linkedObjectFor(item,rawEvent), reference:item.raw_reference, controlResultId:finding.control_result_id, rawEvent,
    }; });
    const related = findings.filter(item => item.finding_id !== finding.finding_id && item.control_id === finding.control_id).slice(0, 4).map(item => this.toListItem(item, controls.find(controlItem => controlItem.control_result_id === item.control_result_id)));
    const history: FindingDetail['history'] = [
      { label:'Finding created', detail:`Generated from failed control result ${finding.control_result_id}.`, occurredAt:finding.opened_at, tone:'blue' },
      { label:'Control evaluated', detail:control?.evaluation_message || 'Control violation detected.', occurredAt:control?.evaluated_at || finding.opened_at, tone:'amber' },
    ];
    if (finding.hitl_decision) history.push({ label:'Human review completed', detail:humanize(finding.hitl_decision), occurredAt:finding.closed_at || finding.opened_at, tone:'green' });
    if (finding.closed_at) history.push({ label:'Finding closed', detail:'Remediation workflow completed.', occurredAt:finding.closed_at, tone:'green' });
    return {
      ...base,
      assignedTo: finding.assigned_to_user_id || 'Unassigned',
      control: { id:finding.control_id, name:control?.control_name || finding.title.replace('Violation detected: ',''), evaluationMessage:control?.evaluation_message || 'Control violation detected.', evaluatedAt:control?.evaluated_at || finding.opened_at },
      issueDescription: finding.root_cause_summary || control?.evaluation_message || 'A control violation was detected and requires review.',
      impact: this.impactFor(finding.severity, control?.domain),
      recommendedActions: (finding.recommended_action || 'Review the supporting evidence and remediate the failed control.').split(';').map((item:string)=>item.trim()).filter(Boolean),
      evidence, history, related,
    };
  }

  private toListItem(finding: CsvRow, control?: CsvRow): FindingListItem { return { id:finding.finding_id, title:finding.title, domain:humanize(control?.domain ?? 'OTHER'), severity:finding.severity as FindingSeverity, status:finding.status as FindingState, createdAt:finding.opened_at }; }
  private impactFor(severity: string, domain?: string) { const prefix = severity === 'CRITICAL' || severity === 'HIGH' ? 'Material compliance risk' : 'Operational control risk'; return `${prefix} affecting ${humanize(domain ?? 'the governed data environment')}. If unresolved, the issue may reduce audit assurance and expose downstream data or processes.`; }
  private async read(fileName: string) { return parseCsv(sources[fileName] ?? ''); }
}

export const findingsDataSource: FindingsDataSource = new LocalCsvFindingsDataSource();
