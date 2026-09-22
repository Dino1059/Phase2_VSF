export interface ColumnProfile { name:string; datatype:string; distinctCount:number; nullRate:number; summary:string; }
export interface DataQualityControl { id:string; name:string; status:string; severity:string; evaluatedAt:string; message:string; }
export interface DataQualityRule { id:string; name:string; evaluations:number; failures:number; passRate:number; }
export interface DatasetProfile {
  datasetName:string; totalRows:number; columnCount:number; completeness:number; failedRules:number;
  columns:ColumnProfile[]; controlResults:DataQualityControl[]; rules:DataQualityRule[];
}
export interface DataQualityDataSource { getDatasetProfile():Promise<DatasetProfile>; }
