import hashlib, json, re, secrets
from datetime import datetime,timedelta,timezone
from .core import Error,fail,encode,digest,utc,text,password_hash,password_matches
from .rules import order_lines

class Orders:
    def customer_account(self,session,validate=True):
        if not session or session.get('kind')!='customer':fail(401,'سجّل الدخول بحساب العميل.')
        rows=self.store.rows('SELECT * FROM customers WHERE user=?',(session['user'],))
        if not rows:fail(403,'لم يوجد ربط لحسابك.')
        row=rows[0];channel=self.store.get('channel');settings=self.store.get('settings')['values']
        if not row['enabled'] or row['epoch']!=channel['epoch'] or row['company']!=settings['company']:fail(403,'ربط الحساب غير مفعّل لهذه الشركة؛ راجع الإدارة.')
        if validate:
            customer=self.integration_client().get('Customer',row['customer'])
            if customer.get('disabled'):fail(403,'حساب العميل متوقف في ERPNext.')
        return row

    def create_customer(self,a,actor,erp):
        email=str(a.get('email','')).strip().lower();name=text(a.get('first_name'),100)
        if not re.fullmatch(r'[^\s@<>]{1,80}@[^\s@<>]{1,80}\.[^\s@<>]{2,20}',email) or len(name)<2:fail(422,'أدخل الاسم والبريد بشكل صحيح.')
        password=password_hash(a.get('password'));customer=erp.get('Customer',a.get('customer',''));company=erp.get('Company',a.get('company',''))
        service=self.integration_client();service.get('Company',company['name']);check=service.get('Customer',customer['name'])
        if check.get('disabled'):fail(403,'العميل متوقف في ERPNext.')
        with self.store.tx() as db:
            if db.execute('SELECT user FROM customers WHERE user=?',(email,)).fetchone():fail(409,'يوجد حساب بهذا البريد؛ استخدم ربط الحسابات لتعديله.')
            epoch=self.store.get('channel',db=db)['epoch'];ident='R'+secrets.token_hex(10)
            db.execute('INSERT INTO customers VALUES(?,?,?,?,?,?,?)',(email,password,name,customer['name'],company['name'],1,epoch))
            rows=self.table('customer-links',db);rows.append(dict(id=ident,title=name,user=email,customer=customer['name'],company=company['name'],active=True,version='1'));self.save_table('customer-links',rows,db)
            self.store.audit(actor,'customer.create',email,db)
        return dict(user=email,customer=customer['name'],company=company['name'],account_source='store-service')

    def change_password(self,a,session):
        account=self.customer_account(session,False)
        if not password_matches(a.get('old_password',''),account['password']):fail(401,'كلمة المرور الحالية غير صحيحة.')
        if a.get('old_password')==a.get('new_password'):fail(422,'اختر كلمة مرور مختلفة.')
        hashed=password_hash(a.get('new_password'))
        with self.store.tx() as db:
            db.execute('UPDATE customers SET password=? WHERE user=?',(hashed,session['user']))
            for row in db.execute('SELECT id,data FROM sessions').fetchall():
                if row['id']!=session['session_id'] and self.store.open(row['data']).get('user')==session['user']:db.execute('DELETE FROM sessions WHERE id=?',(row['id'],))
            self.store.audit(session['user'],'customer.password',session['user'],db)
        return {'ok':True}

    def customer_orders(self,session):
        account=self.customer_account(session);erp=self.integration_client()
        rows=erp.list('Sales Order',['name','status','grand_total','currency','transaction_date'],{'customer':account['customer'],'company':account['company']},100,order='creation desc')
        pending=self.store.rows("SELECT id,state,created_at,error FROM requests WHERE user=? AND epoch=? AND state!='confirmed' ORDER BY created_at DESC LIMIT 50",(session['user'],self.store.get('channel')['epoch']))
        for row in rows:self.order_event(session['user'],row)
        return dict(orders=rows,pending=pending)

    def order_detail(self,name,session):
        account=self.customer_account(session);doc=self.integration_client().get('Sales Order',name)
        if doc.get('customer')!=account['customer'] or doc.get('company')!=account['company']:fail(403,'هذا الطلب لا يخص حسابك.')
        self.order_event(session['user'],doc)
        return self.project_order(doc)

    def project_order(self,doc):
        return {**{k:doc.get(k) for k in ('name','status','docstatus','grand_total','currency','transaction_date')},'items':[{k:r.get(k) for k in ('item_code','item_name','qty','rate','amount')} for r in doc.get('items',[])],'packed_items':[{k:r.get(k) for k in ('item_code','item_name','qty','parent_item')} for r in doc.get('packed_items',[])]}

    def order_event(self,user,doc):
        if not self.store.get('settings')['values']['features'].get('notifications'):return
        epoch=self.store.get('channel')['epoch'];ident=digest([epoch,user,doc['name'],doc.get('status'),doc.get('docstatus')])
        with self.store.tx() as db:db.execute('INSERT OR IGNORE INTO inbox VALUES(?,?,?,?,?,?,?,?)',(ident,user,'تحديث طلبك '+doc['name'],text(doc.get('status')),doc['name'],utc(),None,epoch))

    def place_order(self,a,session):
        account=self.customer_account(session);settings=self.store.get('settings')['values'];ch=self.store.get('channel')
        if not settings['features'].get('orders'):fail(403,'استقبال طلبات البيع متوقف.')
        try:lines=order_lines(a.get('lines'))
        except (ValueError,TypeError):fail(422,'تحقق من أصناف الطلب وكمياتها.')
        if int(a.get('integration_epoch') or 0)!=ch['epoch']:fail(409,'تغير ربط المتجر؛ حدّث السلة والأسعار قبل إرسال الطلب.','integration_changed')
        request_id=a.get('request_id','');delivery=a.get('delivery')
        if not isinstance(request_id,str) or not re.fullmatch(r'[A-Za-z0-9_-]{16,80}',request_id):fail(422,'معرّف الطلب غير صالح.')
        if not isinstance(delivery,dict) or set(delivery)-{'name','phone','address','note'} or any(not isinstance(x,str) or len(x)>500 for x in delivery.values()):fail(422,'تحقق من بيانات التوصيل.')
        if len(delivery.get('name',''))<2 or len(delivery.get('address',''))<5:fail(422,'أدخل اسم المستلم وعنوان التوصيل.')
        payload=dict(lines=lines,delivery=delivery,customer=account['customer'],company=account['company']);fingerprint=digest(payload);ident=digest([ch['store_id'],session['user'],request_id]);marker='HEC-'+ident[:32]
        with self.store.tx() as db:
            latest=self.store.get('channel',db=db)
            if latest['epoch']!=ch['epoch'] or latest['maintenance']:fail(503,'المتجر في صيانة مؤقتة؛ احتفظ بالسلة.')
            old=db.execute('SELECT * FROM requests WHERE id=?',(ident,)).fetchone()
            if old:
                if old['fingerprint']!=fingerprint or old['epoch']!=ch['epoch']:fail(409,'استُخدم معرّف الطلب سابقاً لبيانات أخرى.')
                if old['erp_name']:return {'name':old['erp_name'],'replayed':True,'status':'confirmed'}
                return {'pending':True,'reference':ident,'state':old['state'],'message':'الطلب محفوظ لدى الخدمة؛ لم يتأكد إنشاؤه في ERPNext بعد.'}
            db.execute('INSERT INTO requests VALUES(?,?,?,?,?,?,?,?,?,?)',(ident,session['user'],fingerprint,self.store.seal(payload),'validating',None,utc(),utc(),ch['epoch'],None))
        erp=self.integration_client()
        try:
            existing=erp.list('Sales Order',['name'],{'customer':account['customer'],'company':account['company'],'po_no':marker},2)
            if len(existing)>1:fail(409,'وجد أكثر من مستند مرجعي؛ يلزم مراجعة المدير.')
            if existing:
                doc=erp.get('Sales Order',existing[0]['name']);return self.confirm_order(ident,doc,session['user'])
            items=[]
            for line in lines:
                item=erp.get('Item',self.resolve_code(line['id']))
                if item.get('disabled') or not item.get('is_sales_item'):fail(422,'يوجد صنف متوقف أو غير متاح للبيع.')
                dto=self.item_dto(item,settings,erp,{})
                if not dto:fail(422,'يوجد صنف دون سعر صالح في قائمة البيع.')
                entry=dict(item_code=item['name'],qty=line['qty'],uom=item['stock_uom'],warehouse=settings.get('warehouse') or None,delivery_date=(datetime.now(timezone.utc).date()+timedelta(days=settings['delivery_days'])).isoformat())
                items.append(entry)
            document=dict(doctype='Sales Order',customer=account['customer'],company=account['company'],order_type='Sales',selling_price_list=settings['price_list'],currency=settings['currency'],set_warehouse=settings.get('warehouse') or None,items=items,po_no=marker,delivery_date=items[0]['delivery_date'])
            if settings.get('tax_template'):
                template=erp.get('Sales Taxes and Charges Template',settings['tax_template'])
                if template.get('company')!=account['company']:fail(422,'قالب الضرائب تابع لشركة أخرى.')
                keys=('charge_type','account_head','description','rate','row_id','included_in_print_rate','cost_center','add_deduct_tax','category')
                document.update(taxes_and_charges=template['name'],taxes=[{k:r[k] for k in keys if k in r} for r in template.get('taxes',[])])
            if settings.get('selling_cost_center'):
                for entry in items:entry['cost_center']=settings['selling_cost_center']
            # Standard read-only pricing method runs in ERP; posted values are freshly sourced from it.
            for entry in items:
                pricing=erp.method('erpnext.stock.get_item_details.get_item_details',{'args':dict(doctype='Sales Order',item_code=entry['item_code'],qty=entry['qty'],uom=entry['uom'],company=account['company'],customer=account['customer'],selling_price_list=settings['price_list'],price_list=settings['price_list'],currency=settings['currency'],transaction_date=datetime.now(timezone.utc).date().isoformat(),conversion_rate=1,plc_conversion_rate=1,warehouse=settings.get('warehouse'))})
                if not isinstance(pricing,dict) or pricing.get('rate') is None:fail(422,'لم يؤكد ERPNext تسعير الصنف.')
                for k in ('rate','price_list_rate','discount_percentage','discount_amount','conversion_factor'):
                    if pricing.get(k) is not None:entry[k]=pricing[k]
            with self.store.tx() as db:
                latest=self.store.get('channel',db=db)
                if latest['maintenance'] or latest['epoch']!=ch['epoch']:fail(503,'بدأت صيانة المتجر؛ لم يُرسل الطلب.')
                db.execute("UPDATE requests SET state='sending',updated_at=? WHERE id=?",(utc(),ident))
            doc=erp.create('Sales Order',document)
            if not doc.get('name'):fail(502,'لم يتأكد مستند الطلب.')
            # ERP document and intent cannot share a database transaction. Ambiguous replies
            # are held for reconciliation, never blindly retried.
            return self.confirm_order(ident,doc,session['user'])
        except Error as exc:
            with self.store.tx() as db:
                row=db.execute('SELECT state FROM requests WHERE id=?',(ident,)).fetchone()
                state='unknown' if row['state']=='sending' else 'failed'
                db.execute('UPDATE requests SET state=?,error=?,updated_at=? WHERE id=?',(state,text(str(exc)),utc(),ident))
            if state=='failed':raise
            return dict(pending=True,reference=ident,state='unknown',message='استلمت الخدمة الطلب، لكن تأكيد ERPNext غير مكتمل. لن يُرسل مرة ثانية تلقائياً.')

    def confirm_order(self,ident,doc,user):
        with self.store.tx() as db:
            row=db.execute('SELECT payload FROM requests WHERE id=?',(ident,)).fetchone();payload=self.store.open(row['payload'])
            if doc.get('customer')!=payload['customer'] or doc.get('company')!=payload['company']:fail(409,'المستند المرجعي لا يطابق صاحب الطلب.')
            db.execute("UPDATE requests SET state='confirmed',erp_name=?,updated_at=?,error=NULL WHERE id=?",(doc['name'],utc(),ident))
            self.store.audit(user,'order.confirm',doc['name'],db)
        self.order_event(user,doc)
        return self.project_order(doc)

    def reconcile_order(self,ident,actor,admin_erp):
        rows=self.store.rows('SELECT * FROM requests WHERE id=?',(ident,))
        if not rows:fail(404,'الطلب غير موجود.')
        row=rows[0]
        if row['epoch']!=self.store.get('channel')['epoch']:fail(409,'الطلب يعود إلى ربط سابق.')
        payload=self.store.open(row['payload']);admin_erp.get('Company',payload['company']);admin_erp.get('Customer',payload['customer'])
        erp=self.integration_client();docs=erp.list('Sales Order',['name'],{'customer':payload['customer'],'company':payload['company'],'po_no':'HEC-'+ident[:32]},2)
        if len(docs)!=1:return {'resolved':False,'state':row['state'],'message':'لم يوجد مستند واحد مطابق. لا تعاد الكتابة تلقائياً؛ راجع ERPNext.'}
        result=self.confirm_order(ident,erp.get('Sales Order',docs[0]['name']),row['user']);self.store.audit(actor,'order.reconcile',ident)
        return {'resolved':True,**result}
