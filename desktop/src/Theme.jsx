import React, { useEffect, useState } from 'react';
import { Sun, Moon, Monitor } from 'lucide-react';
export function ThemeSwitch() {
  const [theme,setTheme]=useState(() => localStorage.getItem('marassim.theme') || 'system');
  useEffect(() => { const media=matchMedia('(prefers-color-scheme: dark)'); const apply=()=>{ document.documentElement.dataset.theme=theme==='system' ? (media.matches ? 'dark':'light'):theme; document.querySelector('meta[name="theme-color"]')?.setAttribute('content',document.documentElement.dataset.theme==='dark'?'#101920':'#387b6e'); }; apply(); media.addEventListener('change',apply); localStorage.setItem('marassim.theme',theme); return ()=>media.removeEventListener('change',apply); },[theme]);
  const Icon=theme==='dark'?Moon:theme==='light'?Sun:Monitor;
  return <button className="icon-button theme-switch" aria-label={`Thème ${theme==='system'?'automatique':theme==='dark'?'sombre':'clair'} · changer le thème`} title="Clair / sombre / automatique" onClick={()=>setTheme(theme==='system'?'light':theme==='light'?'dark':'system')}><Icon size={19}/></button>;
}
