"""Framework-independent input validation and public projection rules."""
import hashlib
import json
import math
import re
from datetime import datetime, timezone
from pathlib import Path

OPTION_TYPES = {
    'company':'Company', 'price_list':'Price List', 'warehouse':'Warehouse',
    'currency':'Currency', 'tax_template':'Sales Taxes and Charges Template',
    'customer_group':'Customer Group', 'territory':'Territory',
    'mode_of_payment':'Mode of Payment', 'selling_cost_center':'Cost Center',
    'integration_user':'User',
}
FEATURES = ('catalog','stock','images','bundles','orders','order_submit','loyalty','affiliate','notifications','automation','delivery','returns')
# Unconfigured business workflows are unavailable, not simulated as live ERP writes.
IMPLEMENTED = {'catalog','stock','images','bundles','orders','notifications','delivery'}
PUBLIC = {'videos','reels-settings','home','home-texts','home-shortcuts','home-banners','home-deals','home-groups','home-suggestions','home-new','home-best','home-footer','categories','shop-banners','shop-new','shop-layout','offers-layout','offer-bundles','campaigns','golden','appearance','settings','app-navigation','account-layout','orders-layout','notification-settings','loyalty'}
SCHEMA = {m['id']:m for m in json.loads((Path(__file__).parent/'schema.json').read_text())}
READONLY = {k for k,m in SCHEMA.items() if m.get('readonly')} | {'products','orders','returns','wallet','couriers','messages','affiliate'}


def default_settings():
    return {**dict.fromkeys(OPTION_TYPES,''), 'integration_user':'',
        'delivery_days':3, 'features':dict.fromkeys(FEATURES,False)}


def flag(v):
    if type(v) is bool: return v
    if v in (0,1,'0','1','true','false'): return v in (1,'1','true')
    raise ValueError('Invalid boolean')


def app_id(code):
    return 'ERP_'+hashlib.sha256(str(code).encode()).hexdigest()[:24]


def image_id(path):
    return 'erp-'+hashlib.sha256(path.encode()).hexdigest()[:24]+'.jpg'


def image_path(path):
    return isinstance(path,str) and path.startswith('/files/') and len(path)<500 and not any(x in path for x in ('..','\\','%','?','#')) and path.lower().endswith(('.jpg','.jpeg','.png','.webp'))


def display(value, limit=180):
    return re.sub(r'[<>"\x00-\x1f]', '', str(value or ''))[:limit]


def validate_settings(value):
    if not isinstance(value,dict) or set(value)-set(OPTION_TYPES)-{'features','delivery_days'}: raise ValueError('Unknown settings')
    result=default_settings()
    for key in OPTION_TYPES:
        text=value.get(key,'')
        if not isinstance(text,str) or len(text)>140 or re.search(r'[\x00-\x1f]',text): raise ValueError('Invalid selection: '+key)
        result[key]=text
    flags=value.get('features',{})
    if not isinstance(flags,dict) or set(flags)-set(FEATURES): raise ValueError('Unknown feature')
    result['features']={k:flag(flags.get(k,False)) for k in FEATURES}
    if any(result['features'][k] for k in set(FEATURES)-IMPLEMENTED): raise ValueError('Workflow adapter unavailable')
    days=value.get('delivery_days',3)
    if type(days) not in (int,float) or not math.isfinite(days) or days!=int(days) or not 0<=days<=90: raise ValueError('Invalid delivery days')
    result['delivery_days']=int(days)
    enabled=result['features']
    if any(enabled.values()) and not result['integration_user']: raise ValueError('Select integration user')
    if enabled['catalog'] and not all(result[k] for k in ('company','price_list','currency')): raise ValueError('Company, price list and currency required')
    if any(enabled[k] for k in ('stock','bundles','orders')) and not enabled['catalog']: raise ValueError('Catalog required')
    if enabled['stock'] and not result['warehouse']: raise ValueError('Warehouse required')
    if enabled['order_submit'] and not enabled['orders']: raise ValueError('Orders required')
    return result


def structure(value,depth=0):
    if depth>12: raise ValueError('Nested data too deep')
    if isinstance(value,dict):
        if len(value)>100 or any(k in ('__proto__','constructor','prototype') or not isinstance(k,str) for k in value): raise ValueError('Invalid object')
        return {k:structure(v,depth+1) for k,v in value.items()}
    if isinstance(value,list):
        if len(value)>500: raise ValueError('Too many entries')
        return [structure(v,depth+1) for v in value]
    if isinstance(value,str):
        if len(value)>4000 or re.search(r'[<>\x00-\x08\x0b\x0c\x0e-\x1f]',value): raise ValueError('Use plain text')
        return value
    if value is None or type(value) is bool: return value
    if type(value) in (int,float) and math.isfinite(value) and abs(value)<=1e12: return value
    raise ValueError('Invalid data value')


def record(module,payload):
    if module not in SCHEMA or module in READONLY: raise ValueError('Read-only or unknown module')
    if not isinstance(payload,dict): raise ValueError('Expected object')
    fields={f[0]:f for f in SCHEMA[module]['fields']}
    if set(payload)-set(fields): raise ValueError('Unknown content field')
    value=structure(payload)
    for key,val in value.items():
        spec=fields[key];kind=spec[2]
        if kind=='readonly': raise ValueError('Immutable field')
        if kind=='checkbox': value[key]=flag(val)
        if kind=='number' and (type(val) not in (int,float) or not math.isfinite(val) or not 0<=val<=1e9): raise ValueError('Invalid number')
        if kind=='select' and val not in spec[3]: raise ValueError('Invalid selection')
        if kind=='image' and val and not re.fullmatch(r'[A-Za-z0-9_-]+\.jpg',val): raise ValueError('Image must be uploaded first')
        if kind in ('products','groups') and (not isinstance(val,list) or len(val)>100 or any(not isinstance(v,str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,80}',v) for v in val)): raise ValueError('Invalid item references')
        if kind in ('gallery','allocation','children','customers') and not isinstance(val,list): raise ValueError('Invalid rows')
        if kind in ('marketing','motion','automation') and not isinstance(val,dict): raise ValueError('Invalid configuration')
        if kind=='datetime-local' and val: datetime.fromisoformat(val)
    if value.get('startsAt') and value.get('endsAt') and value['startsAt']>=value['endsAt']: raise ValueError('End must follow start')
    if value.get('title') and len(value['title'])<2: raise ValueError('Title required')
    return value


def order_lines(lines):
    if not isinstance(lines,list) or not 1<=len(lines)<=100: raise ValueError('1–100 items required')
    result=[];seen=set()
    for row in lines:
        if not isinstance(row,dict) or set(row)-{'id','qty'}: raise ValueError('Prices and customer identities must not be supplied by the client')
        code=row.get('id');qty=row.get('qty')
        if not isinstance(code,str) or not re.fullmatch(r'ERP_[a-f0-9]{24}',code) or code in seen: raise ValueError('Invalid or duplicate item')
        if type(qty) not in (int,float) or not math.isfinite(qty) or qty!=int(qty) or not 1<=qty<=999: raise ValueError('Quantity must be 1–999')
        seen.add(code);result.append({'id':code,'qty':int(qty)})
    return result


def request_hash(lines):
    return hashlib.sha256(json.dumps(sorted(lines,key=lambda r:r['id']),sort_keys=True,separators=(',',':')).encode()).hexdigest()
