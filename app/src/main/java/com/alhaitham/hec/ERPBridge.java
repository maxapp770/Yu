package com.alhaitham.hec;

import android.app.Activity;
import android.webkit.JavascriptInterface;
import android.webkit.WebResourceResponse;
import android.webkit.WebView;
import java.io.*;
import java.net.*;
import java.nio.charset.StandardCharsets;
import java.util.*;
import java.util.concurrent.*;
import javax.net.ssl.HttpsURLConnection;
import org.json.*;

/** Allowlisted transport. Customer service origin is fixed at build time; admin origin is explicit. */
final class ERPBridge {
    static final String ORIGIN = AppMode.SERVICE_ORIGIN;
    private volatile String origin = ORIGIN;
    private final Activity activity;
    private final WebView web;
    private final boolean admin;
    private final ThreadPoolExecutor queue = new ThreadPoolExecutor(1, 1, 0, TimeUnit.SECONDS, new ArrayBlockingQueue<Runnable>(24));
    private final Map<String,String> videos = new ConcurrentHashMap<>();
    private final Map<String,String> images = new ConcurrentHashMap<>();
    private volatile String authorization = "";
    private volatile String courierAuthorization = "";
    private volatile boolean closed;

    ERPBridge(Activity a, WebView w, boolean isAdmin) { activity=a;web=w;admin=isAdmin; }
    @JavascriptInterface public void request(String id, String op, String json) {
        if(closed || id==null || !id.matches("r[0-9]{1,12}") || op==null || json==null || json.length()>8000000) return;
        try { queue.execute(()->{
            try { JSONObject args=new JSONObject(json);Object result=dispatch(op,args);complete(id,result,null); }
            catch(Failure e){complete(id,null,e);}
            catch(Exception e){complete(id,null,new Failure(0,"تعذر الاتصال الآمن بالخادم. تحقق من الشبكة وعنوان الخدمة."));}
        }); } catch(RejectedExecutionException e){complete(id,null,new Failure(429,"هناك طلبات كثيرة؛ حاول بعد قليل."));}
    }
    private Object dispatch(String op,JSONObject a) throws Exception {
        Set<String> publicOps=new HashSet<>(Arrays.asList("reels.social","reels.react","reels.comment","reels.comment.delete","reels.feed","public.version","public.config","catalog.search","auth.login","auth.logout","auth.context","customer.password","customer.inbox","customer.inbox.read","customer.order.detail","customer.orders","customer.order","customer.deliveries","courier.auth.login","courier.auth.logout","courier.auth.context","courier.jobs","courier.detail","courier.transition","courier.inbox","courier.profile","courier.password"));
        Set<String> adminOps=new HashSet<>(Arrays.asList("admin.studio.list","admin.studio.save","admin.studio.delete","admin.studio.product","admin.item-media.search","admin.item-media.list","admin.item-media.upload","admin.item-media.main","admin.media-access","admin.media-access.save","admin.reels.comments","admin.reels.comment.delete","admin.reels.discover","admin.reels.upload","admin.reels.import","admin.delivery.options","admin.delivery.accounts","admin.delivery.account.save","admin.delivery.list","admin.delivery.detail","admin.delivery.assign","admin.delivery.reassign","admin.delivery.close","admin.delivery.settle","admin.delivery.sync","admin.publication","admin.publish","admin.rollback","admin.publish.cancel","admin.maintenance","admin.preview","admin.doctor","admin.customer.create","admin.options","admin.settings","admin.settings.save","admin.capabilities","admin.config","admin.list","admin.save","admin.archive","admin.media","admin.integration","admin.integration.test","admin.integration.activate","admin.requests","admin.requests.reconcile","admin.access","admin.access.save","reports.list","reports.meta","reports.options","reports.run","reports.export","reports.presets"));
        if(!publicOps.contains(op)&&!(admin&&adminOps.contains(op)))throw new Failure(403,"عملية غير مسموحة في هذا التطبيق.");
        if(op.equals("auth.login")) { String next=admin?validateOrigin(a.optString("server",ORIGIN)):ORIGIN; if(!next.equals(origin))clear();else authorization="";images.clear();origin=next; }
        a.remove("server");a.put("app_role",admin?"admin":"customer");
        try {
            JSONObject value=call(op,a);
            String token=value.optString("session_token");value.remove("session_token");
            if(!token.isEmpty()){if(op.startsWith("courier."))courierAuthorization="Bearer "+token;else authorization="Bearer "+token;}
            if(op.equals("reports.export")&&admin){
                byte[] bytes=android.util.Base64.decode(value.getString("content_base64"),android.util.Base64.DEFAULT);
                if(bytes.length>2000000)throw new Failure(413,"ضيّق فلاتر التقرير قبل التصدير.");
                value.remove("content_base64");value.put("save_dialog",true);
                ((MainActivity)activity).saveReport(bytes,value.optString("filename","HEC-report.csv"));
            }
            return value;
        } finally { if(op.equals("auth.logout"))authorization=""; if(op.equals("courier.auth.logout")||op.equals("courier.password"))courierAuthorization=""; }
    }
    private JSONObject call(String op,JSONObject payload) throws Exception {
        if(origin.endsWith(".invalid")){if(op.equals("auth.logout"))return new JSONObject().put("ok",true);throw new Failure(503,"اضبط عنوان الخدمة المستقلة للاتصال الفعلي، أو استخدم المراجعة المحلية.");}
        URL url=new URL(origin+"/v1/rpc");
        HttpsURLConnection c=(HttpsURLConnection)url.openConnection();c.setInstanceFollowRedirects(false);c.setConnectTimeout(15000);c.setReadTimeout(op.startsWith("reports.")?120000:45000);c.setRequestMethod("POST");
        c.setRequestProperty("Accept","application/json");c.setRequestProperty("X-HEC-App-Role",admin?"admin":"customer");c.setRequestProperty("User-Agent","HECAndroid/2.6.0 "+(admin?"Admin":"Customer"));
        String bearer=op.startsWith("courier.")?courierAuthorization:authorization; if(!bearer.isEmpty())c.setRequestProperty("Authorization",bearer);
        try {
            c.setDoOutput(true);c.setRequestProperty("Content-Type","application/json; charset=UTF-8");
            byte[] bytes=new JSONObject().put("op",op).put("args",payload).toString().getBytes(StandardCharsets.UTF_8);
            c.setFixedLengthStreamingMode(bytes.length);try(OutputStream out=c.getOutputStream()){out.write(bytes);}
            int code=c.getResponseCode();String body=new String(read(code>=400?c.getErrorStream():c.getInputStream(),12000000),StandardCharsets.UTF_8);
            JSONObject data;try{data=new JSONObject(body);}catch(Exception e){throw new Failure(code,"استجابة الخدمة غير صالحة. تحقق من عنوان الخدمة المستقلة.");}
            if(code>=300||data.has("error")){
                if(code==401){if(op.startsWith("courier."))courierAuthorization="";else authorization="";}JSONObject error=data.optJSONObject("error");
                String message=error!=null?error.optString("message"):"تعذر إكمال الطلب من الخدمة ("+code+").";
                throw new Failure(code,message.length()>500?"رفضت الخدمة الطلب.":message);
            }
            JSONObject value=data.optJSONObject("message");if(value==null)throw new Failure(502,"استجابة الخدمة غير مكتملة.");
            JSONObject vm=value.optJSONObject("_videos");if(vm!=null){videos.clear();Iterator<String> vs=vm.keys();while(vs.hasNext()){String k=vs.next(),v=vm.optString(k);if(k.matches("[A-Za-z0-9_-]{1,80}")&&(v.startsWith("https://")||v.matches("/v1/reels-media/rv-[a-f0-9]{32}\\.(mp4|webm)")))videos.put(k,v);}}
            JSONObject im=value.optJSONObject("_images");if(im!=null){Iterator<String> it=im.keys();while(it.hasNext()){String k=it.next(),v=im.optString(k);if(k.matches("erp-[a-f0-9]{24}\\.jpg")&&safeImage(v))images.put(k,v);}}
            if(op.startsWith("admin.item-media.")||op.equals("admin.studio.product"))registerImages(value);
            return value;
        }finally{c.disconnect();}
    }
    private void registerImages(Object value){
        if(value instanceof JSONObject){JSONObject o=(JSONObject)value;Iterator<String> k=o.keys();while(k.hasNext())registerImages(o.opt(k.next()));}
        else if(value instanceof JSONArray){JSONArray a=(JSONArray)value;for(int i=0;i<a.length();i++)registerImages(a.opt(i));}
        else if(value instanceof String&&((String)value).matches("erp-[a-f0-9]{24}\\.jpg"))images.put((String)value,"/v1/images/"+value);
    }
    private static String validateOrigin(String value) throws Failure {
        try {
            URI u=new URI(value.trim());String host=u.getHost();
            if(!"https".equalsIgnoreCase(u.getScheme())||host==null||host.length()>253||u.getUserInfo()!=null||u.getRawQuery()!=null||u.getRawFragment()!=null||!(u.getPath()==null||u.getPath().isEmpty()||u.getPath().equals("/"))||!(u.getPort()==-1||u.getPort()==443))throw new Exception();
            if(host.equalsIgnoreCase("appassets.androidplatform.net"))throw new Exception();
            return "https://"+host.toLowerCase(Locale.ROOT);
        }catch(Exception e){throw new Failure(422,"أدخل عنوان HTTPS فقط، دون مسار أو اسم مستخدم أو معاملات.");}
    }
    private static boolean safeImage(String p){return p!=null&&p.matches("/v1/images/erp-[a-f0-9]{24}\\.jpg");}
    WebResourceResponse image(String name) {
        String path=images.get(name);if(path==null)return null;
        HttpsURLConnection c=null;
        try{c=(HttpsURLConnection)new URL(origin+new URI(null,null,path,null).getRawPath()).openConnection();c.setInstanceFollowRedirects(false);c.setConnectTimeout(10000);c.setReadTimeout(15000);int status=c.getResponseCode();if(status!=200)return null;String mime=c.getContentType();if(mime==null||!mime.matches("image/(jpeg|png|webp)(;.*)?"))return null;byte[] content=read(c.getInputStream(),6000000);return new WebResourceResponse(mime.split(";")[0],null,new ByteArrayInputStream(content));}catch(Exception e){return null;}finally{if(c!=null)c.disconnect();}
    }
    WebResourceResponse video(String id,String range) {
        String value=videos.get(id);if(value==null)return null;
        HttpsURLConnection c=null;
        try{
            URI u=new URI(value.startsWith("/")?origin+value:value);
            if(!"https".equals(u.getScheme())||u.getUserInfo()!=null||u.getHost()==null||(u.getPort()!=-1&&u.getPort()!=443)||u.getPath().contains("/private/"))return null;
            c=(HttpsURLConnection)u.toURL().openConnection();c.setInstanceFollowRedirects(false);c.setConnectTimeout(15000);c.setReadTimeout(30000);
            if(range!=null&&range.matches("bytes=[0-9]*-[0-9]*"))c.setRequestProperty("Range",range);
            int status=c.getResponseCode();String mime=c.getContentType();if((status!=200&&status!=206)||mime==null||!mime.matches("video/(mp4|webm)(;.*)?")){c.disconnect();return null;}
            Map<String,String> h=new HashMap<>();h.put("Cache-Control","no-store");h.put("X-Content-Type-Options","nosniff");h.put("Referrer-Policy","no-referrer");
            for(String k:new String[]{"Content-Range","Accept-Ranges","Content-Length"})if(c.getHeaderField(k)!=null)h.put(k,c.getHeaderField(k));
            final HttpsURLConnection connection=c;InputStream stream=new FilterInputStream(c.getInputStream()){public void close()throws IOException{try{super.close();}finally{connection.disconnect();}}};
            return new WebResourceResponse(mime.split(";")[0],null,status,status==206?"Partial Content":"OK",h,stream);
        }catch(Exception e){if(c!=null)c.disconnect();return null;}
    }
    private Object unwrap(JSONObject r){return r.opt("message");}
    private static byte[] read(InputStream in,int max)throws Exception{if(in==null)return new byte[0];try(InputStream stream=in;ByteArrayOutputStream out=new ByteArrayOutputStream()){byte[] b=new byte[8192];int n;while((n=stream.read(b))!=-1){if(out.size()+n>max)throw new IOException("size");out.write(b,0,n);}return out.toByteArray();}}
    private void complete(String id,Object value,Failure error){if(closed)return;activity.runOnUiThread(()->{if(closed||web.getUrl()==null||!web.getUrl().startsWith("https://appassets.androidplatform.net/index.html"))return;try{JSONObject result=new JSONObject();if(error!=null)result.put("error",new JSONObject().put("status",error.code).put("message",error.getMessage()));else result.put("value",value==null?JSONObject.NULL:value);web.evaluateJavascript("window.HECERP&&HECERP.receive("+JSONObject.quote(id)+","+result.toString()+")",null);}catch(Exception ignored){}});}
    private void clear(){videos.clear();images.clear();courierAuthorization="";authorization="";}
    void close(){closed=true;clear();queue.shutdownNow();}
    private static final class Failure extends Exception{final int code;Failure(int c,String m){super(m);code=c;}}
}
