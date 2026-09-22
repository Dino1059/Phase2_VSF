import * as React from 'react';
import { cn } from '@/lib/utils';

type Props = React.ButtonHTMLAttributes<HTMLButtonElement> & { variant?: 'default' | 'outline' | 'ghost'; size?: 'default' | 'sm' | 'icon' };
export function Button({ className, variant = 'default', size = 'default', ...props }: Props) {
  return <button className={cn('inline-flex items-center justify-center gap-2 rounded-md font-medium transition-colors disabled:pointer-events-none disabled:opacity-50', variant === 'default' && 'bg-blue-600 text-white hover:bg-blue-700', variant === 'outline' && 'border border-slate-200 bg-white text-slate-700 hover:bg-slate-50', variant === 'ghost' && 'text-slate-600 hover:bg-slate-100', size === 'default' && 'h-9 px-4 text-sm', size === 'sm' && 'h-8 px-3 text-xs', size === 'icon' && 'size-9', className)} {...props} />;
}
