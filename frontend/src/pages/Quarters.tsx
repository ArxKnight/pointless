import {useEffect,useState} from 'react';
import {api,post} from '../lib/api';
import {Plan,Quarter} from '../types/api';

export function Quarters(){
 const [quarters,setQuarters]=useState<Quarter[]>([]);
 const [preview,setPreview]=useState<any>(null);
 const [detail,setDetail]=useState<Plan[]>([]);
 const [error,setError]=useState('');
 const [busy,setBusy]=useState(false);
 const load=()=>api<Quarter[]>('/quarters').then(setQuarters);
 useEffect(()=>{void load()},[]);
 async function gen(commit=false){
  setBusy(true);setError('');
  try{
   const r=await post<any>('/quarters/generate',{preview:!commit});
   if(commit){setPreview(null);await load()} else setPreview(r);
  }catch(e:any){setError(e.message||'Could not generate quarter')}
  finally{setBusy(false)}
 }
 return <div className="space-y-6"><div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between"><h1 className="text-3xl font-semibold">Quarter Management</h1><div className="space-x-2"><button disabled={busy} onClick={()=>gen(false)} className="rounded border border-border px-4 py-2 disabled:opacity-60">Preview</button><button disabled={busy} onClick={()=>gen(true)} className="rounded bg-indigo-500 px-4 py-2 font-semibold disabled:bg-slate-700">{busy?'Working...':'Generate New Quarter'}</button></div></div>{error&&<div className="rounded-xl border border-red-500/30 bg-red-500/10 p-4 text-sm text-red-200"><strong>Quarter generation failed.</strong><p className="mt-1">{error}</p><p className="mt-2 text-slate-400">Make sure at least two active people exist. Active user accounts are automatically synced into the participant list before generation.</p></div>}{preview&&<div className="card p-4"><h2 className="font-semibold">Preview {preview.quarter.label}</h2><p className="text-sm text-slate-400">{preview.plan.length} planned sends. Click Generate New Quarter to commit.</p></div>}<div className="card overflow-hidden"><table className="w-full text-sm"><thead><tr className="bg-black/20 text-left text-slate-400"><th className="p-3">Quarter</th><th>Status</th><th>Actions</th></tr></thead><tbody>{quarters.map(q=><tr key={q.id} className="border-t border-border"><td className="p-3">{q.label}</td><td>{q.is_completed?'Completed':q.is_active?'Active':'Draft'}</td><td className="space-x-2"><button onClick={async()=>{const r=await api<any>(`/quarters/${q.id}`);setDetail(r.plan)}} className="rounded border border-border px-3 py-1">View</button><button onClick={async()=>{await post(`/quarters/${q.id}/complete`);load()}} className="rounded border border-border px-3 py-1">Complete</button></td></tr>)}</tbody></table></div>{detail.length>0&&<div className="card p-4"><h2 className="font-semibold">Distribution Matrix</h2><div className="mt-3 grid gap-2 md:grid-cols-2">{detail.map(p=><div className="rounded bg-black/20 p-2" key={p.id}>{p.from_name} → {p.to_name}: <span className="font-mono">{p.amount}</span></div>)}</div></div>}</div>;
}
