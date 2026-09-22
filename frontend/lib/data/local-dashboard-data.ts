import type { DashboardData, DashboardDataSource, FindingSeverity, FindingState } from './dashboard-types';
import { humanize, parseCsv } from './csv';
import controlsCsv from '../../../data/datatrust_audit_demo_csv/control_results.csv?raw';
import findingsCsv from '../../../data/datatrust_audit_demo_csv/findings.csv?raw';
import runsCsv from '../../../data/datatrust_audit_demo_csv/pipeline_runs.csv?raw';

export class LocalCsvDashboardDataSource implements DashboardDataSource {
  async getDashboardData(): Promise<DashboardData> {
    const [controls, findings, runs] = await Promise.all([
      Promise.resolve(parseCsv(controlsCsv)), Promise.resolve(parseCsv(findingsCsv)), Promise.resolve(parseCsv(runsCsv)),
    ]);
    const controlByResult = new Map(controls.map(control => [control.control_result_id, control]));
    const countControl = (status: string) => controls.filter(control => control.status === status).length;
    const pass = countControl('PASS'), fail = countControl('FAIL'), notEvaluated = countControl('NOT_EVALUATED');
    const evaluated = pass + fail;
    const latestFindingDate = Math.max(...findings.map(finding => Date.parse(finding.opened_at)));
    const overdueCutoff = latestFindingDate - 7 * 24 * 60 * 60 * 1000;
    const activeStates = new Set(['OPEN', 'IN_REVIEW']);

    const domainCounts = new Map<string, number>();
    findings.forEach(finding => {
      const domain = controlByResult.get(finding.control_result_id)?.domain ?? 'OTHER';
      domainCounts.set(domain, (domainCounts.get(domain) ?? 0) + 1);
    });

    const trend = new Map<string, { pass: number; fail: number }>();
    runs.forEach(run => {
      const day = run.started_at.slice(0, 10);
      const current = trend.get(day) ?? { pass: 0, fail: 0 };
      current.pass += Number(run.rule_pass_count || 0);
      current.fail += Number(run.rule_fail_count || 0);
      trend.set(day, current);
    });

    return {
      metrics: {
        total: findings.length,
        resolved: findings.filter(finding => ['CLOSED', 'REMEDIATED'].includes(finding.status)).length,
        inProgress: findings.filter(finding => activeStates.has(finding.status)).length,
        overdue: findings.filter(finding => activeStates.has(finding.status) && Date.parse(finding.opened_at) < overdueCutoff).length,
      },
      complianceScore: evaluated ? Math.round((pass / evaluated) * 100) : 0,
      controls: [{ name: 'Pass', value: pass }, { name: 'Fail', value: fail }, { name: 'Not Evaluated', value: notEvaluated }],
      findingsByDomain: [...domainCounts.entries()].map(([name, value]) => ({ name: humanize(name), value })).sort((a, b) => b.value - a.value),
      complianceTrend: [...trend.entries()].sort(([a], [b]) => a.localeCompare(b)).map(([date, counts]) => ({ date: date.slice(5), score: Math.round((counts.pass / Math.max(1, counts.pass + counts.fail)) * 100) })),
      recentFindings: findings.sort((a, b) => b.opened_at.localeCompare(a.opened_at)).slice(0, 8).map(finding => ({
        id: finding.finding_id,
        title: finding.title,
        domain: humanize(controlByResult.get(finding.control_result_id)?.domain ?? 'OTHER'),
        severity: finding.severity as FindingSeverity,
        status: finding.status as FindingState,
        openedAt: finding.opened_at,
      })),
      generatedAt: new Date(latestFindingDate).toISOString(),
    };
  }

}

export const dashboardDataSource: DashboardDataSource = new LocalCsvDashboardDataSource();
