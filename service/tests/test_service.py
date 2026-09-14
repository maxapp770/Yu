import base64,io,json,os,sys,tempfile,unittest
from pathlib import Path
from cryptography.fernet import Fernet
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from hec_service.api import Service
from hec_service.core import Store,Error,encode
from hec_service.erp import origin
from hec_service.server import Application
from fake_erp import FakeERP

def fixture(path):
    FakeERP.documents={};FakeERP.calls=[];FakeERP.lost_reply=False;FakeERP.offline=False;FakeERP.revoked=False;FakeERP.export=True
    store=Store(path,Fernet.generate_key());service=Service(store,erp_factory=FakeERP)
    store.put('integration',store.seal({'origin':service.default_origin,'user':'support@example.test','auth':{'token':'service-key:test-secret'}}))
    config=store.get('settings');config['values'].update(company='شركة الاختبار',price_list='البيع',warehouse='المخزن الرئيسي',currency='YER',integration_user='support@example.test');config['values']['features'].update(catalog=True,images=True,stock=True,orders=True,notifications=True);store.put('settings',config)
    channel=store.get('channel');channel['maintenance']=False;store.put('channel',channel)
    return service

class Tests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.service=fixture(Path(self.temp.name)/'store.db');self.store=self.service.store
        self.admin=self.call('auth.login',{'app_role':'admin','user':'manager@example.test','password':'manager-password'})['session_token']
    def tearDown(self):self.temp.cleanup()
    def call(self,op,args=None,token=''):return self.service.dispatch(op,args or {},token,'test')
    def customer(self,email='customer@example.test',customer='CUST-1'):
        self.call('admin.customer.create',dict(email=email,first_name='عميل الاختبار',customer=customer,company='شركة الاختبار',password='a-customer-password'),self.admin)
        return self.call('auth.login',dict(user=email,password='a-customer-password'))['session_token']
    def order(self):
        product=self.call('catalog.search')['items'][0]
        return dict(request_id='request-test-0000001',integration_epoch=1,lines=[{'id':product['app_id'],'qty':2}],delivery={'name':'عميل الاختبار','address':'صنعاء شارع الاختبار','phone':'777000000','note':''})
    def test_customer_has_no_admin_access(self):
        customer=self.customer()
        with self.assertRaises(Error) as e:self.call('admin.settings',token=customer)
        self.assertEqual(e.exception.status,401)
    def test_integration_user_cannot_login_as_admin(self):
        with self.assertRaises(Error) as e:self.call('auth.login',dict(app_role='admin',kind='token',key='service-key',secret='test-secret'))
        self.assertEqual(e.exception.status,403)
    def test_revoked_role_blocks_next_action(self):
        FakeERP.revoked=True
        with self.assertRaises(Error):self.call('admin.settings',token=self.admin)
    def test_report_uses_requesting_user_not_service(self):
        reporter=self.call('auth.login',dict(app_role='admin',user='reporter@example.test',password='manager-password'))['session_token']
        self.call('reports.run',dict(report_name='Sales Register',filters={'company':'شركة الاختبار','from_date':'2026-09-01','to_date':'2026-09-12'}),reporter)
        calls=[c for c in FakeERP.calls if 'query_report.run' in c[1]]
        self.assertEqual(len(calls),1);self.assertTrue(calls[0][0].startswith('reporter'))
        with self.assertRaises(Error):self.call('admin.settings',token=reporter)
    def test_report_exports_check_permission_and_formula_safety(self):
        a=dict(report_name='Sales Register',filters={'company':'شركة الاختبار','from_date':'2026-09-01','to_date':'2026-09-12'})
        self.call('reports.run',a,self.admin);data=self.call('reports.export',a,self.admin)
        self.assertIn("'=HYPERLINK",base64.b64decode(data['content_base64']).decode())
        FakeERP.export=False
        with self.assertRaises(Error):self.call('reports.export',a,self.admin)
    def test_no_report_cache_cross_user(self):
        a=dict(report_name='Sales Register',filters={'company':'شركة الاختبار','from_date':'2026-09-01','to_date':'2026-09-12'})
        self.call('reports.run',a,self.admin)
        reporter=self.call('auth.login',dict(app_role='admin',user='reporter@example.test',password='manager-password'))['session_token']
        with self.assertRaises(Error):self.call('reports.run',{**a,'cached':True},reporter)
    def test_no_offline_permission_bypass(self):
        a=dict(report_name='Sales Register',filters={'company':'شركة الاختبار','from_date':'2026-09-01','to_date':'2026-09-12'})
        self.call('reports.run',a,self.admin);FakeERP.offline=True
        with self.assertRaises(Error):self.call('reports.run',{**a,'cached':True},self.admin)
    def test_report_rejects_impersonation_filters(self):
        with self.assertRaises(Error):self.call('reports.run',dict(report_name='Sales Register',filters={'user':'Administrator'}),self.admin)
    def test_draft_publish_and_restore(self):
        initial=self.call('public.config')['modules']['home-texts']
        rows=self.service.table('home-texts');r=rows[0]
        self.call('admin.save',dict(module='home-texts',id=r['id'],version=r['version'],payload={'text':'عنوان جديد'}),self.admin)
        self.assertEqual(self.call('public.config')['modules']['home-texts'],initial)
        d=self.call('admin.publication',token=self.admin)
        published=self.call('admin.publish',dict(expected_digest=d['draft_digest'],title='اختبار'),self.admin)
        self.assertEqual(self.call('public.config')['modules']['home-texts'][0]['text'],'عنوان جديد')
        with self.assertRaises(Error):self.call('admin.publish',dict(expected_digest='old'),self.admin)
        restored=self.call('admin.rollback',dict(publication=published['publication'],revision=published['revision']),self.admin)
        self.assertNotEqual(published['publication'],restored['publication'])
    def test_order_and_same_id_retry(self):
        customer=self.customer();a=self.order();first=self.call('customer.order',a,customer);second=self.call('customer.order',a,customer)
        self.assertEqual(first['name'],second['name']);self.assertEqual(len(FakeERP.documents),1)
    def test_uncertain_reply_never_blindly_retried(self):
        customer=self.customer();a=self.order();FakeERP.lost_reply=True
        first=self.call('customer.order',a,customer);second=self.call('customer.order',a,customer)
        self.assertTrue(first['pending']);self.assertEqual(second['state'],'unknown');self.assertEqual(len(FakeERP.documents),1)
        result=self.call('admin.requests.reconcile',{'id':first['reference']},self.admin)
        self.assertTrue(result['resolved']);self.assertEqual(len(FakeERP.documents),1)
    def test_order_rejects_prices_and_customer_injection(self):
        customer=self.customer();a=self.order();a['lines'][0]['rate']=1
        with self.assertRaises(Error):self.call('customer.order',a,customer)
        self.assertEqual(FakeERP.documents,{})
    def test_order_and_inbox_customer_ownership(self):
        c1=self.customer();c2=self.customer('two@example.test','CUST-2');result=self.call('customer.order',self.order(),c1)
        with self.assertRaises(Error):self.call('customer.order.detail',{'name':result['name']},c2)
        notice=self.call('customer.inbox',token=c1)['rows'][0]
        with self.assertRaises(Error):self.call('customer.inbox.read',{'name':notice['id']},c2)
    def test_maintenance_fences_orders(self):
        customer=self.customer();a=self.order();self.call('admin.maintenance',{'enabled':True,'revision':self.service.bootstrap()['revision']},self.admin)
        with self.assertRaises(Error):self.call('customer.order',a,customer)
        self.assertEqual(FakeERP.documents,{})
    def test_origin_validation(self):
        for bad in ['http://erptest.wahatalhaitham.com','https://evil.example','https://erptest.wahatalhaitham.com@evil.example','https://erptest.wahatalhaitham.com/path']:
            with self.assertRaises(Error):origin(bad,self.service.allowed_hosts)
    def test_secrets_encrypted_on_disk(self):
        data=self.store.path.read_bytes()
        self.assertNotIn(b'service-key:test-secret',data);self.assertNotIn(self.admin.encode(),data)
    def test_customer_password_change_revokes_other_sessions(self):
        c1=self.customer();c2=self.call('auth.login',dict(user='customer@example.test',password='a-customer-password'))['session_token']
        self.call('customer.password',dict(old_password='a-customer-password',new_password='a-new-customer-password'),c1)
        self.call('auth.context',token=c1)
        with self.assertRaises(Error):self.call('auth.context',token=c2)
    def test_rotation_requires_test_and_maintenance_and_reauth(self):
        test=self.call('admin.integration.test',dict(key='service-key',secret='new-test-secret'),self.admin)
        with self.assertRaises(Error):self.call('admin.integration.activate',dict(ticket=test['ticket'],revision=self.service.bootstrap()['revision']),self.admin)
        self.call('admin.maintenance',dict(enabled=True,revision=self.service.bootstrap()['revision']),self.admin)
        result=self.call('admin.integration.activate',dict(ticket=test['ticket'],revision=self.service.bootstrap()['revision']),self.admin)
        self.assertTrue(result['reauthenticate']);self.assertEqual(self.service.bootstrap()['integration_epoch'],1)
        with self.assertRaises(Error):self.call('admin.settings',token=self.admin)
    def test_origin_change_disables_customer_mapping(self):
        self.customer();self.service.allowed_hosts.append('new.example.test')
        test=self.call('admin.integration.test',dict(key='service-key',secret='new-test-secret',erp_origin='https://new.example.test'),self.admin)
        self.call('admin.maintenance',dict(enabled=True,revision=self.service.bootstrap()['revision']),self.admin)
        self.call('admin.integration.activate',dict(ticket=test['ticket'],revision=self.service.bootstrap()['revision'],confirm_origin='https://new.example.test'),self.admin)
        self.assertEqual(self.service.bootstrap()['integration_epoch'],2);self.assertEqual(self.store.rows('SELECT enabled FROM customers')[0]['enabled'],0)
    def test_http_transport_and_cors(self):
        app=Application(self.service)
        def request(origin=None):
            body=encode({'op':'public.version','args':{}}).encode();env={'PATH_INFO':'/v1/rpc','REQUEST_METHOD':'POST','CONTENT_TYPE':'application/json','CONTENT_LENGTH':str(len(body)),'wsgi.input':io.BytesIO(body)}
            if origin:env['HTTP_ORIGIN']=origin
            result=[];data=b''.join(app(env,lambda status,headers:result.append(status)))
            return result[0],json.loads(data)
        self.assertEqual(request()[0],'200 OK');self.assertEqual(request('https://evil.example')[0],'403 Forbidden')

if __name__=='__main__':unittest.main(verbosity=2)
