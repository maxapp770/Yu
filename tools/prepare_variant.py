"""Package physically distinct customer/admin assets from a shared source tree."""
from pathlib import Path
import re, shutil, sys, os, json
from urllib.parse import urlsplit

ROOT=Path(__file__).resolve().parents[1]
def prepare(role, target=None):
    if role not in ('customer','admin'): raise ValueError('role')
    origin=os.environ.get('HEC_SERVICE_ORIGIN','https://hec-service.invalid').rstrip('/')
    u=urlsplit(origin)
    if u.scheme!='https' or not u.hostname or u.username or u.password or u.query or u.fragment or u.path or u.port not in (None,443): raise ValueError('HEC_SERVICE_ORIGIN must be an HTTPS origin')
    out=Path(target) if target else ROOT/'build/variants'/role
    if out.exists(): shutil.rmtree(out)
    web=out/'assets/web';web.mkdir(parents=True)
    excluded={'studio-source.js','studio-engine.js','studio.js','studio.css','item-media.js','management.js','management.css','management-api.js','management-preview.js',
        'management-config.js','management-picker.js','marketing-editor.js','slides-editor.js',
        'engagement-editor.js','reports.js','reports.css','integration-panel.js','delivery-admin.js','reels-admin.js','reels-schema.js','erp-admin.js','admin-help.js','admin-console.js','admin-help.css','admin-guide-data.js','admin-guide-images'} if role=='customer' else {'customer-shell.js'}
    source=ROOT/'app/src/main/assets/web'
    for file in source.iterdir():
        if file.name in excluded: continue
        if file.is_dir(): shutil.copytree(file,web/file.name)
        else: shutil.copy2(file,web/file.name)
    index=(web/'index.html').read_text()
    for name in excluded:
        index=re.sub(r'<script defer src="'+re.escape(name)+r'"></script>','',index)
        index=re.sub(r'<link rel="stylesheet" href="'+re.escape(name)+r'">','',index)
    if role=='customer':
        index=index.replace('<script defer src="app.js"></script>','<script defer src="customer-shell.js"></script><script defer src="app.js"></script>')
    (web/'index.html').write_text(index)
    (web/'build-mode.js').write_text("'use strict';\nwindow.HECBuild=Object.freeze({role:'"+role+"',version:'2.6.0',server:'"+origin+"'});\n")
    app=(web/'app.js').read_text()
    if role=='customer':
        app=app.replace("'admin','admin-list',",'')
        app=app.replace("admin:()=>Management.render(),'admin-list':()=>Management.render(),",'')
        # Keep the courier entry reachable. It opens a separate, explicitly local
        # preview and does not grant an administrative role or an ERP session.
    (web/'app.js').write_text(app)
    manifest=(ROOT/'app/src/main/AndroidManifest.xml').read_text()
    package='com.alhaitham.hec.admin' if role=='admin' else 'com.alhaitham.hec.preview'
    manifest=manifest.replace('HEC_MEDIA_AUTHORITY',package+'.media')
    manifest=manifest.replace('<manifest ', '<manifest package="'+package+'" ',1)
    if role=='admin':
        manifest=manifest.replace('android:label="الهيثم HEC+"','android:label="إدارة الهيثم"')
        manifest=re.sub(r'<intent-filter[^>]*>(?:(?!</intent-filter>).)*android.intent.action.(?:VIEW|SEND)(?:(?!</intent-filter>).)*</intent-filter>','',manifest,flags=re.S)
    (out/'AndroidManifest.xml').write_text(manifest)
    (out/'AppMode.java').write_text('package com.alhaitham.hec;\npublic final class AppMode { public static final boolean ADMIN = '+str(role=='admin').lower()+'; public static final String SERVICE_ORIGIN = '+json.dumps(origin)+'; }\n')
    java=out/'java/com/alhaitham/hec';java.mkdir(parents=True);shutil.copy2(out/'AppMode.java',java/'AppMode.java')
    print(f'{role}: {len(list(web.rglob("*")))} packaged files')
    return out
if __name__=='__main__': prepare(sys.argv[1])
