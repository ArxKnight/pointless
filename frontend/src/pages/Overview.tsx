import { useCallback, useEffect, useMemo, useState } from 'react';
import ReactFlow,{Background,Controls,MiniMap,MarkerType,Node,Edge,useNodesState,useEdgesState} from 'reactflow';
import 'reactflow/dist/style.css';
import { api } from '../lib/api';
import { OverviewTreeAllocation, OverviewTreeData, OverviewTreeUser, Team, TeamGroup } from '../types/api';

type Region={id:string;label:string;teams:Team[];isUnassigned?:boolean};
const neutral='#64748b';
function byOrderName<T extends {display_order?:number;name:string}>(a:T,b:T){return (a.display_order??0)-(b.display_order??0)||a.name.localeCompare(b.name)}
function userTeamLabel(u:OverviewTreeUser){return u.team_name||'Unassigned'}
function userGroupLabel(u:OverviewTreeUser){return u.team_group_name||'Unassigned'}
function relatedMemberIds(memberId:number, allocations:OverviewTreeAllocation[]){const ids=new Set<number>([memberId]);for(const a of allocations){if(a.source_member_id===memberId)ids.add(a.recipient_member_id);if(a.recipient_member_id===memberId)ids.add(a.source_member_id)}return ids}

function buildRegions(data:OverviewTreeData):Region[]{
  const teamsByGroup=new Map<number,string[]>();
  data.teams.filter(t=>t.is_active&&t.group_id!==null&&t.group_id!==undefined).forEach(t=>{const arr=teamsByGroup.get(t.group_id as number)||[];arr.push(String(t.id));teamsByGroup.set(t.group_id as number,arr)});
  const regions:Region[]=data.team_groups.filter(g=>g.is_active).sort(byOrderName).map(g=>({id:`g-${g.id}`,label:g.name,teams:data.teams.filter(t=>t.is_active&&t.group_id===g.id).sort(byOrderName)}));
  const independent=data.teams.filter(t=>t.is_active&&(t.group_id===null||t.group_id===undefined||!data.team_groups.some(g=>g.is_active&&g.id===t.group_id))).sort(byOrderName);
  if(independent.length)regions.push({id:'independent',label:'Independent teams',teams:independent});
  regions.push({id:'unassigned',label:'Unassigned',teams:[],isUnassigned:true});
  return regions;
}

