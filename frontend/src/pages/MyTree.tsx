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
  const incomingTotal=useMemo(()=>data?.incoming_allocations?.reduce((sum,a)=>sum+a.amount,0)??0,[data]);
  if(loading)return <PublicShell><p>Loading giving tree...</p></PublicShell>;
  if(error)return <PublicShell><div className="card mx-auto max-w-xl p-8 text-center"><h1 className="text-3xl font-semibold">My Giving Tree</h1><p className="mt-4 text-slate-300">{error}</p><button onClick={load} className="mt-6 rounded bg-indigo-500 px-4 py-2 font-semibold">Retry</button></div></PublicShell>;
  if(!data)return <PublicShell><p>The Giving Tree could not be loaded. Please try again.</p></PublicShell>;
  if(data.status!=='ok')return <PublicShell><div className="card mx-auto max-w-xl p-8 text-center"><h1 className="text-3xl font-semibold">My Giving Tree</h1><h2 className="mt-3 text-xl">{data.participant.display_name}'s Giving Tree</h2><p className="mt-4 text-slate-300">{data.message||statusMessage(data.status)}</p><button onClick={load} className="mt-6 rounded bg-indigo-500 px-4 py-2 font-semibold">Retry</button></div></PublicShell>;
  const incoming=data.incoming_allocations||[];
  return <PublicShell>
    <div className="mx-auto flex max-w-5xl flex-col items-center gap-8 text-center print:text-black">
      <header className="w-full">
        <p className="text-sm uppercase tracking-[0.3em] text-indigo-300 print:text-slate-600">My Giving Tree</p>
        <h1 className="mt-2 text-4xl font-bold">{data.participant.display_name}'s Giving Tree</h1>
        <p className="mt-2 text-xl text-slate-300 print:text-slate-700">{data.quarter?.label}</p>
      </header>
      <section className="w-full rounded-3xl border-2 border-orange-400/70 bg-orange-500/15 p-6 text-center shadow-2xl shadow-orange-950/30 print:border-orange-500 print:bg-white">
        <div className="mx-auto max-w-3xl rounded-2xl bg-orange-400/15 px-5 py-4 print:bg-orange-50">
          <p className="text-sm font-bold uppercase tracking-[0.28em] text-orange-200 print:text-orange-700">Send your points</p>
          <h2 className="mt-2 text-2xl font-bold text-orange-50 print:text-black">Who {data.participant.display_name} needs to send points to</h2>
          <p className="mt-2 text-sm text-orange-100/90 print:text-slate-700">These are the people to give your 50 points to this quarter.</p>
        </div>
        <div className="mx-auto mt-7 flex w-full max-w-4xl flex-wrap justify-center gap-4">
          {data.allocations.map(a=><AllocationCard key={a.recipient_name} label="send to" name={a.recipient_name} amount={a.amount} tone="orange" />)}
        </div>
        <ul className="mx-auto mt-7 max-w-3xl divide-y divide-orange-300/25 rounded-2xl border border-orange-300/40 bg-black/20 text-left print:border-orange-300 print:bg-white">
          {data.allocations.map(a=><li key={a.recipient_name} className="flex items-center justify-between gap-4 p-4"><span>{a.recipient_name}</span><strong className="text-orange-100 print:text-black">{a.amount} points</strong></li>)}
          <li className="flex items-center justify-between gap-4 p-4 text-lg"><span>Total to send</span><strong className="text-orange-100 print:text-black">{total} points</strong></li>
        </ul>
      </section>
      <section className="w-full rounded-3xl border-2 border-green-400/70 bg-green-500/15 p-6 text-center shadow-2xl shadow-green-950/30 print:border-green-500 print:bg-white">
        <div className="mx-auto max-w-3xl rounded-2xl bg-green-400/15 px-5 py-4 print:bg-green-50">
          <p className="text-sm font-bold uppercase tracking-[0.28em] text-green-200 print:text-green-700">Receive points</p>
          <h2 className="mt-2 text-2xl font-bold text-green-50 print:text-black">Who {data.participant.display_name} should expect points from</h2>
          <p className="mt-2 text-sm text-green-100/90 print:text-slate-700">These are the people currently assigned to give points to you.</p>
        </div>
        <div className="mx-auto mt-7 flex w-full max-w-4xl flex-wrap justify-center gap-4">
          {incoming.length===0?<p className="w-full text-green-100/80">No incoming points are listed for this quarter yet.</p>:incoming.map(a=><AllocationCard key={a.sender_name} label="receive from" name={a.sender_name} amount={a.amount} tone="green" />)}
        </div>
        {incoming.length>0&&<ul className="mx-auto mt-7 max-w-3xl divide-y divide-green-300/25 rounded-2xl border border-green-300/40 bg-black/20 text-left print:border-green-300 print:bg-white">{incoming.map(a=><li key={a.sender_name} className="flex items-center justify-between gap-4 p-4"><span>{a.sender_name}</span><strong className="text-green-100 print:text-black">{a.amount} points</strong></li>)}<li className="flex items-center justify-between gap-4 p-4 text-lg"><span>Total expected in</span><strong className="text-green-100 print:text-black">{incomingTotal} points</strong></li></ul>}
      </section>
    </div>
  </PublicShell>;
}

function AllocationCard({label,name,amount,tone}:{label:string;name:string;amount:number;tone:'orange'|'green'}){const colour=tone==='orange'?'border-orange-200/50 bg-orange-950/50 text-orange-100':'border-green-200/50 bg-green-950/50 text-green-100';const number=tone==='orange'?'text-orange-200':'text-green-200';return <div className={`w-full max-w-[220px] rounded-2xl border p-5 text-center shadow-lg ${colour} print:border-slate-300 print:bg-white print:text-black`}><div className="text-xs font-bold uppercase tracking-[0.22em] opacity-80">{label}</div><div className="mt-2 text-xl font-bold">{name}</div><div className={`mt-3 text-4xl font-black ${number} print:text-black`}>{amount}</div><div className="text-sm opacity-80">points</div></div>}
function mapPublicError(message:string){
  if(/not found/i.test(message))return 'Giving Tree not found.';
  if(/not currently participating/i.test(message))return message;
  if(/no giving distribution/i.test(message))return 'No active quarterly tree is currently available.';
  if(/not have a giving tree/i.test(message))return 'This participant is not currently participating in the active quarterly tree.';
  return 'The Giving Tree could not be loaded. Please try again.';
}
function statusMessage(status:string){return status==='not_currently_participating'?'This participant is not currently participating in any quarterly tree.':status==='no_published_quarter'?'No active quarterly tree is currently available.':status==='not_included'?'This participant is not currently participating in the active quarterly tree.':'The Giving Tree could not be loaded. Please try again.'}
function PublicShell({children}:{children:React.ReactNode}){return <main className="min-h-screen bg-bg px-4 py-8 text-slate-100 print:bg-white print:text-black">{children}</main>}
