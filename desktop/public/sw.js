const CACHE='marassim-shell-3.4.0';
const SHELL=['/','/manifest.webmanifest','/icon.svg','/icon-256.png','/icon-512.png','/offline.html'];
self.addEventListener('install',event=>event.waitUntil(caches.open(CACHE).then(cache=>cache.addAll(SHELL)).then(()=>self.skipWaiting())));
self.addEventListener('activate',event=>event.waitUntil(caches.keys().then(keys=>Promise.all(keys.filter(k=>k.startsWith('marassim-shell-')&&k!==CACHE).map(k=>caches.delete(k)))).then(()=>self.clients.claim())));
self.addEventListener('fetch',event=>{
  const request=event.request,url=new URL(request.url);
  // Personal data and authentication always travel over the network, never through CacheStorage.
  if(request.method!=='GET'||url.origin!==self.location.origin||url.pathname.startsWith('/api/'))return;
  if(request.mode==='navigate'){event.respondWith(fetch(request).then(response=>{if(response.ok){const copy=response.clone();caches.open(CACHE).then(c=>c.put('/',copy));}return response;}).catch(()=>caches.match('/').then(r=>r||caches.match('/offline.html'))));return;}
  if(url.pathname.startsWith('/assets/')||SHELL.includes(url.pathname))event.respondWith(caches.match(request).then(cached=>cached||fetch(request).then(response=>{if(response.ok){const copy=response.clone();caches.open(CACHE).then(c=>c.put(request,copy));}return response;})));
});
self.addEventListener('push',event=>{let message={title:'Nouvelle réservation Marassim',body:'La copie en ligne a été actualisée.'};try{Object.assign(message,event.data.json());}catch{}event.waitUntil(self.registration.showNotification(message.title,{body:message.body,icon:'/icon-256.png',badge:'/icon-256.png',tag:message.tag||'marassim-reservations',data:{url:'/'}}));});
self.addEventListener('notificationclick',event=>{event.notification.close();event.waitUntil(self.clients.matchAll({type:'window',includeUncontrolled:true}).then(clients=>{const existing=clients.find(c=>new URL(c.url).origin===self.location.origin);return existing?existing.focus():self.clients.openWindow('/');}));});
