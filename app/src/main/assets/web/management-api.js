'use strict';
let hecLocalReview=false;try{hecLocalReview=sessionStorage.getItem('hec.admin.preview')==='1'}catch{}
window.HECManagementTransport=window.HECBuild?.role==='admin'&&!hecLocalReview?HECERP.management:HECAdminPreview;
