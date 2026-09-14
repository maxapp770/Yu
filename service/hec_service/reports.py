"""Report access always uses the requesting ERP user's own credentials."""
import base64,csv,io,json,re,secrets,time
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from .core import Error,fail,text,encode,digest,utc

TEMPLATES={
 'Stock Balance':('المخزون',[('company','الشركة','Link','Company'),('from_date','من تاريخ','Date',''),('to_date','إلى تاريخ','Date',''),('warehouse','المخزن','Link','Warehouse'),('item_code','الصنف','Link','Item')]),
 'Stock Ledger':('المخزون',[('company','الشركة','Link','Company'),('from_date','من تاريخ','Date',''),('to_date','إلى تاريخ','Date',''),('warehouse','المخزن','Link','Warehouse'),('item_code','الصنف','Link','Item')]),
 'General Ledger':('الحسابات',[('company','الشركة','Link','Company'),('from_date','من تاريخ','Date',''),('to_date','إلى تاريخ','Date',''),('account','الحساب','Link','Account')]),
 'Accounts Receivable':('الحسابات',[('company','الشركة','Link','Company'),('report_date','حتى تاريخ','Date',''),('customer','العميل','Link','Customer')]),
 'Accounts Payable':('الحسابات',[('company','الشركة','Link','Company'),('report_date','حتى تاريخ','Date',''),('supplier','المورد','Link','Supplier')]),
 'Sales Register':('المبيعات',[('company','الشركة','Link','Company'),('from_date','من تاريخ','Date',''),('to_date','إلى تاريخ','Date',''),('customer','العميل','Link','Customer')]),
 'Purchase Register':('المشتريات',[('company','الشركة','Link','Company'),('from_date','من تاريخ','Date',''),('to_date','إلى تاريخ','Date',''),('supplier','المورد','Link','Supplier')]),
 'Item-wise Sales Register':('المبيعات',[('company','الشركة','Link','Company'),('from_date','من تاريخ','Date',''),('to_date','إلى تاريخ','Date',''),('item_code','الصنف','Link','Item')]),
}
LINKS={'Company','Warehouse','Customer','Supplier','Item','Item Group','Account','Cost Center','Currency','Brand','Sales Person','Territory','Project','Fiscal Year','Mode of Payment'}

