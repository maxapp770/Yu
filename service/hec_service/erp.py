"""HTTPS-only, DNS-pinned, bounded REST client. Never redirects credentials."""
import http.client, ipaddress, json, socket, ssl, os, urllib.request, urllib.error
from http.cookies import SimpleCookie
from urllib.parse import urlsplit, quote, urlencode
from .core import Error, fail, encode, text

def origin(value,allowed):
    try:
        u=urlsplit(value.strip().rstrip('/'));host=u.hostname
        if u.scheme!='https' or not host or u.username or u.password or u.path or u.query or u.fragment or u.port not in (None,443):raise ValueError()
        host=host.encode('idna').decode().lower()
        if host not in allowed:fail(403,'النطاق غير موجود في قائمة خوادم ERP المسموحة على الخدمة.')
        return 'https://'+host
    except (ValueError,AttributeError,UnicodeError):fail(422,'أدخل عنوان HTTPS صالحاً دون مسار أو بيانات دخول.')

class PinnedHTTPS(http.client.HTTPSConnection):
    def connect(self):
        addresses=socket.getaddrinfo(self.host,443,type=socket.SOCK_STREAM)
        if not addresses or any(not ipaddress.ip_address(a[4][0]).is_global for a in addresses):fail(403,'عنوان الخادم غير عام؛ الاتصال الداخلي غير مسموح.')
        last=None
        for family,kind,proto,_,sockaddr in addresses:
            sock=socket.socket(family,kind,proto);sock.settimeout(self.timeout)
            try:
                sock.connect(sockaddr);self.sock=self._context.wrap_socket(sock,server_hostname=self.host);return
            except OSError as exc:last=exc;sock.close()
        raise last or OSError('No address')

class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,*args,**kwargs):return None

class ProxyResponse:
    def __init__(self,response):self.response=response;self.status=response.code
    def read(self,n):return self.response.read(n)
    def getheader(self,k):return self.response.headers.get(k)
    def getheaders(self):return list(self.response.headers.items())

class TrustedProxy:
    """Optional deployment-owned egress proxy; never configured from an API request.

    The proxy must enforce public destination resolution. The fixed ERP host
    allowlist is still checked before handing any credentials to this transport.
    """
    def __init__(self,host,proxy):self.host=host;self.proxy=proxy;self.response=None
    def request(self,method,path,body,headers):
        opener=urllib.request.build_opener(urllib.request.ProxyHandler({'https':self.proxy}),NoRedirect(),urllib.request.HTTPSHandler(context=ssl.create_default_context()))
        try:self.response=opener.open(urllib.request.Request('https://'+self.host+path,data=body,headers=headers,method=method),timeout=25)
        except urllib.error.HTTPError as exc:self.response=exc
    def getresponse(self):return ProxyResponse(self.response)
    def close(self):
        if self.response:self.response.close()

