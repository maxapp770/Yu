"""Published short videos. ERP credentials never appear in a video URL."""
import base64,copy,hashlib,json,re,time
from html.parser import HTMLParser
from urllib.parse import urlsplit,urljoin,unquote,quote,urlunsplit
from .core import fail,text,encode,digest,utc
from .rules import app_id

DEFAULTS=dict(shortcutDesign='شفاف بإطار لامع',shortcutPalette='أسود وذهبي',shortcutOpacity=16,shortcutMovable=True,shortcutShine=True,enableShare=True,enableLikes=True,enableComments=True,enableCart=True,enabled=True,shortcut=True,shortcutTitle='أحدث الريلز',latestCount=6,autoPlay=True,dataSaver=True,rings=True,ringStyle='brand',autoDiscover=False,description=True,attachments=True,sourceOrder='hosted,external,attachment,description',limit=60)
EXT=re.compile(r'\.(mp4|webm)(?:[?#]|$)',re.I)
MEDIA=re.compile(r'^rv-[a-f0-9]{32}\.(mp4|webm)$')
def safe_url(value,origin=''):
    if not isinstance(value,str) or len(value)>2000 or re.search(r'[\x00-\x1f<>"\\]',value):return ''
    value=value.replace(' ','%20')
    if value.startswith('/files/'):value=origin+value
    try:
        u=urlsplit(value);host=u.hostname or '';path=unquote(u.path)
        if u.scheme!='https' or u.username or u.password or u.port not in (None,443) or not re.fullmatch(r'[a-zA-Z0-9-]+(?:\.[a-zA-Z0-9-]+)+',host) or host.rsplit('.',1)[-1].isdigit() or host.endswith(('.localhost','.local','.internal','.test','.invalid')) or '/private/' in path or '..' in path.split('/') or re.search(r'(?:api_key|api_secret|authorization|password)=',u.query,re.I):return ''
        return value
    except ValueError:return ''
def video_kind(url):return 'video' if EXT.search(urlsplit(url).path) else 'link'
class Links(HTMLParser):
    def __init__(self):super().__init__(convert_charrefs=True);self.urls=[]
    def handle_starttag(self,tag,attrs):
        if tag in ('a','video','source'):
            self.urls.extend(v for k,v in attrs if k in ('href','src') and v)
    def handle_data(self,data):self.urls.extend(re.findall(r'https://[^\s<>"\']+',data))
def description_links(value,origin):
    p=Links();p.feed(str(value or '')[:100000]);out=[]
    for url in p.urls:
        v=safe_url(url,origin)
        if v and (EXT.search(urlsplit(v).path) or urlsplit(v).hostname in ('youtube.com','www.youtube.com','youtu.be','vimeo.com','www.vimeo.com','www.instagram.com','instagram.com','www.facebook.com','facebook.com')) and v not in out:out.append(v)
    return out[:30]
def validate_video(raw):
    if not 32<=len(raw)<=5_000_000:fail(413,'حجم الفيديو من 32 بايت إلى 5 ميجابايت. للفيديو الأكبر استخدم رابط استضافة مباشر.')
    if raw[4:8]==b'ftyp':return 'mp4','video/mp4'
    if raw[:4]==b'\x1aE\xdf\xa3' and b'webm' in raw[:4096]:return 'webm','video/webm'
    fail(422,'اختر ملف MP4 أو WebM صالحاً؛ إعادة تسمية ملف آخر لا تكفي.')
def range_bounds(value,size):
    if not value:return 0,size-1,200
    m=re.fullmatch(r'bytes=(\d*)-(\d*)',value)
    if not m or not any(m.groups()):fail(416,'نطاق فيديو غير صالح.')
    start=int(m[1]) if m[1] else max(0,size-int(m[2]));end=min(size-1,int(m[2])) if m[1] and m[2] else size-1
    if start>=size or end<start or (not m[1] and int(m[2])==0):fail(416,'نطاق فيديو غير صالح.')
    return start,end,206

