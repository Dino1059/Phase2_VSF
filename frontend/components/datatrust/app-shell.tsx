'use client';
import { useState } from 'react';
import type { ComponentProps } from 'react';
import { Link as RouterLink, useLocation } from 'react-router-dom';
import { Bell, ChevronDown, Database, FileCheck2, FolderCheck, LayoutDashboard, Menu, Search, Settings, ShieldCheck, Workflow, X } from 'lucide-react';
import { Brand } from './brand';
import { cn } from '@/lib/utils';

const navigation=[
  {label:'Dashboard',href:'/dashboard',icon:LayoutDashboard},
  {label:'Findings',href:'/findings',icon:FileCheck2,badge:'12'},
  {label:'Data Quality',href:'/data-quality',icon:Database},
  {label:'Privacy & Protection',href:'/privacy',icon:ShieldCheck},
  {label:'Controls (ITGC)',href:'/controls',icon:FileCheck2},
  {label:'Evidence',href:'/evidence',icon:FolderCheck},
  {label:'Data Pipeline',href:'/pipeline-runs',icon:Workflow},
  {label:'Administration',href:'/administration',icon:Settings},
];
function Link({href,...props}:Omit<ComponentProps<typeof RouterLink>,'to'>&{href:string}){return <RouterLink to={href} {...props}/>}

export function AppShell({children}:{children:React.ReactNode}){
  const pathname=useLocation().pathname; const [open,setOpen]=useState(false);
  return <div className="min-h-screen bg-[#f3f7fb] text-slate-900">
    {open&&<button aria-label="Close navigation" className="fixed inset-0 z-30 bg-slate-950/40 lg:hidden" onClick={()=>setOpen(false)}/>}
    <aside className={cn('fixed inset-y-0 left-0 z-40 flex w-[232px] flex-col bg-[#0b2034] px-3 py-5 text-slate-300 shadow-xl transition-transform lg:translate-x-0',open?'translate-x-0':'-translate-x-full')}>
      <div className="px-2"><Brand/></div>
      <nav className="mt-7 flex flex-1 flex-col gap-1">{navigation.map(item=>{const active=pathname===item.href||pathname.startsWith(item.href+'/')||(item.href==='/findings'&&pathname.startsWith('/findings')); const Icon=item.icon; return <Link key={item.label} href={item.href} onClick={()=>setOpen(false)} className={cn('flex h-10 items-center gap-3 rounded-md px-3 text-[13px] font-medium transition',active?'bg-blue-600 text-white shadow-md shadow-blue-950/30':'hover:bg-white/8 hover:text-white')}><Icon size={16}/><span className="flex-1">{item.label}</span>{item.badge&&<span className="rounded-full bg-red-500 px-1.5 py-0.5 text-[10px] font-bold text-white">{item.badge}</span>}</Link>})}</nav>
      <div className="flex items-center gap-3 border-t border-white/10 px-2 pt-4"><span className="grid size-8 place-items-center rounded-md bg-cyan-400/20 text-[10px] font-bold text-cyan-300">GSM</span><span><strong className="block text-xs text-white">GSM Global</strong><small className="text-[10px] text-slate-500">v1.0.0</small></span></div>
    </aside>
    <div className="lg:pl-[232px]">
      <header className="sticky top-0 z-20 flex h-16 items-center gap-3 border-b border-slate-200 bg-white/95 px-4 backdrop-blur md:px-6">
        <button className="grid size-9 place-items-center rounded-md border border-slate-200 lg:hidden" onClick={()=>setOpen(v=>!v)}>{open?<X size={18}/>:<Menu size={18}/>}</button>
        <div className="relative hidden max-w-[430px] flex-1 sm:block"><Search className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" size={15}/><input className="h-9 w-full rounded-md border border-slate-200 bg-slate-50 pl-9 pr-3 text-xs outline-none focus:border-blue-400" placeholder="Search IDs, findings, controls..."/></div>
        <div className="ml-auto flex items-center gap-4"><button aria-label="Notifications" className="relative text-slate-500"><Bell size={18}/><span className="absolute -right-0.5 -top-0.5 size-1.5 rounded-full bg-blue-500"/></button><div className="hidden h-7 w-px bg-slate-200 sm:block"/><span className="grid size-8 place-items-center rounded-full bg-blue-600 text-xs font-semibold text-white">NT</span><span className="hidden leading-tight sm:block"><strong className="block text-xs">Nguyễn Thanh Tùng</strong><small className="text-[10px] text-slate-500">Compliance Analyst</small></span><ChevronDown className="hidden text-slate-400 sm:block" size={14}/></div>
      </header>
      <main className="min-h-[calc(100vh-4rem)] p-4 md:p-6">{children}</main>
    </div>
  </div>
}
