"""WSGI entry point. Bind behind HTTPS reverse proxy; no browser credentials in CORS."""
import base64,json,os,re,threading,time,ipaddress
from pathlib import Path
from wsgiref.simple_server import make_server
from .core import Store,Error,fail,encode
from .api import Service
from .rules import image_path

def create_service():
    key=os.environ.get('HEC_MASTER_KEY')
    if not key:raise RuntimeError('HEC_MASTER_KEY is required; run python -m hec_service.setup init first')
    data=Path(os.environ.get('HEC_DATA_DIR','./data'))
    base=os.environ.get('HEC_ERP_ORIGIN','https://erptest.wahatalhaitham.com')
    allowed=[x.strip().lower() for x in os.environ.get('HEC_ERP_HOSTS','erptest.wahatalhaitham.com').split(',') if x.strip()]
    return Service(Store(data/'store.db',key),base,allowed,timezone=os.environ.get('HEC_TIMEZONE','Asia/Aden'))

class Application:
    def __init__(self,service):self.service=service
    def __call__(self,env,start):
        headers=[('Content-Type','application/json; charset=utf-8'),('Cache-Control','no-store'),('X-Content-Type-Options','nosniff'),('Referrer-Policy','no-referrer')]
        try:
            path=env.get('PATH_INFO','');method=env.get('REQUEST_METHOD','GET')
            if path=='/healthz' and method=='GET':status=200;body=encode({'ok':True,'service':'hec-standalone','version':'2.2.0'}).encode()
            elif re.fullmatch(r'/v1/images/erp-[a-f0-9]{24}\.jpg',path) and method=='GET':
                name=path.rsplit('/',1)[-1]
                if not self.service.store.get('settings')['values']['features'].get('images'):fail(403,'تحميل الصور متوقف.')
                local=self.service.media/name
                if local.is_file():body=local.read_bytes()
                else:
                    rows=self.service.store.rows('SELECT path FROM images WHERE id=? AND epoch=?',(name,self.service.store.get('channel')['epoch']))
                    if not rows or not image_path(rows[0]['path']):fail(404,'الصورة غير متاحة.')
                    raw,mime=self.service.integration_client().raw('GET',rows[0]['path'],limit=5_000_000)
                    if mime.split(';')[0] not in ('image/jpeg','image/png','image/webp'):fail(422,'نوع الصورة غير متاح.')
                    from PIL import Image
                    import io
                    image=Image.open(io.BytesIO(raw))
                    if image.width*image.height>16_000_000:fail(413,'الصورة كبيرة.')
                    image.load();image.thumbnail((1600,1600));out=io.BytesIO();image.convert('RGB').save(out,format='JPEG',quality=85);body=out.getvalue()
                    # Cached public ERP images live separately by integration epoch.
                status=200;headers[0]=('Content-Type','image/png' if body.startswith(b'\x89PNG') else 'image/jpeg');headers[1]=('Cache-Control','private, max-age=300')
            elif path.startswith('/v1/reels-media/') and method=='GET':
                body,mime,a,b,total,status=self.service.reel_bytes(path.rsplit('/',1)[-1],env.get('HTTP_RANGE',''))
                headers[0]=('Content-Type',mime);headers.append(('Accept-Ranges','bytes'))
                if status==206:headers.append(('Content-Range',f'bytes {a}-{b}/{total}'))
            elif path=='/v1/rpc'  and method=='POST':
                if env.get('HTTP_ORIGIN'):fail(403,'لا يقبل هذا المسار طلبات المواقع الخارجية.')
                if not env.get('CONTENT_TYPE','').startswith('application/json'):fail(415,'يلزم JSON.')
                size=int(env.get('CONTENT_LENGTH') or 0)
                if not 1<=size<=8_000_000:fail(413,'حجم الطلب غير صالح.')
                try:payload=json.loads(env['wsgi.input'].read(size),parse_constant=lambda x:(_ for _ in ()).throw(ValueError()))
                except (ValueError,UnicodeError):fail(422,'JSON غير صالح.')
                if not isinstance(payload,dict) or set(payload)-{'op','args'}:fail(422,'صيغة الطلب غير صالحة.')
                authorization=env.get('HTTP_AUTHORIZATION','');token=authorization[7:] if authorization.startswith('Bearer ') else ''
                remote=env.get('REMOTE_ADDR','unknown')
                if remote in os.environ.get('HEC_TRUSTED_PROXY','').split(',') and env.get('HTTP_X_HEC_CLIENT_IP'):
                    remote=str(ipaddress.ip_address(env['HTTP_X_HEC_CLIENT_IP']))
                result=self.service.dispatch(payload.get('op'),payload.get('args') or {},token,remote)
                status=200;body=encode({'message':result}).encode()
            else:fail(404,'المسار غير موجود.')
        except Error as exc:
            status=exc.status if 400<=exc.status<=599 else 502;body=encode({'error':{'status':status,'message':str(exc),'code':exc.code}}).encode()
        except (TypeError,ValueError,OverflowError):status=422;body=encode({'error':{'status':422,'message':'تحقق من صيغة المدخلات.'}}).encode()
        except Exception:
            # Do not serialize request, credentials, ERP response or stack details to callers/logs.
            status=500;body=encode({'error':{'status':500,'message':'تعذر إكمال العملية. راجع حالة الخدمة.'}}).encode()
        headers.append(('Content-Length',str(len(body))))
        start(str(status)+' '+{200:'OK',206:'Partial Content',401:'Unauthorized',403:'Forbidden',404:'Not Found'}.get(status,'Error'),headers)
        return [body]

application=None
def app(env,start):
    global application
    if application is None:application=Application(create_service())
    return application(env,start)

def scheduler():
    service=create_service()
    while True:
        try:
            service.tick();service.store.put('scheduler_heartbeat',time.time())
        except Exception:pass
        time.sleep(30)

if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser();parser.add_argument('--port',type=int,default=8080);parser.add_argument('--scheduler',action='store_true');args=parser.parse_args()
    if args.scheduler:scheduler()
    else:
        # Development server only. Deployment uses the provided Gunicorn service.
        with make_server('127.0.0.1',args.port,app) as server:server.serve_forever()
