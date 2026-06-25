export async function api<T>(path:string, options:RequestInit={}):Promise<T>{
 const res=await fetch(`/api${path}`,{credentials:'include',headers:{'Content-Type':'application/json',...(options.headers||{})},...options});
 if(!res.ok){let msg='Request failed'; try{const j=await res.json(); msg=j.detail||msg}catch{}; throw new Error(msg)}
 return res.json();
}
export const post=<T>(p:string,b:any={})=>api<T>(p,{method:'POST',body:JSON.stringify(b)});
export const patch=<T>(p:string,b:any)=>api<T>(p,{method:'PATCH',body:JSON.stringify(b)});
export const del=<T>(p:string,b:any=undefined)=>api<T>(p,{method:'DELETE',body:b===undefined?undefined:JSON.stringify(b)});
