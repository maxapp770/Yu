"""Small standalone store service. No Frappe imports or ERP schema installation."""
from contextlib import contextmanager
from pathlib import Path
from datetime import datetime, timezone
import hashlib, json, os, re, secrets, sqlite3, time
from cryptography.fernet import Fernet, InvalidToken

class Error(Exception):
    def __init__(self, status, message, code=''):
        super().__init__(message);self.status=status;self.code=code

def fail(status, message, code=''):
    raise Error(status,message,code)

def encode(value):
    return json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False)

def utc():
    return datetime.now(timezone.utc).isoformat()

def digest(value):
    return hashlib.sha256(encode(value).encode()).hexdigest()

def text(value, limit=500):
    return re.sub(r'[<>\x00-\x1f]','',str(value or ''))[:limit]

class Store:
    def __init__(self,path,key):
        self.path=Path(path);self.path.parent.mkdir(parents=True,exist_ok=True)
        self.cipher=Fernet(key.encode() if isinstance(key,str) else key)
        with self.tx() as db:
            db.executescript('''
            CREATE TABLE IF NOT EXISTS kv(key TEXT PRIMARY KEY,value TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS content(module TEXT PRIMARY KEY,data TEXT NOT NULL,revision INTEGER NOT NULL);
            CREATE TABLE IF NOT EXISTS publications(id TEXT PRIMARY KEY,title TEXT,snapshot TEXT NOT NULL,checksum TEXT,state TEXT,scheduled_at TEXT,published_at TEXT,created_by TEXT);
            CREATE TABLE IF NOT EXISTS sessions(id TEXT PRIMARY KEY,data TEXT NOT NULL,expires REAL NOT NULL,epoch INTEGER NOT NULL);
            CREATE TABLE IF NOT EXISTS candidates(id TEXT PRIMARY KEY,actor TEXT,data TEXT NOT NULL,expires REAL NOT NULL);
            CREATE TABLE IF NOT EXISTS customers(user TEXT PRIMARY KEY,password TEXT,name TEXT,customer TEXT,company TEXT,enabled INTEGER,epoch INTEGER NOT NULL);
            CREATE TABLE IF NOT EXISTS requests(id TEXT PRIMARY KEY,user TEXT NOT NULL,fingerprint TEXT NOT NULL,payload TEXT NOT NULL,state TEXT NOT NULL,erp_name TEXT,created_at TEXT,updated_at TEXT,epoch INTEGER NOT NULL,error TEXT);
            CREATE TABLE IF NOT EXISTS inbox(id TEXT PRIMARY KEY,user TEXT NOT NULL,title TEXT,message TEXT,erp_name TEXT,created_at TEXT,read_at TEXT,epoch INTEGER NOT NULL);
            CREATE TABLE IF NOT EXISTS cache(key TEXT PRIMARY KEY,data TEXT NOT NULL,created_at REAL NOT NULL,epoch INTEGER NOT NULL);
            CREATE TABLE IF NOT EXISTS item_refs(id TEXT PRIMARY KEY,code TEXT NOT NULL,epoch INTEGER NOT NULL);
            CREATE TABLE IF NOT EXISTS images(id TEXT PRIMARY KEY,path TEXT NOT NULL,epoch INTEGER NOT NULL);
            CREATE TABLE IF NOT EXISTS audit(id INTEGER PRIMARY KEY,actor TEXT,action TEXT,target TEXT,created_at TEXT);
            CREATE TABLE IF NOT EXISTS presets(id TEXT PRIMARY KEY,user TEXT,title TEXT,data TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS delivery_records(id TEXT PRIMARY KEY,kind TEXT NOT NULL,epoch INTEGER NOT NULL,owner TEXT NOT NULL,parent TEXT NOT NULL,value TEXT NOT NULL,revision INTEGER NOT NULL DEFAULT 1,updated TEXT NOT NULL);
            CREATE INDEX IF NOT EXISTS delivery_owner ON delivery_records(epoch,kind,owner);
            CREATE INDEX IF NOT EXISTS delivery_parent ON delivery_records(epoch,kind,parent);
            CREATE TABLE IF NOT EXISTS limits(key TEXT PRIMARY KEY,count INTEGER,until REAL);
            ''')
            from .rules import default_settings
            for key,value in {'channel':dict(store_id=secrets.token_hex(16),revision=1,publication=None,maintenance=True,epoch=1),
                              'settings':dict(values=default_settings(),version='1'),
                              'access':{'report_roles':['Accounts Manager','Stock Manager','Sales Manager','Purchase Manager']}}.items():
                if not self.get(key,db=db):self.put(key,value,db=db)
            seed=json.loads((Path(__file__).parent/'seed.json').read_text())
            for module,rows in seed.items():db.execute('INSERT OR IGNORE INTO content VALUES(?,?,1)',(module,encode(rows)))
            sentinel=self.get('key-check',db=db)
            if sentinel:
                self.open(sentinel)
            else:self.put('key-check',self.seal({'ok':True}),db=db)
        os.chmod(self.path,0o600)

    @contextmanager
    def tx(self):
        db=sqlite3.connect(self.path,timeout=15,isolation_level=None);db.row_factory=sqlite3.Row
        db.execute('PRAGMA journal_mode=WAL');db.execute('PRAGMA foreign_keys=ON');db.execute('PRAGMA busy_timeout=15000')
        db.execute('BEGIN IMMEDIATE')
        try:yield db;db.commit()
        except BaseException:db.rollback();raise
        finally:db.close()

    def rows(self,sql,args=()):
        with sqlite3.connect(self.path,timeout=15) as db:
            db.row_factory=sqlite3.Row
            return [dict(r) for r in db.execute(sql,args)]

    def get(self,key,default=None,db=None):
        rows=db.execute('SELECT value FROM kv WHERE key=?',(key,)).fetchall() if db else self.rows('SELECT value FROM kv WHERE key=?',(key,))
        return json.loads(rows[0]['value']) if rows else default

    def put(self,key,value,db=None):
        if db is None:
            with self.tx() as conn:self.put(key,value,conn)
        else:db.execute('INSERT INTO kv VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value',(key,encode(value)))

    def seal(self,value):return self.cipher.encrypt(encode(value).encode()).decode()
    def open(self,value):
        try:return json.loads(self.cipher.decrypt(value.encode()))
        except (InvalidToken,ValueError):fail(503,'تعذر فتح البيانات المحمية. تحقق من مفتاح الخدمة والنسخة الاحتياطية.','key_unavailable')

    def audit(self,actor,action,target,db=None):
        if db is None:
            with self.tx() as conn:self.audit(actor,action,target,conn)
        else:db.execute('INSERT INTO audit(actor,action,target,created_at) VALUES(?,?,?,?)',(actor,action,text(target,200),utc()))

    def throttle(self,key,limit=30,seconds=60):
        now=time.time()
        with self.tx() as db:
            row=db.execute('SELECT * FROM limits WHERE key=?',(key,)).fetchone()
            count=1 if not row or row['until']<=now else row['count']+1
            until=now+seconds if not row or row['until']<=now else row['until']
            if count>limit:fail(429,'طلبات كثيرة. انتظر قليلاً ثم أعد المحاولة.')
            db.execute('INSERT OR REPLACE INTO limits VALUES(?,?,?)',(key,count,until))
            db.execute('DELETE FROM limits WHERE until<?',(now-3600,))

    def session(self,data):
        token=secrets.token_urlsafe(40);ident=hashlib.sha256(token.encode()).hexdigest();epoch=self.get('channel')['epoch']
        with self.tx() as db:
            db.execute('DELETE FROM sessions WHERE expires<?',(time.time(),))
            db.execute('INSERT INTO sessions VALUES(?,?,?,?)',(ident,self.seal(data),time.time()+3600,epoch))
        return token

    def resolve(self,token):
        if not token:return None
        ident=hashlib.sha256(token.encode()).hexdigest()
        rows=self.rows('SELECT * FROM sessions WHERE id=?',(ident,))
        if not rows or rows[0]['expires']<time.time() or rows[0]['epoch']!=self.get('channel')['epoch']:fail(401,'انتهت الجلسة؛ سجّل الدخول مجدداً.')
        return {**self.open(rows[0]['data']),'session_id':ident}

    def revoke(self,token):
        with self.tx() as db:db.execute('DELETE FROM sessions WHERE id=?',(hashlib.sha256(token.encode()).hexdigest(),))

def password_hash(password):
    if not isinstance(password,str) or not 12<=len(password)<=128 or len(set(password))<6:fail(422,'استخدم كلمة مرور شخصية من 12 محرفاً على الأقل.')
    salt=secrets.token_bytes(16)
    value=hashlib.scrypt(password.encode(),salt=salt,n=16384,r=8,p=1).hex()
    return salt.hex()+':'+value

def password_matches(password,saved):
    try:
        salt,value=saved.split(':')
        actual=hashlib.scrypt(str(password).encode(),salt=bytes.fromhex(salt),n=16384,r=8,p=1).hex()
        return secrets.compare_digest(value,actual)
    except (ValueError,TypeError):return False
