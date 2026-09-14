'use strict';
window.HECNative=(()=>{
 let seq=0;const pending=new Map();
 const available=()=>!!window.HECDevice&&HECBuild.role==='admin';
 async function transfer(mode,files,text=''){
  if(!available())throw Error('حفظ ومشاركة الملفات غير متاحين في هذه البيئة');
  if(pending.size)throw Error('أكمل نافذة الحفظ أو المشاركة الحالية أولاً');
  if(!files.length||files.length>9)throw Error('اختر من صورة إلى ٩ صور في الدفعة');
  if(files.reduce((sum,file)=>sum+file.size,0)>20000000)throw Error('حجم الصور كبير؛ شارك دفعة أصغر من ٢٠ ميجابايت');
  const rows=[];for(const f of files){if(f.size>5000000||!['image/jpeg','image/png'].includes(f.type))throw Error('اختر JPG أو PNG حتى ٥ ميجابايت');const bytes=new Uint8Array(await f.arrayBuffer());let raw='';for(let i=0;i<bytes.length;i+=16384)raw+=String.fromCharCode(...bytes.subarray(i,i+16384));rows.push({name:f.name||'HEC-design.jpg',type:f.type,data:btoa(raw)});}
  return new Promise((resolve,reject)=>{const id='n'+(++seq),timer=setTimeout(()=>{pending.delete(id);reject(Error('لم تتأكد نتيجة الحفظ؛ راجع المكان الذي اخترته'))},600000);pending.set(id,{resolve,reject,timer});try{HECDevice.transfer(id,mode,JSON.stringify({files:rows,text:String(text).slice(0,6000)}))}catch(e){clearTimeout(timer);pending.delete(id);reject(e)}});
 }
 function receive(id,ok,message){const p=pending.get(id);if(!p)return;pending.delete(id);clearTimeout(p.timer);if(ok)p.resolve(message);else p.reject(Error(message));}
 return {available,active:()=>pending.size>0,receive,save:(blob,name)=>transfer('save',[new File([blob],name,{type:blob.type})]),share:(files,text)=>transfer('share',files,text)};
})();
