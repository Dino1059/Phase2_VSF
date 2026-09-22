import { ArrowRight } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { StatusBadge, type Status } from '@/components/ui/badge';

const statuses: Status[] = ['Pass', 'Fail', 'Open', 'High', 'Medium', 'Low'];

export function ShellPage({ title, description }: { title: string; description: string }) {
  return (
    <section className="page-enter mx-auto max-w-[1440px] space-y-5">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <p className="mb-1 text-[11px] font-semibold uppercase tracking-[.14em] text-blue-600">DataTrust OS</p>
          <h1 className="text-2xl font-bold tracking-tight text-slate-900">{title}</h1>
          <p className="mt-1 max-w-2xl text-sm text-slate-500">{description}</p>
        </div>
        <Button size="sm">Primary action <ArrowRight size={14} /></Button>
      </div>
      <Card>
        <CardHeader><CardTitle>Application shell preview</CardTitle></CardHeader>
        <CardContent className="space-y-6">
          <div className="flex flex-wrap gap-2">{statuses.map(status => <StatusBadge key={status} status={status} />)}</div>
          <div className="grid gap-4 md:grid-cols-3">
            {[1, 2, 3].map(item => <div key={item} className="h-28 rounded-lg border border-dashed border-slate-200 bg-slate-50/70" />)}
          </div>
          <p className="text-xs text-slate-400">Page content and business workflows will be implemented in the next milestone.</p>
        </CardContent>
      </Card>
    </section>
  );
}
