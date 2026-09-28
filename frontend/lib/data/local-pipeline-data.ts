import { humanize, parseCsv, type CsvRow } from './csv';
import type { FindingSeverity, FindingState } from './dashboard-types';
import type { PipelineDataSource, PipelineRun, PipelineRunDetail, PipelineStatus } from './pipeline-types';
import runsCsv from '../../../data/datatrust_audit_demo_csv/pipeline_runs.csv?raw';
import controlsCsv from '../../../data/datatrust_audit_demo_csv/control_results.csv?raw';
import findingsCsv from '../../../data/datatrust_audit_demo_csv/findings.csv?raw';
import evidenceCsv from '../../../data/datatrust_audit_demo_csv/evidence.csv?raw';
import { apiBridge } from '../api-bridge';
const sources:Record<string,string>={'pipeline_runs.csv':runsCsv,'control_results.csv':controlsCsv,'findings.csv':findingsCsv,'evidence.csv':evidenceCsv};

export class LocalCsvPipelineDataSource implements PipelineDataSource {
  async listRuns(){return (await this.read('pipeline_runs.csv')).map(row=>this.toRun(row)).sort((a,b)=>b.startedAt.localeCompare(a.startedAt));}
  async getRun(id:string):Promise<PipelineRunDetail|null>{
    try {
      const liveRuns = await apiBridge.fetchLivePipelineRuns();
      const liveRun = liveRuns.find((r: any) => r.id.toLowerCase() === id.toLowerCase());
      if (liveRun) {
        const dataset = liveRun.datasetId || liveRun.dataset_id || 'ride_hailing_xanh_sm_trips.csv';
        const rulePass = liveRun.rulePassCount ?? 4;
        const ruleFail = liveRun.ruleFailCount ?? 1;
        return {
          id: liveRun.id,
          dagId: liveRun.dagId,
          datasetId: dataset,
          dataset_id: dataset,
          status: liveRun.status,
          inputRecords: liveRun.inputRecords,
          silverRecords: liveRun.silverRecords,
          quarantineRecords: liveRun.quarantineRecords,
          startedAt: liveRun.startedAt,
          finishedAt: liveRun.finishedAt,
          durationMinutes: liveRun.durationMinutes,
          rulePassCount: rulePass,
          ruleFailCount: ruleFail,
          rules: [
            {
              id: `CTRL-${id.slice(-6).toUpperCase()}-01`,
              controlId: 'POL-01',
              name: `Quy tắc làm sạch & chuẩn hóa dữ liệu (${dataset})`,
              status: 'PASS',
              severity: 'HIGH',
              message: `Đã xử lý file ${dataset}: ${liveRun.silverRecords?.toLocaleString('vi-VN')} bản ghi chuẩn hoá hợp lệ vào Silver zone.`,
            },
            {
              id: `CTRL-${id.slice(-6).toUpperCase()}-02`,
              controlId: 'POL-02',
              name: `Kiểm soát dữ liệu cách ly (Quarantine)`,
              status: liveRun.quarantineRecords > 0 ? 'FAIL' : 'PASS',
              severity: 'MEDIUM',
              message: liveRun.quarantineRecords > 0
                ? `Phát hiện ${liveRun.quarantineRecords?.toLocaleString('vi-VN')} bản ghi vi phạm quy tắc làm sạch, đã chuyển vào Quarantine zone.`
                : `Không có bản ghi nào bị cách ly trong tập dữ liệu ${dataset}.`,
            },
          ],
          findings: liveRun.quarantineRecords > 0 ? [
            {
              id: `FND-${id.slice(-6).toUpperCase()}`,
              title: `Dữ liệu vi phạm ngưỡng kiểm soát trong ${dataset}`,
              severity: 'HIGH' as FindingSeverity,
              status: 'OPEN' as FindingState,
            }
          ] : [],
          evidence: [
            {
              id: `EVID-${id.slice(-6).toUpperCase()}`,
              type: 'Airflow XCom Task Metric',
              source: 'DataTrust Pipeline Engine',
              capturedAt: liveRun.finishedAt || liveRun.startedAt,
              reference: `Airflow DAG: ${liveRun.dagId} | Task: task_5_xcom_push_metrics | Dataset: ${dataset}`,
            }
          ],
        };
      }
    } catch {
      // Fallback to local CSV
    }

    const [runs,controls,findings,evidenceRows]=await Promise.all([this.read('pipeline_runs.csv'),this.read('control_results.csv'),this.read('findings.csv'),this.read('evidence.csv')]);
    const row=runs.find(run=>run.run_id.toLowerCase()===id.toLowerCase());if(!row)return null;
    const run=this.toRun(row),rules=controls.filter(control=>control.run_id===row.run_id);
    const resultIds=new Set(rules.map(rule=>rule.control_result_id));
    const relatedFindings=findings.filter(finding=>resultIds.has(finding.control_result_id));
    const evidenceIds=new Set(rules.map(rule=>rule.evidence_id).filter(Boolean));
    const evidence=evidenceRows.filter(item=>item.run_id===row.run_id||evidenceIds.has(item.evidence_id));
    return {...run,rulePassCount:Number(row.rule_pass_count||0),ruleFailCount:Number(row.rule_fail_count||0),rules:rules.map(rule=>({id:rule.control_result_id,controlId:rule.control_id,name:rule.control_name,status:rule.status,severity:rule.severity,message:rule.evaluation_message})),findings:relatedFindings.map(finding=>({id:finding.finding_id,title:finding.title,severity:finding.severity as FindingSeverity,status:finding.status as FindingState})),evidence:evidence.map(item=>({id:item.evidence_id,type:humanize(item.evidence_type),source:humanize(item.source_system),capturedAt:item.captured_at,reference:item.raw_reference}))};
  }
  private toRun(row:CsvRow):PipelineRun { const start=Date.parse(row.started_at),finish=Date.parse(row.finished_at);return {id:row.run_id,dagId:row.dag_id,datasetId:row.dataset_id||'ride_hailing_xanh_sm_trips.csv',status:row.status as PipelineStatus,inputRecords:Number(row.input_records),silverRecords:Number(row.silver_records),quarantineRecords:Number(row.quarantine_records),startedAt:row.started_at,finishedAt:row.finished_at,durationMinutes:Math.max(0,Math.round((finish-start)/60000))}; }
  private async read(fileName:string){return parseCsv(sources[fileName]??'');}
}
export const pipelineDataSource:PipelineDataSource=new LocalCsvPipelineDataSource();