function layout(data:OverviewTreeData, selected:number|null):{nodes:Node[];edges:Edge[]}{
  const regions=buildRegions(data);const selectedRelated=selected?relatedMemberIds(selected,data.allocations):new Set<number>();
  const usersByTeam=new Map<number,OverviewTreeUser[]>();const unassigned=data.users.filter(u=>!u.team_id);
  data.users.filter(u=>u.team_id).forEach(u=>{const arr=usersByTeam.get(u.team_id as number)||[];arr.push(u);usersByTeam.set(u.team_id as number,arr)});
  const nodes:Node[]=[];const memberPosition=new Map<number,{x:number;y:number}>();let x=0;
  const teamNodeIds=new Set<string>();
  for(const region of regions){
    const regionTeams=region.isUnassigned?[]:region.teams;const unassignedCount=region.isUnassigned?Math.max(1,unassigned.length):0;
    const regionWidth=region.isUnassigned?Math.max(320,unassignedCount*170+80):Math.max(360,regionTeams.reduce((sum,t)=>sum+Math.max(260,(usersByTeam.get(t.id)?.length||1)*150+50),0)+Math.max(0,regionTeams.length-1)*40+40);
    const regionId=region.id;nodes.push({id:regionId,type:'default',position:{x,y:0},data:{label:<div className="text-center"><div className="font-semibold">{region.label}</div><div className="text-[10px] text-slate-400">{region.isUnassigned?'No configured team':'Team Group'}</div></div>},draggable:false,selectable:false,style:{width:regionWidth,height:520,background:region.isUnassigned?'rgba(100,116,139,.08)':'rgba(99,102,241,.07)',border:'1px solid rgba(148,163,184,.25)',borderRadius:24,color:'#e2e8f0',paddingTop:14}});
    let teamX=24;
    if(region.isUnassigned){
      const teamId='team-unassigned';teamNodeIds.add(teamId);nodes.push({id:teamId,parentNode:regionId,extent:'parent',position:{x:24,y:70},data:{label:<div className="text-center"><b>Unassigned</b><div className="text-[10px] text-slate-400">{unassigned.length} user(s)</div></div>},draggable:false,selectable:false,style:{width:regionWidth-48,height:410,background:'rgba(100,116,139,.10)',border:`2px solid ${neutral}`,borderRadius:18,color:'#f8fafc'}});
      unassigned.forEach((u,i)=>{const col=i%Math.max(1,Math.floor((regionWidth-80)/160));const row=Math.floor(i/Math.max(1,Math.floor((regionWidth-80)/160)));const px=24+30+col*160,py=70+70+row*125;memberPosition.set(u.member_id,{x:x+px,y:py});nodes.push(userNode(u,teamId,{x:px,y:70+70+row*125},selected,selectedRelated));});
    }else{
      for(const t of regionTeams){const users=(usersByTeam.get(t.id)||[]).sort((a,b)=>((b.total_points_sent-b.total_points_received)-(a.total_points_sent-a.total_points_received))||a.display_name.localeCompare(b.display_name));const width=Math.max(260,Math.max(1,users.length)*150+50);const teamId=`team-${t.id}`;teamNodeIds.add(teamId);nodes.push({id:teamId,parentNode:regionId,extent:'parent',position:{x:teamX,y:70},data:{label:<div className="text-center"><b>{t.name}</b><div className="text-[10px] text-slate-300">{users.length} user(s)</div></div>},draggable:false,selectable:false,style:{width,height:410,background:`${t.colour}22`,border:`2px solid ${t.colour}`,borderRadius:18,color:'#f8fafc'}});
        users.forEach((u,i)=>{const py=70+(i%3)*105+Math.floor(i/3)*28;const px=teamX+35+(i%Math.max(1,Math.floor((width-60)/145)))*145;memberPosition.set(u.member_id,{x:x+px,y:70+py});nodes.push(userNode(u,teamId,{x:px-teamX,y:py},selected,selectedRelated));});teamX+=width+40;}
    }
    x+=regionWidth+70;
  }
  const edgeMap=new Map<string,{points:number;ack:boolean;ids:number[]}>();for(const a of data.allocations){const k=`${a.source_member_id}-${a.recipient_member_id}`;const prev=edgeMap.get(k)||{points:0,ack:true,ids:[]};edgeMap.set(k,{points:prev.points+a.points,ack:prev.ack&&a.acknowledged,ids:[...prev.ids,a.allocation_id]});}
  const edges:Array<Edge>=Array.from(edgeMap.entries()).map(([k,v])=>{const [s,t]=k.split('-').map(Number);const isSelected=selected===null||s===selected||t===selected;return{id:`e-${k}`,source:`u-${s}`,target:`u-${t}`,label:`${v.points} pts`,animated:!v.ack,markerEnd:{type:MarkerType.ArrowClosed},style:{stroke:isSelected?'#f8fafc':'#64748b',strokeWidth:isSelected?3:1.5,opacity:isSelected?1:.15},labelStyle:{fill:'#e2e8f0',fontSize:11,opacity:isSelected?1:.2},labelBgStyle:{fill:'#0f172a',fillOpacity:.85},data:{allocation_ids:v.ids,points:v.points}}});
  return{nodes,edges};
}
function userNode(u:OverviewTreeUser,parentNode:string,position:{x:number;y:number},selected:number|null,related:Set<number>):Node{const colour=u.team_colour||neutral;const isSelected=selected===u.member_id;const isRelated=selected===null||related.has(u.member_id);return{id:`u-${u.member_id}`,parentNode,extent:'parent',position,data:{memberId:u.member_id,label:<div className="min-w-[116px] text-center" title={`${u.display_name}\nTeam: ${userTeamLabel(u)}\nGroup: ${userGroupLabel(u)}\nSent: ${u.total_points_sent}\nReceived: ${u.total_points_received}`}><div className="font-bold text-[13px]">{u.display_name}</div><div className="text-[10px]" style={{color:colour}}>{userTeamLabel(u)}</div><div className="text-[10px] text-slate-300">↑ {u.total_points_sent} · ↓ {u.total_points_received}</div><div className="text-[10px] text-slate-400">to {u.recipient_count} · from {u.incoming_allocation_count}</div></div>},style:{background:isSelected?'#172554':'#111827',border:`${isSelected?3:2}px solid ${colour}`,borderRadius:14,color:'#f8fafc',padding:'8px 10px',opacity:isRelated?1:.18,boxShadow:isSelected?'0 0 0 4px rgba(59,130,246,.25)':'none'}}}

