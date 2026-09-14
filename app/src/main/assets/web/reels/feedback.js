'use strict';
window.HECFeedback=(()=>{
 let timer=null,current=null,remaining=0,started=0,lastText='',lastAt=0;
 const E=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
 const glyph={success:'M4 12l5 5L20 6',error:'M12 7v6m0 4h.01M12 2 2 21h20Z',info:'M12 11v7m0-12h.01M22 12a10 10 0 1 1-20 0 10 10 0 0 1 20 0'};
 function hide(){clearTimeout(timer);current?.el.classList.remove('show');current?.onClose?.();current=null}
 function resume(){if(!current)return;started=Date.now();clearTimeout(timer);timer=setTimeout(hide,Math.max(250,remaining))}
 function pause(){if(!current)return;clearTimeout(timer);remaining=Math.max(0,remaining-(Date.now()-started))}
 function show(message,options={}){
  message=String(message||'');if(!message)return;if(message===lastText&&Date.now()-lastAt<300)return;lastText=message;lastAt=Date.now();clearTimeout(timer);
  let el=document.getElementById('toast');if(!el){el=document.createElement('div');el.id='toast';document.body.append(el)}
  const tone=options.tone||(/تعذر|خطأ|فشل|لا يمكن|غير متاح|تجاوز/.test(message)?'error':/^(تم|تمت|أضيف|أُضيف|حُفظ|أضفت)/.test(message)?'success':'info');
  el.className='hec-feedback show';el.dataset.tone=tone;el.setAttribute('role',tone==='error'?'alert':'status');el.setAttribute('aria-live',tone==='error'?'assertive':'polite');el.setAttribute('aria-atomic','true');
  el.innerHTML=`<span class="feedback-mark"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="${glyph[tone]||glyph.info}"/></svg></span><span class="feedback-message">${E(message)}</span>${options.undo?'<button data-action="undo-remove" class="feedback-action">تراجع</button>':options.action?`<button class="feedback-action" data-feedback-action>${E(options.action.label)}</button>`:''}<button class="feedback-dismiss" data-feedback-dismiss aria-label="إغلاق التنبيه">×</button>`;
  ([...document.querySelectorAll('dialog[open]')].at(-1)||document.getElementById('reels-viewer')||document.body).append(el);
  el.querySelector('[data-feedback-dismiss]').onclick=hide;
  const action=el.querySelector('[data-feedback-action]');if(action)action.onclick=()=>{hide();options.action.run()};
  current={el,onClose:options.onClose};remaining=options.undo?8000:tone==='error'||options.action?6500:3600;
  el.onpointerenter=pause;el.onpointerleave=resume;el.onfocusin=pause;el.onfocusout=resume;resume();return el;
 }
 return {show,hide};
})();
