"""Actual service functions exercised with isolated Frappe persistence doubles.
No remote ERP, SQL engine, scheduler worker or Android runtime is implied.
"""
import copy,json,sys,types,unittest,re
from datetime import datetime,timedelta
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parent))
from bridge20_test import fake,Obj,Denied,api,rules
from hec_bridge import releases,inbox,onboarding,install

class Document(Obj):
    def save(self,**kwargs): return self
    def insert(self,**kwargs):
        if self.doctype=='User': self.name=self.email
        DB[(self.doctype,self.name)]=self
        return self
DB={}
class ReleaseTests(unittest.TestCase):
    def setUp(self):
        DB.clear();fake.session.user='manager';fake.flags=Obj(hec_published=None);fake.local.response={}
        values=rules.default_settings();values.update(company='Company',integration_user='service',price_list='Retail',currency='YER')
        DB[('HEC Bridge Settings','store')]=Document(doctype='HEC Bridge Settings',name='store',data=json.dumps(values),revision=1)
        DB[('HEC Store Channel','live')]=Document(doctype='HEC Store Channel',name='live',store_id='a'*32,revision=1,maintenance=0,publication=None)
        for name in rules.SCHEMA:
            DB[('HEC Content',name)]=Document(doctype='HEC Content',name=name,data=json.dumps([dict(id='sample',title='Original',version='1')]) if name=='home' else '[]',revision=1)
        def get_doc(dt,name=None):
            if isinstance(dt,dict): return Document(dt)
            if (dt,name) not in DB: raise KeyError((dt,name))
            return DB[(dt,name)]
        fake.get_doc=get_doc;fake.has_permission=lambda *a,**k:True;fake.get_list=lambda *a,**k:[]
        fake.get_roles=lambda u:['System Manager'] if u=='manager' else []
        fake.db=Obj(exists=lambda dt,name: (dt,name) in DB,get_value=lambda dt,*a,**k:1 if dt=='User' else None,sql=lambda *a,**k:[])
        def get_all(dt,**kw):
            rows=[r for (kind,n),r in DB.items() if kind==dt]
            for key,value in kw.get('filters',{}).items():
                if isinstance(value,list): rows=[r for r in rows if r.get(key) and r.get(key)<=value[1]]
                else: rows=[r for r in rows if r.get(key)==value]
            if kw.get('pluck'):return [r.get(kw['pluck']) for r in rows]
            return rows
        fake.get_all=get_all
    def publish(self,title='Test'):return releases.publish(releases.digest(releases.draft()),title)
    def test_draft_not_public_until_published(self):
        with releases.published():self.assertEqual(api.table('home')[1],[])
        self.publish()
        with releases.published():self.assertEqual(api.table('home')[1][0]['title'],'Original')
        doc=DB[('HEC Content','home')];doc.data=json.dumps([dict(id='sample',title='Unpublished')])
        with releases.published():self.assertEqual(api.table('home')[1][0]['title'],'Original')
        self.assertEqual(api.table('home')[1][0]['title'],'Unpublished')
    def test_publish_changes_all_modules_atomically(self):
        self.publish();data=releases.public_snapshot()
        self.assertEqual(set(data),rules.PUBLIC|releases.MODULES_EXTRA)
        self.assertEqual(releases.channel().revision,2)
    def test_stale_digest_rejects_publish(self):
        with self.assertRaises(ValueError):releases.publish('not-current')
        self.assertIsNone(releases.channel().publication)
    def test_customer_cannot_publish_or_rollback(self):
        fake.session.user='customer'
        for fn,args in [(releases.publish,('x',)),(releases.rollback,('x','1')),(releases.maintenance,(True,'1')),(onboarding.doctor,())]:
            with self.subTest(fn=fn.__name__),self.assertRaises(Denied):fn(*args)
    def test_guest_bootstrap_contains_no_credentials(self):
        fake.session.user='Guest';r=releases.bootstrap()
        self.assertEqual(r['store_id'],'a'*32)
        self.assertFalse(set(r)&{'integration_user','api_key','api_secret','password','company'})
    def test_rollback_restores_content_without_erasing_history(self):
        self.publish();first=releases.channel().publication
        DB[('HEC Content','home')].data=json.dumps([dict(id='sample',title='Second')]);self.publish()
        releases.rollback(first,str(releases.channel().revision))
        self.assertEqual(releases.public_snapshot()['home'][0]['title'],'Original')
        self.assertNotEqual(first,releases.channel().publication)
        self.assertEqual(len(fake.get_all('HEC Publication')),3)
    def test_stale_rollback_and_maintenance_rejected(self):
        self.publish();pid=releases.channel().publication
        for fn,args in [(releases.rollback,(pid,'0')),(releases.maintenance,(True,'0'))]:
            with self.assertRaises(ValueError):fn(*args)
    def test_maintenance_blocks_orders_preserves_public_content(self):
        self.publish();pid=releases.channel().publication
        releases.maintenance(True,str(releases.channel().revision))
        with self.assertRaises(ValueError):releases.require_orders_open()
        self.assertEqual(releases.channel().publication,pid)
        releases.maintenance(False,str(releases.channel().revision));releases.require_orders_open()
    def test_scheduled_release_waits_for_server_clock(self):
        when=datetime.now()+timedelta(days=1)
        releases.publish(releases.digest(releases.draft()),scheduled_at=when.isoformat())
        releases.tick();self.assertIsNone(releases.channel().publication)
        pending=fake.get_all('HEC Publication')[0];pending.scheduled_at=datetime.now()-timedelta(seconds=1)
        releases.tick();self.assertEqual(releases.channel().publication,pending.name)
        revision=releases.channel().revision;releases.tick();self.assertEqual(releases.channel().revision,revision)
    def test_cancelled_schedule_never_activates(self):
        releases.publish(releases.digest(releases.draft()),scheduled_at=(datetime.now()+timedelta(days=1)).isoformat())
        pending=fake.get_all('HEC Publication')[0];releases.cancel(pending.name)
        pending.scheduled_at=datetime.now()-timedelta(days=1);releases.tick()
        self.assertIsNone(releases.channel().publication)
    def test_public_context_restored_after_exception(self):
        with self.assertRaises(RuntimeError):
            with releases.published():raise RuntimeError()
        self.assertIsNone(fake.flags.hec_published)
    def test_provision_requires_admin_and_create_permission(self):
        fake.session.user='customer'
        with self.assertRaises(Denied):onboarding.create_customer_account('x@example.test','Test','Customer','Company','long-test-password')
        fake.session.user='manager';fake.has_permission=lambda *a,**k:False
        with self.assertRaises(Denied):onboarding.create_customer_account('x@example.test','Test','Customer','Company','long-test-password')
    def test_provision_weak_password_and_existing_user_rejected(self):
        for email,password in [('bad-email','long-test-password'),('x@example.test','123456'),('x@example.test','a'*15)]:
            with self.assertRaises(ValueError):onboarding.create_customer_account(email,'Test','Customer','Company',password)
        DB[('User','x@example.test')]=Document(doctype='User',name='x@example.test')
        with self.assertRaises(ValueError):onboarding.create_customer_account('x@example.test','Test','Customer','Company','long-test-password')
    def test_provision_creates_website_user_and_link(self):
        DB[('Customer','Customer')]=Document(doctype='Customer',name='Customer',disabled=0)
        DB[('Company','Company')]=Document(doctype='Company',name='Company')
        result=onboarding.create_customer_account('x@example.test','Test Customer','Customer','Company','long-test-password')
        self.assertEqual(result['user'],'x@example.test')
        self.assertEqual(DB[('User','x@example.test')].user_type,'Website User')
        self.assertEqual(DB[('User','x@example.test')].roles,[])
        links=fake.get_all('HEC Customer Link');self.assertEqual(len(links),1)
        self.assertEqual(links[0].customer,'Customer')
        self.assertEqual(len(api.table('customer-links')[1]),1)
    def test_order_detail_rejects_foreign_customer(self):
        v=json.loads(DB[('HEC Bridge Settings','store')].data);v['features']['orders']=True;DB[('HEC Bridge Settings','store')].data=json.dumps(v)
        DB[('Sales Order','foreign')]=Document(doctype='Sales Order',name='foreign',customer='Victim',company='Company')
        old=api.customer_link;api.customer_link=lambda:('customer',Obj(customer='Customer',company='Company'))
        try:
            with self.assertRaises(ValueError):inbox.order_detail('foreign')
        finally:api.customer_link=old
    def test_inbox_cannot_be_read_by_another_customer(self):
        DB[('HEC Inbox','private')]=Document(doctype='HEC Inbox',name='private',user='victim',sales_order='SO1')
        old=api.customer_link;api.customer_link=lambda:('customer',Obj(customer='C',company='Company'))
        try:
            with self.assertRaises(ValueError):inbox.mark_read('private')
        finally:api.customer_link=old
        self.assertIsNone(DB[('HEC Inbox','private')].read_at)
    def test_password_change_requires_current_user_and_strong_new_password(self):
        fake.session.user='Guest'
        with self.assertRaises(Denied):onboarding.change_password('old','new-long-password')
        fake.session.user='customer'
        for old,new in [('','new-long-password'),('old','123456'),('same-long-password','same-long-password')]:
            with self.assertRaises(ValueError):onboarding.change_password(old,new)
    def test_android_allowlist_serves_all_packaged_scripts_styles_and_guide_images(self):
        root=Path(__file__).resolve().parents[1]
        source=(root/'app/src/main/java/com/alhaitham/hec/MainActivity.java').read_text()
        matches=re.findall(r'p\.matches\(("(?:\\.|[^"\\])*")\)',source)
        patterns=[re.compile(json.loads(m)) for m in matches]
        self.assertEqual(len(patterns),2)
        for role in ['customer','admin']:
            web=root/'build/variants'/role/'assets/web'
            refs=re.findall(r'(?:src|href)="([^"]+)"',(web/'index.html').read_text())
            refs.extend(str(f.relative_to(web)) for f in web.glob('admin-guide-images/*.png'))
            for ref in refs:
                with self.subTest(role=role,ref=ref):self.assertTrue(any(p.fullmatch('/'+ref) for p in patterns),ref)
        for bad in ['/admin-guide-images/../secret.png','/admin-guide-images/%2e%2e.png','/admin-guide-images/a.html']:
            self.assertFalse(any(p.fullmatch(bad) for p in patterns))
        self.assertIn('path.endsWith(".png") ? "image/png"',source)
    def test_custom_doctypes_do_not_contain_shared_api_secrets(self):
        names={f['fieldname'] for fields in install.specs().values() for f in fields}
        self.assertFalse(names&{'api_key','api_secret','password'})
        self.assertTrue({'HEC Store Channel','HEC Publication','HEC Inbox'}<=set(install.specs()))

if __name__=='__main__':unittest.main(verbosity=2)
