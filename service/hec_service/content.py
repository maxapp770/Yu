import base64, hashlib, io, json, secrets
from datetime import datetime,timezone
from zoneinfo import ZoneInfo
from pathlib import Path
from .core import fail,encode,digest,utc,text
from .rules import PUBLIC,SCHEMA,READONLY,record,flag

class Content:
    def table(self,module,db=None):
        if module not in SCHEMA:fail(404,'قسم غير معروف.')
        rows=db.execute('SELECT data FROM content WHERE module=?',(module,)).fetchall() if db else self.store.rows('SELECT data FROM content WHERE module=?',(module,))
        return json.loads(rows[0]['data']) if rows else []

    def draft(self,db=None):return {m:self.table(m,db) for m in sorted(PUBLIC|{'feature-policies','notifications'})}
    def save_table(self,module,rows,db):
        db.execute('INSERT INTO content VALUES(?,?,1) ON CONFLICT(module) DO UPDATE SET data=excluded.data,revision=revision+1',(module,encode(rows)))

    def publication(self):
        ch=self.store.get('channel')
        history=self.store.rows('SELECT id AS name,title,state,created_by,scheduled_at,published_at FROM publications ORDER BY rowid DESC LIMIT 25')
        return dict(draft_digest=digest(self.draft()),revision=str(ch['revision']),store_id=ch['store_id'],publication=ch['publication'],maintenance=ch['maintenance'],history=history)

    def activate_publication(self,ident,db):
        ch=self.store.get('channel',db=db)
        if ch['publication']:db.execute("UPDATE publications SET state='Superseded' WHERE id=?",(ch['publication'],))
        db.execute("UPDATE publications SET state='Published',published_at=? WHERE id=?",(utc(),ident))
        ch.update(publication=ident,revision=ch['revision']+1);self.store.put('channel',ch,db)

    def publish(self,a,actor):
        with self.store.tx() as db:
            snapshot=self.draft(db)
            if digest(snapshot)!=a.get('expected_digest'):fail(409,'تغيرت المسودة؛ حدّثها ثم انشر.')
            when=a.get('scheduled_at');scheduled=None
            if when:
                try:
                    dt=datetime.fromisoformat(when)
                    if dt.tzinfo is None:dt=dt.replace(tzinfo=ZoneInfo(self.timezone))
                    if dt<=datetime.now(timezone.utc):raise ValueError()
                    scheduled=dt.astimezone(timezone.utc).isoformat()
                except (ValueError,TypeError):fail(422,'حدد وقتاً مستقبلياً للنشر.')
            ident=secrets.token_hex(16)
            db.execute('INSERT INTO publications VALUES(?,?,?,?,?,?,?,?)',(ident,text(a.get('title') or 'نشر المتجر',140),encode(snapshot),digest(snapshot),'Scheduled' if scheduled else 'Pending',scheduled,None,actor))
            if not scheduled:self.activate_publication(ident,db)
            self.store.audit(actor,'publication.schedule' if scheduled else 'publication.publish',ident,db)
        return self.publication()

    def rollback(self,a,actor):
        with self.store.tx() as db:
            ch=self.store.get('channel',db=db)
            if str(ch['revision'])!=str(a.get('revision')):fail(409,'تغير الإصدار المنشور.')
            old=db.execute('SELECT * FROM publications WHERE id=?',(a.get('publication'),)).fetchone()
            if not old or old['state'] not in ('Published','Superseded'):fail(422,'اختر إصداراً سبق نشره.')
            ident=secrets.token_hex(16)
            db.execute('INSERT INTO publications VALUES(?,?,?,?,?,?,?,?)',(ident,'استعادة '+old['id'],old['snapshot'],old['checksum'],'Pending',None,None,actor))
            self.activate_publication(ident,db);self.store.audit(actor,'publication.restore',old['id'],db)
        return self.publication()

    def cancel_publication(self,a,actor):
        with self.store.tx() as db:
            result=db.execute("UPDATE publications SET state='Cancelled' WHERE id=? AND state='Scheduled'",(a.get('publication'),))
            if result.rowcount!=1:fail(409,'لم يعد الإصدار مجدولاً.')
            self.store.audit(actor,'publication.cancel',a.get('publication'),db)
        return self.publication()

    def maintain(self,a,actor):
        with self.store.tx() as db:
            ch=self.store.get('channel',db=db)
            if str(ch['revision'])!=str(a.get('revision')):fail(409,'تغيرت حالة المتجر.')
            enabled=flag(a.get('enabled'))
            if not enabled and not self.store.get('integration',db=db):fail(422,'اختبر إعداد التكامل وفعّله أولاً.')
            ch.update(maintenance=enabled,revision=ch['revision']+1);self.store.put('channel',ch,db)
            self.store.audit(actor,'maintenance.set',str(enabled),db)
        return self.publication()

    def tick(self):
        with self.store.tx() as db:
            for row in db.execute("SELECT id FROM publications WHERE state='Scheduled' AND scheduled_at<=? ORDER BY scheduled_at,rowid LIMIT 20",(utc(),)).fetchall():
                self.activate_publication(row['id'],db);self.store.audit('scheduler','publication.activate',row['id'],db)

    def save_record(self,a,actor,erp):
        module=a.get('module');target='offer-bundles' if module in ('campaigns','golden') else module
        try:value=record(module,a.get('payload'))
        except (ValueError,TypeError):fail(422,'تحقق من حقول السجل والقيم المسموحة.')
        ident=a.get('id');old=next((r for r in self.table(target) if r['id']==ident),None)
        if target=='customer-links':
            customer=erp.get('Customer',value.get('customer',(old or {}).get('customer','')))
            erp.get('Company',value.get('company',(old or {}).get('company','')))
            if customer.get('disabled'):fail(403,'العميل متوقف في النظام.')
            self.integration_client().get('Customer',customer['name']);self.integration_client().get('Company',value.get('company',(old or {}).get('company','')))
        if target=='offer-bundles':
            merged={**(old or {}),**value}
            if merged.get('active') is not False:self.validate_bundle(merged)
        with self.store.tx() as db:
            rows=self.table(target,db);old=next((r for r in rows if r['id']==ident),None)
            if ident and (not old or str(old.get('version'))!=str(a.get('version'))):fail(409,'تغير السجل؛ حدّث البيانات قبل الحفظ.')
            if not ident and SCHEMA[module].get('noCreate'):fail(403,'لا يمكن إضافة سجل لهذا القسم.')
            row={**(old or {}),**value,'id':ident or 'R'+secrets.token_hex(10),'version':str(int((old or {}).get('version',0))+1)}
            if target in ('videos','reels-settings'):self.validate_reel_record(target,row,erp)
            if target=='customer-links':
                user=row.get('user','').lower()
                account=db.execute('SELECT * FROM customers WHERE user=?',(user,)).fetchone()
                if not account:fail(422,'أنشئ حساب المتجر أولاً من تبويب حسابات العملاء.')
                db.execute('UPDATE customers SET customer=?,company=?,enabled=?,epoch=? WHERE user=?',(row['customer'],row['company'],int(row.get('active',True)),self.store.get('channel',db=db)['epoch'],user))
            if old:rows[rows.index(old)]=row
            elif len(rows)<500:rows.append(row)
            else:fail(422,'بلغ القسم الحد الأقصى للسجلات.')
            self.save_table(target,rows,db)
            if target=='offer-bundles':
                for mod in ('campaigns','golden'):
                    rs=self.table(mod,db);index=next((i for i,x in enumerate(rs) if x['id']==row['id']),None)
                    if index is not None:rs[index]=row
                    elif mod=='campaigns' or module=='golden':rs.append(row)
                    self.save_table(mod,rs,db)
            titles={'deals':'home.deals','suggestions':'home.suggestions','new':'home.new','best':'home.best','footer':'home.footer'}
            if module=='home' and row['id'] in titles:
                rs=self.table('home-texts',db)
                for r in rs:
                    if r.get('key')==titles[row['id']]:r.update(text=row.get('displayTitle',''),version=str(int(r.get('version',0))+1))
                self.save_table('home-texts',rs,db)
            if module=='home-texts':
                rs=self.table('home',db)
                for r in rs:
                    if titles.get(r['id'])==row.get('key'):r.update(displayTitle=row.get('text',''),version=str(int(r.get('version',0))+1))
                self.save_table('home',rs,db)
            self.store.audit(actor,'content.save',module+'/'+row['id'],db)
        return row

    def upload(self,a,actor):
        from .studio import photo_bytes
        content,ext=photo_bytes(a.get('data'))
        name='erp-'+hashlib.sha256(content).hexdigest()[:24]+'.jpg'
        path=self.media/name;path.write_bytes(content)
        self.store.audit(actor,'media.upload',name)
        return dict(image=name,_images={name:'/v1/images/'+name})

    def image_map(self,value):
        names=set()
        def walk(v):
            if isinstance(v,dict):
                for x in v.values():walk(x)
            elif isinstance(v,list):
                for x in v:walk(x)
            elif isinstance(v,str) and v.startswith('erp-') and v.endswith('.jpg'):names.add(v)
        walk(value)
        return {name:'/v1/images/'+name for name in names if (self.media/name).is_file() or self.store.rows('SELECT id FROM images WHERE id=? AND epoch=?',(name,self.store.get('channel')['epoch']))}
