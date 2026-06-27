import {useEffect,useMemo,useState} from 'react';
import {api} from '../lib/api';
import {AuditLogEntry,UserAdmin} from '../types/api';

function niceEvent(event:string){return event.replace(/_/g,' ').replace(/\b\w/g,(c:string)=>c.toUpperCase())}
function formatDate(value:string){try{return new Date(value).toLocaleString()}catch{return value}}
function parseMetadata(value?:string|null){if(!value)return null;try{return JSON.parse(value)}catch{return value}}

export function AuditLog(){
  const [entries,setEntries]=useState<AuditLogEntry[]>([]);
  const [admins,setAdmins]=useState<UserAdmin[]>([]);
  const [error,setError]=useState('');
  const [filter,setFilter]=useState('');
  const [actorUserId,setActorUserId]=useState('');
  useEffect(()=>{api<UserAdmin[]>('/users').then(rows=>setAdmins(rows.filter(u=>u.is_admin))).catch(()=>setAdmins([]))},[]);
  useEffect(()=>{const params=new URLSearchParams({limit:'500'});if(actorUserId)params.set('actor_user_id',actorUserId);api<AuditLogEntry[]>(`/audit-logs?${params.toString()}`).then(setEntries).catch(e=>setError(e.message))},[actorUserId]);
  const filtered=useMemo(()=>{const q=filter.trim().toLowerCase();if(!q)return entries;return entries.filter(e=>[e.event_type,e.actor_username,e.target_type,e.target_name,e.message,e.ip_address].filter(Boolean).join(' ').toLowerCase().includes(q))},[entries,filter]);
  if(error)return <div className="card p-6 text-red-400">{error}</div>;
  return <div className="space-y-6">
    <div className="flex flex-wrap items-start justify-between gap-4">
      <div><h1 className="text-3xl font-semibold tracking-tight">Audit Log</h1><p className="mt-1 text-slate-400">Admin activity, settings changes, generation events, invites, and public link views.</p></div>
      <div className="card px-4 py-3 text-sm text-slate-300"><b>{filtered.length}</b> events</div>
    </div>
    <div className="card grid gap-3 p-4 md:grid-cols-[260px_1fr]"><label className="text-sm text-slate-300">Admin user<select value={actorUserId} onChange={e=>setActorUserId(e.target.value)} className="mt-2 w-full rounded-lg border border-border bg-bg px-3 py-2 text-sm outline-none focus:border-indigo-400"><option value="">All admins</option>{admins.map(u=><option key={u.id} value={u.id}>{u.username}</option>)}</select></label><label className="text-sm text-slate-300">Search<input value={filter} onChange={e=>setFilter(e.target.value)} placeholder="Search event, target, message, IP…" className="mt-2 w-full rounded-lg border border-border bg-bg px-3 py-2 text-sm outline-none focus:border-indigo-400"/></label></div>
    <div className="card overflow-hidden">
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead><tr className="border-b border-border text-left text-slate-400"><th className="px-6 py-3">When</th><th>Event</th><th>Actor</th><th>Target</th><th>Message</th><th className="pr-6">Details</th></tr></thead>
          <tbody>{filtered.map(e=>{const meta=parseMetadata(e.metadata_json);return <tr key={e.id} className="border-b border-border/60 align-top last:border-0"><td className="whitespace-nowrap px-6 py-4 text-slate-300">{formatDate(e.created_at)}</td><td className="py-4"><span className="rounded-full bg-indigo-500/15 px-2 py-1 text-xs text-indigo-200">{niceEvent(e.event_type)}</span></td><td className="py-4 text-slate-300">{e.actor_username||'System/public'}</td><td className="py-4 text-slate-300"><div>{e.target_name||'—'}</div>{e.target_type&&<div className="text-xs text-slate-500">{e.target_type}{e.target_id?` #${e.target_id}`:''}</div>}</td><td className="max-w-md py-4 text-slate-200">{e.message}</td><td className="max-w-sm pr-6 py-4 text-xs text-slate-400">{e.ip_address&&<div>IP: {e.ip_address}</div>}{meta&&<pre className="mt-1 max-h-24 overflow-auto rounded bg-black/20 p-2">{typeof meta==='string'?meta:JSON.stringify(meta,null,2)}</pre>}</td></tr>})}</tbody>
        </table>
      </div>
      {!filtered.length&&<div className="p-6 text-slate-400">No audit events found.</div>}
    </div>
  </div>;
}
