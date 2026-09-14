'use strict';
/* Safe performance layer for Android WebView and ordinary browsers. */
(() => {
  const reduced = typeof matchMedia === 'function' && matchMedia('(prefers-reduced-motion: reduce)').matches;
  const saveData = !!navigator.connection?.saveData;
  window.HECPerf = { reducedMotion: reduced, saveData,
    idle(fn) { return (window.requestIdleCallback || (cb => setTimeout(cb, 1)))(fn); },
    cache(key, value, ttl = 300000) { try { if (value === undefined) { const raw = JSON.parse(localStorage.getItem('hec.perf.' + key) || 'null'); return raw && raw.expires > Date.now() ? raw.value : null; } localStorage.setItem('hec.perf.' + key, JSON.stringify({value, expires: Date.now() + ttl})); } catch (_) {} return value; }
  };
  function tune(root=document) { root.querySelectorAll?.('img').forEach(img => { if (!img.loading) img.loading='lazy'; img.decoding='async'; if (!img.getAttribute('fetchpriority')) img.setAttribute('fetchpriority','low'); }); root.querySelectorAll?.('video').forEach(v => { if (!v.getAttribute('preload')) v.preload='none'; if (saveData || reduced) v.autoplay=false; }); }
  const status=document.createElement('div'); status.className='network-status'; status.setAttribute('role','status'); status.hidden=true; status.textContent='أنت غير متصل؛ سيظهر آخر محتوى محفوظ عند توفره.';
  function network(){ if(!status.isConnected&&document.body)document.body.append(status); status.hidden=navigator.onLine!==false; document.documentElement.dataset.network=navigator.onLine===false?'offline':'online'; }
  addEventListener('online',network); addEventListener('offline',network);
  addEventListener('DOMContentLoaded',()=>{ tune(); network(); new MutationObserver(ms=>ms.forEach(m=>m.addedNodes.forEach(n=>{if(n.nodeType===1)tune(n)}))).observe(document.body,{childList:true,subtree:true}); },{once:true});
})();
