import {useEffect,useState} from 'react';
import {BrowserRouter,Navigate,Route,Routes} from 'react-router-dom';
import {api} from './lib/api';
import {User} from './types/api';
import {Layout} from './components/Layout';
import {Login} from './pages/Login';
import {Install} from './pages/Install';
import {Dashboard} from './pages/Dashboard';
import {MyTree} from './pages/MyTree';
import {Overview} from './pages/Overview';
import {History} from './pages/History';
import {Quarters} from './pages/Quarters';
import {Participants} from './pages/Participants';
import {Settings} from './pages/Settings';
import {AdminInvite} from './pages/AdminInvite';

type InstallStatus={installed:boolean;database_configured:boolean};

export default function App(){
  const [installed,setInstalled]=useState<boolean|undefined>(undefined);
  const [user,setUser]=useState<User|null|undefined>(undefined);

  useEffect(()=>{
    api<InstallStatus>('/install/status')
      .then(s=>{
        setInstalled(s.installed);
        if(s.installed) api<User>('/auth/me').then(setUser).catch(()=>setUser(null));
        else setUser(null);
      })
      .catch(()=>{setInstalled(true);setUser(null)});
  },[]);

  if(installed===undefined||user===undefined)
    return <div className="grid h-screen place-items-center bg-bg">Loading...</div>;
  if(!installed)
    return <Install onInstalled={()=>{setInstalled(true);setUser(null)}}/>;

  return (
    <BrowserRouter>
      <Routes>
        <Route path="tree/:slug" element={<MyTree/>}/>
        <Route path="admin-invite/:token" element={<AdminInvite/>}/>
        {!user
          ? <Route path="*" element={<Login setUser={setUser}/>}/>
          : <Route element={<Layout user={user} setUser={setUser}/>}>
              <Route index element={<Dashboard/>}/>
              <Route path="overview" element={<Overview/>}/>
              <Route path="history" element={<History/>}/>
              <Route path="settings" element={<Settings user={user}/>}/>
              {user.is_admin&&<Route path="participants" element={<Participants/>}/>}
              {user.is_admin&&<Route path="quarters" element={<Quarters/>}/>}
              <Route path="*" element={<Navigate to="/"/>}/>
            </Route>
        }
      </Routes>
    </BrowserRouter>
  );
}
