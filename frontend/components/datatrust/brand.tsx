import { Zap } from 'lucide-react';

export function Brand() {
  return (
    <div className="flex items-center gap-3">
      <span className="grid size-9 place-items-center rounded-xl bg-[#0f2824] text-[#00D09C] shadow-sm">
        <Zap size={18} className="fill-[#00D09C]" />
      </span>
      <span className="leading-tight">
        <strong className="block text-[17px] font-bold tracking-tight text-slate-900">datatrust</strong>
        <small className="block text-[9px] font-bold uppercase tracking-[.2em] text-[#008B74]">OS / AGENT</small>
      </span>
    </div>
  );
}

