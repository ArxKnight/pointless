import {useEffect} from 'react';

type SuccessBannerProps={message:string;onClose:()=>void};

export function SuccessBanner({message,onClose}:SuccessBannerProps){
  useEffect(()=>{if(!message)return;const id=window.setTimeout(onClose,4500);return()=>window.clearTimeout(id)},[message,onClose]);
  if(!message)return null;
  return <div className="fixed inset-x-0 top-4 z-[70] flex justify-center px-4"><div role="status" aria-live="polite" className="flex w-full max-w-3xl items-start justify-between gap-4 rounded-xl border border-green-400/40 bg-green-500 px-5 py-4 text-sm font-semibold text-white shadow-2xl shadow-black/40"><span>{message}</span><button type="button" onClick={onClose} className="rounded px-2 text-lg leading-none text-white/90 hover:bg-white/15" aria-label="Dismiss success message">×</button></div></div>;
}
