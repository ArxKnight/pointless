import {NavLink,Outlet,useNavigate} from 'react-router-dom';
import {User} from '../types/api';
import {post} from '../lib/api';

const item='rounded-xl px-3 py-2 text-sm font-medium text-slate-300 hover:bg-white/5';

export function Layout({user,setUser}:{user:User;setUser:(u:null)=>void}){
  const nav=useNavigate();
  const links:[string,string][]=[
    ['/','◈ Dashboard'],
    ['/tree','🌳 My Giving Tree'],
    ['/overview','🌐 Overview'],
    ['/history','🕐 History'],
    ...(user.is_admin?[['/quarters','⚙️ Quarters']] as [string,string][]:[]),
    ['/settings','⚙️ Settings'],
  ];

  return (
    <div className="min-h-screen bg-bg">
      {/* Sidebar */}
      <aside className="fixed inset-y-0 left-0 hidden w-64 border-r border-border bg-surface/80 p-4 md:block">
        <h1 className="mb-8 text-xl font-bold tracking-tight">Quarterly Points</h1>
        <nav className="space-y-1">
          {links.map(([to,label])=>(
            <NavLink
              key={to}
              to={to}
              end={to==='/'}
              className={({isActive})=>`${item} block ${isActive?'bg-indigo-500/20 text-indigo-200':''}`}
            >
              {label}
            </NavLink>
          ))}
        </nav>
      </aside>

      {/* Main */}
      <main className="pb-24 md:ml-64">
        <header className="sticky top-0 z-10 flex items-center justify-between border-b border-border bg-bg/80 p-4 backdrop-blur">
          <p className="text-sm text-slate-400">Welcome, <span className="text-slate-100">{user.display_name}</span></p>
          <button
            onClick={async()=>{await post('/auth/logout');setUser(null);nav('/login');}}
            className="rounded-lg border border-border px-3 py-2 text-sm"
          >
            Logout
          </button>
        </header>
        <div className="p-4 md:p-8"><Outlet/></div>
      </main>

      {/* Mobile bottom nav */}
      <nav className="fixed inset-x-0 bottom-0 flex gap-1 overflow-x-auto border-t border-border bg-surface p-2 md:hidden">
        {links.slice(0,5).map(([to,label])=>(
          <NavLink key={to} to={to} end={to==='/'} className="min-w-fit rounded-lg px-3 py-2 text-xs text-slate-300">
            {label}
          </NavLink>
        ))}
      </nav>
    </div>
  );
}
