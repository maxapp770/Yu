#!/usr/bin/env python3
"""Live HEC readiness / explicit test-order runner. Credentials come from environment.

Default is read-only. --place-order requires an authenticated test customer and
an explicit ERP item code; it creates ONE real Sales Order (and retries the same
idempotency key). Use a test company/customer. It never publishes or sends mail.
"""
import argparse
import http.cookiejar
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
import uuid
from datetime import datetime,timezone
from pathlib import Path

class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,*args,**kwargs): return None

class Client:
    def __init__(self,origin,key='',secret=''):
        u=urllib.parse.urlsplit(origin)
        if u.scheme!='https' or not u.hostname or u.username or u.password or u.query or u.fragment or u.path not in ('','/') or u.port not in (None,443): raise ValueError('HTTPS origin required')
        self.origin=origin.rstrip('/');self.token=('token '+key+':'+secret) if key and secret else '';self.csrf=''
        self.opener=urllib.request.build_opener(NoRedirect(),urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
    def call(self,method,endpoint,args=None):
        payload=args or {};url=self.origin+'/api/method/'+endpoint
        headers={'Accept':'application/json','User-Agent':'HEC-Live-Check/2.1'}
        if self.token:headers['Authorization']=self.token
        if self.csrf:headers['X-Frappe-CSRF-Token']=self.csrf
        body=None
        if method=='GET' and payload:url+='?'+urllib.parse.urlencode(payload)
        if method=='POST':body=json.dumps(payload).encode();headers['Content-Type']='application/json'
        try:
            with self.opener.open(urllib.request.Request(url,data=body,headers=headers,method=method),timeout=30) as response:
                data=response.read(2_000_001)
                if len(data)>2_000_000:raise ValueError('Response too large')
                result=json.loads(data).get('message')
                if isinstance(result,dict):self.csrf=result.pop('csrf_token',self.csrf)
                return result
        except urllib.error.HTTPError as error:
            sample=error.read(2000)
            raise RuntimeError('HTTP '+str(error.code)+(' / Cloudflare 1010' if b'1010' in sample else '')) from None

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--url',default=os.environ.get('HEC_SERVICE_ORIGIN','https://erptest.wahatalhaitham.com'))
    p.add_argument('--report',default='hec-live-report.json')
    p.add_argument('--place-order',action='store_true')
    p.add_argument('--item-code');p.add_argument('--expected-store-id')
    args=p.parse_args();steps=[];report={'timestamp':datetime.now(timezone.utc).isoformat(),'server':args.url,'mode':'live test order' if args.place_order else 'read-only','steps':steps}
    def check(name,fn):
        try:r=fn();steps.append({'step':name,'passed':True});return r
        except Exception as e:steps.append({'step':name,'passed':False,'reason':str(e) if isinstance(e,(RuntimeError,ValueError)) else type(e).__name__});raise
    try:
        visitor=Client(args.url);health=check('bootstrap',lambda:visitor.call('GET','hec_bridge.releases.bootstrap'))
        report['store_id']=health['store_id']
        if args.expected_store_id and health['store_id']!=args.expected_store_id:raise ValueError('Store identity mismatch; do not migrate or place orders')
        admin=Client(args.url,os.environ.get('HEC_ADMIN_API_KEY',''),os.environ.get('HEC_ADMIN_API_SECRET',''))
        if not admin.token:raise ValueError('Set HEC_ADMIN_API_KEY and HEC_ADMIN_API_SECRET privately')
        check('manager role',lambda:admin.call('GET','hec_bridge.api.context',{'admin':1}))
        report['doctor']=check('schema and capabilities',lambda:admin.call('GET','hec_bridge.onboarding.doctor'))
        report['publication']=check('publication status',lambda:admin.call('GET','hec_bridge.releases.status'))
        check('customer storefront',lambda:visitor.call('GET','hec_bridge.api.storefront'))
        try:visitor.call('GET','hec_bridge.api.settings')
        except RuntimeError as e:
            if '401' not in str(e) and '403' not in str(e):raise
            steps.append({'step':'guest denied administrative settings','passed':True})
        else:raise ValueError('Guest unexpectedly read administrative settings')
        if args.place_order:
            if not args.item_code:raise ValueError('--item-code is required for a real test order')
            user=os.environ.get('HEC_TEST_CUSTOMER_EMAIL','');password=os.environ.get('HEC_TEST_CUSTOMER_PASSWORD','')
            if not user or not password:raise ValueError('Set the test customer email and password privately')
            buyer=Client(args.url);check('customer login',lambda:buyer.call('POST','login',{'usr':user,'pwd':password}))
            identity=check('customer mapping',lambda:buyer.call('GET','hec_bridge.api.context'))
            if not identity.get('customer'):raise ValueError('Test user is not mapped to a Customer')
            result=check('find requested test item',lambda:buyer.call('GET','hec_bridge.api.catalog',{'q':args.item_code}))
            item=next((x for x in result['items'] if x['item_code']==args.item_code),None)
            if not item:raise ValueError('Exact test item is not in the permitted catalog results')
            payload={'lines':[{'id':item['app_id'],'qty':1}],'request_id':uuid.uuid4().hex,'delivery':{'name':'HEC integration test','phone':'','address':'TEST — integration validation only','note':'Created explicitly using --place-order'}}
            order=check('create ONE test Sales Order',lambda:buyer.call('POST','hec_bridge.api.place_order',payload))
            retry=check('retry same request ID',lambda:buyer.call('POST','hec_bridge.api.place_order',payload))
            if order['name']!=retry['name']:raise ValueError('Idempotency failure')
            report['test_order']=check('retrieve owned order and packed items',lambda:buyer.call('GET','hec_bridge.inbox.order_detail',{'name':order['name']}))
            check('private inbox',lambda:buyer.call('GET','hec_bridge.inbox.list_messages'))
        report['passed']=True
    except Exception as e:
        report['passed']=False;report['blocked_reason']=str(e) if isinstance(e,(RuntimeError,ValueError)) else type(e).__name__
    Path(args.report).write_text(json.dumps(report,ensure_ascii=False,indent=2))
    print(json.dumps({'passed':report['passed'],'report':args.report,'steps':len(steps)},ensure_ascii=False))
    return 0 if report['passed'] else 1

if __name__=='__main__':sys.exit(main())