class Reports:
    def report_metadata(self,name,erp):
        if not isinstance(name,str) or not 1<=len(name)<=140:fail(422,'اسم تقرير غير صالح.')
        doc=erp.get('Report',name)
        if doc.get('disabled'):fail(403,'التقرير متوقف في النظام.')
        # This standard method checks report roles, custom role overrides and ref DocType report permission.
        descriptor=erp.method('frappe.desk.query_report.get_script',{'report_name':name})
        if not isinstance(descriptor,dict):fail(403,'لم يتأكد إذن قراءة التقرير.')
        fields=[]
        for f in descriptor.get('filters') or []:
            if not re.fullmatch(r'[a-zA-Z_][a-zA-Z0-9_]{0,79}',str(f.get('fieldname',''))):continue
            kind=f.get('fieldtype','Data');options=f.get('options','')
            if kind=='Link' and options not in LINKS:kind='Data';options=''
            if kind not in ('Data','Date','Int','Float','Currency','Check','Select','Link'):kind='Data'
            default=f.get('default')
            if not isinstance(default,(str,int,float,bool,type(None))) or isinstance(default,str) and any(x in default for x in ('frappe.','__','eval:',':')):default=None
            fields.append(dict(fieldname=f['fieldname'],label=text(f.get('label') or f['fieldname'],100),fieldtype=kind,options=options if kind in ('Select','Link') else '',reqd=bool(f.get('reqd')),default=default))
        category=TEMPLATES.get(name,('أخرى',[]))[0]
        if not fields and name in TEMPLATES:
            fields=[dict(fieldname=k,label=l,fieldtype=t,options=o,reqd=k in ('company','from_date','to_date','report_date'),default=None) for k,l,t,o in TEMPLATES[name][1]]
        if category=='أخرى':category={'Accounts':'الحسابات','Stock':'المخزون','Buying':'المشتريات','Selling':'المبيعات','HR':'الموظفون','Payroll':'الموظفون','Manufacturing':'التصنيع'}.get(doc.get('module'),'أخرى')
        return dict(name=name,title=text(name,140),category=category,report_type=doc.get('report_type'),ref_doctype=doc.get('ref_doctype'),filters=fields,prepared=bool(doc.get('prepared_report')),supported=doc.get('report_type') in ('Query Report','Script Report','Custom Report'),filter_source='server' if descriptor.get('filters') else 'template' if name in TEMPLATES else 'manual',module=doc.get('module'))

    def report_catalog(self,a,erp,actor):
        q=text(a.get('q'),100);start=max(0,min(int(a.get('cursor') or 0),10000));filters={'disabled':0}
        if q:filters['name']=['like','%'+q+'%']
        rows=erp.list('Report',['name'],filters,16,start,'name asc')
        def check(r):
            try:return self.report_metadata(r['name'],erp)
            except Error as exc:
                if exc.status in (401,502,503,504):raise
                return None
        with ThreadPoolExecutor(max_workers=4) as pool:items=[r for r in pool.map(check,rows[:15]) if r]
        self.store.audit(actor,'reports.list',q or 'page '+str(start))
        return dict(items=items,next_cursor=start+15 if len(rows)>15 else None,as_of=utc(),permission_source='requesting-user')

    def report_options(self,a,erp):
        doctype=a.get('doctype');q=text(a.get('q'),100);filters={}
        if doctype not in LINKS:fail(403,'نوع اختيار غير مسموح.')
        if q:filters['name']=['like','%'+q+'%']
        if doctype in ('Warehouse','Account','Cost Center') and a.get('company'):filters['company']=a['company']
        if doctype in ('Warehouse','Account','Cost Center'):filters['is_group']=0
        return {'items':erp.list(doctype,['name'],filters,50,order='name asc')}

    def clean_filters(self,filters):
        if not isinstance(filters,dict) or len(filters)>35:fail(422,'فلاتر التقرير غير صالحة.')
        forbidden={'user','ignore_permissions','ignore_prepared_report','prepared_report_name','custom_columns','cmd','doctype','report_name','are_default_filters'}
        for k,v in filters.items():
            if k in forbidden or not re.fullmatch(r'[a-zA-Z_][a-zA-Z0-9_]{0,79}',k):fail(422,'اسم فلتر غير مسموح.')
            if isinstance(v,list):
                if len(v)>100 or any(not isinstance(x,(str,int,float)) or len(str(x))>140 for x in v):fail(422,'قائمة فلتر كبيرة أو غير صالحة.')
            elif v is not None and not isinstance(v,(str,int,float,bool)):fail(422,'قيمة فلتر غير صالحة.')
            if isinstance(v,str) and len(v)>1000:fail(422,'قيمة فلتر طويلة.')
        if filters.get('from_date') and filters.get('to_date'):
            try:
                start=date.fromisoformat(filters['from_date']);end=date.fromisoformat(filters['to_date'])
                if start>end or (end-start).days>366:fail(422,'اختر فترة صحيحة لا تتجاوز سنة لكل تشغيل.')
            except (TypeError,ValueError):fail(422,'تحقق من تاريخ بداية التقرير ونهايته.')
        return filters

    def report_run(self,a,erp,actor):
        meta=self.report_metadata(a.get('report_name'),erp)
        if not meta['supported']:fail(422,'هذا التقرير من نوع Report Builder ويحتاج محول عرض خاص. لم يُنفذ كتقرير Query.')
        filters=self.clean_filters(a.get('filters') or {})
        for f in meta['filters']:
            if f['reqd'] and filters.get(f['fieldname']) in (None,'',[]):fail(422,'الحقل مطلوب: '+f['label'])
            if f['fieldtype']=='Link' and filters.get(f['fieldname']):
                val=filters[f['fieldname']]
                for name in val if isinstance(val,list) else [val]:erp.get(f['options'],name)
        if meta['name'] in ('Accounts Receivable','Accounts Payable'):
            filters.setdefault('ageing_based_on','Due Date');filters.setdefault('range1',30);filters.setdefault('range2',60);filters.setdefault('range3',90);filters.setdefault('range4',120)
        key='report:'+digest([actor,meta['name'],filters]);epoch=self.store.get('channel')['epoch']
        if a.get('cached'):
            rows=self.store.rows('SELECT * FROM cache WHERE key=? AND epoch=?',(key,epoch))
            if not rows or time.time()-rows[0]['created_at']>86400:fail(404,'لا توجد نسخة محفوظة حديثة لهذا التقرير وهذه الفلاتر.')
            result=self.store.open(rows[0]['data']);result.update(cached=True,stale=True)
            return result
        data=erp.method('frappe.desk.query_report.run',{'report_name':meta['name'],'filters':filters,'ignore_prepared_report':0,'are_default_filters':0})
        if not isinstance(data,dict):fail(502,'رد التقرير غير صالح.')
        if data.get('prepared_report') or data.get('doc'):
            return dict(prepared=True,message='هذا التقرير يُحضّر على ERPNext. جهّزه هناك ثم أعد التحميل.',columns=[],rows=[],as_of=utc(),cached=False,stale=False)
        columns=[]
        for i,c in enumerate(data.get('columns') or []):
            if isinstance(c,str):
                label=c.split(':')[0];fieldtype=c.split(':')[1].split('/')[0] if ':' in c else 'Data';fieldname=str(i)
            else:label=c.get('label') or c.get('fieldname') or str(i);fieldtype=c.get('fieldtype','Data');fieldname=c.get('fieldname',str(i))
            columns.append(dict(label=text(label,120),fieldname=fieldname,fieldtype=fieldtype))
        if len(columns)>100:fail(413,'أعمدة كثيرة؛ استخدم تقريراً مختصراً.')
        result_rows=data.get('result') or [];limit=2000
        def cell(value):
            if isinstance(value,(int,float,bool)) or value is None:return value
            return text(value,4000)
        rows=[[cell(r.get(c['fieldname'])) if isinstance(r,dict) else cell(r[i]) if i<len(r) else None for i,c in enumerate(columns)] for r in result_rows[:limit]]
        can_export=bool((erp.method('frappe.client.has_permission',{'doctype':meta['ref_doctype'],'docname':'','perm_type':'export'}) or {}).get('has_permission'))
        result=dict(name=meta['name'],columns=columns,rows=rows,filters=filters,as_of=utc(),cached=False,stale=False,truncated=len(result_rows)>limit,row_limit=limit,loaded_rows=len(rows),can_export=can_export,summary=[dict(label=text(x.get('label'),100),value=cell(x.get('value')),datatype=x.get('datatype'),currency=text(x.get('currency'),20)) for x in (data.get('report_summary') or []) if isinstance(x,dict)][:12])
        with self.store.tx() as db:db.execute('INSERT OR REPLACE INTO cache VALUES(?,?,?,?)',(key,self.store.seal(result),time.time(),epoch))
        self.store.audit(actor,'report.run',meta['name']);return result

    def report_export(self,a,erp,actor):
        meta=self.report_metadata(a.get('report_name'),erp)
        allowed=erp.method('frappe.client.has_permission',{'doctype':meta['ref_doctype'],'docname':'','perm_type':'export'})
        if not allowed or not allowed.get('has_permission'):fail(403,'حسابك لا يملك إذن تصدير هذا التقرير.')
        result=self.report_run({**a,'cached':True},erp,actor)
        buffer=io.StringIO();writer=csv.writer(buffer)
        def safe(v):
            s='' if v is None else str(v)
            return "'"+s if isinstance(v,str) and s.lstrip().startswith(('=','+','-','@','\t','\r')) else s
        writer.writerow([safe(c['label']) for c in result['columns']]);writer.writerows([[safe(v) for v in row] for row in result['rows']])
        raw=('\ufeff'+buffer.getvalue()).encode()
        if len(raw)>2_000_000:fail(413,'التصدير كبير؛ ضيّق الفلاتر.')
        self.store.audit(actor,'report.export',meta['name'])
        return dict(filename='HEC-report-'+date.today().isoformat()+'.csv',content_base64=base64.b64encode(raw).decode(),mime='text/csv',rows=len(result['rows']),as_of=result['as_of'],truncated=result['truncated'])

    def report_presets(self,a,actor):
        if a.get('save'):
            filters=self.clean_filters(a.get('filters') or {});name=text(a.get('report_name'),140);title=text(a.get('title'),100)
            if not name or not title:fail(422,'اسم العرض والتقرير مطلوبان.')
            ident=secrets.token_hex(12)
            with self.store.tx() as db:
                if db.execute('SELECT count(*) FROM presets WHERE user=?',(actor,)).fetchone()[0]>=100:fail(422,'بلغت الحد الأقصى للعروض المحفوظة.')
                db.execute('INSERT INTO presets VALUES(?,?,?,?)',(ident,actor,title,self.store.seal({'report_name':name,'filters':filters})))
        if a.get('delete'):
            with self.store.tx() as db:db.execute('DELETE FROM presets WHERE id=? AND user=?',(a['delete'],actor))
        return {'items':[dict(id=r['id'],title=r['title'],**self.store.open(r['data'])) for r in self.store.rows('SELECT * FROM presets WHERE user=?',(actor,))]}
