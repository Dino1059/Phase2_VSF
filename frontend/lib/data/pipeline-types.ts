import type { FindingSeverity, FindingState } from './dashboard-types';
export type PipelineStatus='SUCCESS'|'FAILED'|'PARTIAL';
export interface PipelineRun { id:string; dagId:string; status:PipelineStatus; inputRecords:number; silverRecords:number; quarantineRecords:number; startedAt:string; finishedAt:string; durationMinutes:number; }
export interface PipelineRuleResult { id:string; controlId:string; name:string; status:string; severity:string; message:string; }
export interface PipelineFinding { id:string; title:string; severity:FindingSeverity; status:FindingState; }
export interface PipelineEvidence { id:string; type:string; source:string; capturedAt:string; reference:string; }
export interface PipelineRunDetail extends PipelineRun { rulePassCount:number; ruleFailCount:number; rules:PipelineRuleResult[]; findings:PipelineFinding[]; evidence:PipelineEvidence[]; }
export interface PipelineDataSource { listRuns():Promise<PipelineRun[]>; getRun(id:string):Promise<PipelineRunDetail|null>; }
