import base64,io,tempfile,unittest,json
from pathlib import Path
from copy import deepcopy
from PIL import Image
from test_service import fixture
from fake_erp import FakeERP
from hec_service.core import Error,fail
from hec_service.erp import ERP
from hec_service.studio import photo_bytes

class PhotoERP(FakeERP):
    files=[];modified='1';main='';uploads=0;lost=False;permitted=True
    def identity(self):
        if self.auth.get('token','').startswith('photo'):return dict(user='photo@example.test',name='المصور',roles=['Photo Editor'])
        return super().identity()
    def get(self,t,n):
        if t=='User':return dict(name=n,enabled=1,user_type='System User')
        if t=='Item':return {**super().get(t,n), 'modified':self.modified,'image':self.main,'uoms':[{'uom':'Nos','conversion_factor':1},{'uom':'Box','conversion_factor':12}]}
        if t=='File':return deepcopy(next(f for f in self.files if f['name']==n))
        if t=='WhatsApp Share Settings':fail(404,'not installed')
        return super().get(t,n)
    def list(self,t,*args,**kw):
        if t=='File':return deepcopy(self.files)
        if t=='User':return [dict(name='photo@example.test',full_name='المصور')]
        if t=='Role':return [dict(name='Photo Editor'),dict(name='All')]
        return super().list(t,*args,**kw)
    def method(self,n,a=None,post=False):
        if n.endswith('has_permission'):return dict(has_permission=self.permitted)
        if n.endswith('set_value'):type(self).main=a['value'];type(self).modified=str(int(self.modified)+1);return dict(ok=True)
        return super().method(n,a,post)
    def upload_file(self,raw,filename,mime,doctype,docname):
        type(self).uploads+=1;f=dict(name='FILE-'+str(self.uploads),file_name=filename,file_url='/files/'+filename,attached_to_doctype=doctype,attached_to_name=docname,is_private=0);self.files.append(f)
        if self.lost:fail(503,'lost response')
        return f

class StudioTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.s=fixture(Path(self.tmp.name)/'s.db');self.s.erp_factory=PhotoERP
        PhotoERP.files=[];PhotoERP.modified='1';PhotoERP.main='';PhotoERP.uploads=0;PhotoERP.lost=False;PhotoERP.permitted=True
        self.admin=self.call('auth.login',dict(app_role='admin',user='manager@example.test',password='manager-password'))['session_token'];self.id=self.call('admin.item-media.search',token=self.admin)['items'][0]['id']
        b=io.BytesIO();Image.new('RGBA',(64,64),(255,0,0,50)).save(b,'PNG');self.data=base64.b64encode(b.getvalue()).decode()
    def tearDown(self):self.tmp.cleanup()
    def call(self,op,a=None,token=''):return self.s.dispatch(op,a or {},token,'test')
    def grant(self):
        access=self.call('admin.media-access',token=self.admin);self.call('admin.media-access.save',dict(enabled=True,users=['photo@example.test'],roles=[],version=access['version']),self.admin)
        return self.call('auth.login',dict(app_role='admin',user='photo@example.test',password='manager-password'))['session_token']
    def test_photo_role_upload_and_revoke(self):
        with self.assertRaises(Error):self.call('auth.login',dict(app_role='admin',user='photo@example.test',password='manager-password'))
        actor=self.grant();context=self.call('auth.context',token=actor);self.assertTrue(context['can_media']);self.assertFalse(context['can_manage']);self.assertFalse(context['can_reports'])
        for op in ['admin.config','admin.studio.list','reports.list','admin.media-access']:
            with self.assertRaises(Error):self.call(op,token=actor)
        args=dict(id=self.id,data=self.data);r=self.call('admin.item-media.upload',args,actor);self.assertIn('ITEM-1',r['name']);self.assertIn('طقم',r['name']);self.assertEqual(PhotoERP.files[0]['attached_to_doctype'],'Item');self.call('admin.item-media.upload',args,actor);self.assertEqual(PhotoERP.uploads,1)
        rows=self.call('admin.item-media.list',dict(id=self.id),actor);self.assertEqual(len(rows['images']),1);self.call('admin.item-media.main',dict(id=self.id,file=r['file'],version=rows['version']),actor)
        with self.assertRaises(Error):self.call('admin.item-media.main',dict(id=self.id,file=r['file'],version=rows['version']),actor)
        access=self.call('admin.media-access',token=self.admin);self.call('admin.media-access.save',dict(enabled=True,users=[],roles=[],version=access['version']),self.admin)
        with self.assertRaises(Error):self.call('admin.item-media.list',dict(id=self.id),actor)
    def test_invalid_permissions_and_lost_response(self):
        actor=self.grant();PhotoERP.permitted=False
        with self.assertRaises(Error):self.call('admin.item-media.upload',dict(id=self.id,data=self.data),actor)
        self.assertEqual(PhotoERP.uploads,0);PhotoERP.permitted=True
        with self.assertRaises(Error):self.call('admin.item-media.upload',dict(id=self.id,data=base64.b64encode(b'<svg/>').decode()),actor)
        PhotoERP.lost=True
        with self.assertRaises(Error):self.call('admin.item-media.upload',dict(id=self.id,data=self.data),actor)
        self.assertEqual(PhotoERP.uploads,1);PhotoERP.lost=False;self.call('admin.item-media.upload',dict(id=self.id,data=self.data),actor);self.assertEqual(PhotoERP.uploads,1)
    def test_design_document_and_unit_price(self):
        product=self.call('admin.studio.product',dict(id=self.id),self.admin);self.assertEqual(product['price'],500)
        self.assertIsNone(self.call('admin.studio.product',dict(id=self.id,uom='Box'),self.admin)['price'])
        d=dict(width=1440,height=600,layers=[],title='تصميم الاختبار');saved=self.call('admin.studio.save',dict(design=d),self.admin);self.assertEqual(self.call('admin.studio.list',token=self.admin)['rows'][0]['id'],saved['id'])
        self.call('admin.studio.save',dict(id=saved['id'],version=saved['version'],design=d),self.admin)
        with self.assertRaises(Error):self.call('admin.studio.save',dict(id=saved['id'],version=saved['version'],design=d),self.admin)
        with self.assertRaises(Error):self.call('admin.studio.save',dict(design={**d,'width':999999}),self.admin)
    def test_png_metadata_removed_alpha_retained_and_multipart(self):
        raw,ext=photo_bytes(self.data);im=Image.open(io.BytesIO(raw));self.assertEqual(ext,'png');self.assertEqual(im.getpixel((0,0))[3],50)
        class Capture(ERP):
            def raw(self,*args,**kw):self.captured=(args,kw);return {'message':{'name':'FILE-1'}}
        erp=Capture('https://example.com',{'token':'fixture-key:fixture-secret'},['example.com']);erp.upload_file(raw,'اسم_ITEM-1.png','image/png','Item','ITEM-1');args,kw=erp.captured;self.assertEqual(args,('POST','/api/method/upload_file'));self.assertIn(b'name="doctype"\r\n\r\nItem',kw['body_override']);self.assertIn(b'name="docname"\r\n\r\nITEM-1',kw['body_override']);self.assertIn(raw,kw['body_override'])
if __name__=='__main__':unittest.main()
