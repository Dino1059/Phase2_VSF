import { Zap } from 'lucide-react';

export function Brand({ collapsed = false }: { collapsed?: boolean }) {
  return (
    <div className="flex items-center gap-3">
      <span className="grid size-9 shrink-0 place-items-center rounded-xl bg-slate-950 text-[#04D3D4] border border-[#04D3D4]/40 shadow-xs">
        <Zap size={18} className="text-[#04D3D4] fill-[#FFC402]" />
      </span>
      {!collapsed && (
        <span className="leading-tight overflow-hidden transition-all duration-300">
          <strong className="block text-[17px] font-bold tracking-tight text-slate-900">
            datatrust
          </strong>
          <small className="block text-[9px] font-extrabold uppercase tracking-[.22em] text-[#04D3D4]">
            OS / AGENT
          </small>
        </span>
      )}
    </div>
  );
}
