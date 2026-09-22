import type { ComponentProps } from 'react';
import { Link as RouterLink } from 'react-router-dom';
import { ChevronRight, Filter, Plus, Search } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Card } from '@/components/ui/card';
import type { FindingListItem } from '@/lib/data/findings-types';
import { SeverityBadge, StateBadge } from './finding-badges';
function Link({href,...props}:Omit<ComponentProps<typeof RouterLink>,'to'>&{href:string}){return <RouterLink to={href} {...props}/>}

export function FindingsList({ findings }: { findings: FindingListItem[] }) {
  return <section className="page-enter mx-auto max-w-[1440px] space-y-5">
    <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between"><div><h1 className="text-2xl font-bold tracking-tight">Findings</h1><p className="mt-1 text-sm text-slate-500">Detected control violations requiring review and remediation.</p></div><Button size="sm"><Plus size={14}/> Create finding</Button></div>
    <Card className="overflow-hidden">
      <div className="flex flex-col gap-3 border-b border-slate-200 p-4 lg:flex-row lg:items-center"><div className="relative max-w-md flex-1"><Search className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" size={14}/><input className="h-9 w-full rounded-md border border-slate-200 bg-slate-50 pl-9 pr-3 text-xs outline-none focus:border-blue-400" placeholder="Search finding ID or title..."/></div><div className="flex flex-wrap gap-2"><button className="flex h-9 items-center gap-2 rounded-md border border-slate-200 bg-white px-3 text-xs text-slate-600"><Filter size={13}/> All statuses</button><button className="h-9 rounded-md border border-slate-200 bg-white px-3 text-xs text-slate-600">All severities</button><button className="h-9 rounded-md border border-slate-200 bg-white px-3 text-xs text-slate-600">All domains</button></div></div>
      <div className="overflow-x-auto"><table className="w-full min-w-[920px] text-left text-xs"><thead className="border-b border-slate-200 bg-slate-50 text-[10px] uppercase tracking-wide text-slate-500"><tr>{['Finding ID','Title','Control domain','Severity','Status','Created at',''].map((column,index)=><th key={`${column}-${index}`} className="px-5 py-3 font-semibold">{column}</th>)}</tr></thead><tbody>{findings.map(finding=><tr key={finding.id} className="group border-b border-slate-100 last:border-0 hover:bg-blue-50/40"><td className="px-5 py-3.5"><Link href={`/findings/${finding.id}`} className="font-semibold text-blue-600 hover:underline">{finding.id}</Link></td><td className="max-w-md px-5 py-3.5"><Link href={`/findings/${finding.id}`} className="block truncate font-medium text-slate-800">{finding.title}</Link></td><td className="px-5 py-3.5 text-slate-500">{finding.domain}</td><td className="px-5 py-3.5"><SeverityBadge value={finding.severity}/></td><td className="px-5 py-3.5"><StateBadge value={finding.status}/></td><td className="px-5 py-3.5 text-slate-500">{new Intl.DateTimeFormat('en',{month:'short',day:'2-digit',year:'numeric'}).format(new Date(finding.createdAt))}</td><td className="px-5 py-3.5"><Link href={`/findings/${finding.id}`} aria-label={`Open ${finding.id}`}><ChevronRight className="text-slate-300 group-hover:text-blue-600" size={16}/></Link></td></tr>)}</tbody></table></div>
      <div className="flex items-center justify-between border-t border-slate-200 px-5 py-3 text-xs text-slate-500"><span>Showing {findings.length} findings</span><div className="flex gap-1"><button className="grid size-8 place-items-center rounded border border-slate-200 bg-blue-600 text-white">1</button></div></div>
    </Card>
  </section>;
}
