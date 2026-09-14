import base64,hashlib,json,os,re,secrets,time
from pathlib import Path
from . import __version__
from .core import Store,Error,fail,encode,digest,utc,text,password_matches
from .erp import ERP,origin
from .content import Content
from .catalog import Catalog
from .orders import Orders
from .reports import Reports
from .delivery import Delivery
from .reels import Reels
from .studio import Studio
from .reel_social import ReelSocial
from .rules import SCHEMA,READONLY,OPTION_TYPES,FEATURES,IMPLEMENTED,validate_settings,flag,app_id,image_path

class Service(Content,Catalog,Orders,Reports,Delivery,Reels,Studio,ReelSocial):
    def __init__(self,store,erp_origin='https://erptest.wahatalhaitham.com',allowed_hosts=None,erp_factory=ERP,timezone='Asia/Aden'):
        self.store=store;self.default_origin=erp_origin;self.allowed_hosts=allowed_hosts or ['erptest.wahatalhaitham.com'];self.erp_factory=erp_factory;self.timezone=timezone
        with self.store.tx() as db:
            if not db.execute("SELECT 1 FROM content WHERE module='reels-settings'").fetchone():self.save_table('reels-settings',json.loads((Path(__file__).parent/'seed.json').read_text())['reels-settings'],db)
        origin(erp_origin,self.allowed_hosts);self.media=store.path.parent/'media';self.media.mkdir(exist_ok=True)

    def erp_origin(self):
        value=self.store.get('integration')
        return self.store.open(value)['origin'] if value else self.default_origin
    def client(self,auth,base=None):return self.erp_factory(base or self.erp_origin(),auth,self.allowed_hosts)
    def integration_client(self):
        value=self.store.get('integration')
        if not value:fail(503,'لم يُفعّل اتصال الخدمة بـERPNext بعد.')
        config=self.store.open(value)
        return self.client(config['auth'],config['origin'])

    def bootstrap(self):
        ch=self.store.get('channel')
        return dict(api_version=2,server_version=__version__,service='hec-standalone',store_id=ch['store_id'],revision=str(ch['revision']),publication=ch['publication'],maintenance=bool(ch['maintenance']),integration_epoch=ch['epoch'],refresh_seconds=60)

    def admin(self,session,manager=True):
        if not session or session.get('kind')!='admin':fail(401,'سجّل الدخول بحسابك الإداري.')
        erp=self.client(session['auth']);identity=erp.identity()
        if identity['user']!=session['user']:fail(403,'هوية الحساب لا تطابق الجلسة.')
        roles=identity['roles'];is_manager='System Manager' in roles
        report_roles=self.store.get('access')['report_roles']
        if manager and not is_manager or not manager and not (is_manager or set(roles)&set(report_roles)):fail(403,'الحساب لا يملك الدور المسموح لهذا الإجراء.')
        return erp,identity

    def context(self,session):
        if not session:fail(401,'سجّل الدخول أولاً.')
        if session['kind']=='courier':return self.courier_context(session)
        if session['kind']=='admin':
            erp=self.client(session['auth']);identity=erp.identity()
            if identity['user']!=session['user']:fail(403,'هوية الجلسة غير مطابقة.')
            manager='System Manager' in identity['roles'];reports=manager or bool(set(identity['roles'])&set(self.store.get('access')['report_roles']));media=self.media_granted(identity)
            if not reports and not media:fail(403,'أُلغيت صلاحية هذا الحساب.')
            return dict(authenticated=True,**identity,can_manage=manager,can_reports=reports,can_media=media,customer=None,server_version=__version__)
        account=self.customer_account(session,False)
        return dict(authenticated=True,user=account['user'],name=account['name'],roles=[],customer=account['customer'],company=account['company'],server_version=__version__)

    def login(self,a):
        if a.get('app_role')=='admin':
            erp=self.client({});identity=erp.login(a)
            allowed='System Manager' in identity['roles'] or bool(set(identity['roles'])&set(self.store.get('access')['report_roles'])) or self.media_granted(identity)
            if not allowed:fail(403,'حسابك لا يملك دور مدير النظام أو أحد أدوار التقارير المسموحة.')
            data=dict(kind='admin',user=identity['user'],auth=erp.auth)
            token=self.store.session(data)
            return {**self.context(data),'session_token':token}
        if a.get('kind')=='token':fail(403,'حساب العميل يستخدم كلمة مروره الشخصية فقط.')
        user=str(a.get('user','')).strip().lower();password=a.get('password','')
        if len(user)>160 or not isinstance(password,str) or len(password)>128:fail(401,'بيانات الدخول غير صحيحة.')
        self.store.throttle('customer-login:'+hashlib.sha256(user.encode()).hexdigest(),10,300)
        rows=self.store.rows('SELECT * FROM customers WHERE user=?',(user,))
        saved=rows[0]['password'] if rows else '00'*16+':'+'00'*64
        matches=password_matches(password,saved)
        if not rows or not matches or not rows[0]['enabled']:fail(401,'بيانات الدخول غير صحيحة أو الحساب متوقف.')
        data=dict(kind='customer',user=user);context=self.context(data);token=self.store.session(data)
        return {**context,'session_token':token}

    def capabilities(self):
        settings=self.store.get('settings')['values']
        notes={'catalog':'كتالوج من ERPNext مع نسخة محفوظة للانقطاع','stock':'التوفر من Bin؛ لا يمثل حجز المخزون','images':'صور الخدمة وملفات ERP العامة','bundles':'Product Bundle والصنف الرئيسي وجدول packed_items','orders':'Sales Order مسودة مع تسعير النظام ومراجعة نتائج الإرسال','notifications':'إشعارات داخل التطبيق؛ Push يحتاج مزود إرسال منفصلاً','order_submit':'الاعتماد الآلي يحتاج مطابقة سير العمل؛ مسودات البيع متاحة'}
        return {k:dict(supported=k in IMPLEMENTED,enabled=bool(settings['features'].get(k)),reason=notes.get(k,'الدورة التشغيلية أو المالية لم تُنفذ على الخدمة بعد')) for k in FEATURES}

    def settings(self):return {**self.store.get('settings'),'server_version':__version__,'capabilities':self.capabilities()}

    def option_rows(self,a,erp):
        doctype=a.get('doctype');q=text(a.get('q'),100);start=max(0,min(int(a.get('cursor') or 0),10000));filters={}
        if doctype not in set(OPTION_TYPES.values())|{'Customer'}:fail(403,'هذا النوع غير متاح في قوائم الربط.')
        if doctype=='User':
            users=[dict(name=r['user']) for r in self.store.rows('SELECT user FROM customers WHERE user LIKE ? LIMIT 50',('%'+q.lower()+'%',))]
            config=self.store.get('integration')
            if config:
                name=self.store.open(config)['user']
                if not q or q.lower() in name.lower():users.insert(0,{'name':name})
            return dict(items=users,has_more=False)
        if doctype in ('Warehouse','Cost Center'):
            filters['is_group']=0
        if doctype=='Price List':filters.update(enabled=1,selling=1)
        if doctype in ('Warehouse','Cost Center','Sales Taxes and Charges Template'):
            if not a.get('company'):return dict(items=[],has_more=False)
            filters['company']=a['company']
        if doctype=='Customer':filters['disabled']=0
        if q:filters['name']=['like','%'+q+'%']
        rows=erp.list(doctype,['name'],filters,51,start,'name asc')
        if self.store.get('integration') and rows:
            permitted=self.integration_client().list(doctype,['name'],{**filters,'name':['in',[r['name'] for r in rows]]},51,order='name asc')
            names={r['name'] for r in permitted};rows=[r for r in rows if r['name'] in names]
        return dict(items=rows[:50],has_more=len(rows)>50,next_cursor=start+50 if len(rows)>50 else None)

    def save_settings(self,a,actor,erp):
        try:value=validate_settings(a.get('values'))
        except (TypeError,ValueError):fail(422,'تحقق من إعدادات الربط والخدمات المتاحة.')
        integration=self.store.get('integration')
        if not integration:fail(422,'اختبر حساب التكامل وفعّله أولاً.')
        config=self.store.open(integration)
        if value['integration_user']!=config['user']:fail(422,'مستخدم التكامل يأتي من المفاتيح التي اختبرتها؛ لا يمكن انتحال مستخدم آخر.')
        service=self.integration_client()
        for key,doctype in OPTION_TYPES.items():
            if value.get(key) and key!='integration_user':
                erp.get(doctype,value[key]);doc=service.get(doctype,value[key])
                if key in ('warehouse','tax_template','selling_cost_center') and doc.get('company')!=value['company']:fail(422,'الاختيار تابع لشركة أخرى.')
                if key in ('warehouse','selling_cost_center') and doc.get('is_group'):fail(422,'اختر سجلاً غير تجميعي.')
                if key=='price_list' and (not doc.get('selling') or not doc.get('enabled') or doc.get('currency')!=value['currency']):fail(422,'اختر قائمة بيع مفعلة ومتوافقة مع العملة.')
        requirements={'catalog':[('Item','read'),('Item Price','read')],'stock':[('Bin','read')],'bundles':[('Product Bundle','read')],'orders':[('Sales Order','create'),('Sales Order','read')],'delivery':[('Sales Order','read'),('Delivery Note','read')]}
        for feature,rights in requirements.items():
            if value['features'][feature]:
                for doctype,permission in rights:
                    check=service.method('frappe.client.has_permission',{'doctype':doctype,'docname':'','perm_type':permission})
                    if not check or not check.get('has_permission'):fail(403,'حساب التكامل يفتقد إذن '+permission+' على '+doctype)
        with self.store.tx() as db:
            current=self.store.get('settings',db=db);ch=self.store.get('channel',db=db)
            if str(current['version'])!=str(a.get('version')):fail(409,'تغيرت الإعدادات؛ حدّثها قبل الحفظ.')
            sensitive=any(current['values'].get(k)!=value.get(k) for k in ('company','currency','price_list','warehouse'))
            if sensitive and self.delivery_open():fail(409,'أغلق التوصيلات وسوّ العهد النقدية قبل تغيير الربط.')
            if sensitive and not ch['maintenance']:fail(409,'شغّل الصيانة قبل تغيير الشركة أو العملة أو القائمة أو المخزن.')
            if sensitive and db.execute("SELECT id FROM requests WHERE state IN ('validating','sending','unknown') LIMIT 1").fetchone():fail(409,'راجع الطلبات المعلقة قبل تغيير الربط.')
            self.store.put('settings',dict(values=value,version=str(int(current['version'])+1)),db)
            ch['revision']+=1;self.store.put('channel',ch,db);db.execute('DELETE FROM cache')
            self.store.audit(actor,'settings.save','store',db)
        return self.settings()

    def integration_status(self):
        config=self.store.get('integration');ch=self.store.get('channel')
        return dict(configured=bool(config),origin=self.erp_origin(),user=self.store.open(config)['user'] if config else '',epoch=ch['epoch'],revision=str(ch['revision']),maintenance=ch['maintenance'],allowed_hosts=self.allowed_hosts)

    def test_integration(self,a,actor):
        base=origin(a.get('erp_origin') or self.erp_origin(),self.allowed_hosts);erp=self.client({},base)
        identity=erp.login({**a,'kind':'token'});choices={}
        for doctype in ('Company','Price List','Warehouse'):
            try:choices[doctype]=erp.list(doctype,['name'],{},50,order='name asc')
            except Error as exc:choices[doctype]={'status':exc.status}
        ticket=secrets.token_urlsafe(32)
        with self.store.tx() as db:
            db.execute('DELETE FROM candidates WHERE expires<?',(time.time(),))
            db.execute('INSERT INTO candidates VALUES(?,?,?,?)',(hashlib.sha256(ticket.encode()).hexdigest(),actor,self.store.seal(dict(origin=base,user=identity['user'],auth=erp.auth)),time.time()+600))
        return dict(ticket=ticket,origin=base,user=identity['user'],choices=choices,expires_in=600,requires_migration=base!=self.erp_origin())

    def activate_integration(self,a,actor):
        if self.delivery_open():fail(409,'أغلق التوصيلات وسوّ العهد النقدية قبل نقل بيانات التكامل.')
        ident=hashlib.sha256(str(a.get('ticket','')).encode()).hexdigest()
        with self.store.tx() as db:
            candidate=db.execute('SELECT * FROM candidates WHERE id=? AND actor=?',(ident,actor)).fetchone();ch=self.store.get('channel',db=db)
            if not candidate or candidate['expires']<time.time():fail(409,'انتهت نتيجة الاختبار؛ اختبر المفاتيح مجدداً.')
            if str(ch['revision'])!=str(a.get('revision')):fail(409,'تغيرت إعدادات الخدمة؛ حدّث الصفحة.')
            if not ch['maintenance']:fail(409,'شغّل الصيانة قبل تغيير بيانات التكامل.')
            if db.execute("SELECT id FROM requests WHERE state IN ('validating','sending','unknown') LIMIT 1").fetchone():fail(409,'راجع الطلبات المعلقة قبل تغيير بيانات التكامل.')
            value=self.store.open(candidate['data']);existing=self.store.get('integration',db=db);old=self.store.open(existing) if existing else None
            migrated=bool(old and value['origin']!=old['origin'])
            if migrated and a.get('confirm_origin')!=value['origin']:fail(422,'راجع واكتب عنوان الخادم الجديد لتأكيد النقل.')
            self.store.put('integration',self.store.seal(value),db);ch['revision']+=1
            current=self.store.get('settings',db=db)
            current['values']['integration_user']=value['user'];current['values']['features']={k:False for k in FEATURES};current['version']=str(int(current['version'])+1)
            if migrated:
                ch['epoch']+=1
                self.store.put('media-access',dict(enabled=False,users=[],roles=[],version='1'),db)
                db.execute('UPDATE customers SET enabled=0');db.execute('DELETE FROM item_refs');db.execute('DELETE FROM images');db.execute('DELETE FROM presets')
                rows=self.table('customer-links',db)
                for row in rows:row['active']=False;row['version']=str(int(row.get('version',0))+1)
                self.save_table('customer-links',rows,db)
                for k in OPTION_TYPES:
                    if k!='integration_user':current['values'][k]=''
            self.store.put('settings',current,db);self.store.put('channel',ch,db)
            db.execute('DELETE FROM cache');db.execute('DELETE FROM candidates');db.execute('DELETE FROM sessions')
            self.store.audit(actor,'integration.activate',value['origin'],db)
        return dict(ok=True,reauthenticate=True,migrated=migrated,maintenance=True)

    def doctor(self,erp):
        checks=[]
        for doctype in ('Company','Price List','Warehouse','Item','Item Price','Product Bundle','Sales Order','Customer','Report'):
            try:
                permission=erp.method('frappe.client.has_permission',{'doctype':doctype,'docname':'','perm_type':'read'});readable=bool(permission and permission.get('has_permission'))
                checks.append(dict(doctype=doctype,custom=False,exists=True,readable=readable,fields=[]))
            except Error as exc:checks.append(dict(doctype=doctype,custom=False,exists=False,readable=False,fields=[],status=exc.status))
        return {**self.integration_status(),'checks':checks,'store_id':self.store.get('channel')['store_id'],'timezone':self.timezone,'scheduler_disabled':time.time()-self.store.get('scheduler_heartbeat',0)>120,'versions':{'hec_service':__version__},'capabilities':self.capabilities(),'erp_installation_required':False}

    def list_records(self,module,erp):
        if module=='products':
            data=self.catalog({},erp,False)
            return {'rows':[dict(id=p['app_id'],version='erp-read-only',title=p['item_name'],code=p['item_code'],price=p['rate'],category=p['item_group'],brand=p['brand'],unit=p['stock_uom'],image=p['image'],isStockItem=bool(p['is_stock_item']),barcodes='\n'.join(x['barcode'] for x in p['barcodes'])) for p in data['items']], '_images':data['_images']}
        if module=='audit':return {'rows':[dict(id=str(r['id']),title=r['action']+' '+r['target'],actor=r['actor'],date=r['created_at'],result='مسجل',version='read-only') for r in self.store.rows('SELECT * FROM audit ORDER BY id DESC LIMIT 100')]}
        if module=='orders':
            company=self.store.get('settings')['values']['company']
            return {'rows':[dict(id=app_id(r['name']),title=r['name'],customer=r['customer'],status=r['status'],total=r['grand_total'],version=r['modified']) for r in erp.list('Sales Order',['name','customer','status','grand_total','modified'],{'company':company},100)]}
        if module=='users':return {'rows':[dict(id=app_id(r['user']),title=r['user'],roles='عميل المتجر',status='مفعّل' if r['enabled'] else 'متوقف',version='read-only') for r in self.store.rows('SELECT user,enabled FROM customers LIMIT 100')]}
        if module in READONLY:return {'rows':[]}
        rows=self.table('offer-bundles' if module=='campaigns' else module)
        return {'rows':rows,'_images':self.image_map(rows)}

    def dispatch(self,op,a,token='',remote='local'):
        if not isinstance(op,str) or not isinstance(a,dict):fail(422,'طلب غير صالح.')
        self.store.throttle('ip:'+remote,240,60)
        if op=='public.version':return self.bootstrap()
        if op=='courier.auth.login':
            self.store.throttle('courier-login-ip:'+remote,15,300);return self.courier_login(a)
        if op=='auth.login':
            self.store.throttle('login:'+remote,15,300);return self.login(a)
        if op in ('auth.logout','courier.auth.logout'):self.store.revoke(token);return {'ok':True}
        session=self.store.resolve(token)
        if op=='auth.context':return self.context(session)
        if op.startswith('courier.'):return self.courier_dispatch(op,a,session)
        if op in ('reels.social','reels.react','reels.comment','reels.comment.delete','admin.reels.comments','admin.reels.comment.delete'):return self.reel_social(op,a,session)
        if op=='reels.feed':return self.reels_feed(a)
        if op=='public.config':return self.storefront(user=session)
        if op=='catalog.search':
            if session and session['kind']=='admin':erp,_=self.admin(session);return self.catalog(a,erp,False)
            return self.catalog(a)
        if op.startswith('admin.item-media.'):
            erp,who=self.media_actor(session);return self.item_media(op,a,erp,who['user'])
        if op.startswith('reports.'):
            erp,identity=self.admin(session,False);actor=identity['user']
            if op=='reports.list':return self.report_catalog(a,erp,actor)
            if op=='reports.meta':return self.report_metadata(a.get('report_name'),erp)
            if op=='reports.options':return self.report_options(a,erp)
            if op=='reports.run':return self.report_run(a,erp,actor)
            if op=='reports.export':return self.report_export(a,erp,actor)
            if op=='reports.presets':return self.report_presets(a,actor)
            fail(404,'عملية تقرير غير معروفة.')
        if op.startswith('customer.'):
            self.customer_account(session,False)
            if op=='customer.deliveries':return self.customer_deliveries(session,a)
            if op=='customer.orders':return self.customer_orders(session)
            if op=='customer.order':return self.place_order(a,session)
            if op=='customer.order.detail':return self.order_detail(a.get('name'),session)
            if op=='customer.password':return self.change_password(a,session)
            if op=='customer.inbox':
                self.customer_orders(session);self.delivery_inbox(session)
                return {'rows':[{**r,'name':r['id'],'sales_order':r['erp_name']} for r in self.store.rows('SELECT * FROM inbox WHERE user=? AND epoch=? ORDER BY created_at DESC LIMIT 100',(session['user'],self.store.get('channel')['epoch']))]}
            if op=='customer.inbox.read':
                row=self.store.rows('SELECT * FROM inbox WHERE id=? AND user=? AND epoch=?',(a.get('name'),session['user'],self.store.get('channel')['epoch']))
                if not row:fail(404,'الإشعار غير موجود.')
                self.order_detail(row[0]['erp_name'],session)
                with self.store.tx() as db:db.execute('UPDATE inbox SET read_at=? WHERE id=?',(utc(),a['name']))
                return {'ok':True}
            fail(404,'عملية عميل غير معروفة.')
        if op.startswith('admin.') or op=='connection.test':
            erp,identity=self.admin(session);actor=identity['user']
            if op.startswith('admin.studio.'):return self.studio(op,a,erp,actor)
            if op in ('admin.media-access','admin.media-access.save'):return self.media_access(op,a,erp,actor)
            if op=='admin.reels.discover':return self.discover_reels(a,erp)
            if op=='admin.reels.upload':return self.reel_upload(a,actor)
            if op=='admin.reels.import':return self.reel_import(a,erp,actor)
            if op.startswith('admin.delivery.'):return self.delivery_admin(op,a,erp,actor)
            if op=='admin.config':return {'modules':{m:self.table(m) for m in SCHEMA}}
            if op=='admin.settings':return self.settings()
            if op=='admin.settings.save':return self.save_settings(a,actor,erp)
            if op=='admin.options':return self.option_rows(a,erp)
            if op=='admin.list':return self.list_records(a.get('module'),erp)
            if op=='admin.save':return self.save_record(a,actor,erp)
            if op=='admin.archive':return self.save_record({**a,'payload':{'active':False}},actor,erp)
            if op in ('admin.media','admin.media.upload'):return self.upload(a,actor)
            if op=='admin.publication':return self.publication()
            if op=='admin.publish':return self.publish(a,actor)
            if op=='admin.rollback':return self.rollback(a,actor)
            if op=='admin.publish.cancel':return self.cancel_publication(a,actor)
            if op=='admin.maintenance':return self.maintain(a,actor)
            if op=='admin.preview':return self.storefront(True)
            if op=='admin.doctor':return self.doctor(erp)
            if op=='admin.customer.create':return self.create_customer(a,actor,erp)
            if op=='admin.integration':return self.integration_status()
            if op in ('admin.integration.test','connection.test'):return self.test_integration(a,actor)
            if op=='admin.integration.activate':return self.activate_integration(a,actor)
            if op=='admin.requests':
                rows=self.store.rows('SELECT id,user,state,erp_name,created_at,error,payload FROM requests WHERE epoch=? ORDER BY created_at DESC LIMIT 100',(self.store.get('channel')['epoch'],))
                for row in rows:row['delivery']=self.store.open(row.pop('payload')).get('delivery',{})
                return {'rows':rows}
            if op=='admin.requests.reconcile':return self.reconcile_order(a.get('id'),actor,erp)
            if op=='admin.access':return {**self.store.get('access'),'available_roles':[r['name'] for r in erp.list('Role',['name'],{'disabled':0},500,order='name asc') if r['name'] not in {'All','Guest','Customer','Supplier','Desk User','System Manager'}]}
            if op=='admin.access.save':
                roles=a.get('report_roles');available=erp.list('Role',['name'],{'disabled':0},500,order='name asc');allowed={r['name'] for r in available}-{'Guest','All','Customer','Supplier','Desk User','System Manager'}
                if not isinstance(roles,list) or len(roles)>20 or any(r not in allowed for r in roles):fail(422,'اختر أدوار تقارير إدارية محددة من النظام.')
                self.store.put('access',{'report_roles':roles});self.store.audit(actor,'access.save','report roles');return self.store.get('access')
            fail(404,'عملية إدارية غير معروفة.')
        fail(404,'العملية غير متاحة.')
