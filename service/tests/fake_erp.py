"""Deterministic ERP fixture used only by local tests, never production server."""
from copy import deepcopy
from hec_service.core import Error,fail
class FakeERP:
    documents={};calls=[];lost_reply=False;offline=False;revoked=False;export=True
    def __init__(self,base,auth,allowed):self.base=base;self.auth=dict(auth or {})
    def identity(self):
        if self.offline:fail(503,'offline')
        token=self.auth.get('token','')
        if token.startswith('manager'):roles=[] if self.revoked else ['System Manager'];user='manager@example.test'
        elif token.startswith('reporter'):roles=['Accounts Manager'];user='reporter@example.test'
        elif token.startswith('service'):roles=['Sales User','Item User'];user='support@example.test'
        else:fail(401,'invalid credentials')
        return {'user':user,'name':user,'roles':roles}
    def login(self,a):
        if a.get('kind')=='token':self.auth={'token':a.get('key','')+':'+a.get('secret','')}
        else:
            if a.get('password')!='manager-password':fail(401,'invalid credentials')
            self.auth={'token':a.get('user','').split('@')[0]+'-key:test-secret'}
        return self.identity()
    def get(self,doctype,name):
        if self.offline:fail(503,'offline')
        self.calls.append((self.auth.get('token'),doctype,'get',name))
        if doctype=='Report':return {'name':name,'report_type':'Script Report','ref_doctype':'Sales Invoice' if 'Sales' in name else 'Bin','module':'Selling' if 'Sales' in name else 'Stock','disabled':0}
        if doctype=='Sales Order':
            if name not in self.documents:fail(404,'missing')
            return deepcopy(self.documents[name])
        if doctype=='Item':return dict(name=name,item_name='طقم أواني الطبخ',stock_uom='Nos',item_group='أدوات المطبخ',brand='HEC',image='',is_stock_item=1,is_sales_item=1,disabled=0,creation='2026-09-01T00:00:00Z',modified='2026-09-12T00:00:00Z',barcodes=[{'barcode':'1234567890123'}])
        if doctype=='Price List':return {'name':name,'selling':1,'enabled':1,'currency':'YER'}
        if doctype in ('Warehouse','Cost Center','Sales Taxes and Charges Template'):return {'name':name,'company':'شركة الاختبار','is_group':0,'taxes':[]}
        return {'name':name,'disabled':0,'enabled':1,'default_currency':'YER'}
    def list(self,doctype,fields=None,filters=None,limit=50,start=0,order='modified desc',or_filters=None):
        if self.offline:fail(503,'offline')
        self.calls.append((self.auth.get('token'),doctype,'list',filters))
        f=filters or {}
        if doctype=='Report':names=['Sales Register','Stock Balance','General Ledger']
        elif doctype=='Company':names=['شركة الاختبار','شركة ثانية']
        elif doctype=='Price List':names=['البيع']
        elif doctype=='Warehouse':names=['المخزن الرئيسي']
        elif doctype=='Currency':names=['YER']
        elif doctype=='Customer':names=['CUST-1','CUST-2']
        elif doctype=='Role':names=['System Manager','Accounts Manager','Stock Manager','Sales Manager']
        elif doctype=='Item':return [self.get('Item','ITEM-1')]
        elif doctype=='Item Price':return [dict(item_code='ITEM-1',price_list_rate=500,uom='Nos',valid_from=None,valid_upto=None,customer=None,supplier=None,batch_no=None)]
        elif doctype=='Bin':return [dict(item_code='ITEM-1',actual_qty=20,reserved_qty=2)]
        elif doctype=='Product Bundle':return []
        elif doctype=='Sales Order':return [deepcopy(r) for r in self.documents.values() if all(r.get(k)==v for k,v in f.items())][:limit]
        else:names=['اختيار']
        if isinstance(f.get('name'),list):
            op,value=f['name']
            if op=='in':names=[n for n in names if n in value]
            if op=='like':names=[n for n in names if value.strip('%').lower() in n.lower()]
        return [{'name':n} for n in names[start:start+limit]]
    def method(self,name,args=None,post=False):
        if self.offline:fail(503,'offline')
        a=args or {};self.calls.append((self.auth.get('token'),name,'method',deepcopy(a)))
        if name.endswith('has_permission'):return {'has_permission':self.export if a.get('perm_type')=='export' else True}
        if name.endswith('get_script'):
            if self.auth.get('token','').startswith('service'):fail(403,'report denied')
            return {'filters':[],'script':'throw new Error("MUST NEVER EXECUTE ERP SCRIPT")'}
        if name.endswith('query_report.run'):return {'columns':[{'fieldname':'item','label':'الصنف','fieldtype':'Data'},{'fieldname':'amount','label':'الإجمالي','fieldtype':'Currency'}],'result':[{'item':'صنف الاختبار','amount':500},{'item':'=HYPERLINK("bad")','amount':-10}],'report_summary':[{'label':'الإجمالي','value':490,'currency':'YER'}]}
        if name.endswith('get_item_details'):return {'rate':500,'price_list_rate':500,'conversion_factor':1}
        if name.endswith('get_logged_user'):return self.identity()['user']
        if name.endswith('get_roles'):return self.identity()['roles']
        fail(404,'unknown mock method')
    def create(self,doctype,document):
        assert doctype=='Sales Order'
        doc=deepcopy(document);doc.update(name='SO-TEST-'+str(len(self.documents)+1),status='Draft',docstatus=0,grand_total=sum(r['qty']*r['rate'] for r in doc['items']),transaction_date='2026-09-12',modified='2026-09-12',packed_items=[])
        for r in doc['items']:r.update(item_name='طقم أواني الطبخ',amount=r['qty']*r['rate'])
        self.documents[doc['name']]=doc
        if self.lost_reply:fail(503,'reply lost')
        return deepcopy(doc)
