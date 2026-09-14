"""Courier accounts and delivery custody, without installing ERPNext customizations."""
import re,secrets,math
from .core import fail,Error,digest,utc,text,password_hash,password_matches

LABELS={'offered':'بانتظار قبول الموصّل','accepted':'قَبِل الموصّل المهمة','picked_up':'استلم الموصّل الشحنة','onway':'في الطريق إليك','delivered':'تم التسليم','failed':'تعذر التسليم','rejected':'اعتذر الموصّل','returned':'أعيدت الشحنة للمتجر','cancelled':'ألغيت المهمة'}
TERMINAL={'delivered','returned','cancelled'}
NEXT={'offered':['accepted','rejected'],'accepted':['picked_up','failed'],'picked_up':['onway','failed'],'onway':['delivered','failed']}
def email(v):
    u=str(v or '').strip().lower()
    if not re.fullmatch(r'[^\s@<>]{1,80}@[^\s@<>]{1,80}\.[^\s@<>]{2,20}',u):fail(422,'أدخل بريد حساب الموصّل.')
    return u
def amount(v):
    if type(v) not in (int,float) or not math.isfinite(v) or v<0 or v>1e10 or abs(v*100-round(v*100))>.001:fail(422,'أدخل مبلغاً موجباً أو صفراً بمنزلتين عشريتين كحد أقصى.')
    return v
def pick(d,keys):return {k:d.get(k) for k in keys.split()}

