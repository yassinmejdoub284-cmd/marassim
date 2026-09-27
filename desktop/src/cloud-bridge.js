export const cloudApi=async(path,options={})=>{
  const response=await fetch('/api/online'+path,{method:options.method || 'GET',credentials:'same-origin',headers:options.body?{'Content-Type':'application/json'}:{},body:options.body?JSON.stringify(options.body):undefined,cache:'no-store'});
  let value;try{value=await response.json();}catch{throw new Error('Le site ne répond pas. Vérifiez votre connexion Internet.');}
  if(!response.ok){const error=new Error(value.error || 'Opération refusée.');error.status=response.status;throw error;}return value;
};
export async function downloadCloud(file){
  const bytes=Uint8Array.from(atob(file.base64),c=>c.charCodeAt(0));
  const url=URL.createObjectURL(new Blob([bytes]));const link=document.createElement('a');link.href=url;link.download=file.name;link.click();setTimeout(()=>URL.revokeObjectURL(url),10000);return {saved:true};
}
