import * as React from 'react';
import { cn } from '@/lib/utils';

type Props = React.ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: 'default' | 'xanhsm' | 'outline' | 'ghost' | 'danger';
  size?: 'default' | 'sm' | 'lg' | 'icon';
};

export function Button({ className, variant = 'default', size = 'default', ...props }: Props) {
  return (
    <button
      className={cn(
        'inline-flex items-center justify-center gap-2 rounded-lg font-medium transition-all disabled:pointer-events-none disabled:opacity-50 cursor-pointer',
        variant === 'default' && 'bg-slate-900 text-white hover:bg-slate-800 shadow-sm active:scale-[0.99]',
        variant === 'xanhsm' && 'bg-[#04D3D4] text-slate-950 font-bold hover:bg-[#03b8b9] shadow-sm active:scale-[0.99]',
        variant === 'outline' && 'border border-slate-200 bg-white text-slate-700 hover:bg-slate-50 shadow-xs',
        variant === 'ghost' && 'text-slate-600 hover:bg-slate-100',
        variant === 'danger' && 'border border-red-200 bg-red-50 text-red-600 hover:bg-red-100',
        size === 'default' && 'h-9 px-4 text-sm',
        size === 'sm' && 'h-8 px-3 text-xs',
        size === 'lg' && 'h-11 px-5 text-sm',
        size === 'icon' && 'size-9',
        className
      )}
      {...props}
    />
  );
}

