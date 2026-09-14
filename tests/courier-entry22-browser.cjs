// Regression: the customer packaging step must preserve the courier destination.
// Exercises only local preview data; no ERP authentication or writes are performed.
const {chromium}=require('playwright');
const http=require('node:http'),fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
const root=path.resolve(__dirname,'../build/variants/customer/assets/web');
const out=path.resolve(__dirname,'../build/review23');
(async()=>{
 fs.mkdirSync(out,{recursive:true});
 const server=http.createServer((req,res)=>{
  const file=path.resolve(root,'.'+req.url.split('?')[0]);
  if(!file.startsWith(root+'/')){res.writeHead(404).end();return;}
  try{res.setHeader('Content-Type',file.endsWith('.js')?'text/javascript':file.endsWith('.css')?'text/css':file.endsWith('.jpg')?'image/jpeg':'text/html');res.end(fs.readFileSync(file));}catch{res.writeHead(404).end();}
 }).listen(0,'127.0.0.1');
 await new Promise(r=>server.once('listening',r));
 const browser=await chromium.launch({executablePath:process.env.HEC_CHROME_BIN,headless:true,args:['--no-sandbox']});
 const page=await browser.newPage({viewport:{width:390,height:844},isMobile:true,hasTouch:true}),errors=[],checks=[];
 page.on('pageerror',e=>errors.push(e.message));
 const ok=s=>{checks.push(s);console.log('PASS '+s)};
 try{
  await page.goto('http://127.0.0.1:'+server.address().port+'/index.html#account');
  for(const width of [320,390,460]){
   await page.setViewportSize({width,height:844});
   const link=page.locator('.account-tools [data-go=courier-login]');
   await link.waitFor();assert.equal(await link.count(),1);await link.scrollIntoViewIfNeeded();
   assert.match(await link.innerText(),/الاتصال بحساب الموصّل/);
   const rect=await link.boundingBox();assert(rect.height>=48);assert(rect.x>=0&&rect.x+rect.width<=width);
   assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false);
   assert.equal(await page.locator('.account-tools [data-go=erp-account]').count(),1);
   if(width===390)await page.screenshot({path:out+'/account-courier-link.png'});
  }
  ok('Courier and store account destinations remain separately reachable at 320/390/460px');
  await page.locator('.account-tools [data-go=erp-account]').click();
  const reviewLink=page.locator('.erp-review-link');await reviewLink.waitFor();
  assert.equal(await reviewLink.getAttribute('href'),'https://hec-service-review.fadhel-motaher.chatgpt.site/customer/index.html#erp-account');
  assert.equal(await page.locator('#erp-customer-login').count(),0);
  assert.match(await page.locator('.erp-panel').innerText(),/لا يلزم تثبيت HEC Bridge/);
  await page.locator('.erp-panel [data-go=account]').click();
  ok('Unconfigured Android points to connected browser review without collecting credentials or requesting the old add-on');
  await page.locator('.account-tools [data-go=courier-login]').click();
  await page.locator('.courier-login').waitFor();assert.match(await page.locator('.courier-login .notice').innerText(),/الخدمة المستقلة/);
  await page.locator('[data-go=account]').click();await page.locator('.account-tools').waitFor();
  await page.evaluate(()=>location.hash='courier-home');await page.locator('.courier-login').waitFor();
  assert.equal(await page.locator('.courier-stats').count(),0);
  ok('The link opens courier access; direct navigation cannot skip explicit preview entry');
  await page.locator('.courier-login summary').click();
  assert.equal(await page.locator('#courier-live-login').count(),0);
  assert.equal(await page.locator('a[href$="#courier-login"]').count(),1);
  assert.equal(await page.evaluate(()=>Courier.canManage()),false);
  ok('Unconfigured native courier offers connected browser review and does not collect credentials');
  await page.locator('[data-action=courier-enter]').click();await page.locator('.courier-stats').waitFor();
  assert.match(await page.locator('.demo-ribbon').first().innerText(),/معاينة محلية/);
  assert.equal(await page.evaluate(()=>Management.canManage()),false);
  assert.equal(await page.evaluate(()=>typeof HECAdminConfig),'undefined');
  await page.locator('.courier-nav [data-go=courier-deliveries]').click();await page.locator('.delivery-list').waitFor();
  await page.locator('.courier-nav [data-go=courier-account]').click();
  await page.locator('[data-action=courier-logout]').click();
  await page.locator('[data-action=courier-confirm-logout]').click();await page.locator('.courier-login').waitFor();
  await page.evaluate(()=>location.hash='courier-home');assert.equal(await page.evaluate(()=>Courier.canManage()),false);
  ok('Preview delivery navigation and logout work without granting administrative access');
  await page.evaluate(()=>location.hash='admin');await page.waitForFunction(()=>location.hash==='#home');
  assert.deepEqual(errors,[]);ok('Customer administrator route remains unavailable; no browser errors');
  fs.writeFileSync(out+'/result.json',JSON.stringify({checks,errors,mode:'packaged customer UI, local courier preview only'},null,2));
 }finally{await browser.close();server.close();}
})().catch(e=>{console.error(e);process.exitCode=1});
