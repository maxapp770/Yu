"""Local contract tests; not a replacement for tests on an installed Frappe site."""
import importlib
import json
from pathlib import Path
import sys
import types
import unittest
from contextlib import contextmanager
from datetime import datetime
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'integration/frappe/hec_bridge'))
from hec_bridge import rules

class Obj(dict):
    def __getattr__(self,k): return self.get(k)
    def __setattr__(self,k,v): self[k]=v
    def save(self,**kw): self['saved']=True;return self
    def insert(self,**kw): return self
class Denied(Exception): pass
fake=types.ModuleType('frappe');fake.session=Obj(user='manager');fake.local=Obj(response={})
fake.PermissionError=Denied;fake.ValidationError=ValueError
fake.whitelist=lambda *args,**kw:lambda f:f
fake.throw=lambda m,t:(_ for _ in ()).throw(t(m))
fake.get_roles=lambda user:['System Manager'] if user=='manager' else []
fake.get_cached_value=lambda dt,u,k:u!='disabled'
fake.set_user=lambda user:setattr(fake.session,'user',user)
fake.get_list=lambda *a,**k:[]
fake.has_permission=lambda *a,**k:True
utils=types.ModuleType('frappe.utils');utils.now_datetime=datetime.now;utils.nowdate=lambda:'2026-09-12';utils.add_days=lambda d,n:d;utils.getdate=lambda d:d;utils.get_datetime=datetime.fromisoformat
fake.utils=utils
sessions=types.ModuleType('frappe.sessions');sessions.get_csrf_token=lambda:'test-token'
sys.modules.update({'frappe':fake,'frappe.utils':utils,'frappe.sessions':sessions})
from hec_bridge import api

