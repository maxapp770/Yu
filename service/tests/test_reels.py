import unittest,tempfile,base64,copy,io
from pathlib import Path
from test_service import fixture
from fake_erp import FakeERP
from hec_service.core import Error
from hec_service.reels import safe_url,description_links,range_bounds,DEFAULTS
class VideoERP(FakeERP):
    def list(self,t,*args,**kw):
        if t=='Item':return [dict(name='ITEM-1',item_name='اختبار ريلز',item_group='أدوات المطبخ',description='<p><a href="https://media.example.com/test.mp4?x=1&amp;y=2">فيديو</a></p><script>alert(1)</script>',modified='2026-09-13')]
        if t=='File':return [dict(name='PUBLIC',attached_to_name='ITEM-1',file_url='/files/clip.webm',is_private=0),dict(name='PRIVATE',attached_to_name='ITEM-1',file_url='/private/files/private.mp4',is_private=1)]
        return super().list(t,*args,**kw)
class ReelsTest(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.s=fixture(Path(self.tmp.name)/'s.db');self.s.erp_factory=VideoERP
        self.admin=self.rpc('auth.login',dict(app_role='admin',user='manager@example.test',password='manager-password'))['session_token']
    def tearDown(self):self.tmp.cleanup()
    def rpc(self,op,a=None,t=''):return self.s.dispatch(op,a or {},t,'test')
    def publish(self):
        p=self.rpc('admin.publication',t=self.admin);self.rpc('admin.publish',dict(expected_digest=p['draft_digest'],title='اختبار فيديو'),self.admin)
    def test_html_and_url_boundaries(self):
        for url in ['javascript:alert(1)','http://cdn.example.com/a.mp4','https://user:pass@cdn.example.com/a.mp4','https://127.0.0.1/a.mp4','https://a.local/a.mp4','https://cdn.example.com/private/a.mp4','https://cdn.example.com/a.mp4?api_secret=abc']:
            self.assertFalse(safe_url(url),url)
        links=description_links('<video src="/files/a.mp4"></video><a href="https://cdn.example.com/b.webm?a=1&amp;b=2">شاهد</a><img src="https://cdn.example.com/no.mp4">',self.s.default_origin)
        self.assertEqual(len(links),2);self.assertTrue(links[1].endswith('a=1&b=2'))
    def test_discovery_permissions_and_private_files(self):
        with self.assertRaises(Error):self.rpc('admin.reels.discover')
        r=self.rpc('admin.reels.discover',{},self.admin);self.assertEqual(len(r['rows']),3)
        private=next(x for x in r['rows'] if x['private']);self.assertEqual(private['url'],'')
        cfg=self.s.table('reels-settings')[0];self.rpc('admin.save',dict(module='reels-settings',id=cfg['id'],version=cfg['version'],payload=dict(autoDiscover=True)),self.admin);self.publish()
        feed=self.rpc('reels.feed');self.assertEqual(len(feed['rows']),2);self.assertNotIn('/private/',str(feed))
        with self.assertRaises(Error):self.rpc('admin.reels.import',dict(file_id='PRIVATE'),self.admin)
    def test_upload_publish_range_hide_epoch(self):
        raw=b'\x00\x00\x00\x20ftypisom'+bytes(300)
        up=self.rpc('admin.reels.upload',dict(data=base64.b64encode(raw).decode()),self.admin)
        with self.assertRaises(Error):self.s.reel_bytes(up['mediaId'])
        row=self.rpc('admin.save',dict(module='videos',payload=dict(title='ريل الاختبار',source='hosted',mediaId=up['mediaId'],productIds=[],groupNames=[],active=True,position=0)),self.admin)
        self.assertEqual(self.rpc('reels.feed')['rows'],[]);self.publish();self.assertEqual(len(self.rpc('reels.feed')['rows']),1)
        b,m,a,z,total,status=self.s.reel_bytes(up['mediaId'],'bytes=4-11');self.assertEqual(b,raw[4:12]);self.assertEqual(status,206)
        self.rpc('admin.save',dict(module='videos',id=row['id'],version=row['version'],payload={'active':False}),self.admin);self.publish()
        with self.assertRaises(Error):self.s.reel_bytes(up['mediaId'])
        ch=self.s.store.get('channel');ch['epoch']+=1;self.s.store.put('channel',ch)
        with self.assertRaises(Error):self.rpc('admin.save',dict(module='videos',payload=dict(title='نسخة قديمة',source='hosted',mediaId=up['mediaId'])),self.admin)
    def test_range_invalid_and_fake_upload(self):
        for r in ['bytes=9-2','bytes=100-','bytes=-0','bytes=1-2,4-5','wat']:
            with self.assertRaises(Error):range_bounds(r,20)
        self.assertEqual(range_bounds('bytes=-5',20),(15,19,206))
        with self.assertRaises(Error):self.rpc('admin.reels.upload',dict(data=base64.b64encode(b'<script>'+bytes(50)).decode()),self.admin)
    def test_social_auth_persistence_idempotency_and_ownership(self):
        raw=b'\x00\x00\x00\x20ftypisom'+bytes(300)
        up=self.rpc('admin.reels.upload',dict(data=base64.b64encode(raw).decode()),self.admin)
        self.rpc('admin.save',dict(module='videos',payload=dict(title='التفاعل',source='hosted',mediaId=up['mediaId'],active=True)),self.admin);self.publish()
        rid=self.rpc('reels.feed')['rows'][0]['id'];a=dict(reel_id=rid)
        self.assertFalse(self.rpc('reels.social',a)['canInteract'])
        with self.assertRaises(Error):self.rpc('reels.react',dict(**a,liked=True))
        tokens=[]
        for i in [1,2]:
            email=f'customer{i}@example.test'
            self.rpc('admin.customer.create',dict(email=email,first_name='عميل',customer=f'CUST-{i}',company='شركة الاختبار',password='a-customer-password'),self.admin)
            tokens.append(self.rpc('auth.login',dict(user=email,password='a-customer-password'))['session_token'])
        for _ in range(2):result=self.rpc('reels.react',dict(**a,liked=True),tokens[0])
        self.assertEqual(result['likes'],1);self.assertTrue(result['liked'])
        for _ in range(2):result=self.rpc('reels.comment',dict(**a,text='صنف رائع',request_id='comment-request-1'),tokens[0])
        self.assertEqual(result['commentCount'],1);cid=result['comments'][0]['id']
        other=self.rpc('reels.social',a,tokens[1]);self.assertFalse(other['comments'][0]['canDelete'])
        with self.assertRaises(Error):self.rpc('reels.comment.delete',dict(**a,comment_id=cid),tokens[1])
        result=self.rpc('admin.reels.comment.delete',dict(**a,comment_id=cid),self.admin);self.assertEqual(result['commentCount'],0)
        self.assertEqual(self.rpc('reels.react',dict(**a,liked=False),tokens[0])['likes'],0)
        with self.assertRaises(Error):self.rpc('reels.social',dict(reel_id='not-published'))
if __name__=='__main__':unittest.main()
