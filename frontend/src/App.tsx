import { useCallback, useEffect, useState, type ReactNode } from 'react';
import { Navigate, Route, Routes, useParams } from 'react-router-dom';
import { AppShell } from '@/components/datatrust/app-shell';
import { ShellPage } from '@/components/datatrust/shell-page';
import { DashboardPage } from '@/components/datatrust/dashboard/dashboard-page';
import { FindingsList } from '@/components/datatrust/findings/findings-list';
import { FindingDetail } from '@/components/datatrust/findings/finding-detail';
import { DatasetProfiling } from '@/components/datatrust/data-quality/dataset-profiling';
import { PipelineRuns } from '@/components/datatrust/pipeline/pipeline-runs';
import { PipelineRunDetail } from '@/components/datatrust/pipeline/pipeline-run-detail';
import { dashboardDataSource } from '@/lib/data/local-dashboard-data';
import { findingsDataSource } from '@/lib/data/local-findings-data';
import { dataQualityDataSource } from '@/lib/data/local-data-quality-data';
import { pipelineDataSource } from '@/lib/data/local-pipeline-data';

function Load<T>({load,children}:{load:()=>Promise<T>;children:(data:T)=>ReactNode}){
  const [data,setData]=useState<T>(); const [error,setError]=useState('');
  useEffect(()=>{let active=true;load().then(value=>{if(active)setData(value)}).catch(reason=>{if(active)setError(reason instanceof Error?reason.message:String(reason))});return()=>{active=false}},[load]);
  if(error)return <div className="rounded-xl border border-red-200 bg-red-50 p-6 text-sm text-red-700">Unable to load demo data: {error}</div>;
  if(!data)return <div className="grid min-h-[50vh] place-items-center text-sm text-slate-400">Loading local demo data…</div>;
  return children(data);
}
const loadDashboard=()=>dashboardDataSource.getDashboardData();
const loadFindings=()=>findingsDataSource.listFindings();
const loadProfile=()=>dataQualityDataSource.getDatasetProfile();
const loadRuns=()=>pipelineDataSource.listRuns();

function Dashboard(){return <Load load={loadDashboard}>{data=><DashboardPage data={data}/>}</Load>}
function Findings(){return <Load load={loadFindings}>{data=><FindingsList findings={data}/>}</Load>}
function Finding(){const {id=''}=useParams();const load=useCallback(()=>findingsDataSource.getFinding(id),[id]);return <Load load={load}>{data=>data?<FindingDetail finding={data}/>:<Navigate to="/findings" replace/>}</Load>}
function DataQuality(){return <Load load={loadProfile}>{data=><DatasetProfiling profile={data}/>}</Load>}
function Runs(){return <Load load={loadRuns}>{data=><PipelineRuns runs={data}/>}</Load>}
function Run(){const {id=''}=useParams();const load=useCallback(()=>pipelineDataSource.getRun(id),[id]);return <Load load={load}>{data=>data?<PipelineRunDetail run={data}/>:<Navigate to="/pipeline-runs" replace/>}</Load>}

export default function App(){return <AppShell><Routes>
  <Route path="/" element={<Navigate to="/dashboard" replace/>}/>
  <Route path="/dashboard" element={<Dashboard/>}/>
  <Route path="/findings" element={<Findings/>}/>
  <Route path="/findings/:id" element={<Finding/>}/>
  <Route path="/data-quality" element={<DataQuality/>}/>
  <Route path="/pipeline-runs" element={<Runs/>}/>
  <Route path="/pipeline-runs/:id" element={<Run/>}/>
  <Route path="/privacy" element={<ShellPage title="Privacy & Protection" description="Privacy policies and data protection controls."/>}/>
  <Route path="/controls" element={<ShellPage title="Controls (ITGC)" description="Control library and ITGC testing workspace."/>}/>
  <Route path="/evidence" element={<ShellPage title="Evidence" description="Evidence inventory and audit trail workspace."/>}/>
  <Route path="/administration" element={<ShellPage title="Administration" description="Users, roles, and platform settings."/>}/>
  <Route path="*" element={<Navigate to="/dashboard" replace/>}/>
</Routes></AppShell>}