class ContractTests(unittest.TestCase):
    def setUp(self):
        fake.session.user='manager';fake.local.response={};self.values=rules.default_settings();self.values.update(company='Allowed',price_list='Retail',currency='YER',warehouse='Main',integration_user='service')
        self.doc=Obj(doctype='HEC Bridge Settings',name='store',data=json.dumps(self.values),revision=1)
        self.audit=[];self.sql=[]
        def get_doc(dt,name=None):
            if isinstance(dt,dict): self.audit.append(dt);return Obj(dt)
            if dt=='HEC Bridge Settings': return self.doc
            return Obj(doctype=dt,name=name,company='Other' if name=='Foreign' else 'Allowed',enabled=1,selling=1,currency='YER',is_group=0)
        fake.get_doc=get_doc
        fake.db=Obj(get_value=lambda *a,**kw:1,sql=lambda q,p:self.sql.append((q,p)),exists=lambda *a:True)
        fake.get_list=lambda *a,**k:[]
        fake.has_permission=lambda dt,ptype='read',doc=None,user=None:not(doc and doc.name=='Denied')
    def test_guest_has_no_admin_access(self):
        fake.session.user='Guest'
        for fn,args in [(api.settings,()),(api.options,('Company',)),(api.list_records,('home',)),(api.save_record,('home',)),(api.save_settings,({},'1'))]:
            with self.subTest(fn=fn.__name__),self.assertRaises(Denied):fn(*args)
    def test_customer_has_no_admin_access(self):
        fake.session.user='customer'
        with self.assertRaises(Denied):api.manager()
    def test_disabled_user_denied(self):
        fake.session.user='disabled'
        with self.assertRaises(Denied):api.user_required()
    def test_role_is_checked_again_after_revocation(self):
        self.assertEqual(api.manager(),'manager');fake.session.user='customer'
        with self.assertRaises(Denied):api.settings()
    def test_client_role_flag_cannot_enable_admin(self):
        fake.session.user='customer'
        with self.assertRaises(Denied):api.context(admin=1)
    def test_service_user_restored_on_error(self):
        with self.assertRaises(RuntimeError):
            with api.service(self.values):
                self.assertEqual(fake.session.user,'service');raise RuntimeError()
        self.assertEqual(fake.session.user,'manager')
    def test_document_permissions_enforced_for_choices(self):
        self.values['company']='Denied'
        with self.assertRaises(Denied):api.check_choices(self.values)
    def test_cross_company_warehouse_rejected(self):
        self.values['warehouse']='Foreign'
        with self.assertRaises(ValueError):api.check_choices(self.values)
    def test_stale_settings_revision_rejected(self):
        with self.assertRaises(ValueError):api.save_settings(self.values,'0')
        self.assertNotIn('saved',self.doc);self.assertTrue(self.sql)
    def test_valid_settings_saved_and_audited(self):
        result=api.save_settings(self.values,'1')
        self.assertEqual(result['version'],'2');self.assertEqual(len(self.audit),1);self.assertEqual(self.audit[0]['actor'],'manager')
    def test_company_options_intersect_user_permissions(self):
        def get_list(dt,**kw):
            if fake.session.user=='service':return [Obj(name='Allowed'),Obj(name='Denied')]
            return [Obj(name='Allowed')]
        fake.get_list=get_list
        result=api.options('Company')
        self.assertEqual([r['name'] for r in result['items']],['Allowed'])
    def test_arbitrary_doctype_selector_rejected(self):
        with self.assertRaises(Denied):api.options('DocType')
    def test_unknown_and_unsupported_features_rejected(self):
        for feature in ['ignore_permissions','automation','affiliate','delivery']:
            v=json.loads(json.dumps(self.values));v['features'][feature]=True
            with self.subTest(feature=feature),self.assertRaises(ValueError):rules.validate_settings(v)
    def test_no_catalog_without_required_pricelist(self):
        self.values['features']['catalog']=True;self.values['price_list']=''
        with self.assertRaises(ValueError):rules.validate_settings(self.values)
    def test_submit_requires_orders(self):
        self.values['features']['order_submit']=True
        with self.assertRaises(ValueError):rules.validate_settings(self.values)
    def test_price_list_currency_must_match(self):
        self.values['currency']='USD'
        with self.assertRaises(ValueError):api.check_choices(self.values)
    def test_disabled_flags_are_real_booleans(self):
        self.assertFalse(rules.flag('false'));self.assertFalse(rules.flag('0'));self.assertTrue(rules.flag('true'))
        with self.assertRaises(ValueError):rules.flag('yes')
    def test_readonly_or_unknown_module_rejected(self):
        for module in ('users','products','orders','System Settings'):
            with self.subTest(module=module),self.assertRaises(ValueError):rules.record(module,{'title':'test'})
    def test_content_plain_text_and_field_allowlist(self):
        for payload in ({'displayTitle':'<img src=x onerror=alert(1)>'},{'api_secret':'secret'},{'displayTitle':'a','roles':['System Manager']}):
            with self.subTest(payload=payload),self.assertRaises(ValueError):rules.record('home',payload)
        self.assertEqual(rules.record('home',{'displayTitle':'أي قطعة 500 ر.ي'})['displayTitle'],'أي قطعة 500 ر.ي')
    def test_prototype_payload_rejected(self):
        with self.assertRaises(ValueError):rules.record('home',{'motion':{'__proto__':{'admin':True}}})
    def test_prices_cannot_be_supplied_on_order(self):
        with self.assertRaises(ValueError):rules.order_lines([{'id':rules.app_id('item'),'qty':1,'rate':0.01}])
    def test_customer_identity_cannot_be_supplied_on_order(self):
        with self.assertRaises(ValueError):rules.order_lines([{'id':rules.app_id('item'),'qty':1,'customer':'victim'}])
    def test_order_quantities_and_duplicates(self):
        code=rules.app_id('صنف / طويل وبه مسافات')
        for lines in ([],[{'id':code,'qty':0}],[{'id':code,'qty':float('nan')}],[{'id':code,'qty':1000}],[{'id':code,'qty':1}]*2):
            with self.subTest(lines=lines),self.assertRaises(ValueError):rules.order_lines(lines)
        self.assertEqual(rules.order_lines([{'id':code,'qty':2}])[0]['qty'],2)
    def test_hash_supports_unicode_and_is_stable(self):
        self.assertEqual(rules.app_id('صنف'),rules.app_id('صنف'));self.assertRegex(rules.app_id('صنف'),'ERP_[a-f0-9]{24}')
    def test_request_digest_is_order_independent(self):
        lines=[{'id':rules.app_id('a'),'qty':1},{'id':rules.app_id('b'),'qty':2}]
        self.assertEqual(rules.request_hash(lines),rules.request_hash(list(reversed(lines))))
    def test_remote_images_reject_private_or_foreign_paths(self):
        self.assertTrue(rules.image_path('/files/صورة المنتج.jpg'))
        for value in ('/private/files/a.jpg','https://evil.test/a.jpg','/files/../a.jpg','/files/a.svg','/files/a.jpg?token=x','/files/%2e%2e/a.jpg'):
            self.assertFalse(rules.image_path(value))
    def test_native_no_credentials_and_fixed_tls_origin(self):
        source=(ROOT/'app/src/main/java/com/alhaitham/hec/ERPBridge.java').read_text()
        self.assertIn('if(!admin)throw new Failure(403',source)
        self.assertIn('setInstanceFollowRedirects(false)',source)
        self.assertNotIn('setHostnameVerifier',source);self.assertNotIn('TrustAll',source)
        self.assertNotIn('SharedPreferences',source);self.assertNotIn('123456',source)
    def test_customer_bundle_excludes_dashboard_files(self):
        web=ROOT/'build/variants/customer/assets/web'
        for name in ['management.js','management-preview.js','management-config.js','erp-admin.js']:
            self.assertFalse((web/name).exists())
        self.assertNotIn('management.js',(web/'index.html').read_text())
    def test_admin_owns_distinct_android_package(self):
        customer=(ROOT/'build/variants/customer/AndroidManifest.xml').read_text();admin=(ROOT/'build/variants/admin/AndroidManifest.xml').read_text()
        self.assertIn('com.alhaitham.hec.preview',customer);self.assertIn('com.alhaitham.hec.admin',admin)
        self.assertNotIn('android.intent.action.SEND',admin);self.assertNotIn('android.intent.action.VIEW',admin)

if __name__=='__main__': unittest.main(verbosity=2)
