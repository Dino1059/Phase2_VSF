import * as React from 'react';
import { cn } from '@/lib/utils';
type Props = React.HTMLAttributes<HTMLSpanElement> & { tone?: 'blue'|'red'|'amber'|'green'|'slate' };
export function Badge({ tone='slate', className, ...props }: Props) { const tones={blue:'border-blue-200 bg-blue-50 text-blue-700',red:'border-red-200 bg-red-50 text-red-600',amber:'border-amber-200 bg-amber-50 text-amber-700',green:'border-emerald-200 bg-emerald-50 text-emerald-700',slate:'border-slate-200 bg-slate-50 text-slate-600'}; return <span className={cn('inline-flex items-center rounded-md border px-2 py-0.5 text-[11px] font-medium',tones[tone],className)} {...props}/>; }

export type Status = 'Pass' | 'Fail' | 'Open' | 'High' | 'Medium' | 'Low';
const statusTone: Record<Status, Props['tone']> = { Pass: 'green', Fail: 'red', Open: 'red', High: 'red', Medium: 'amber', Low: 'blue' };
export function StatusBadge({ status, className }: { status: Status; className?: string }) {
  return <Badge tone={statusTone[status]} className={className}>{status}</Badge>;
}
