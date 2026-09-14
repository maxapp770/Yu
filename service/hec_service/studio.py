"""Adaptive design documents and delegated Item photos. No custom ERP DocTypes."""
import base64,hashlib,io,json,math,re,secrets,time,unicodedata
from copy import deepcopy
from .core import fail,Error,text,utc,encode
from .rules import image_id,image_path
from .reels import description_links

def photo_bytes(data):
    try:
        from PIL import Image,ImageOps
        if not isinstance(data,str) or len(data)>7100000:raise ValueError()
        raw=base64.b64decode(data,validate=True)
        if len(raw)>5000000:raise ValueError()
        im=Image.open(io.BytesIO(raw));fmt=im.format
        if fmt not in ('PNG','JPEG') or im.width*im.height>16000000 or max(im.size)>8192:raise ValueError()
        im.load();im=ImageOps.exif_transpose(im);out=io.BytesIO()
        clean=Image.new('RGBA' if fmt=='PNG' else 'RGB',im.size);clean.paste(im.convert(clean.mode));clean.save(out,format=fmt,**({'quality':93} if fmt=='JPEG' else {}))
        raw=out.getvalue()
        if len(raw)>5000000:raise ValueError()
        return raw,'png' if fmt=='PNG' else 'jpg'
    except Exception:fail(422,'اختر صورة JPG أو PNG صالحة حتى ٥ ميجابايت و١٦ مليون بكسل.')

def design_valid(d):
    def walk(v,depth=0):
        if depth>8:fail(422,'تصميم متداخل أكثر من المسموح.')
        if isinstance(v,dict):
            if len(v)>100 or any(k in ('__proto__','constructor','prototype') for k in v):fail(422,'تصميم غير صالح.')
            for x in v.values():walk(x,depth+1)
        elif isinstance(v,list):
            if len(v)>100:fail(422,'عناصر كثيرة.')
            for x in v:walk(x,depth+1)
        elif isinstance(v,str) and (len(v)>4000 or re.search(r'[<>\x00-\x08]',v)):fail(422,'استخدم نصاً عادياً في التصميم.')
        elif isinstance(v,(float,int)) and (not math.isfinite(v) or abs(v)>1e9):fail(422,'رقم غير صالح.')
    walk(d)
    if not isinstance(d,dict) or len(encode(d))>80000:fail(422,'التصميم كبير أو غير صالح.')
    w=d.get('width');h=d.get('height');layers=d.get('layers')
    if type(w)!=int or type(h)!=int or not 240<=w<=4096 or not 160<=h<=4096 or w*h>8000000 or not isinstance(layers,list) or len(layers)>40:fail(422,'أبعاد التصميم أو طبقاته غير صالحة.')
    for l in layers:
        if not isinstance(l,dict) or l.get('type') not in ('image','text','rect','ellipse','star','triangle','line'):fail(422,'نوع طبقة غير صالح.')
        for k,lo,hi in [('x',0,1),('y',0,1),('w',0.000001,1),('h',0.000001,1),('opacity',0,1),('font',8,300),('border',0,30),('radius',0,500),('rotation',-360,360)]:
            if type(l.get(k)) not in (int,float) or not lo<=l[k]<=hi:fail(422,'حدود طبقة غير صالحة.')
        if l['type']=='image' and not re.fullmatch(r'[A-Za-z0-9_-]+\.jpg',l.get('image','')):fail(422,'اختر صورة من مكتبة المتجر.')
        if any(not re.fullmatch(r'(#[a-fA-F0-9]{6}|transparent)',l.get(k,'')) for k in ('color','fill','stroke')):fail(422,'لون غير صالح.')
    return deepcopy(d)

