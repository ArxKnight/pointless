import {useEffect,useState} from 'react';
import {useParams,Link} from 'react-router-dom';
import {api,post} from '../lib/api';

type InviteInfo={invitee_name:string;invitee_email?:string|null;expires_at:string;status:string};

export function AdminInvite(){
  const {token}=useParams();
  const [info,setInfo]=useState<InviteInfo|null>(null);
  const [error,setError]=useState('');
  const [message,setMessage]=useState('');
  const [form,setForm]=useState({username:'',email:'',password:'',password_confirm:''});
  useEffect(()=>{document.title='Accept administrator invitation'; if(!token)return; api<InviteInfo>(`/admin-invitations/${token}`).then(i=>{setInfo(i);setForm(f=>({...f,username:i.invitee_name,email:i.invitee_email||''}))}).catch(e=>setError(e.message||'Invalid invitation link'))},[token]);
  async function submit(e:React.FormEvent){
    e.preventDefault(); setError(''); setMessage('');
    const username=form.username.trim();
    try{await post(`/admin-invitations/${token}/accept`,{...form,username,display_name:username,email:form.email.trim()}); setMessage('Administrator account created. You can now log in.');}
    catch(e:any){setError(e.message||'Unable to accept invitation')}
  }
  return <main className="min-h-screen bg-bg px-4 py-10 text-slate-100"><div className="mx-auto max-w-lg card p-8">
    <h1 className="text-3xl font-semibold">Administrator invitation</h1>
    {error&&<p className="mt-4 rounded border border-red-400/40 bg-red-500/10 p-3 text-red-200">{error}</p>}
    {message&&<div className="mt-4 rounded border border-green-400/40 bg-green-500/10 p-3 text-green-200"><p>{message}</p><Link className="mt-2 inline-block underline" to="/login">Go to login</Link></div>}
    {!info&&!error&&<p className="mt-4 text-slate-300">Checking invitation...</p>}
    {info&&!message&&<form onSubmit={submit} className="mt-6 space-y-4">
      <p className="text-sm text-slate-400">Create an administrator account. This invitation expires {new Date(info.expires_at).toLocaleString()}.</p>
      <label className="block text-sm">Username<input required value={form.username} onChange={e=>setForm({...form,username:e.target.value})} className="mt-1 w-full rounded bg-bg p-3"/></label>
      <label className="block text-sm">Email<input required type="email" value={form.email} onChange={e=>setForm({...form,email:e.target.value})} className="mt-1 w-full rounded bg-bg p-3"/></label>
      <label className="block text-sm">Password<input required minLength={8} type="password" value={form.password} onChange={e=>setForm({...form,password:e.target.value})} className="mt-1 w-full rounded bg-bg p-3"/></label>
      <label className="block text-sm">Confirm password<input required minLength={8} type="password" value={form.password_confirm} onChange={e=>setForm({...form,password_confirm:e.target.value})} className="mt-1 w-full rounded bg-bg p-3"/></label>
      <button className="w-full rounded bg-indigo-500 py-3 font-semibold">Create administrator account</button>
    </form>}
  </div></main>
}
