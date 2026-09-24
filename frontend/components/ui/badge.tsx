import * as React from 'react';
import { cn } from '@/lib/utils';

type Tone = 'blue' | 'red' | 'amber' | 'green' | 'slate' | 'xanhsm' | 'gold' | 'yellow';
type Props = React.HTMLAttributes<HTMLSpanElement> & { tone?: Tone };

export function Badge({ tone = 'slate', className, ...props }: Props) {
  const tones: Record<Tone, string> = {
    xanhsm: 'border-[#a2ded1] bg-[#e6f6f2] text-[#006e5b] font-semibold',
    green: 'border-emerald-200 bg-emerald-50 text-emerald-700',
    blue: 'border-teal-200 bg-teal-50 text-teal-700',
    red: 'border-red-200 bg-red-50 text-red-600',
    amber: 'border-amber-200 bg-amber-50 text-amber-700',
    gold: 'border-amber-300 bg-amber-50 text-amber-800 font-semibold',
    yellow: 'border-yellow-300 bg-yellow-50 text-yellow-800 font-semibold',
    slate: 'border-slate-200 bg-slate-50 text-slate-600',
  };
  return (
    <span
      className={cn('inline-flex items-center rounded-md border px-2 py-0.5 text-[11px] font-medium', tones[tone], className)}
      {...props}
    />
  );
}

export type Status = 'Pass' | 'Fail' | 'Open' | 'High' | 'Medium' | 'Low' | 'Done' | 'Pending';
const statusTone: Record<Status, Tone> = {
  Pass: 'green',
  Done: 'green',
  Fail: 'red',
  Open: 'red',
  High: 'red',
  Medium: 'amber',
  Pending: 'amber',
  Low: 'xanhsm',
};

export function StatusBadge({ status, className }: { status: Status; className?: string }) {
  return <Badge tone={statusTone[status]} className={className}>{status}</Badge>;
}

