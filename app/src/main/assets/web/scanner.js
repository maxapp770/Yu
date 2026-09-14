'use strict';
window.HECScanner=(()=>{
 let pending=null,stream=null,timer=null,busy=false;
 const valid=x=>typeof x==='string'&&x.trim().length>0&&x.trim().length<=200&&!/[\x00-\x1f]/.test(x.trim());
 function stop(){clearTimeout(timer);if(stream)stream.getTracks().forEach(t=>t.stop());stream=null;busy=false}
 function receive(code){const task=pending;pending=null;stop();if(!task)return;if(code===null){task.cancel&&task.cancel();return}if(!valid(code)){task.cancel&&task.cancel('لم تُقرأ شفرة صالحة');return}task.done(code.trim())}
 function arm(done,cancel){stop();pending={done,cancel};return '/native-scan'}
 async function browser(video,status){if(!pending)return;try{if(!('BarcodeDetector' in window))throw Error('قراءة الكاميرا متاحة في تطبيق أندرويد. يمكنك إدخال الرمز يدوياً هنا.');const wanted=['ean_13','ean_8','upc_a','upc_e','code_128','code_39','code_93','itf','codabar','qr_code','data_matrix','aztec','pdf417'];let formats=wanted;try{if(BarcodeDetector.getSupportedFormats){const supported=await BarcodeDetector.getSupportedFormats();formats=wanted.filter(x=>supported.includes(x));}}catch{}const detector=new BarcodeDetector({formats});const s=await navigator.mediaDevices.getUserMedia({video:{facingMode:{ideal:'environment'},width:{ideal:1280}},audio:false});if(!pending){s.getTracks().forEach(t=>t.stop());return}stream=s;video.srcObject=s;await video.play();status.textContent='وجّه الكاميرا إلى الباركود';async function frame(){if(!stream||!pending)return;try{const codes=await detector.detect(video);if(codes.length){receive(codes[0].rawValue);return}}catch{}timer=setTimeout(frame,250)}frame()}catch(e){stop();status.textContent=e.name==='NotAllowedError'?'لم تسمح بالكاميرا. يمكنك إدخال الرمز يدوياً.':e.message}}
 function cancel(){receive(null)}
 document.addEventListener('visibilitychange',()=>{if(document.hidden&&!/HECAndroid\//.test(navigator.userAgent||''))cancel()});
 return Object.freeze({arm,receive,cancel,stop,browser,active:()=>!!pending,valid});
})();