class Reels:
    def reel_snapshot(self,preview=False):
        if preview:return self.draft()
        ch=self.store.get('channel')
        rows=self.store.rows('SELECT snapshot FROM publications WHERE id=?',(ch['publication'],)) if ch.get('publication') else []
        return json.loads(rows[0]['snapshot']) if rows else {}
    def reel_config(self,snapshot):
        row=next(iter(snapshot.get('reels-settings',[])),{})
        if row.get('active') is False:row={**row,'enabled':False}
        return {**DEFAULTS,**{k:v for k,v in row.items() if k in DEFAULTS}}
    def discover_reels(self,a,erp,public=False):
        origin=self.erp_origin();code=text(a.get('item_code'),140);group=text(a.get('group'),140);cursor=max(0,min(int(a.get('cursor') or 0),100000));filters={'disabled':0,'is_sales_item':1}
        if code:filters['name']=code
        if group:filters['item_group']=group
        items=erp.list('Item',['name','item_name','item_group','description','image','modified'],filters,21,cursor,'modified desc, name asc');selected=items[:20];names=[p['name'] for p in selected];rows=[];warnings=[]
        files=[]
        if a.get('attachments',True) and names:
            try:files=erp.list('File',['name','file_name','file_url','is_private','attached_to_name','modified'],{'attached_to_doctype':'Item','attached_to_name':['in',names],'is_folder':0},201,0,'modified desc')
            except Exception:warnings.append('تعذر قراءة المرفقات ضمن صلاحيات الحساب. روابط الوصف تُعرض إن توفرت.')
        if len(files)>200:warnings.append('توجد مرفقات إضافية؛ ضيّق البحث إلى صنف واحد.')
        for p in selected:
            ident=self.reference(p['name'])
            def add(url,source,file=None):
                private=bool(file and file.get('is_private'));clean=safe_url(url,origin)
                if not private and not clean:return
                if public and (private or video_kind(clean)!='video'):return
                rows.append(dict(id='rv-'+digest([self.store.get('channel')['epoch'],p['name'],source,url])[:24],title=text(p.get('item_name')),source=source,url=clean if not private else '',fileId=(file or {}).get('name',''),private=private,kind='private' if private else video_kind(clean),productIds=[ident],groupNames=[text(p.get('item_group'))],item_code=p['name'],image='logo.jpg',modified=(file or p).get('modified',utc()),active=True,position=0,epoch=self.store.get('channel')['epoch']))
            if a.get('description',True):
                for url in description_links(p.get('description'),origin):add(url,'description')
            for f in files[:200]:
                if f.get('attached_to_name')==p['name'] and EXT.search(str(f.get('file_url',''))):add(f['file_url'],'attachment',f)
        return dict(rows=rows,warnings=warnings,next_cursor=cursor+20 if len(items)>20 else None)
    def validate_reel_record(self,module,row,erp):
        if module=='reels-settings':
            if not 0<=float(row.get('shortcutOpacity',16))<=85:fail(422,'عتامة الاختصار من 0 إلى 85.')
            if not 1<=int(row.get('latestCount',6))<=12 or not 1<=int(row.get('limit',60))<=100:fail(422,'عدد الاختصارات 1–12 وحد الريلز 1–100.')
            order=row.get('sourceOrder',DEFAULTS['sourceOrder']).split(',')
            if len(order)!=4 or set(order)!={'hosted','external','attachment','description'}:fail(422,'ترتيب المصادر يجب أن يشمل المصادر الأربعة دون تكرار.')
            return
        if module!='videos':return
        if row.get('source')=='hosted':
            if not MEDIA.fullmatch(row.get('mediaId','')) or not (self.media/row['mediaId']).is_file():fail(422,'ارفع الفيديو أولاً.')
            meta=self.store.get('reel-media:'+row['mediaId'])
            if not meta or meta['epoch']!=self.store.get('channel')['epoch']:fail(409,'ارفع الفيديو بعد تغيير اتصال المتجر.')
            row['url']=''
        elif not safe_url(row.get('url',''),self.erp_origin()):fail(422,'استخدم رابط HTTPS عاماً دون أسرار أو مسار مرفق خاص.')
        else:row['url']=safe_url(row['url'],self.erp_origin())
        row['epoch']=self.store.get('channel')['epoch']
    def reel_upload(self,a,actor):
        try:raw=base64.b64decode(a.get('data',''),validate=True)
        except Exception:fail(422,'بيانات فيديو غير صالحة.')
        ext,mime=validate_video(raw);name='rv-'+digest([self.store.get('channel')['epoch'],hashlib.sha256(raw).hexdigest()])[:32]+'.'+ext
        (self.media/name).write_bytes(raw);self.store.put('reel-media:'+name,dict(epoch=self.store.get('channel')['epoch'],mime=mime,size=len(raw),owner=actor));self.store.audit(actor,'reels.upload',name)
        return dict(mediaId=name,size=len(raw),mime=mime)
    def reel_import(self,a,erp,actor):
        if a.get('publish_copy') is not True:fail(422,'أكّد السماح بنشر نسخة الفيديو للعملاء.')
        f=erp.get('File',text(a.get('file_id'),140))
        if f.get('attached_to_doctype')!='Item':fail(422,'الملف ليس مرفقاً بصنف.')
        p=erp.get('Item',f.get('attached_to_name'))
        if p.get('disabled') or not p.get('is_sales_item'):fail(422,'الصنف غير متاح للبيع.')
        path=f.get('file_url','')
        if not re.fullmatch(r'/(?:private/)?files/[^\\%?#]+\.(?:mp4|webm)',path,re.I) or '..' in path:fail(422,'مسار المرفق غير مدعوم.')
        raw,mime=erp.raw('GET',path,limit=5_000_000);result=self.reel_upload({'data':base64.b64encode(raw).decode()},actor)
        result.update(productIds=[self.reference(p['name'])],groupNames=[p.get('item_group','')],title=text(p.get('item_name')));return result
    def reels_feed(self,a=None):
        a=a or {};snapshot=self.reel_snapshot();cfg=self.reel_config(snapshot);ch=self.store.get('channel');rows=[];warnings=[]
        if cfg['enabled'] and not ch['maintenance']:
            rows=[copy.deepcopy(r) for r in snapshot.get('videos',[]) if r.get('active') is not False and self.in_window(r) and r.get('epoch')==ch['epoch']]
            if cfg['autoDiscover'] and self.store.get('settings')['values']['features'].get('catalog'):
                scope={'item_code':self.resolve_code(a['item_id'])} if a.get('item_id') else {'group':text(a['group'],140)} if a.get('group') else {}
                key='reels-auto:'+digest([ch['epoch'],ch['publication'],scope]);cached=self.store.get(key)
                if cached and time.time()-cached['at']<300:found=cached['data']
                else:
                    try:found=self.discover_reels({**cfg,**scope},self.integration_client(),True);self.store.put(key,dict(at=time.time(),data=found))
                    except Exception:found=dict(rows=[],warnings=['تعذر تحديث فيديوهات الأصناف الآن.'])
                rows+=found['rows'];warnings+=found['warnings']
        order=cfg['sourceOrder'].split(',');rows.sort(key=lambda r:(float(r.get('position',0)),order.index(r['source']) if r.get('source') in order else 9));out=[];seen=set();media={}
        for r in rows:
            src=r.get('source');name=r.get('mediaId','');url='/v1/reels-media/'+name if src=='hosted' and MEDIA.fullmatch(name) else safe_url(r.get('url',''),self.erp_origin())
            if not url:continue
            key=(tuple(r.get('productIds',[])),url)
            if key in seen:continue
            seen.add(key);rid=r['id'];media[rid]=url
            out.append({k:r.get(k) for k in ('id','title','productIds','groupNames','image','modified','position') }|dict(kind='video' if src=='hosted' else video_kind(url),source=src,url=url))
        return dict(rows=out[:int(cfg['limit'])],settings=cfg,_videos={r['id']:media[r['id']] for r in out[:int(cfg['limit'])]},warnings=warnings,epoch=ch['epoch'])
    def reel_bytes(self,name,range_header=''):
        if not MEDIA.fullmatch(name):fail(404,'الفيديو غير موجود.')
        feed=self.reels_feed()
        if '/v1/reels-media/'+name not in feed['_videos'].values():fail(404,'الفيديو غير منشور أو انتهت فترته.')
        path=self.media/name
        if not path.is_file():fail(404,'الفيديو غير متاح.')
        size=path.stat().st_size;start,end,status=range_bounds(range_header,size)
        with path.open('rb') as f:f.seek(start);body=f.read(end-start+1)
        return body,('video/mp4' if name.endswith('.mp4') else 'video/webm'),start,end,size,status
