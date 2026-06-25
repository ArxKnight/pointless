import {useEffect,useState} from 'react';
import {api,post} from '../lib/api';
import {Plan,Quarter} from '../types/api';

export function Quarters(){
 const [quarters,setQuarters]=useState<Quarter[]>([]);
 const [detail,setDetail]=useState<Plan[]>([]);
 const load=()=>api<Quarter[]>('/quarters').then(setQuarters);
 useEffect(()=>{void load()},[]);
 return <div className="space-y-6">
  <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
   <div>
    <h1 className="text-3xl font-semibold">Quarters</h1>
    <p className="text-slate-400 text-sm mt-1">Quarters are generated automatically at the start of each calendar quarter.</p>
   </div>
  </div>
  <div className="card overflow-hidden">
   <table className="w-full text-sm">
    <thead><tr className="bg-black/20 text-left text-slate-400"><th className="p-3">Quarter</th><th>Status</th><th>Actions</th></tr></thead>
    <tbody>{quarters.map(q=><tr key={q.id} className="border-t border-border">
     <td className="p-3">{q.label}</td>
     <td>{q.is_completed?'Completed':q.is_active?'Active':'Draft'}</td>
     <td className="space-x-2">
      <button onClick={async()=>{const r=await api<any>(`/quarters/${q.id}`);setDetail(r.plan)}} className="rounded border border-border px-3 py-1">View</button>
      {q.is_active&&!q.is_completed&&<button onClick={async()=>{await post(`/quarters/${q.id}/complete`);void load()}} className="rounded border border-border px-3 py-1">Complete</button>}
     </td>
    </tr>)}</tbody>
   </table>
  </div>
  {detail.length>0&&<div className="card p-4">
   <h2 className="font-semibold mb-3">Distribution</h2>
   <div className="space-y-2">{detail.map(p=><div key={p.id} className="rounded bg-black/20 p-3 flex items-center justify-between"><span className="text-sm"><span className="font-medium">{p.from_name}</span><span className="text-slate-400"> → </span><span className="font-medium">{p.to_name}</span></span><span className="font-mono text-indigo-300">{p.amount} pts <span className={p.acknowledged?'text-green-400':'text-yellow-400'}>{p.acknowledged?'✓':'pending'}</span></span></div>)}
   </div>
  </div>}
 </div>
}
