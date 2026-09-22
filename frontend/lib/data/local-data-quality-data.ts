import { parseCsv } from './csv';
import type { ColumnProfile, DataQualityDataSource, DatasetProfile } from './data-quality-types';
import datasetCsv from '../../../data/vingroup_pilot_dataset/ride_hailing_xanh_sm_trips.csv?raw';
import controlsCsv from '../../../data/datatrust_audit_demo_csv/control_results.csv?raw';

function inferType(values:string[]) {
  if(values.every(value=>/^(true|false)$/i.test(value))) return 'boolean';
  if(values.every(value=>/^-?\d+$/.test(value))) return 'integer';
  if(values.every(value=>/^-?\d+(\.\d+)?$/.test(value))) return 'decimal';
  if(values.every(value=>!Number.isNaN(Date.parse(value)) && /\d{4}-\d{2}-\d{2}/.test(value))) return 'datetime';
  return 'string';
}
function columnSummary(values:string[],datatype:string) {
  if(!values.length) return 'No values';
  if(datatype==='integer'||datatype==='decimal') { const nums=values.map(Number); return `Min ${Math.min(...nums).toLocaleString()} · Max ${Math.max(...nums).toLocaleString()}`; }
  if(datatype==='datetime') { const sorted=[...values].sort(); return `${sorted[0]} → ${sorted.at(-1)}`; }
  return `Example: ${values[0]}`;
}

export class LocalCsvDataQualityDataSource implements DataQualityDataSource {
  async getDatasetProfile():Promise<DatasetProfile> {
    const rows=parseCsv(datasetCsv), controls=parseCsv(controlsCsv).filter(control=>control.domain==='DATA_QUALITY');
    const names=rows[0]?Object.keys(rows[0]):[];
    let populated=0;
    const columns:ColumnProfile[]=names.map(name=>{const all=rows.map(row=>row[name]??'');const values=all.filter(value=>value!=='');populated+=values.length;const datatype=inferType(values);return {name,datatype,distinctCount:new Set(values).size,nullRate:Number((((all.length-values.length)/Math.max(1,all.length))*100).toFixed(2)),summary:columnSummary(values,datatype)};});
    const grouped=new Map<string,{name:string;evaluations:number;failures:number}>();
    controls.forEach(control=>{const current=grouped.get(control.control_id)??{name:control.control_name,evaluations:0,failures:0};current.evaluations+=1;if(control.status==='FAIL')current.failures+=1;grouped.set(control.control_id,current);});
    return {datasetName:'ride_hailing_xanh_sm_trips.csv',totalRows:rows.length,columnCount:names.length,completeness:Number(((populated/Math.max(1,rows.length*names.length))*100).toFixed(2)),failedRules:controls.filter(control=>control.status==='FAIL').length,columns,controlResults:controls.sort((a,b)=>b.evaluated_at.localeCompare(a.evaluated_at)).map(control=>({id:control.control_result_id,name:control.control_name,status:control.status,severity:control.severity,evaluatedAt:control.evaluated_at,message:control.evaluation_message})),rules:[...grouped.entries()].map(([id,rule])=>({id,name:rule.name,evaluations:rule.evaluations,failures:rule.failures,passRate:Math.round(((rule.evaluations-rule.failures)/rule.evaluations)*100)}))};
  }
}
export const dataQualityDataSource:DataQualityDataSource=new LocalCsvDataQualityDataSource();
