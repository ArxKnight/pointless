import {useEffect,useMemo,useState} from 'react';
import {User,UserAdmin} from '../types/api';
import {api,del,patch,post} from '../lib/api';
import {SuccessBanner} from '../components/SuccessBanner';

type Invite={id:number;invitee_name:string;invitee_email?:string|null;created_by_name?:string|null;created_at:string;expires_at:string;status:string;invitation_url?:string;token?:string;expires_label?:string};

const expiryOptions=[
  {label:'24 hours',hours:24},
  {label:'48 hours',hours:48},
  {label:'1 week',hours:168},
  {label:'1 month',hours:720},
  {label:'1 year',hours:8760},
  {label:'Never',hours:0},
];

export function Settings({user}:{user:User}){
  return <div className="space-y-6">
    <div>
      <h1 className="text-3xl font-semibold">Settings</h1>
      <p className="mt-1 text-slate-400">Administrator accounts and invitation links.</p>
    </div>
    <Admins current={user}/>
  </div>;
}

function Admins({current}:{current:User}){
 const[users,setUsers]=useState<UserAdmin[]>([]);const[invites,setInvites]=useState<Invite[]>([]);const[msg,setMsg]=useState('');const[success,setSuccess]=useState('');const[created,setCreated]=useState<Invite|null>(null);const[invite,setInvite]=useState({invitee_name:'',invitee_email:'',expires_in_hours:168});const[edit,setEdit]=useState<Record<number,Partial<UserAdmin>&{password?:string}>>({});
 const isProtected=current.is_super_admin===true;
 const load=async()=>{setUsers(await api<UserAdmin[]>('/users')); if(isProtected)setInvites(await api<Invite[]>('/admin-invitations'))};useEffect(()=>{void load()},[]);
 const firstAdminId=useMemo(()=>users.filter(u=>u.is_admin).sort((a,b)=>a.id-b.id)[0]?.id,[users]);
 async function save(u:UserAdmin){setMsg('');try{const e=edit[u.id]||{};const updated=await patch<UserAdmin>(`/users/${u.id}`,{username:e.username,display_name:e.display_name,email:e.email,is_admin:true,password:e.password});setEdit(prev=>{const n={...prev};delete n[u.id];return n});setSuccess(`${updated.display_name} has been saved successfully.`);await load()}catch(e:any){setMsg(e.message)}}
 async function deactivate(u:UserAdmin){if(!confirm(`${u.is_active?'Deactivate':'Reactivate'} ${u.display_name}?`))return;setMsg('');try{const updated=await patch<UserAdmin>(`/users/${u.id}`,{is_active:!u.is_active});setSuccess(`${updated.display_name} has been ${updated.is_active?'enabled':'disabled'} successfully.`);await load()}catch(e:any){setMsg(e.message)}}
 async function remove(u:UserAdmin){if(!confirm(`Delete ${u.display_name}? Historical records will be preserved and the account will be deactivated.`))return;setMsg('');try{await del(`/users/${u.id}`);setSuccess(`${u.display_name} has been removed successfully.`);await load()}catch(e:any){setMsg(e.message)}}
 async function createInvite(e:React.FormEvent){e.preventDefault();setMsg('');setCreated(null);try{const r=await post<Invite>('/admin-invitations',invite);setCreated(r);setSuccess(`Invitation for ${r.invitee_name} has been created successfully.`);setInvite({invitee_name:'',invitee_email:'',expires_in_hours:168});await load()}catch(e:any){setMsg(e.message)}}
 async function revoke(i:Invite){if(!confirm(`Revoke invitation for ${i.invitee_name}?`))return;setMsg('');try{await del(`/admin-invitations/${i.id}`);setSuccess(`Invitation for ${i.invitee_name} has been revoked successfully.`);await load()}catch(e:any){setMsg(e.message)}}
 const field=(u:UserAdmin,k:keyof UserAdmin)=>String((edit[u.id]?.[k]??u[k]??''));
 return <div className="space-y-6"><SuccessBanner message={success} onClose={()=>setSuccess('')}/><div className="card p-6"><h2 className="text-lg font-semibold">Administrators</h2><p className="mt-1 text-sm text-slate-400">There is one visible role: Admin. The installer-created Admin is protected and cannot be demoted by later invited Admins.</p>{msg&&<p className="mt-3 text-red-300">{msg}</p>}<div className="mt-4 overflow-auto"><table className="w-full text-sm"><thead className="text-left text-slate-400"><tr><th className="p-2">Name</th><th>Username</th><th>Email</th><th>Role</th><th>Status</th><th>Last login</th><th/></tr></thead><tbody>{users.map(u=><tr key={u.id} className="border-t border-border align-top"><td className="p-2"><input disabled={!isProtected} value={field(u,'display_name')} onChange={e=>setEdit({...edit,[u.id]:{...edit[u.id],display_name:e.target.value}})} className="w-36 rounded bg-bg p-2"/></td><td><input disabled={!isProtected} value={field(u,'username')} onChange={e=>setEdit({...edit,[u.id]:{...edit[u.id],username:e.target.value}})} className="w-32 rounded bg-bg p-2"/></td><td><input disabled={!isProtected} value={field(u,'email')} onChange={e=>setEdit({...edit,[u.id]:{...edit[u.id],email:e.target.value}})} className="w-48 rounded bg-bg p-2"/></td><td><span className="rounded-full bg-indigo-500/20 px-2 py-1 text-indigo-200">Admin</span>{u.id===firstAdminId&&<span className="ml-2 rounded-full bg-amber-500/20 px-2 py-1 text-amber-200">Protected installer admin</span>}</td><td>{u.is_active?'Active':'Inactive'}</td><td>{u.last_login_at?new Date(u.last_login_at).toLocaleString():'—'}</td><td className="space-x-2 whitespace-nowrap">{isProtected&&<><button onClick={()=>save(u)} className="rounded bg-indigo-500 px-3 py-1 text-xs">Save</button><button onClick={()=>deactivate(u)} className="rounded border border-border px-3 py-1 text-xs">{u.is_active?'Deactivate':'Reactivate'}</button><button onClick={()=>remove(u)} className="rounded border border-red-400 px-3 py-1 text-xs text-red-200">Delete</button></>}</td></tr>)}</tbody></table></div></div>
 {isProtected&&<div className="card p-6"><h2 className="text-lg font-semibold">Invitation links</h2><form onSubmit={createInvite} className="mt-4 grid gap-3 md:grid-cols-[1fr_1fr_180px_auto]"><input required value={invite.invitee_name} onChange={e=>setInvite({...invite,invitee_name:e.target.value})} placeholder="Invitee name" className="rounded bg-bg p-3"/><input type="email" value={invite.invitee_email} onChange={e=>setInvite({...invite,invitee_email:e.target.value})} placeholder="Optional email" className="rounded bg-bg p-3"/><select value={invite.expires_in_hours} onChange={e=>setInvite({...invite,expires_in_hours:Number(e.target.value)})} className="rounded bg-bg p-3" aria-label="Invite link expiry"><option value="" disabled>Invite link expires</option>{expiryOptions.map(o=><option key={o.hours} value={o.hours}>Expires in {o.label}</option>)}</select><button className="rounded bg-teal-500 px-4 font-semibold">Create invite</button></form><p className="mt-2 text-xs text-slate-400">Choose when the invite link expires: 24 hours, 48 hours, a week, a month, a year, or never.</p>{created&&<p className="mt-4 rounded bg-green-500/10 p-3 text-green-200">Invitation created. Copy now: <code>{location.origin}{created.invitation_url}</code> <button className="ml-2 underline" onClick={()=>navigator.clipboard?.writeText(`${location.origin}${created.invitation_url}`)}>Copy</button></p>}<table className="mt-4 w-full text-sm"><thead className="text-left text-slate-400"><tr><th className="p-2">Name</th><th>Email</th><th>Created by</th><th>Invite expires</th><th>Status</th><th/></tr></thead><tbody>{invites.map(i=><tr key={i.id} className="border-t border-border"><td className="p-2">{i.invitee_name}</td><td>{i.invitee_email||'—'}</td><td>{i.created_by_name||'—'}</td><td>{i.expires_label||formatExpiry(i.expires_at)}</td><td>{i.status}</td><td>{i.status==='pending'&&<button onClick={()=>revoke(i)} className="rounded border border-red-400 px-3 py-1 text-xs text-red-200">Revoke</button>}</td></tr>)}</tbody></table></div>}
 </div>
}

function formatExpiry(value:string){const d=new Date(value);return d.getFullYear()>new Date().getFullYear()+50?'Never':d.toLocaleString()}