class Studio:
    def media_granted(self,identity):
        a=self.store.get('media-access',{'enabled':True,'users':[],'roles':[]})
        return a.get('enabled') is not False and ('System Manager' in identity['roles'] or identity['user'] in a['users'] or bool(set(identity['roles'])&set(a['roles'])))
    def media_actor(self,session):
        if not session or session.get('kind')!='admin':fail(401,'سجّل الدخول الإداري.')
        erp=self.client(session['auth']);who=erp.identity()
        if who['user']!=session['user'] or not self.media_granted(who):fail(403,'ليس لديك إذن إدارة صور الأصناف.')
        return erp,who
    def media_access(self,op,a,erp,actor):
        current=self.store.get('media-access',dict(enabled=True,users=[],roles=[],version='1'))
        blocked={'All','Guest','Customer','Supplier','System Manager','Desk User'}
        if op.endswith('.save'):
            if type(a.get('enabled'))!=bool or not isinstance(a.get('users'),list) or len(a['users'])>100 or not isinstance(a.get('roles'),list) or len(a['roles'])>30:fail(422,'إعداد الصلاحيات غير صالح.')
            for u in a['users']:
                if not isinstance(u,str) or len(u)>140:fail(422,'المستخدم غير صالح.')
                doc=erp.get('User',u)
                if not doc.get('enabled') or doc.get('user_type')!='System User':fail(422,'اختر مستخدماً إدارياً نشطاً.')
            for role in a['roles']:
                if not isinstance(role,str) or role in blocked or erp.get('Role',role).get('disabled'):fail(422,'اختر دوراً إدارياً مخصصاً.')
            with self.store.tx() as db:
                current=self.store.get('media-access',current,db)
                if str(a.get('version'))!=current['version']:fail(409,'تغيرت الصلاحيات؛ حدّث الصفحة.')
                current=dict(enabled=a['enabled'],users=list(dict.fromkeys(a['users'])),roles=list(dict.fromkeys(a['roles'])),version=str(int(current['version'])+1));self.store.put('media-access',current,db);self.store.audit(actor,'media.access','Item photos',db)
        q=text(a.get('q'),100)
        return dict(**current,availableUsers=erp.list('User',['name','full_name'],{'enabled':1,'user_type':'System User',**({'name':['like','%'+q+'%']} if q else {})},50,order='name asc'),availableRoles=[r for r in erp.list('Role',['name'],{'disabled':0},100,order='name asc') if r['name'] not in blocked])
    def photo_id(self,path):
        if not image_path(path):return 'logo.jpg'
        ident=image_id(path)
        with self.store.tx() as db:db.execute('INSERT OR REPLACE INTO images VALUES(?,?,?)',(ident,path,self.store.get('channel',db=db)['epoch']))
        return ident
    def photo_changed(self,actor,action,code):
        with self.store.tx() as db:
            db.execute('DELETE FROM cache');ch=self.store.get('channel',db=db);ch['revision']+=1;self.store.put('channel',ch,db);self.store.audit(actor,action,code,db)
    def item_media(self,op,a,erp,actor):
        if op.endswith('.search'):
            q=text(a.get('q'),100);rows=erp.list('Item',['name','item_name','image','modified'],{'disabled':0},30,order='modified desc',or_filters=[['Item','name','like','%'+q+'%'],['Item','item_name','like','%'+q+'%'],['Item Barcode','barcode','=',q]] if q else None)
            items=[dict(id=self.reference(r['name']),code=r['name'],name=r['item_name'],image=self.photo_id(r.get('image'))) for r in rows];return dict(items=items,_images=self.image_map(items))
        code=self.resolve_code(a.get('id'));doc=erp.get('Item',code)
        if doc.get('disabled'):fail(422,'الصنف متوقف.')
        if not op.endswith('.list'):
            for doctype,name,perm in [('Item',code,'write'),('File','','create')]:
                if not (erp.method('frappe.client.has_permission',dict(doctype=doctype,docname=name,perm_type=perm)) or {}).get('has_permission'):fail(403,'يلزم إذن تعديل الصنف وإنشاء مرفقات File.')
        files=erp.list('File',['name','file_name','file_url','is_private','attached_to_name','attached_to_doctype'],dict(attached_to_doctype='Item',attached_to_name=code,is_private=0),100)
        files=[f for f in files if not f.get('is_private') and image_path(f.get('file_url')) and f.get('attached_to_name')==code and f.get('attached_to_doctype')=='Item']
        if op.endswith('.list'):
            images=[dict(file=f['name'],name=f['file_name'],image=self.photo_id(f['file_url']),main=f['file_url']==doc.get('image')) for f in files];return dict(id=a['id'],code=code,name=doc.get('item_name',code),version=doc.get('modified'),images=images,_images=self.image_map(images))
        if op.endswith('.main'):
            f=next((f for f in files if f['name']==a.get('file')),None)
            if not f:fail(422,'اختر مرفق صورة تابعاً لهذا الصنف.')
            if a.get('version')!=doc.get('modified'):fail(409,'تغير الصنف؛ حدّث الصور قبل تغيير الرئيسية.')
            erp.method('frappe.client.set_value',dict(doctype='Item',name=code,fieldname='image',value=f['file_url']),True);self.photo_changed(actor,'item.photo.main',code);image=self.photo_id(f['file_url']);return dict(ok=True,image=image,_images={image:'/v1/images/'+image})
        if not op.endswith('.upload'):fail(404,'إجراء الصور غير معروف.')
        raw,ext=photo_bytes(a.get('data'));fingerprint=hashlib.sha256(raw).hexdigest()[:12]
        base=re.sub(r'[^\w-]+','_',unicodedata.normalize('NFKC',doc.get('item_name') or code),flags=re.UNICODE).strip('_')[:35];short=re.sub(r'[^A-Za-z0-9_-]','_',code)[:24];filename=f'{base}_{short}_{fingerprint}.{ext}'
        key='item-photo:'+str(self.store.get('channel')['epoch'])+':'+hashlib.sha256((code+fingerprint).encode()).hexdigest();f=next((f for f in files if f['file_name']==filename),None)
        if not f:
            with self.store.tx() as db:
                if self.store.get(key,db=db):fail(409,'رفع سابق لهذه الصورة لم يُحسم. حدّث المرفقات قبل إعادة المحاولة.')
                self.store.put(key,dict(state='sending',at=utc(),user=actor),db)
            try:value=erp.upload_file(raw,filename,'image/png' if ext=='png' else 'image/jpeg','Item',code)
            except Error as exc:
                if exc.status in (400,401,403,413,415,417,422):
                    with self.store.tx() as db:db.execute('DELETE FROM kv WHERE key=?',(key,))
                raise
            if not isinstance(value,dict) or not value.get('name'):fail(502,'لم يتأكد المرفق؛ حدّث صور الصنف.')
            f=erp.get('File',value['name'])
            if f.get('attached_to_doctype')!='Item' or f.get('attached_to_name')!=code or f.get('is_private') or not image_path(f.get('file_url')):fail(502,'لم يُربط المرفق بالصنف المطلوب؛ راجع النظام.')
        self.store.put(key,dict(state='complete',file=f['name'],at=utc()));self.photo_changed(actor,'item.photo.upload',code);image=self.photo_id(f['file_url']);return dict(ok=True,file=f['name'],name=f['file_name'],image=image,_images={image:'/v1/images/'+image})
    def studio(self,op,a,erp,actor):
        epoch=self.store.get('channel')['epoch'];key='studio:'+str(epoch)
        if op=='admin.studio.product':return self.studio_product(a,erp)
        if op=='admin.studio.list':return {'rows':self.store.get(key,[])}
        if op not in ('admin.studio.save','admin.studio.delete'):fail(404,'إجراء تصميم غير معروف.')
        design=design_valid(a.get('design')) if op.endswith('.save') else None
        with self.store.tx() as db:
            rows=self.store.get(key,[],db);old=next((r for r in rows if r['id']==a.get('id')),None)
            if a.get('id') and (not old or old['version']!=str(a.get('version'))):fail(409,'تغير التصميم؛ حدّث مكتبة التصاميم.')
            if op.endswith('.delete'):
                if not old:fail(404,'التصميم غير موجود.')
                rows.remove(old);result={'ok':True}
            else:
                if not old and len(rows)>=50:fail(422,'مكتبة التصاميم ممتلئة؛ احذف تصميماً قديماً.')
                result=dict(id=old['id'] if old else secrets.token_hex(16),version=str(int(old['version'])+1) if old else '1',design=design,title=text(a.get('title') or design.get('title'),140),epoch=epoch,updatedAt=utc(),actor=actor)
                if old:rows[rows.index(old)]=result
                else:rows.append(result)
            self.store.put(key,rows,db);self.store.audit(actor,op,result.get('id',a.get('id','')),db)
        return result
    def studio_product(self,a,erp):
        settings=self.store.get('settings')['values']
        if not settings['features'].get('catalog'):fail(403,'فعّل قراءة الأصناف أولاً.')
        code=self.resolve_code(a.get('id'));doc=erp.get('Item',code)
        if doc.get('disabled'):fail(422,'الصنف متوقف.')
        lists=erp.list('Price List',['name','currency'],dict(selling=1,enabled=1),100,order='name asc');pl=a.get('price_list') or settings['price_list']
        if pl not in [r['name'] for r in lists]:fail(403,'قائمة السعر غير متاحة.')
        price_list=erp.get('Price List',pl);uoms=[dict(uom=u['uom'],conversion_factor=u.get('conversion_factor',1)) for u in doc.get('uoms',[])]
        if doc.get('stock_uom') not in [r['uom'] for r in uoms]:uoms.insert(0,dict(uom=doc.get('stock_uom'),conversion_factor=1))
        unit=a.get('uom') or doc.get('sales_uom') or doc.get('stock_uom')
        if unit not in [r['uom'] for r in uoms]:fail(422,'الوحدة غير موجودة للصنف.')
        prices=erp.list('Item Price',['name','price_list_rate','uom','currency','valid_from','valid_upto','customer','supplier','batch_no'],dict(item_code=code,price_list=pl,selling=1),100,order='valid_from desc, modified desc');today=utc()[:10]
        price=next((p for p in prices if (p.get('uom')==unit or not p.get('uom') and unit==doc.get('stock_uom')) and not any(p.get(k) for k in ('customer','supplier','batch_no')) and (not p.get('valid_from') or p['valid_from']<=today) and (not p.get('valid_upto') or p['valid_upto']>=today)),None)
        images=[];warnings=[]
        if image_path(doc.get('image')):images.append(dict(id=self.photo_id(doc['image']),label='الصورة الرئيسية'))
        try:
            for f in erp.list('File',['name','file_name','file_url','is_private'],dict(attached_to_doctype='Item',attached_to_name=code,is_private=0),100):
                if not f.get('is_private') and image_path(f.get('file_url')):
                    ident=self.photo_id(f['file_url'])
                    if ident not in [im['id'] for im in images]:images.append(dict(id=ident,label=f.get('file_name','صورة')))
        except Error:warnings.append('تعذر قراءة المرفقات ضمن صلاحيات الحساب.')
        components=[]
        if not doc.get('is_stock_item',1) and settings['features'].get('bundles'):
            try:
                rows=erp.list('Product Bundle',['name'],dict(new_item_code=code,disabled=0),1)
                if rows:components=[dict(code=x['item_code'],name=x.get('description') or x['item_code'],qty=x['qty']) for x in erp.get('Product Bundle',rows[0]['name']).get('items',[])]
            except Error:warnings.append('تعذر قراءة مكونات الصنف المجمع.')
        company={}
        try:
            co=erp.get('WhatsApp Share Settings',settings['company'])
            company={k:text(co.get(k),1000) for k in ('company_name','company_phone','company_whatsapp','company_address','company_map_link','facebook_link','instagram_link','tiktok_link','community_link','custom_hashtags')};company['templates']=[]
        except Error:pass
        if not images:images=[dict(id='logo.jpg',label='الشعار الافتراضي')]
        return dict(id=a['id'],code=code,name=doc.get('item_name',code),description=doc.get('description',''),image=images[0]['id'],images=images,unit=unit,uoms=uoms,price=float(price['price_list_rate']) if price else None,price_list=pl,price_lists=lists,currency=price_list.get('currency','YER'),components=components,company=company,warnings=warnings,_images=self.image_map(images))