class ERP:
    def __init__(self,base,auth=None,allowed=()):
        self.base=origin(base,allowed);self.host=urlsplit(self.base).hostname;self.auth=auth or {}

    def raw(self,method,path,args=None,limit=12_000_000,body_override=None,content_type=None):
        headers={'Accept':'application/json','User-Agent':'HEC-Standalone/2.2'}
        if self.auth.get('token'):headers['Authorization']='token '+self.auth['token']
        if self.auth.get('sid'):headers['Cookie']='sid='+self.auth['sid']
        if self.auth.get('csrf'):headers['X-Frappe-CSRF-Token']=self.auth['csrf']
        body=None
        if method=='GET' and args:
            path+='?'+urlencode({k:encode(v) if isinstance(v,(dict,list,bool)) else v for k,v in args.items() if v is not None})
        elif method!='GET':body=body_override if body_override is not None else encode(args or {}).encode();headers['Content-Type']=content_type or 'application/json'
        proxy=os.environ.get('HEC_EGRESS_PROXY')
        connection=TrustedProxy(self.host,proxy) if proxy else PinnedHTTPS(self.host,timeout=25,context=ssl.create_default_context())
        try:
            connection.request(method,path,body=body,headers=headers);response=connection.getresponse()
            raw=response.read(limit+1)
            if len(raw)>limit:fail(413,'النتيجة كبيرة. ضيّق فترة التقرير أو الفلاتر.')
            if response.status>=300:
                message='رفض ERPNext العملية أو إعداداتها.'
                if response.status in (401,403):message='رفض ERPNext صلاحيات حسابك لهذه البيانات أو انتهت جلسته.'
                elif response.status==429:message='الخادم مشغول بطلبات كثيرة؛ حاول لاحقاً.'
                elif response.status>=500:message='تعذر إكمال العملية في ERPNext الآن.'
                fail(response.status,message,'erp_'+str(response.status))
            if method!='GET':
                for name,value in response.getheaders():
                    if name.lower()=='set-cookie':
                        cookie=SimpleCookie();cookie.load(value)
                        if 'sid' in cookie:self.auth['sid']=cookie['sid'].value
            if 'json' not in (response.getheader('Content-Type') or ''):
                if path.startswith('/files/'):return raw,response.getheader('Content-Type')
                fail(502,'رد غير متوقع من ERPNext؛ لم تُعتمد العملية.')
            try:return json.loads(raw)
            except ValueError:fail(502,'تعذر قراءة رد ERPNext.')
        except (OSError,http.client.HTTPException) as exc:
            raise Error(503,'تعذر الوصول إلى ERPNext. احتفظ بالطلب وأعد التحقق لاحقاً.','erp_unreachable') from exc
        finally:connection.close()

    def upload_file(self,raw,filename,mime,doctype,docname):
        import secrets
        boundary='HEC'+secrets.token_hex(20);parts=[]
        for key,value in [('doctype',doctype),('docname',docname),('is_private','0')]:
            parts.append(('--'+boundary+'\r\nContent-Disposition: form-data; name="'+key+'"\r\n\r\n'+str(value)+'\r\n').encode())
        if any(x in filename for x in ('"','\r','\n','\\')):fail(422,'اسم ملف غير صالح.')
        parts.extend([('--'+boundary+'\r\nContent-Disposition: form-data; name="file"; filename="'+filename+'"\r\nContent-Type: '+mime+'\r\n\r\n').encode(),raw,('\r\n--'+boundary+'--\r\n').encode()])
        return self.raw('POST','/api/method/upload_file',limit=1000000,body_override=b''.join(parts),content_type='multipart/form-data; boundary='+boundary).get('message')
    def method(self,name,args=None,post=False):
        return self.raw('POST' if post else 'GET','/api/method/'+name,args).get('message')
    def list(self,doctype,fields=None,filters=None,limit=50,start=0,order='modified desc',or_filters=None):
        return self.raw('GET','/api/resource/'+quote(doctype,safe=''),dict(fields=fields or ['name'],filters=filters or {},limit_page_length=limit,limit_start=start,order_by=order,or_filters=or_filters)).get('data',[])
    def get(self,doctype,name):
        return self.raw('GET','/api/resource/'+quote(doctype,safe='')+'/'+quote(name,safe='')).get('data',{})
    def create(self,doctype,document):
        return self.raw('POST','/api/resource/'+quote(doctype,safe=''),document).get('data',{})
    def identity(self):
        user=self.method('frappe.auth.get_logged_user')
        if not user or user=='Guest':fail(401,'لم يعتمد ERPNext تسجيل الدخول.')
        roles=self.method('frappe.core.doctype.user.user.get_roles',{'uid':user})
        if not isinstance(roles,list):fail(403,'لم يتأكد دور الحساب من النظام.')
        return dict(user=user,name=user,roles=[str(r) for r in roles if isinstance(r,str)])
    def login(self,args):
        if args.get('kind')=='token':
            key=args.get('key','');secret=args.get('secret','')
            import re
            if not re.fullmatch(r'[A-Za-z0-9]{8,128}',key) or not re.fullmatch(r'[A-Za-z0-9]{8,128}',secret):fail(422,'أدخل مفتاح الحساب والسر بصورة صحيحة.')
            self.auth={'token':key+':'+secret}
        else:
            value=self.raw('POST','/api/method/login',dict(usr=args.get('user',''),pwd=args.get('password','')))
            if value.get('verification'):fail(428,'الحساب يتطلب التحقق الإضافي. استخدم مفتاحاً شخصياً مخولاً؛ لم يُعطّل التحقق الثنائي.')
            if not self.auth.get('sid'):fail(401,'لم تُنشأ جلسة في ERPNext.')
        return self.identity()
