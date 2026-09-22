'use client';
import { AlertTriangle, ArrowDownRight, ArrowUpRight, CheckCircle2, Clock3, FileWarning } from 'lucide-react';
import { Bar, BarChart, CartesianGrid, Cell, Line, LineChart, Pie, PieChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import { Badge } from '@/components/ui/badge';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import type { DashboardData, FindingSeverity, FindingState } from '@/lib/data/dashboard-types';

const domainColors = ['#2563eb', '#06b6d4', '#f59e0b', '#8b5cf6', '#64748b'];
const metricIcons = [FileWarning, CheckCircle2, Clock3, AlertTriangle];

const severityTone: Record<FindingSeverity, 'red' | 'amber' | 'blue' | 'slate'> = { CRITICAL: 'red', HIGH: 'red', MEDIUM: 'amber', LOW: 'blue' };
const stateTone: Record<FindingState, 'red' | 'amber' | 'green' | 'blue'> = { OPEN: 'red', IN_REVIEW: 'blue', REMEDIATED: 'green', CLOSED: 'green' };

export function DashboardPage({ data }: { data: DashboardData }) {
  const metrics = [
    { label: 'Total Findings', value: data.metrics.total, change: '+8%', positive: false },
    { label: 'Resolved', value: data.metrics.resolved, change: '58%', positive: true },
    { label: 'In Progress', value: data.metrics.inProgress, change: 'Active', positive: true },
    { label: 'Overdue', value: data.metrics.overdue, change: 'Needs action', positive: false },
  ];
  return <section className="page-enter mx-auto max-w-[1440px] space-y-5">
    <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
      <div><h1 className="text-2xl font-bold tracking-tight">Compliance Overview</h1><p className="mt-1 text-sm text-slate-500">Monitor data quality, privacy, and ITGC controls across the platform.</p></div>
      <div className="flex gap-2"><button className="h-9 rounded-md border border-slate-200 bg-white px-3 text-xs font-medium text-slate-600">Last 14 days</button><button className="h-9 rounded-md border border-slate-200 bg-white px-3 text-xs font-medium text-slate-600">All domains</button></div>
    </div>

    <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">{metrics.map((metric, index) => { const Icon = metricIcons[index]; return <Card key={metric.label}><CardContent className="flex items-center justify-between p-5"><div><p className="text-xs font-medium text-slate-500">{metric.label}</p><p className="mt-2 text-2xl font-bold">{metric.value}</p><span className={metric.positive?'mt-2 flex items-center gap-1 text-[11px] font-medium text-emerald-600':'mt-2 flex items-center gap-1 text-[11px] font-medium text-red-500'}>{metric.positive?<ArrowUpRight size={12}/>:<ArrowDownRight size={12}/>} {metric.change}</span></div><span className={index===1?'grid size-10 place-items-center rounded-lg bg-emerald-50 text-emerald-600':'grid size-10 place-items-center rounded-lg bg-blue-50 text-blue-600'}><Icon size={19}/></span></CardContent></Card>})}</div>

    <div className="grid gap-4 xl:grid-cols-12">
      <Card className="xl:col-span-3"><CardHeader><CardTitle>Overall compliance score</CardTitle></CardHeader><CardContent><div className="relative mx-auto grid size-44 place-items-center rounded-full" style={{background:`conic-gradient(#10b981 ${data.complianceScore * 3.6}deg,#e2e8f0 0)`}}><div className="grid size-32 place-items-center rounded-full bg-white text-center"><div><strong className="text-3xl">{data.complianceScore}%</strong><span className="block text-[11px] text-slate-400">Compliant</span></div></div></div><p className="mt-4 text-center text-xs font-medium text-emerald-600">↑ 5% from previous period</p></CardContent></Card>
      <Card className="xl:col-span-4"><CardHeader><CardTitle>Control results</CardTitle></CardHeader><CardContent className="h-[240px]"><ResponsiveContainer width="100%" height="100%"><BarChart data={data.controls} margin={{top:10,right:8,left:-22,bottom:0}}><CartesianGrid vertical={false} stroke="#e2e8f0"/><XAxis dataKey="name" tick={{fontSize:10}} axisLine={false} tickLine={false}/><YAxis tick={{fontSize:10}} axisLine={false} tickLine={false}/><Tooltip/><Bar dataKey="value" radius={[4,4,0,0]}>{data.controls.map(item=><Cell key={item.name} fill={item.name==='Pass'?'#2563eb':item.name==='Fail'?'#ef4444':'#94a3b8'}/>)}</Bar></BarChart></ResponsiveContainer></CardContent></Card>
      <Card className="xl:col-span-5"><CardHeader><CardTitle>Findings by domain</CardTitle></CardHeader><CardContent className="grid h-[240px] grid-cols-[1fr_150px] items-center"><ResponsiveContainer width="100%" height="100%"><PieChart><Pie data={data.findingsByDomain} dataKey="value" nameKey="name" innerRadius={48} outerRadius={76} paddingAngle={2}>{data.findingsByDomain.map((item,index)=><Cell key={item.name} fill={domainColors[index%domainColors.length]}/>)}</Pie><Tooltip/></PieChart></ResponsiveContainer><div className="space-y-3">{data.findingsByDomain.map((item,index)=><div key={item.name} className="flex items-center gap-2 text-[11px]"><span className="size-2 rounded-full" style={{background:domainColors[index%domainColors.length]}}/><span className="flex-1 text-slate-500">{item.name}</span><strong>{item.value}</strong></div>)}</div></CardContent></Card>
    </div>

    <Card><CardHeader><CardTitle>Compliance trend</CardTitle><span className="text-[11px] text-slate-400">Derived from pipeline rule results</span></CardHeader><CardContent className="h-[240px]"><ResponsiveContainer width="100%" height="100%"><LineChart data={data.complianceTrend} margin={{top:10,right:16,left:-18,bottom:0}}><CartesianGrid vertical={false} stroke="#e2e8f0"/><XAxis dataKey="date" tick={{fontSize:10}} axisLine={false} tickLine={false}/><YAxis domain={[0,100]} tick={{fontSize:10}} axisLine={false} tickLine={false}/><Tooltip formatter={(value)=>[`${value}%`,'Compliance']}/><Line type="monotone" dataKey="score" stroke="#059669" strokeWidth={2.5} dot={{r:3,fill:'#059669',strokeWidth:0}}/></LineChart></ResponsiveContainer></CardContent></Card>

    <Card><CardHeader><CardTitle>Recent Findings</CardTitle><button className="text-xs font-semibold text-blue-600">View all →</button></CardHeader><CardContent className="overflow-x-auto p-0"><table className="w-full min-w-[820px] text-left text-xs"><thead className="border-y border-slate-200 bg-slate-50 text-[10px] uppercase tracking-wide text-slate-500"><tr>{['Finding ID','Title','Domain','Severity','Status','Opened'].map(column=><th key={column} className="px-5 py-3 font-semibold">{column}</th>)}</tr></thead><tbody>{data.recentFindings.map(finding=><tr key={finding.id} className="border-b border-slate-100 last:border-0 hover:bg-slate-50"><td className="px-5 py-3 font-semibold text-blue-600">{finding.id}</td><td className="max-w-sm truncate px-5 py-3 font-medium">{finding.title}</td><td className="px-5 py-3 text-slate-500">{finding.domain}</td><td className="px-5 py-3"><Badge tone={severityTone[finding.severity]}>{finding.severity}</Badge></td><td className="px-5 py-3"><Badge tone={stateTone[finding.status]}>{finding.status.replace('_',' ')}</Badge></td><td className="px-5 py-3 text-slate-500">{new Intl.DateTimeFormat('en',{month:'short',day:'2-digit',year:'numeric'}).format(new Date(finding.openedAt))}</td></tr>)}</tbody></table></CardContent></Card>
  </section>;
}
