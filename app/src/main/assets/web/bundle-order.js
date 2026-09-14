'use strict';
/* Local order projection. ERP must rebuild packed rows with its actual child-row IDs. */
window.HECOrderModel=(()=>{
 const round=n=>Math.round((Number(n)+Number.EPSILON)*100)/100;
 function project(lines,doctype='Sales Order'){
  if(!['Sales Order','Sales Invoice'].includes(doctype)||!Array.isArray(lines)||lines.length>100)throw Error('نوع طلب غير صالح');
  const items=[],packed_items=[];
  for(const [i,l] of lines.entries()){
   const p=HEC.products.find(p=>p.id===l.id);if(!p||!Number.isInteger(l.qty)||l.qty<1||l.qty>999||!Number.isFinite(l.price)||l.price<0)throw Error('بيانات طلب غير صالحة');
   const name='local-line-'+(i+1),b=p.bundleId&&HEC.featuredBundles.find(b=>b.id===p.bundleId&&b.active!==false);
   items.push({name,item_code:p.id,item_name:l.name,qty:l.qty,rate:l.price,amount:round(l.price*l.qty),uom:p.unit||'حبة',is_stock_item:b?0:p.isStockItem===false?0:1});
   if(b){const pricing=HECOfferEngine.allocate(b.total,b.rows);for(const row of pricing.rows){const component=HEC.products.find(p=>p.id===row.id);if(!component||component.bundleId)throw Error('مكون الحزمة غير متاح');packed_items.push({parent_item:p.id,parent_detail_docname:name,item_code:row.id,item_name:component.name,variant:row.variant,qty:row.qty*l.qty,uom:component.unit||'حبة',rate:row.unitPrice,amount:round(row.amount*l.qty)})}}
  }
  return {doctype,items,packed_items,total:round(items.reduce((n,r)=>n+r.amount,0))};
 }
 function sanitize(raw,lines){if(!raw||!Array.isArray(raw.packed_items)||!Array.isArray(raw.items))return null;const copy={doctype:['Sales Order','Sales Invoice'].includes(raw.doctype)?raw.doctype:'Sales Order',items:[],packed_items:[],total:0};const text=(x,n)=>HECStore.text(x,n);for(const [i,l] of lines.entries()){const r=raw.items[i];if(!r||r.item_code!==l.id||r.qty!==l.qty||r.rate!==l.price)return null;copy.items.push({name:'local-line-'+(i+1),item_code:l.id,item_name:l.name,qty:l.qty,rate:l.price,amount:round(l.qty*l.price),uom:text(r.uom,40),is_stock_item:r.is_stock_item===0?0:1})}for(const r of raw.packed_items.slice(0,1000)){const parent=copy.items.find(p=>p.name===r.parent_detail_docname&&p.item_code===r.parent_item&&p.is_stock_item===0);if(!parent||!/^[A-Za-z0-9_-]{1,80}$/.test(r.item_code)||!Number.isFinite(r.qty)||r.qty<=0||r.qty>998001||!Number.isFinite(r.amount)||r.amount<0||!Number.isFinite(r.rate)||r.rate<0)return null;copy.packed_items.push({parent_item:parent.item_code,parent_detail_docname:parent.name,item_code:r.item_code,item_name:text(r.item_name,180),variant:text(r.variant,80),qty:r.qty,rate:r.rate,amount:round(r.amount),uom:text(r.uom,40)})}copy.total=round(copy.items.reduce((n,r)=>n+r.amount,0));return copy}
 return Object.freeze({project,sanitize});
})();
