import * as React from 'react';
import { cn } from '@/lib/utils';
export function Input({className,...props}:React.InputHTMLAttributes<HTMLInputElement>){return <input className={cn('h-9 w-full rounded-md border border-slate-200 bg-white px-3 text-sm text-slate-700 outline-none placeholder:text-slate-400 focus:border-blue-500 focus:ring-2 focus:ring-blue-100',className)} {...props}/>}
