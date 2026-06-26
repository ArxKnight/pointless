import {useCallback,useEffect,useMemo,useState} from 'react';
import {useParams} from 'react-router-dom';
import {api} from '../lib/api';
import {PublicTree} from '../types/api';

export function MyTree(){
  const {slug}=useParams();
  const [data,setData]=useState<PublicTree|null>(null);
  const [error,setError]=useState('');
  const [loading,setLoading]=useState(true);
  const load=useCallback(()=>{setLoading(true);setError('');api<PublicTree>(`/public/tree/${slug}`).then(setData).catch(e=>setError(mapPublicError(e.message))).finally(()=>setLoading(false))},[slug]);
  useEffect(()=>{
    document.title='My Giving Tree';
    const meta=document.createElement('meta');
    meta.name='robots'; meta.content='noindex,nofollow'; document.head.appendChild(meta);
    load();
    return()=>{document.head.removeChild(meta)};
  },[load]);
  const total=useMemo(()=>data?.allocations.reduce((sum,a)=>sum+a.amount,0)??0,[data]);
  if(loading)return <PublicShell><p>Loading giving tree...</p></PublicShell>;
  if(error)return <PublicShell><div className="card mx-auto max-w-xl p-8 text-center"><h1 className="text-3xl font-semibold">My Giving Tree</h1><p className="mt-4 text-slate-300">{error}</p><button onClick={load} className="mt-6 rounded bg-indigo-500 px-4 py-2 font-semibold">Retry</button></div></PublicShell>;
  if(!data)return <PublicShell><p>The Giving Tree could not be loaded. Please try again.</p></PublicShell>;
  if(data.status!=='ok')return <PublicShell><div className="card mx-auto max-w-xl p-8 text-center"><h1 className="text-3xl font-semibold">My Giving Tree</h1><h2 className="mt-3 text-xl">{data.participant.display_name}'s Giving Tree</h2><p className="mt-4 text-slate-300">{data.message||statusMessage(data.status)}</p><button onClick={load} className="mt-6 rounded bg-indigo-500 px-4 py-2 font-semibold">Retry</button></div></PublicShell>;
  return <PublicShell>
    <div className="mx-auto max-w-4xl space-y-6 print:text-black">
      <header className="text-center">
        <p className="text-sm uppercase tracking-[0.3em] text-indigo-300 print:text-slate-600">My Giving Tree</p>
        <h1 className="mt-2 text-4xl font-bold">{data.participant.display_name}'s Giving Tree</h1>
        <p className="mt-2 text-xl text-slate-300 print:text-slate-700">{data.quarter?.label}</p>
      </header>
      <section className="card p-6 print:border print:border-slate-300 print:bg-white">
        <p className="text-lg"><strong>{data.participant.display_name}</strong> has 50 points to give:</p>
        <div className="mt-6 overflow-x-auto rounded-2xl bg-black/20 p-6 print:bg-white">
          <div className="flex min-w-[520px] flex-col items-center gap-6">
            <div className="rounded-full bg-indigo-500 px-8 py-4 text-xl font-semibold text-white shadow-lg print:border print:border-slate-400 print:bg-white print:text-black">{data.participant.display_name}</div>
            <div className="flex h-10 flex-col items-center"><span className="text-slate-400">↓</span><div className="h-8 w-px bg-slate-500" /></div>
            <div className="grid w-full gap-4 sm:grid-cols-2 lg:grid-cols-4">
              {data.allocations.map(a=><div key={a.recipient_name} className="rounded-xl border border-border bg-bg p-4 text-center print:border-slate-300 print:bg-white">
                <div className="text-xs uppercase text-slate-400">gives to</div>
                <div className="font-semibold">{a.recipient_name}</div>
                <div className="mt-1 text-2xl font-mono text-indigo-300 print:text-black">{a.amount}</div>
                <div className="text-xs text-slate-400 print:text-slate-600">points</div>
              </div>)}
            </div>
          </div>
        </div>
        <h2 className="sr-only">Text list of point allocations</h2>
        <ul className="mt-6 divide-y divide-border rounded-xl border border-border print:border-slate-300">
          {data.allocations.map(a=><li key={a.recipient_name} className="flex items-center justify-between p-4"><span>{a.recipient_name}</span><strong>{a.amount} points</strong></li>)}
          <li className="flex items-center justify-between p-4 text-lg"><span>Total allocated</span><strong>{total} points</strong></li>
        </ul>
      </section>
    </div>
  </PublicShell>;
}

function mapPublicError(message:string){
  if(/not found/i.test(message))return 'Giving Tree not found.';
  if(/not currently participating/i.test(message))return message;
  if(/no giving distribution/i.test(message))return 'No active quarterly tree is currently available.';
  if(/not have a giving tree/i.test(message))return 'This participant is not currently participating in the active quarterly tree.';
  return 'The Giving Tree could not be loaded. Please try again.';
}
function statusMessage(status:string){return status==='not_currently_participating'?'This participant is not currently participating in any quarterly tree.':status==='no_published_quarter'?'No active quarterly tree is currently available.':status==='not_included'?'This participant is not currently participating in the active quarterly tree.':'The Giving Tree could not be loaded. Please try again.'}
function PublicShell({children}:{children:React.ReactNode}){return <main className="min-h-screen bg-bg px-4 py-8 text-slate-100 print:bg-white print:text-black">{children}</main>}
