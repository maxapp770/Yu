package com.alhaitham.hec;
import android.net.Uri;
import android.webkit.JavascriptInterface;
import android.webkit.WebView;
import android.util.Base64;
import android.graphics.BitmapFactory;
import org.json.*;
import java.util.*;
import java.util.concurrent.*;

final class HECDevice {
 private final MainActivity activity;private final WebView web;
 private final ThreadPoolExecutor worker=new ThreadPoolExecutor(1,1,0,TimeUnit.SECONDS,new ArrayBlockingQueue<Runnable>(3));
 private volatile boolean closed;
 HECDevice(MainActivity a,WebView w){activity=a;web=w;}
 @JavascriptInterface public void transfer(String id,String mode,String data){
  if(closed||!AppMode.ADMIN||id==null||!id.matches("n[0-9]{1,12}")||!("save".equals(mode)||"share".equals(mode))||data==null||data.length()>28000000)return;
  activity.runOnUiThread(()->{if(!MainActivity.trustedPage(web.getUrl()))return;try{worker.execute(()->{try{
   JSONObject obj=new JSONObject(data);JSONArray files=obj.getJSONArray("files");if(files.length()<1||files.length()>9||("save".equals(mode)&&files.length()!=1))throw new Exception("عدد الملفات غير صالح");
   ArrayList<Uri> uris=new ArrayList<>();long total=0;
   for(int i=0;i<files.length();i++){JSONObject f=files.getJSONObject(i);String mime=f.getString("type"),name=f.getString("name"),base=f.getString("data");if(!(mime.equals("image/jpeg")||mime.equals("image/png"))||base.length()>7100000)throw new Exception("نوع الصورة أو حجمها غير صالح");byte[] bytes=Base64.decode(base,Base64.DEFAULT);total+=bytes.length;if(bytes.length>5000000||total>20000000)throw new Exception("حجم الصور كبير؛ شارك دفعة أصغر");BitmapFactory.Options opt=new BitmapFactory.Options();opt.inJustDecodeBounds=true;BitmapFactory.decodeByteArray(bytes,0,bytes.length,opt);if(opt.outWidth<1||opt.outHeight<1||(long)opt.outWidth*opt.outHeight>16000000L||!mime.equals(opt.outMimeType))throw new Exception("الصورة غير صالحة");uris.add(HECFileProvider.create(activity,name,bytes));}
   String text=obj.optString("text","");if(text.length()>6000)throw new Exception("نص المشاركة طويل");String filename=files.getJSONObject(0).getString("name"),mime=files.getJSONObject(0).getString("type");
   activity.runOnUiThread(()->{if(!closed&&MainActivity.trustedPage(web.getUrl()))activity.deviceFiles(id,mode,uris,text,filename,mime);});
  }catch(Exception e){result(id,false,e.getMessage()==null?"تعذر تجهيز الصورة":e.getMessage());}});}catch(RejectedExecutionException e){result(id,false,"انتظر اكتمال العملية السابقة");}});
 }
 void result(String id,boolean ok,String message){if(closed)return;activity.runOnUiThread(()->{if(closed||!MainActivity.trustedPage(web.getUrl()))return;web.evaluateJavascript("window.HECNative&&HECNative.receive("+JSONObject.quote(id)+","+ok+","+JSONObject.quote(message)+")",null);});}
 void close(){closed=true;worker.shutdownNow();}
}