export function Overview(){
  const [data,setData]=useState<OverviewTreeData|null>(null);const [error,setError]=useState('');const [selected,setSelected]=useState<number|null>(null);const [nodes,setNodes,onNodesChange]=useNodesState([]);const [edges,setEdges,onEdgesChange]=useEdgesState([]);
  const rebuild=useCallback((d:OverviewTreeData,sel:number|null)=>{const built=layout(d,sel);setNodes(built.nodes);setEdges(built.edges)},[setNodes,setEdges]);
  useEffect(()=>{api<OverviewTreeData>('/quarters/active/overview-tree').then(d=>{setData(d);rebuild(d,null)}).catch(e=>setError(e.message))},[rebuild]);
  useEffect(()=>{if(data)rebuild(data,selected)},[selected,data,rebuild]);
  const selectedUser=useMemo(()=>data?.users.find(u=>u.member_id===selected),[data,selected]);
  if(error)return <div className="card p-6 text-red-400">{error}</div>;if(!data)return <div className="card p-6 text-slate-400">Loading Overview Tree…</div>;
  return <div className="space-y-6"><div><h1 className="text-3xl font-semibold">Overview Tree</h1><p className="mt-1 text-slate-400">{data.quarter?`${data.quarter.label} — top-down team-grouped points distribution from real allocation records.`:'No active quarter yet. Team structure is ready; allocation links will appear once a quarter is generated.'}</p></div>
    <div className="grid gap-3 md:grid-cols-4"><div className="card p-4"><p className="text-xs text-slate-400">Team groups</p><p className="text-2xl font-semibold">{data.team_groups.length}</p></div><div className="card p-4"><p className="text-xs text-slate-400">Teams</p><p className="text-2xl font-semibold">{data.teams.length}</p></div><div className="card p-4"><p className="text-xs text-slate-400">Users</p><p className="text-2xl font-semibold">{data.users.length}</p></div><div className="card p-4"><p className="text-xs text-slate-400">Allocation links</p><p className="text-2xl font-semibold">{data.allocations.length}</p></div></div>
    {selectedUser&&<div className="card p-4 text-sm"><button className="float-right rounded border border-border px-3 py-1 text-xs" onClick={()=>setSelected(null)}>Clear selection</button><b>{selectedUser.display_name}</b> — {userTeamLabel(selectedUser)} / {userGroupLabel(selectedUser)}. Sent {selectedUser.total_points_sent}, received {selectedUser.total_points_received}; highlighting direct incoming and outgoing allocations.</div>}
    <div className="h-[650px] overflow-hidden rounded-2xl border border-border bg-[#0d0f1a]"><ReactFlow nodes={nodes} edges={edges} onNodesChange={onNodesChange} onEdgesChange={onEdgesChange} onNodeClick={(_,n)=>{const id=n.data?.memberId;if(typeof id==='number')setSelected(id)}} onPaneClick={()=>setSelected(null)} fitView fitViewOptions={{padding:.15}} minZoom={0.2}><Background color="#2a2d3e"/><MiniMap nodeColor={n=>String((n.style as any)?.border||'#64748b').split(' ').pop()||'#64748b'} style={{background:'#0d0f1a',border:'1px solid #2a2d3e'}}/><Controls/></ReactFlow></div>
    <div className="card overflow-hidden"><div className="border-b border-border px-6 py-4"><h2 className="text-lg font-semibold">User points breakdown</h2><p className="text-sm text-slate-400">Team headings are visual containers only; they are not counted as users or fake allocation endpoints.</p></div><div className="overflow-x-auto"><table className="w-full text-sm"><thead><tr className="border-b border-border text-left text-slate-400"><th className="px-6 py-3">User</th><th>Team</th><th>Team group</th><th className="text-right">Sent</th><th className="text-right">Received</th><th className="text-right">Recipients</th><th className="text-right">Incoming</th></tr></thead><tbody>{data.users.map(u=><tr key={u.member_id} className="border-b border-border/40 hover:bg-white/5"><td className="px-6 py-3 font-medium">{u.display_name}</td><td><span className="inline-flex items-center gap-2"><span className="h-3 w-3 rounded-full" style={{background:u.team_colour||neutral}}/>{userTeamLabel(u)}</span></td><td>{userGroupLabel(u)}</td><td className="text-right text-yellow-400">{u.total_points_sent}</td><td className="text-right text-indigo-400">{u.total_points_received}</td><td className="text-right">{u.recipient_count}</td><td className="pr-6 text-right">{u.incoming_allocation_count}</td></tr>)}</tbody></table></div></div>
  </div>;
}
