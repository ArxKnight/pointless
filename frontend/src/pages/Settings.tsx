import {useEffect,useState} from 'react';import {User,UserAdmin,Member} from '../types/api';import {api,patch,post} from '../lib/api';

export function Settings({user}:{user:User}){
  const [regen,setRegen]=useState<'idle'|'loading'|'done'|'error'>('idle');
  const [regenMsg,setRegenMsg]=useState('');
  const [users,setUsers]=useState<UserAdmin[]>([]);
  const [members,setMembers]=useState<Member[]>([]);
  const [memberForm,setMemberForm]=useState({display_name:'',email:'',username:'',password:''});
  const [roleLoading,setRoleLoading]=useState<number|null>(null);
  const [memberLoading,setMemberLoading]=useState<number|null>(null);

  const loadUsers=()=>api<UserAdmin[]>('/users').then(setUsers).catch(()=>{});
  const loadMembers=()=>api<Member[]>('/members').then(setMembers).catch(()=>{});

  useEffect(()=>{if(user.is_admin){void loadUsers();void loadMembers()}},[user.is_admin]);

  async function handleSetRole(u:UserAdmin,makeAdmin:boolean){
    setRoleLoading(u.id);
    try{const updated=await patch<UserAdmin>(`/users/${u.id}/role`,{is_admin:makeAdmin});setUsers(prev=>prev.map(x=>x.id===updated.id?updated:x));}
    catch{}
    setRoleLoading(null);
  }

  async function handleToggleMember(m:Member){
    setMemberLoading(m.id);
    try{const updated=await patch<Member>(`/members/${m.id}`,{active:!m.active});setMembers(prev=>prev.map(x=>x.id===updated.id?updated:x));}
    catch{}
    setMemberLoading(null);
  }

  async function handleAddMember(e:React.FormEvent){
    e.preventDefault();
    await post('/members',memberForm);
    setMemberForm({display_name:'',email:'',username:'',password:''});
    void loadMembers();void loadUsers();
  }

  async function handleRegenerate(){
    if(!confirm('This will delete and regenerate all giving assignments for the current quarter. Any points already marked as sent will block this action. Continue?'))return;
    setRegen('loading');
    try{const res=await post<{quarter:{label:string};plans:unknown[]}>('/quarters/regenerate');setRegenMsg(`Done — ${res.quarter.label} regenerated with ${(res.plans as unknown[]).length} new assignments.`);setRegen('done');}
    catch(e:any){setRegenMsg(e.message||'Regeneration failed.');setRegen('error');}
  }

  return(
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-semibold">Settings</h1>
        <p className="mt-1 text-slate-400">Account and system settings.</p>
      </div>

      {/* Account info */}
      <div className="card p-6 space-y-3">
        <h2 className="text-lg font-semibold">Your Account</h2>
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 text-sm">
          <div><p className="text-slate-400">Display name</p><p className="mt-0.5 font-medium">{user.display_name}</p></div>
          <div><p className="text-slate-400">Username</p><p className="mt-0.5 font-medium">{user.username}</p></div>
          <div><p className="text-slate-400">Email</p><p className="mt-0.5 font-medium">{user.email}</p></div>
          <div><p className="text-slate-400">Role</p><p className="mt-0.5 font-medium">{user.is_admin?'🔑 Administrator':'Member'}</p></div>
        </div>
      </div>

      {/* Admin-only sections */}
      {user.is_admin&&(<>

        {/* User roles */}
        <div className="card p-6 space-y-4 border border-indigo-500/20">
          <div>
            <h2 className="text-lg font-semibold">User Roles</h2>
            <p className="mt-1 text-sm text-slate-400">Promote or demote users between Admin and User. You cannot change your own role.</p>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-black/20 text-left text-slate-400">
                <tr><th className="p-3">Name</th><th>Username</th><th>Email</th><th>Role</th><th></th></tr>
              </thead>
              <tbody>
                {users.map(u=>(
                  <tr className="border-t border-border" key={u.id}>
                    <td className="p-3">{u.display_name}</td>
                    <td className="text-slate-300">{u.username}</td>
                    <td className="text-slate-300">{u.email}</td>
                    <td>
                      <span className={`inline-block rounded-full px-2 py-0.5 text-xs font-medium ${u.is_admin?'bg-indigo-500/20 text-indigo-300':'bg-slate-700 text-slate-300'}`}>
                        {u.is_admin?'Admin':'User'}
                      </span>
                    </td>
                    <td className="py-2 pr-3 text-right">
                      {u.id!==user.id&&(
                        <button
                          onClick={()=>handleSetRole(u,!u.is_admin)}
                          disabled={roleLoading===u.id}
                          className="rounded border border-border px-3 py-1 text-xs hover:bg-white/5 disabled:opacity-50"
                        >
                          {roleLoading===u.id?'Saving…':u.is_admin?'Make User':'Make Admin'}
                        </button>
                      )}
                    </td>
                  </tr>
                ))}
                {users.length===0&&<tr><td colSpan={5} className="p-4 text-center text-slate-500">No users found.</td></tr>}
              </tbody>
            </table>
          </div>
        </div>

        {/* Members */}
        <div className="card p-6 space-y-4 border border-teal-500/20">
          <div>
            <h2 className="text-lg font-semibold">Department Members</h2>
            <p className="mt-1 text-sm text-slate-400">Add members and toggle their active status. Adding a username and password also creates a login account.</p>
          </div>
          <form onSubmit={handleAddMember} className="grid gap-3 sm:grid-cols-5">
            <input required placeholder="Display name" value={memberForm.display_name} onChange={e=>setMemberForm({...memberForm,display_name:e.target.value})} className="rounded bg-bg p-3 text-sm"/>
            <input required placeholder="Email" type="email" value={memberForm.email} onChange={e=>setMemberForm({...memberForm,email:e.target.value})} className="rounded bg-bg p-3 text-sm"/>
            <input placeholder="Username (optional)" value={memberForm.username} onChange={e=>setMemberForm({...memberForm,username:e.target.value})} className="rounded bg-bg p-3 text-sm"/>
            <input type="password" placeholder="Password (optional)" value={memberForm.password} onChange={e=>setMemberForm({...memberForm,password:e.target.value})} className="rounded bg-bg p-3 text-sm"/>
            <button type="submit" className="rounded bg-indigo-500 px-4 py-3 text-sm font-semibold hover:bg-indigo-400">Add Member</button>
          </form>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-black/20 text-left text-slate-400">
                <tr><th className="p-3">Name</th><th>Email</th><th>Status</th><th></th></tr>
              </thead>
              <tbody>
                {members.map(m=>(
                  <tr className="border-t border-border" key={m.id}>
                    <td className="p-3">{m.display_name}</td>
                    <td className="text-slate-300">{m.email}</td>
                    <td>
                      <span className={`inline-block rounded-full px-2 py-0.5 text-xs font-medium ${m.active?'bg-green-500/20 text-green-300':'bg-red-500/20 text-red-300'}`}>
                        {m.active?'Active':'Inactive'}
                      </span>
                    </td>
                    <td className="py-2 pr-3 text-right">
                      <button
                        onClick={()=>handleToggleMember(m)}
                        disabled={memberLoading===m.id}
                        className="rounded border border-border px-3 py-1 text-xs hover:bg-white/5 disabled:opacity-50"
                      >
                        {memberLoading===m.id?'Saving…':m.active?'Deactivate':'Activate'}
                      </button>
                    </td>
                  </tr>
                ))}
                {members.length===0&&<tr><td colSpan={4} className="p-4 text-center text-slate-500">No members yet.</td></tr>}
              </tbody>
            </table>
          </div>
        </div>

        {/* Regenerate quarter */}
        <div className="card p-6 space-y-4 border border-yellow-500/20">
          <div>
            <h2 className="text-lg font-semibold">Regenerate Current Quarter</h2>
            <p className="mt-1 text-sm text-slate-400">Use this if the quarter assignments need to be rebuilt — for example after members were added or removed. All existing assignments for the current quarter will be wiped and regenerated. This is blocked once any points have been marked as sent.</p>
          </div>
          {regenMsg&&(<p className={`rounded-lg p-3 text-sm ${regen==='error'?'bg-red-500/10 text-red-400':'bg-green-500/10 text-green-400'}`}>{regenMsg}</p>)}
          <button onClick={handleRegenerate} disabled={regen==='loading'} className="rounded-xl bg-yellow-500 px-5 py-2.5 text-sm font-semibold text-black hover:bg-yellow-400 disabled:opacity-50 disabled:cursor-not-allowed transition">
            {regen==='loading'?'Regenerating…':'⟳ Regenerate Quarter'}
          </button>
        </div>

      </>)}
    </div>
  );
}
