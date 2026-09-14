import copy, hashlib, json, re, time
from datetime import datetime,timezone
from .core import Error,fail,encode,digest,utc,text
from .rules import app_id,image_id,image_path,flag,PUBLIC

class Catalog:
    @staticmethod
    def _search_text(value):
        return re.sub(r'\s+', ' ', str(value or '').strip().lower())

    @classmethod
    def _contains_all(cls, row, query):
        terms=list(dict.fromkeys(cls._search_text(query).split()))[:8]
        if not terms:return True
        hay=cls._search_text(' '.join(str(row.get(k,'')) for k in ('name','item_name','item_group','brand')))
        return all(t in hay for t in terms)

    def reference(self,code):
        ident=app_id(code)
        with self.store.tx() as db:db.execute('INSERT OR REPLACE INTO item_refs VALUES(?,?,?)',(ident,code,self.store.get('channel',db=db)['epoch']))
        return ident

    def resolve_code(self,ident):
        if not isinstance(ident,str) or not re.fullmatch(r'ERP_[a-f0-9]{24}',ident):fail(422,'كود صنف غير صالح.')
        rows=self.store.rows('SELECT code FROM item_refs WHERE id=? AND epoch=?',(ident,self.store.get('channel')['epoch']))
        if not rows:fail(409,'حدّث الصنف من الكتالوج قبل الطلب.')
        return rows[0]['code']

    def catalog(self,a,erp=None,allow_stale=True):
        shared=erp is None
        settings=self.store.get('settings')['values'];features=settings['features'];epoch=self.store.get('channel')['epoch']
        if not features.get('catalog'):fail(403,'قراءة الكتالوج غير مفعلة بعد.')
        q=text(a.get('q'),100);start=max(0,min(int(a.get('cursor') or 0),100000));parent=flag(a.get('parent_only',False))
        key='catalog:'+digest([q,start,parent]);cached=self.store.rows('SELECT * FROM cache WHERE key=? AND epoch=?',(key,epoch))
        if shared and cached and time.time()-cached[0]['created_at']<60 and allow_stale:
            value=self.store.open(cached[0]['data']);value.update(stale=False,cached=True);return value
        try:
            erp=erp or self.integration_client()
            erp.get('Company',settings['company']);erp.get('Price List',settings['price_list'])
            filters={'disabled':0,'is_sales_item':1}
            if parent:filters['is_stock_item']=0
            terms=list(dict.fromkeys(self._search_text(q).split()))[:8]
            matches=[['Item','name','like','%'+q+'%'],['Item','item_name','like','%'+q+'%'],['Item Barcode','barcode','=',q]] if q else None
            fields=['name','item_name','stock_uom','item_group','brand','image','is_stock_item','creation','modified']
            if len(terms)>1:
                # Frappe's OR filters do not express multi-word AND search. Fetch each token
                # and intersect locally, preserving exact barcode lookup for single tokens.
                pools=[]
                for term in terms:
                    pool=erp.list('Item',fields,filters,201,0,'modified desc, name asc', [['Item','name','like','%'+term+'%'],['Item','item_name','like','%'+term+'%']])
                    pools.append({r.get('name'):r for r in pool if r.get('name')})
                keys=set(pools[0]) if pools else set()
                for pool in pools[1:]: keys &= set(pool)
                rows=[pools[0][k] for k in keys if self._contains_all(pools[0][k],q)]
                rows.sort(key=lambda r:(str(r.get('modified','')),str(r.get('name',''))),reverse=True)
                rows=rows[start:start+51]
            else:
                rows=erp.list('Item',fields,filters,51,start,'modified desc, name asc',matches)
            unique=list({r['name']:r for r in rows}.values());selected=unique[:50];names=[r['name'] for r in selected]
            prices=erp.list('Item Price',['item_code','price_list_rate','uom','valid_from','valid_upto','customer','supplier','batch_no'],{'item_code':['in',names],'price_list':settings['price_list'],'currency':settings['currency'],'selling':1},1000,order='valid_from desc, modified desc') if names else []
            bins=erp.list('Bin',['item_code','actual_qty','reserved_qty'],{'item_code':['in',names],'warehouse':settings['warehouse']},1000) if names and features.get('stock') else []
            barcodes=erp.list('Item Barcode',['parent','barcode','uom'],{'parent':['in',names]},1000) if names else []
            barcode_map={code:[] for code in names}
            for b in barcodes:
                if b.get('parent') in barcode_map and b.get('barcode'):
                    barcode_map[b['parent']].append({'barcode':str(b['barcode'])[:200],'uom':str(b.get('uom') or '')[:40]})
            by_bin={r['item_code']:r for r in bins};images={};items=[]
            for row in selected:
                dto=self.item_dto(row,settings,erp,images,prices,by_bin,barcode_map.get(row.get('name'),[]))
                if dto:items.append(dto)
            result=dict(items=items,next_cursor=start+50 if len(unique)>50 else None,_images=images,as_of=utc(),stale=False,cached=False)
            if shared:
                with self.store.tx() as db:db.execute('INSERT OR REPLACE INTO cache VALUES(?,?,?,?)',(key,self.store.seal(result),time.time(),epoch))
            return result
        except Error as exc:
            # No stale fallback on permission/credential/configuration failures.
            if shared and allow_stale and cached and exc.status in (502,503,504) and time.time()-cached[0]['created_at']<86400:
                value=self.store.open(cached[0]['data']);value.update(stale=True,cached=True);return value
            raise

    def item_dto(self,row,settings,erp,images,prices=None,bins=None,barcode_rows=None):
        code=row['name'];today=datetime.now(timezone.utc).date().isoformat()
        if prices is None:prices=erp.list('Item Price',['item_code','price_list_rate','uom','valid_from','valid_upto','customer','supplier','batch_no'],{'item_code':code,'price_list':settings['price_list'],'currency':settings['currency'],'selling':1},100,order='valid_from desc, modified desc')
        valid=[p for p in prices if p.get('item_code')==code and not any(p.get(k) for k in ('customer','supplier','batch_no')) and (not p.get('valid_from') or p['valid_from']<=today) and (not p.get('valid_upto') or p['valid_upto']>=today)]
        if not valid:return None
        base=next((p for p in valid if not p.get('uom') or p.get('uom')==row['stock_uom']),valid[0])
        history=[dict(uom=text(p.get('uom'),40) or text(row.get('stock_uom'),40),price=float(p['price_list_rate']),valid_from=p.get('valid_from'),valid_upto=p.get('valid_upto')) for p in prices if p.get('item_code')==code and not any(p.get(k) for k in ('customer','supplier','batch_no'))][:100]
        variants=[];seen=set()
        for p in valid:
            uom=text(p.get('uom'),40) or text(row.get('stock_uom'),40)
            key=uom+'|'+str(float(p['price_list_rate']))
            if key in seen:continue
            seen.add(key);variants.append({'id':uom.replace(' ','_')[:30], 'label':uom, 'price':float(p['price_list_rate'])})
        photo='logo.jpg'
        if settings['features'].get('images') and image_path(row.get('image')):
            photo=image_id(row['image']);images[photo]='/v1/images/'+photo
            with self.store.tx() as db:db.execute('INSERT OR REPLACE INTO images VALUES(?,?,?)',(photo,row['image'],self.store.get('channel',db=db)['epoch']))
        barcode_rows=barcode_rows if barcode_rows is not None else [{'barcode':x.get('barcode'),'uom':x.get('uom','')} for x in row.get('barcodes',[]) if isinstance(x,dict)]
        item=dict(app_id=self.reference(code),item_code=code,item_name=text(row.get('item_name')),rate=float(base['price_list_rate']),stock_uom=text(row.get('stock_uom'),40),item_group=text(row.get('item_group'),100),brand=text(row.get('brand'),80),is_stock_item=row.get('is_stock_item',1),image=photo,barcodes=barcode_rows[:50],variants=variants,priceHistory=history,components=[],marketingMetrics=dict(createdAt=row.get('creation'),modifiedAt=row.get('modified')))
        if settings['features'].get('stock'):
            if bins is None:bins={r['item_code']:r for r in erp.list('Bin',['item_code','actual_qty','reserved_qty'],{'item_code':code,'warehouse':settings['warehouse']},1)}
            entry=bins.get(code,{})
            item['marketingMetrics'].update(stockQty=max(0,float(entry.get('actual_qty',0))-float(entry.get('reserved_qty',0))),stockAsOf=utc())
        if settings['features'].get('bundles') and not row.get('is_stock_item'):
            bundles=erp.list('Product Bundle',['name'],{'new_item_code':code,'disabled':0},1)
            if bundles:
                bundle=erp.get('Product Bundle',bundles[0]['name']);item['bundle_source']=bundle['name']
                item['components']=[dict(item_code=self.reference(r['item_code']),erp_item_code=r['item_code'],qty=float(r['qty'])) for r in bundle.get('items',[])]
        return item

    def validate_bundle(self,row):
        settings=self.store.get('settings')['values']
        if not settings['features'].get('bundles'):fail(422,'فعّل قراءة الحزم بعد إعداد التكامل.')
        erp=self.integration_client();code=self.resolve_code(row.get('parentItem'));item=erp.get('Item',code)
        if item.get('disabled') or item.get('is_stock_item'):fail(422,'الصنف الرئيسي يجب أن يكون غير مخزني ومفعلاً.')
        dto=self.item_dto(item,settings,erp,{})
        if not dto or not dto['components']:fail(422,'لم توجد حزمة Product Bundle صالحة للصنف.')
        expected={r['item_code']:r['qty'] for r in dto['components']};actual={r.get('id'):float(r.get('qty',0)) for r in row.get('allocation',[])}
        if expected!=actual or len(actual)!=len(row.get('allocation',[])):fail(422,'مكونات العرض وكمياته يجب أن تطابق ERPNext.')
        if not row.get('useParentValues') or float(row.get('parentRate',-1))!=dto['rate']:fail(422,'حدّث سعر الصنف الرئيسي واستخدم قيمه المعتمدة.')

    def storefront(self,preview=False,user=None):
        channel=self.bootstrap();snapshot=json.loads((__import__('pathlib').Path(__file__).parent/'seed.json').read_text())
        if preview:snapshot=self.draft()
        elif channel.get('publication'):
            rows=self.store.rows('SELECT snapshot FROM publications WHERE id=?',(channel['publication'],))
            if rows:snapshot=json.loads(rows[0]['snapshot'])
        modules={k:copy.deepcopy(snapshot.get(k,[])) for k in PUBLIC};settings=self.store.get('settings')['values'];catalog=[];images={};stale=False;as_of=utc();next_cursor=None
        modules['products']=[]
        modules['feature-policies']=[dict(id='resolved-'+f,title=f,feature=f,scope='الجميع',customerIds=[],visible=False,enabled=False,active=True,priority=100) for f in ('loyalty','affiliate')]
        # Preserve visibility policies without pretending financial workflows are implemented.
        for resolved in modules['feature-policies']:
            policies=[r for r in snapshot.get('feature-policies',[]) if r.get('feature')==resolved['feature'] and r.get('active') is not False and self.in_window(r)]
            eligible=[]
            customer=(user or {}).get('customer')
            if (user or {}).get('kind')=='customer':customer=self.customer_account(user,False)['customer']
            for p in policies:
                selected=customer in p.get('customerIds',[]);scope=p.get('scope','الجميع')
                if scope=='عملاء محددون' and not selected or scope=='الجميع عدا المحددين' and selected:continue
                eligible.append(p)
            eligible.sort(key=lambda r:(float(r.get('priority') or 0),r.get('scope')!='الجميع'),reverse=True)
            if eligible:resolved['visible']=bool(eligible[0].get('visible'))
        modules['notifications']=[r for r in snapshot.get('notifications',[]) if settings['features'].get('notifications') and r.get('active') is not False and r.get('recipient')!='الموصل' and r.get('type') in ('تسويق',None) and self.in_window(r,'publishAt')][:100]
        if settings['features'].get('catalog'):
            data=self.catalog({});catalog=data['items'];images=data['_images'];stale=data['stale'];as_of=data['as_of'];next_cursor=data['next_cursor']
        modules['offer-bundles']=[r for r in modules.get('offer-bundles',[]) if settings['features'].get('bundles') and str(r.get('parentItem','')).startswith('ERP_')]
        for bundle in modules['offer-bundles']:
            dto=next((p for p in catalog if p['app_id']==bundle['parentItem']),None)
            if dto:
                if float(bundle.get('parentRate',0))!=dto['rate']:
                    for line in bundle.get('allocation',[]):line.update(kind='auto',value=0)
                bundle.update(parentRate=dto['rate'],total=dto['rate'],parentName=dto['item_name'])
            else:bundle['active']=False
        valid={b['id'] for b in modules['offer-bundles']}
        for mod in ('campaigns','golden'):modules[mod]=[r for r in modules.get(mod,[]) if r.get('id') in valid]
        images.update(self.image_map(modules))
        return dict(modules=modules,catalog=catalog,next_cursor=next_cursor,liveCatalog=settings['features'].get('catalog',False),_images=images,channel=channel,version='2.2.0',server_time=utc(),as_of=as_of,stale=stale)

    def in_window(self,row,start='startsAt'):
        from zoneinfo import ZoneInfo
        now=datetime.now(timezone.utc)
        for key,is_start in ((start,True),('endsAt',False)):
            if row.get(key):
                try:
                    value=datetime.fromisoformat(row[key])
                    if value.tzinfo is None:value=value.replace(tzinfo=ZoneInfo(self.timezone))
                    if (is_start and now<value) or (not is_start and now>=value):return False
                except (TypeError,ValueError):return False
        return True
