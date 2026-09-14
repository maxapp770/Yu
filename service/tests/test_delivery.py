import tempfile,unittest,uuid
from pathlib import Path
from copy import deepcopy
from test_service import fixture
from fake_erp import FakeERP
from hec_service.core import Error,fail
class DeliveryERP(FakeERP):
    comments=[];comment_lost=False
    def get(self,t,n):
        if t=='Driver':return dict(name=n,status='Active')
        if t=='Delivery Note':return dict(name=n,docstatus=0 if n=='DN-DRAFT' else 1,company='شركة الاختبار',customer='CUST-1',currency='YER',grand_total=1000,items=[dict(against_sales_order='SO-REAL',item_code='ITEM-1',item_name='طقم الاختبار',qty=2,rate=500,amount=1000)],packed_items=[])
        if t=='Payment Entry':return dict(name=n,docstatus=1,payment_type='Receive',party_type='Customer',party='CUST-2' if n=='PE-WRONG' else 'CUST-1',company='شركة الاختبار',paid_to_account_currency='YER',references=[dict(reference_doctype='Sales Order',reference_name='SO-REAL',allocated_amount=1000)])
        return super().get(t,n)
    def list(self,t,*args,**kw):
        if t=='Comment':return deepcopy(self.comments)
        return super().list(t,*args,**kw)
    def create(self,t,doc):
        if t=='Comment':
            d=dict(**doc,name='COMMENT-'+str(len(self.comments)+1));self.comments.append(d)
            if self.comment_lost:fail(503,'lost reply')
            return d
        return super().create(t,doc)
class DeliveryTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.s=fixture(Path(self.tmp.name)/'store.db');self.s.erp_factory=DeliveryERP;DeliveryERP.comments=[];DeliveryERP.comment_lost=False
        st=self.s.store.get('settings');st['values']['features']['delivery']=True;self.s.store.put('settings',st)
        self.admin=self.call('auth.login',dict(app_role='admin',user='manager@example.test',password='manager-password'))['session_token']
        for u,c in [('one@example.test','CUST-1'),('two@example.test','CUST-2')]:self.call('admin.customer.create',dict(email=u,first_name='عميل اختبار',customer=c,company='شركة الاختبار',password='Customer-Test-42!'),self.admin)
        self.customer=self.call('auth.login',dict(user='one@example.test',password='Customer-Test-42!'))['session_token'];self.other=self.call('auth.login',dict(user='two@example.test',password='Customer-Test-42!'))['session_token']
        self.account=dict(user='driver@example.test',name='موصّل الاختبار',phone='777123456',driver='DRIVER-1',enabled=True,password='Courier-Test-42!')
        self.call('admin.delivery.account.save',self.account,self.admin);self.call('admin.delivery.account.save',{**self.account,'user':'driver2@example.test','driver':'DRIVER-2'},self.admin)
        self.courier=self.call('courier.auth.login',dict(user=self.account['user'],password=self.account['password']))['session_token'];self.courier2=self.call('courier.auth.login',dict(user='driver2@example.test',password=self.account['password']))['session_token']
        FakeERP.documents['SO-REAL']=dict(name='SO-REAL',docstatus=1,status='To Deliver',company='شركة الاختبار',customer='CUST-1',grand_total=1000,currency='YER')
        self.assignment=dict(sales_order='SO-REAL',delivery_note='DN-REAL',courier=self.account['user'],expected_cash=1000,commission=50,delivery=dict(name='عميل اختبار',phone='777456789',address='صنعاء شارع الاختبار',note=''))
        self.j=self.call('admin.delivery.assign',self.assignment,self.admin)
    def tearDown(self):self.tmp.cleanup()
    def call(self,op,a=None,token=''):return self.s.dispatch(op,a or {},token,'test')
    def reject(self,status,op,a=None,token=''):
        with self.assertRaises(Error) as e:self.call(op,a,token)
        self.assertEqual(e.exception.status,status)
    def step(self,status,**a):
        self.j=self.call('courier.transition',dict(id=self.j['id'],version=self.j['version'],request_id=str(uuid.uuid4()),status=status,**a),self.courier);return self.j
    def deliver(self):
        code=self.call('customer.deliveries',token=self.customer)['rows'][0]['delivery_code']
        for state in ('accepted','picked_up','onway'):self.step(state)
        return self.step('delivered',delivery_code=code,collected=1000,received_cash=True,receiver='عميل الاختبار')
    def test_role_ownership_proof(self):
        self.reject(401,'admin.delivery.list',token=self.courier);self.reject(403,'courier.detail',dict(id=self.j['id']),self.courier2)
        self.assertEqual(self.call('courier.jobs',token=self.courier2)['rows'],[]);self.assertEqual(self.call('customer.deliveries',token=self.other)['rows'],[])
        self.assertNotIn('delivery_code',self.call('courier.detail',dict(id=self.j['id']),self.courier))
    def test_erp_submission_and_unique_assignment(self):
        self.reject(409,'admin.delivery.assign',self.assignment,self.admin)
        self.reject(422,'admin.delivery.assign',{**self.assignment,'delivery_note':'DN-DRAFT'},self.admin)
    def test_delivery_cash_idempotency_and_notifications(self):
        self.reject(409,'courier.transition',dict(id=self.j['id'],version=1,request_id=str(uuid.uuid4()),status='delivered'),self.courier)
        code=self.call('customer.deliveries',token=self.customer)['rows'][0]['delivery_code']
        for state in ('accepted','picked_up','onway'):self.step(state)
        a=dict(id=self.j['id'],version=self.j['version'],request_id=str(uuid.uuid4()),status='delivered',delivery_code=code,collected=1000,received_cash=True,receiver='عميل')
        self.reject(422,'courier.transition',{**a,'delivery_code':'000000'},self.courier);self.j=self.call('courier.transition',a,self.courier)
        self.assertTrue(self.call('courier.transition',a,self.courier)['replayed']);self.assertEqual(self.j['collected'],1000)
        self.assertTrue(any(r['message']=='تم التسليم' for r in self.call('customer.inbox',token=self.customer)['rows']))
    def test_failure_return_and_reassignment(self):
        self.step('rejected',reason='لا أستطيع الوصول اليوم');j=self.call('admin.delivery.reassign',dict(id=self.j['id'],version=self.j['version'],courier='driver2@example.test',reason='تبديل الموصّل'),self.admin)
        self.reject(403,'courier.detail',dict(id=j['id']),self.courier);self.courier=self.courier2;self.j=j
        self.step('accepted');self.step('picked_up');self.step('failed',reason='تعذر الاتصال بالعميل')
        self.reject(409,'admin.delivery.reassign',dict(id=self.j['id'],version=self.j['version'],courier='driver@example.test'),self.admin)
        j=self.call('admin.delivery.close',dict(id=self.j['id'],version=self.j['version'],status='returned',reason='استلم المتجر الشحنة المرتجعة'),self.admin);self.assertEqual(j['status'],'returned')
    def test_settle_and_lost_erp_reply(self):
        self.deliver();a=dict(id=self.j['id'],version=self.j['version'],payment_entry='PE-WRONG',cash_received=True,request_id=str(uuid.uuid4()))
        self.reject(422,'admin.delivery.settle',a,self.admin);a['payment_entry']='PE-1';self.j=self.call('admin.delivery.settle',a,self.admin);self.assertTrue(self.j['settled'])
        DeliveryERP.comment_lost=True;self.assertTrue(self.call('admin.delivery.sync',dict(id=self.j['id'],version=self.j['version']),self.admin)['pending'])
        j=self.call('admin.delivery.detail',dict(id=self.j['id']),self.admin);DeliveryERP.comment_lost=False;j=self.call('admin.delivery.sync',dict(id=j['id'],version=j['version']),self.admin)
        self.assertEqual(j['sync'],'synced');self.assertEqual(len(DeliveryERP.comments),1)
    def test_migration_guard_password_reset_and_disable(self):
        self.assertTrue(self.s.delivery_open())
        self.reject(409,'admin.integration.activate',{},self.admin)
        a=self.call('admin.delivery.accounts',token=self.admin)['rows'][0]
        a=next(x for x in self.call('admin.delivery.accounts',token=self.admin)['rows'] if x['user']==self.account['user'])
        self.call('admin.delivery.account.save',{**self.account,'version':a['version'],'password':'Changed-Courier-52!'},self.admin);self.reject(401,'courier.jobs',token=self.courier)
        c=self.call('courier.auth.login',dict(user=self.account['user'],password='Changed-Courier-52!'))['session_token']
        a=next(x for x in self.call('admin.delivery.accounts',token=self.admin)['rows'] if x['user']==self.account['user'])
        self.call('admin.delivery.account.save',{**self.account,'password':'','enabled':False,'version':a['version']},self.admin);self.reject(401,'courier.jobs',token=c)
if __name__=='__main__':unittest.main()
