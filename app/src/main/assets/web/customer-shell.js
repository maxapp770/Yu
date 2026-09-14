'use strict';
window.Management=Object.freeze({init(){},refresh(){},entry:()=>'',canManage:()=>false,click:()=>false,submit:()=>false,render:()=>'',revoke(){}});
// Purge obsolete administrator preview state on an upgrade from the combined APK.
if(window.HECBuild?.role==='customer')try{const previous=localStorage.getItem('hec.admin.review.v1');if(previous&&!localStorage.getItem('hec.legacy-review.backup.v1'))localStorage.setItem('hec.legacy-review.backup.v1',previous);localStorage.removeItem('hec.admin.review.v1')}catch{}
