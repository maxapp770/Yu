'use strict';
/* Explicit, bounded local schemas. Stored content is data, never authority or HTML. */
window.HECStore = (() => {
  const CLIENT = 'hec.phase1.v1', COURIER = 'hec.courier.demo.v1';
  const MAX_BYTES = 2 * 1024 * 1024;
  const object = value => value && typeof value === 'object' && !Array.isArray(value);
  const text = (value, max = 100) => typeof value === 'string' ? value.slice(0, max).trim() : '';
  const clone = value => JSON.parse(JSON.stringify(value));
  const digits = value => text(value, 100).replace(/[٠-٩۰-۹]/g, c => String('٠١٢٣٤٥٦٧٨٩'.includes(c) ? '٠١٢٣٤٥٦٧٨٩'.indexOf(c) : '۰۱۲۳۴۵۶۷۸۹'.indexOf(c)));
  const phone = value => { const s = digits(value), n = s.replace(/\D/g, '').length; return /^[+0-9 ()-]+$/.test(s) && n >= 7 && n <= 15; };
  const quantity = value => Math.max(1, Math.min(999, Math.floor(Number(value) || 1)));
  const product = id => HEC.products.find(p => p.id === id);
  function lineKey(value) {
    if (typeof value !== 'string') return null;
    const parts = value.split('~'), p = product(parts[0]);
    if (!p || parts.length > 2 || (parts.length === 2 && !(p.variants || []).some(v => v.id === parts[1]))) return null;
    return parts[1] && parts[1] !== p.variants[0].id ? value : p.id;
  }
  function blank() { return {schema: 3, variants: {}, cart: {}, favorites: [], orders: [], addresses: [], profile: {name:"", phone:"", email:""}, locale:"ar", campaignEpoch:0, readNotifications:[], returns:[], messages:[], walletRequests:[], affiliateDraft:null}; }
  function customer(raw) {
    const s = blank(); if (!object(raw)) return s;
    if (object(raw.cart)) for (const [id, q] of Object.entries(raw.cart).slice(0, 300)) {
      const key = lineKey(id); if (key) s.cart[key] = Math.min(999, (s.cart[key] || 0) + quantity(q));
    }
    if (object(raw.variants)) for (const p of HEC.products) {
      if ((p.variants || []).some(v => v.id === raw.variants[p.id])) s.variants[p.id] = raw.variants[p.id];
    }
    if (Array.isArray(raw.favorites)) s.favorites = [...new Set(raw.favorites.filter(id => product(id)))].slice(0, 200);
    const used = new Set();
    if (Array.isArray(raw.orders)) for (const o of raw.orders.slice(0, 100)) {
      if (!object(o) || !/^D-[A-Z0-9-]{1,64}$/.test(o.id) || used.has(o.id) || !Array.isArray(o.lines)) continue;
      const lines = o.lines.slice(0, 100).filter(l => object(l) && product(l.id) && Number.isFinite(l.price) && Math.abs(l.price*100-Math.round(l.price*100))<.00001 && l.price >= 0 && l.price <= 1000000000).map(l => ({id: l.id, lineKey: lineKey(l.lineKey || l.id) || l.id, name: text(l.name, 180), variant: text(l.variant, 80), price: l.price, qty: quantity(l.qty)}));
      if (!lines.length) continue;
      const c = object(o.customer) ? o.customer : {};
      s.orders.push({id: o.id, date: text(o.date, 60), status: 'draft', lines, document:window.HECOrderModel?HECOrderModel.sanitize(o.document,lines):null, total: lines.reduce((n, l) => n + l.price * l.qty, 0), customer: {name: text(c.name, 80), phone: digits(c.phone).slice(0, 20), address: text(c.address, 300), note: text(c.note, 500)}});
      used.add(o.id);
    }
    if (Array.isArray(raw.addresses)) s.addresses = raw.addresses.filter(a => object(a) && text(a.name, 60) && text(a.address, 300)).slice(0, 20).map(a => ({name: text(a.name, 60), address: text(a.address, 300)}));
    const p = object(raw.profile) ? raw.profile : {};
    s.profile = {name:text(p.name,80), phone:digits(p.phone).slice(0,20), email:text(p.email,100)};
    s.locale = raw.locale === 'en' ? 'en' : 'ar';
    s.campaignEpoch = Number.isSafeInteger(raw.campaignEpoch) && raw.campaignEpoch > 0 && raw.campaignEpoch <= Date.now() ? raw.campaignEpoch : 0;
    s.readNotifications = Array.isArray(raw.readNotifications) ? [...new Set(raw.readNotifications.filter(id=>HEC.notifications.some(n=>n.id===id)))].slice(0,100) : [];
    const rows=(key,clean)=>{const ids=new Set();return (Array.isArray(raw[key])?raw[key]:[]).slice(0,100).filter(x=>object(x)&&/^[A-Z0-9-]{1,80}$/.test(x.id)&&!ids.has(x.id)&&ids.add(x.id)).map(x=>({id:x.id,date:text(x.date,40),status:'draft',...clean(x)}));};
    s.returns=rows('returns',x=>({orderId:text(x.orderId,80),productId:product(x.productId)?x.productId:'',lineKey:lineKey(x.lineKey||x.productId)||'',qty:quantity(x.qty),reason:['damaged','wrong','other'].includes(x.reason)?x.reason:'other',note:text(x.note,500)})).filter(x=>s.orders.some(o=>o.id===x.orderId&&o.lines.some(l=>l.id===x.productId&&(l.lineKey||l.id)===x.lineKey&&x.qty<=l.qty)));
    s.messages=rows('messages',x=>({subject:text(x.subject,100),body:text(x.body,1000),productId:product(x.productId)?x.productId:''})).filter(x=>x.subject&&x.body);
    s.walletRequests=rows('walletRequests',x=>({type:['deposit','withdraw'].includes(x.type)?x.type:'deposit',amount:Number.isSafeInteger(x.amount)&&x.amount>0&&x.amount<=100000000?x.amount:0,note:text(x.note,300)})).filter(x=>x.amount>0);
    if(object(raw.affiliateDraft)&&text(raw.affiliateDraft.name,80))s.affiliateDraft={name:text(raw.affiliateDraft.name,80),channel:text(raw.affiliateDraft.channel,160),note:text(raw.affiliateDraft.note,500),status:'draft'};
    return s;
  }
  function courier(raw, defaults) {
    const s = clone(defaults); if (!object(raw) || !Array.isArray(raw.jobs)) return s;
    s.online = raw.online !== false;
    const p = object(raw.profile) ? raw.profile : {};
    s.profile = {name: text(p.name, 80) || defaults.profile.name, phone: digits(p.phone).slice(0, 20), email: text(p.email, 100)};
    const used = new Set();
    s.jobs = raw.jobs.slice(0, 100).filter(j => object(j) && defaults.jobs.some(d => d.id === j.id) && ['offered', 'accepted', 'onway', 'delivered', 'rejected'].includes(j.status) && !used.has(j.id) && used.add(j.id)).map(j => {
      const original = defaults.jobs.find(d => d.id === j.id);
      const collected = j.status === 'delivered' && (!original.paid || original.collected === original.amount) && j.collected === original.amount ? original.amount : 0;
      return {...original, status: j.status, paid: original.paid || collected > 0, collected};
    });
    return s;
  }
  function read(key) {
    try {
      const raw = localStorage.getItem(key);
      if (!raw) return {value: null, issue: ''};
      if (raw.length > MAX_BYTES) return {value: null, issue: 'oversize'};
      try { return {value: JSON.parse(raw), issue: ''}; } catch (_) { return {value: null, issue: 'corrupt'}; }
    } catch (_) { return {value: null, issue: 'unavailable'}; }
  }
  function write(key, value) {
    try { const data = JSON.stringify(value); if (data.length > MAX_BYTES) return false; localStorage.setItem(key, data); return true; } catch (_) { return false; }
  }
  const search = value => digits(value).toLowerCase().replace(/[\u064b-\u065f\u0670\u0640]/g, '').replace(/[أإآٱ]/g, 'ا').replace(/ى/g, 'ي').replace(/ة/g, 'ه').replace(/\s+/g, ' ').trim();
  return Object.freeze({CLIENT, COURIER, text, clone, digits, phone, lineKey, blank, customer, courier, read, write, search});
})();