class Delivery:
    def delivery_state(self):return self.store.get('channel'),self.store.get('settings')['values']
    def delivery_enabled(self):
        ch,st=self.delivery_state()
        if not st['features'].get('delivery'):fail(403,'التوصيل متوقف من إعدادات الخدمة.')
        if ch['maintenance']:fail(503,'الخدمة في صيانة؛ أعد المحاولة لاحقاً.')
    def delivery_id(self,kind,name):
        ch,_=self.delivery_state();return digest([ch['store_id'],ch['epoch'],kind,name])
    def delivery_read(self,id):
        rows=self.store.rows('SELECT * FROM delivery_records WHERE id=?',(id,))
        if not rows:fail(404,'السجل غير متاح.')
        r=rows[0];r['data']=self.store.open(r['value']);return r
    def delivery_valid(self,r,kind):
        ch,st=self.delivery_state()
        if r['kind']!=kind or r['epoch']!=ch['epoch'] or r['data']['company']!=st['company']:fail(403,'السجل تابع لربط أو شركة أخرى.')
    def delivery_rows(self,kind,owner=None):
        ch,_=self.delivery_state();query='SELECT * FROM delivery_records WHERE epoch=? AND kind=?';args=[ch['epoch'],kind]
        if owner:query+=' AND owner=?';args.append(owner)
        rows=self.store.rows(query+' ORDER BY updated DESC LIMIT 501',args)
        for r in rows:r['data']=self.store.open(r['value'])
        return rows[:500],len(rows)>500
    def delivery_insert(self,kind,owner,parent,data):
        ch,_=self.delivery_state();id=self.delivery_id(kind,parent)
        with self.store.tx() as db:
            if not db.execute('INSERT OR IGNORE INTO delivery_records(id,kind,epoch,owner,parent,value,revision,updated) VALUES(?,?,?,?,?,?,1,?)',(id,kind,ch['epoch'],owner,parent,self.store.seal(data),utc())).rowcount:fail(409,'السجل موجود؛ حدّث قائمة التوصيلات.')
        return self.delivery_read(id)
    def delivery_update(self,r,db=None):
        if db is None:
            with self.store.tx() as conn:return self.delivery_update(r,conn)
        if not db.execute('UPDATE delivery_records SET value=?,owner=?,revision=revision+1,updated=? WHERE id=? AND revision=?',(self.store.seal(r['data']),r['owner'],utc(),r['id'],r['revision'])).rowcount:fail(409,'تغير السجل من جهاز آخر؛ حدّثه أولاً.')
        r['revision']+=1;return r
    def courier_account(self,session):
        if not session or session.get('kind')!='courier':fail(401,'سجّل الدخول بحساب الموصّل.')
        r=self.delivery_read(self.delivery_id('courier',session['user']));self.delivery_valid(r,'courier')
        if not r['data']['enabled'] or r['data']['password_version']!=session.get('passwordVersion'):fail(401,'انتهت صلاحية الحساب أو تغيّرت كلمة المرور.')
        return r
    def courier_view(self,r):return dict(id=r['id'],version=r['revision'],**pick(r['data'],'user name phone driver company enabled online'))
    def courier_context(self,session):
        ch,st=self.delivery_state();return dict(authenticated=True,kind='courier',**self.courier_view(self.courier_account(session)),delivery_enabled=bool(st['features'].get('delivery')),maintenance=bool(ch['maintenance']))
    def courier_login(self,a):
        u=email(a.get('user'));self.store.throttle('courier-login:'+digest(u),8,300)
        try:r=self.delivery_read(self.delivery_id('courier',u))
        except Error:r=None
        matched=password_matches(str(a.get('password',''))[:128],r['data']['password'] if r else '00'*16+':'+'00'*64)
        if not r or not matched:fail(401,'بيانات الدخول غير صحيحة أو الحساب غير مفعّل.')
        session=dict(kind='courier',user=u,passwordVersion=r['data']['password_version']);ctx=self.courier_context(session)
        return dict(**ctx,session_token=self.store.session(session))
    def delivery_job(self,id,session):
        r=self.delivery_read(id);self.delivery_valid(r,'job')
        if session['kind']=='courier' and r['owner']!=session['user']:fail(403,'هذه المهمة غير مسندة لك.')
        return r
    def delivery_view(self,r,scope='courier'):
        d=r['data'];out=dict(id=r['id'],version=r['revision'],**pick(d,'sales_order delivery_note customer currency status expected_cash commission collected settled receiver delivered_at created_at courier_name sync erp_comment items packed_items'))
        out['history']=[pick(e,'status at reason label') for e in d['history']]
        if scope in ('courier','admin'):out['delivery']=d['delivery']
        if scope=='admin':out.update(pick(d,'courier operations settlement'))
        if scope=='customer' and d['status'] not in TERMINAL:out['delivery_code']=d['delivery_code']
        return out
    def delivery_event(self,d,status,actor,reason=''):
        if len(d['history'])>=180:fail(422,'بلغت المهمة حد المحاولات؛ راجع المدير.')
        d['status']=status;d['history'].append(dict(status=status,actor=actor,at=utc(),reason=reason,label=LABELS.get(status,status)))
        if status in TERMINAL:d['sync']='pending'
    def delivery_revision(self,r,a):
        if str(a.get('version'))!=str(r['revision']):fail(409,'تغيرت المهمة؛ حدّثها قبل المحاولة.')
    def delivery_operation(self,d,a):
        if not re.fullmatch(r'[A-Za-z0-9_-]{16,80}',str(a.get('request_id',''))):fail(422,'معرّف العملية غير صالح.')
        fp=digest({k:v for k,v in a.items() if k not in ('version','app_role','server')});old=d['operations'].get(a['request_id'])
        if old and old!=fp:fail(409,'معرّف العملية مستخدم لمحتوى آخر.')
        return fp,bool(old)
    def delivery_docs(self,erp,so_name,dn_name):
        _,st=self.delivery_state();so=erp.get('Sales Order',so_name);dn=erp.get('Delivery Note',dn_name)
        if so['company']!=st['company'] or dn['company']!=so['company'] or dn['customer']!=so['customer'] or so.get('docstatus')!=1 or dn.get('docstatus')!=1 or dn.get('is_return') or so.get('status') in ('Closed','Cancelled'):fail(422,'يلزم طلب بيع وسند تسليم معتمدان للعميل والشركة نفسيهما، وسند غير مرتجع.')
        if not dn.get('items') or any(i.get('against_sales_order')!=so['name'] for i in dn['items']):fail(422,'كل أصناف السند يجب أن تتبع طلب البيع المحدد.')
        return so,dn
    def delivery_open(self):
        rows,more=self.delivery_rows('job');return more or any(r['data']['status'] not in TERMINAL or r['data']['collected']>0 and not r['data']['settled'] or r['data']['sync']=='unknown' for r in rows)
    def delivery_admin(self,op,a,erp,user):
        ch,st=self.delivery_state();op=op.removeprefix('admin.delivery.')
        if op=='options':
            dt=a.get('doctype')
            if dt not in ('Driver','Sales Order','Delivery Note','Payment Entry'):fail(403,'نوع غير مسموح.')
            filters={'status':'Active'} if dt=='Driver' else {'company':st['company']}
            if dt not in ('Driver','Payment Entry'):filters['docstatus']=1
            if dt=='Delivery Note':filters['is_return']=0
            if a.get('q'):filters['name']=['like','%'+text(a['q'],80)+'%']
            start=max(0,min(int(a.get('cursor',0)),10000));return dict(items=erp.list(dt,['name'],filters,50,start),next_cursor=start+50)
        if op in ('accounts','list'):
            rows,more=self.delivery_rows('courier' if op=='accounts' else 'job');return dict(rows=[self.courier_view(r) if op=='accounts' else self.delivery_view(r,'admin') for r in rows if r['data']['company']==st['company']],truncated=more)
        if op=='account.save':
            u=email(a.get('user'));driver=erp.get('Driver',a.get('driver'));erp.get('Company',st['company'])
            if driver.get('status','Active')!='Active':fail(422,'سجل السائق غير نشط.')
            name=text(a.get('name'),100);phone=text(a.get('phone'),30)
            if len(name)<2 or not re.fullmatch(r'\+?[0-9 ()-]{7,25}',phone) or type(a.get('enabled')) is not bool:fail(422,'تحقق من بيانات الموصّل.')
            d=dict(user=u,name=name,phone=phone,driver=driver['name'],company=st['company'],enabled=a['enabled'])
            try:r=self.delivery_read(self.delivery_id('courier',u))
            except Error as e:
                if e.status!=404:raise
                r=None
            if r:
                self.delivery_valid(r,'courier');self.delivery_revision(r,a)
                if a.get('password'):r['data']['password']=password_hash(a['password']);r['data']['password_version']+=1
                r['data'].update(d);self.delivery_update(r)
            else:r=self.delivery_insert('courier',u,u,dict(**d,online=True,password=password_hash(a.get('password')),password_version=1,created_at=utc()))
            return self.courier_view(r)
        if op=='assign':
            self.delivery_enabled();so,dn=self.delivery_docs(erp,a.get('sales_order'),a.get('delivery_note'));self.delivery_docs(self.integration_client(),so['name'],dn['name']);c=self.delivery_read(self.delivery_id('courier',email(a.get('courier'))));self.delivery_valid(c,'courier')
            if not c['data']['enabled']:fail(422,'حساب الموصّل متوقف.')
            if not self.store.rows('SELECT user FROM customers WHERE customer=? AND company=? AND epoch=? AND enabled=1 LIMIT 1',(so['customer'],so['company'],ch['epoch'])):fail(422,'اربط العميل بحساب المتجر ليصله رمز التسليم.')
            address=a.get('delivery')
            if not address:
                req=self.store.rows('SELECT payload FROM requests WHERE erp_name=? AND epoch=? LIMIT 1',(so['name'],ch['epoch']));address=self.store.open(req[0]['payload']).get('delivery') if req else None
            if not isinstance(address,dict):fail(422,'أدخل بيانات التسليم.')
            address={k:text(address.get(k),100 if k=='name' else 30 if k=='phone' else 500) for k in ('name','phone','address','note')}
            if len(address['name'])<2 or len(address['address'])<5 or not re.fullmatch(r'\+?[0-9 ()-]{7,25}',address['phone']):fail(422,'تحقق من اسم المستلم والهاتف والعنوان.')
            expected=amount(a.get('expected_cash'));commission=amount(a.get('commission',0))
            if expected>float(dn.get('rounded_total') or dn['grand_total']):fail(422,'التحصيل يتجاوز إجمالي سند التسليم.')
            d=dict(company=so['company'],customer=so['customer'],courier=c['data']['user'],courier_name=c['data']['name'],sales_order=so['name'],delivery_note=dn['name'],currency=dn['currency'],expected_cash=expected,commission=commission,collected=0,settled=False,delivery=address,delivery_code=str(secrets.randbelow(900000)+100000),created_at=utc(),status='offered',history=[],operations={},sync='not_due',items=[pick(i,'item_code item_name qty rate amount') for i in dn['items']],packed_items=[pick(i,'item_code item_name qty parent_item') for i in dn.get('packed_items',[])])
            self.delivery_event(d,'offered',user);return self.delivery_view(self.delivery_insert('job',d['courier'],dn['name'],d),'admin')
        r=self.delivery_job(a.get('id'),{'kind':'admin'});d=r['data']
        if op=='detail':return self.delivery_view(r,'admin')
        if op=='reassign':
            self.delivery_enabled();self.delivery_revision(r,a)
            if d['status'] not in ('offered','rejected','failed','accepted') or any(e['status']=='picked_up' for e in d['history']) or d['collected']:fail(409,'استلم الموصّل الشحنة؛ سجل إعادتها أولاً.')
            c=self.delivery_read(self.delivery_id('courier',email(a.get('courier'))));self.delivery_valid(c,'courier')
            if not c['data']['enabled']:fail(422,'الموصّل متوقف.')
            r['owner']=d['courier']=c['data']['user'];d['courier_name']=c['data']['name'];self.delivery_event(d,'offered',user,text(a.get('reason'),300));self.delivery_update(r);return self.delivery_view(r,'admin')
        if op=='close':
            self.delivery_revision(r,a);reason=text(a.get('reason'),300);status=a.get('status');picked=any(e['status']=='picked_up' for e in d['history'])
            if len(reason)<5 or status not in ('returned','cancelled') or d['status'] in TERMINAL:fail(422,'حدد إجراء الإغلاق وسببه.')
            if picked and status!='returned' or not picked and status=='returned':fail(422,'اختر إعادة الشحنة بعد استلامها، وإلغاء قبل الاستلام.')
            self.delivery_event(d,status,user,reason);self.delivery_update(r);return self.delivery_view(r,'admin')
        if op=='settle':
            fp,replayed=self.delivery_operation(d,a)
            if replayed:return dict(**self.delivery_view(r,'admin'),replayed=True)
            self.delivery_revision(r,a)
            if d['sync']=='unknown':fail(409,'راجع نتيجة إثبات ERPNext المعلق قبل تسوية العهدة.')
            if d['status']!='delivered' or d['collected']<=0 or d['settled']:fail(409,'لا توجد عهدة نقدية معلقة.')
            pe=erp.get('Payment Entry',a.get('payment_entry'));ref=next((x for x in pe.get('references',[]) if x.get('reference_doctype')=='Sales Order' and x.get('reference_name')==d['sales_order']),{})
            if pe.get('docstatus')!=1 or pe.get('payment_type')!='Receive' or pe.get('party_type')!='Customer' or pe.get('party')!=d['customer'] or pe.get('company')!=d['company'] or pe.get('paid_to_account_currency')!=d['currency'] or round(float(ref.get('allocated_amount',0))*100)<round(d['collected']*100):fail(422,'اختر سند قبض معتمداً ومخصصاً لطلب البيع بالعميل والشركة والعملة نفسها.')
            if a.get('cash_received') is not True:fail(422,'أكد استلام النقد من الموصّل فعلياً.')
            rid=self.delivery_id('receipt',pe['name'])
            with self.store.tx() as db:
                old=db.execute('SELECT owner FROM delivery_records WHERE id=?',(rid,)).fetchone()
                if old and old['owner']!=r['id']:fail(409,'سند القبض مستخدم لتسوية مهمة أخرى.')
                db.execute('INSERT OR IGNORE INTO delivery_records VALUES(?,?,?,?,?,?,1,?)',(rid,'receipt',ch['epoch'],r['id'],pe['name'],self.store.seal({'company':d['company'],'job':r['id']}),utc()))
                d['settled']=True;d['settlement']=dict(payment_entry=pe['name'],received_by=user,received_at=utc());d['operations'][a['request_id']]=fp;self.delivery_event(d,'delivered',user,'استلم المدير العهدة وربطها بسند القبض '+pe['name']);self.delivery_update(r,db)
            return self.delivery_view(r,'admin')
        if op=='sync':
            self.delivery_revision(r,a)
            if d['status'] not in TERMINAL:fail(409,'أغلق المهمة قبل مزامنة إثباتها.')
            if d['sync']=='synced':return self.delivery_view(r,'admin')
            if d.get('sync_marker') and d['sync']=='unknown':
                found=erp.list('Comment',['name','content'],{'reference_doctype':'Delivery Note','reference_name':d['delivery_note'],'content':['like','%'+d['sync_marker']+'%']},2)
                if len(found)!=1:return dict(pending=True,message='لم يتأكد الإثبات؛ راجعه قبل إرسال جديد.')
                d['sync']='synced';d['erp_comment']=found[0]['name'];self.delivery_update(r);return self.delivery_view(r,'admin')
            self.delivery_docs(erp,d['sales_order'],d['delivery_note']);marker='HEC-DELIVERY-'+r['id']+'-v'+str(r['revision']);d['sync']='unknown';d['sync_marker']=marker;self.delivery_update(r)
            try:
                doc=erp.create('Comment',dict(doctype='Comment',comment_type='Comment',reference_doctype='Delivery Note',reference_name=d['delivery_note'],content=marker+' | '+LABELS[d['status']]+' | '+d['history'][-1]['at']+' | Courier: '+text(d['courier_name'])+' | Collected: '+str(d['collected'])+' '+d['currency']+' | '+('Cash handed over: '+d['settlement']['payment_entry'] if d['settled'] else 'Cash custody pending')))
                d['sync']='synced';d['erp_comment']=doc['name'];self.delivery_update(r);return self.delivery_view(r,'admin')
            except Error:return dict(pending=True,message='حُفظت المهمة؛ لم يتأكد الإثبات في ERPNext. استخدم مراجعة النتيجة.')
        fail(404,'إجراء توصيل غير معروف.')
    def courier_dispatch(self,op,a,session):
        c=self.courier_account(session)
        if op=='courier.auth.context':return self.courier_context(session)
        if op=='courier.profile':
            if 'online' in a:
                if type(a['online']) is not bool:fail(422,'قيمة توفر غير صالحة.')
                self.delivery_revision(c,a);c['data']['online']=a['online'];self.delivery_update(c)
            return self.courier_context(session)
        if op=='courier.password':
            if not password_matches(a.get('old_password'),c['data']['password']):fail(401,'كلمة المرور الحالية غير صحيحة.')
            if a.get('old_password')==a.get('new_password'):fail(422,'اختر كلمة مختلفة.')
            c['data']['password']=password_hash(a.get('new_password'));c['data']['password_version']+=1;self.delivery_update(c);return dict(ok=True,reauthenticate=True)
        if op in ('courier.jobs','courier.inbox'):
            rows,more=self.delivery_rows('job',session['user']);return dict(rows=[self.delivery_view(r) for r in rows if r['data']['company']==c['data']['company']],truncated=more)
        r=self.delivery_job(a.get('id'),session);d=r['data']
        if op=='courier.detail':return self.delivery_view(r)
        if op=='courier.transition':
            self.delivery_enabled();fp,replayed=self.delivery_operation(d,a)
            if replayed:return dict(**self.delivery_view(r),replayed=True)
            self.delivery_revision(r,a);status=a.get('status')
            if status not in NEXT.get(d['status'],[]):fail(409,'انتقال غير مسموح من الحالة الحالية.')
            if status=='accepted' and not c['data']['online']:fail(409,'فعّل التوفر أولاً.')
            if status in ('failed','rejected') and len(text(a.get('reason'),300))<5:fail(422,'أدخل سبباً واضحاً.')
            if status in ('picked_up','onway'):self.delivery_docs(self.integration_client(),d['sales_order'],d['delivery_note'])
            if status=='delivered':
                self.store.throttle('delivery-proof:'+r['id'],6,300)
                if not secrets.compare_digest(str(a.get('delivery_code','')),d['delivery_code']):fail(422,'رمز الاستلام غير صحيح.')
                cash=amount(a.get('collected'))
                if round(cash*100)!=round(d['expected_cash']*100) or cash>0 and a.get('received_cash') is not True:fail(422,'أكد التحصيل الفعلي المطابق للمطلوب.')
                if len(text(a.get('receiver'),100))<2:fail(422,'أدخل اسم المستلم.')
                d.update(receiver=text(a['receiver'],100),collected=cash,delivered_at=utc())
            self.delivery_event(d,status,session['user'],text(a.get('reason'),300));d['operations'][a['request_id']]=fp;self.delivery_update(r);return self.delivery_view(r)
        fail(404,'إجراء موصّل غير معروف.')
    def customer_deliveries(self,session,a):
        ac=self.customer_account(session,False);rows,more=self.delivery_rows('job')
        return dict(rows=[self.delivery_view(r,'customer') for r in rows if r['data']['customer']==ac['customer'] and r['data']['company']==ac['company'] and (not a.get('sales_order') or r['data']['sales_order']==a['sales_order'])],truncated=more)
    def delivery_inbox(self,session):
        ch,_=self.delivery_state()
        for j in self.customer_deliveries(session,{})['rows']:
            with self.store.tx() as db:
                for e in j['history'][-10:]:
                    id=digest([ch['epoch'],session['user'],j['id'],e['at'],e['status']]);db.execute('INSERT OR IGNORE INTO inbox(id,user,title,message,erp_name,created_at,epoch) VALUES(?,?,?,?,?,?,?)',(id,session['user'],'توصيل طلبك '+j['sales_order'],e['label'],j['sales_order'],e['at'],ch['epoch']))
