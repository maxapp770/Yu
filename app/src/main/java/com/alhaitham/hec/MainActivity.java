package com.alhaitham.hec;

import android.app.Activity;
import android.app.AlertDialog;
import android.content.Intent;
import android.content.ActivityNotFoundException;
import android.os.Bundle;
import android.net.Uri;
import android.graphics.Color;
import android.view.View;
import android.view.WindowManager;
import android.widget.Button;
import android.widget.FrameLayout;
import android.widget.LinearLayout;
import android.widget.ProgressBar;
import android.widget.TextView;
import android.webkit.CookieManager;
import android.webkit.GeolocationPermissions;
import android.webkit.PermissionRequest;
import android.webkit.RenderProcessGoneDetail;
import android.webkit.WebChromeClient;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import android.webkit.WebResourceError;
import android.webkit.WebResourceRequest;
import android.webkit.WebResourceResponse;
import android.webkit.WebSettings;
import java.io.ByteArrayInputStream;
import java.io.IOException;
import java.util.HashMap;
import java.util.Map;
import java.util.Arrays;
import android.util.Base64;
import org.json.JSONObject;
import org.json.JSONArray;
import java.nio.charset.StandardCharsets;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

/** Owned offline content only. No native JavaScript bridge or remote permission. */
public final class MainActivity extends Activity {
    private static final String HOST = "appassets.androidplatform.net";
    private static final String SHARE_HOST = "hec-shared-cart.fadhel-motaher.chatgpt.site";
    private static final String START = "https://" + HOST + "/index.html#home";
    private WebView web;
    private ERPBridge erp;
    private HECDevice device;
    private Uri cameraUri;
    private String deviceRequest;
    private Uri deviceSaveUri;
    private FrameLayout root;
    private ProgressBar progress;
    private boolean errorVisible;
    private boolean scanning;
    private boolean choosingFiles;
    private android.webkit.ValueCallback<Uri[]> fileCallback;

    @Override public void onCreate(Bundle state) {
        super.onCreate(state);
        WebView.setWebContentsDebuggingEnabled(false);
        openApp(state);
    }

    private void openApp(Bundle state) {
        errorVisible = false;
        if (erp != null) erp.close();
        if(device!=null)device.close();
        if (web != null) { web.stopLoading(); web.destroy(); }
        root = new FrameLayout(this);
        root.setBackgroundColor(Color.WHITE);
        web = new WebView(this);
        web.setBackgroundColor(Color.WHITE);
        web.setImportantForAutofill(View.IMPORTANT_FOR_AUTOFILL_NO_EXCLUDE_DESCENDANTS);
        WebSettings s = web.getSettings();
        s.setUserAgentString(s.getUserAgentString() + " HECAndroid/2.6.0");
        s.setJavaScriptEnabled(true); // Required by the packaged UI; no unowned scripts can load.
        s.setDomStorageEnabled(true);
        erp = new ERPBridge(this, web, AppMode.ADMIN);
        web.addJavascriptInterface(erp, "HECRemote");
        device=new HECDevice(this,web);if(AppMode.ADMIN)web.addJavascriptInterface(device,"HECDevice");
        s.setAllowFileAccess(false);
        s.setAllowContentAccess(false);
        s.setAllowFileAccessFromFileURLs(false);
        s.setAllowUniversalAccessFromFileURLs(false);
        s.setJavaScriptCanOpenWindowsAutomatically(false);
        s.setSupportMultipleWindows(false);
        s.setMixedContentMode(WebSettings.MIXED_CONTENT_NEVER_ALLOW);
        s.setBlockNetworkLoads(true);
        s.setSafeBrowsingEnabled(true);
        s.setGeolocationEnabled(false);
        s.setSaveFormData(false);
        s.setMediaPlaybackRequiresUserGesture(true);
        CookieManager.getInstance().setAcceptCookie(false);
        CookieManager.getInstance().setAcceptThirdPartyCookies(web, false);
        web.setWebChromeClient(new WebChromeClient() {
            @Override public void onProgressChanged(WebView view, int value) {
                progress.setProgress(value);
                progress.setVisibility(value == 100 ? View.GONE : View.VISIBLE);
            }
            @Override public boolean onShowFileChooser(WebView view, android.webkit.ValueCallback<Uri[]> callback, WebChromeClient.FileChooserParams params) {
                if (!AppMode.ADMIN || !trustedPage(view.getUrl())) { callback.onReceiveValue(null);return true; }
                if(fileCallback!=null)fileCallback.onReceiveValue(null);
                fileCallback=callback;choosingFiles=true;
                if(params.isCaptureEnabled()){if(checkSelfPermission(android.Manifest.permission.CAMERA)!=android.content.pm.PackageManager.PERMISSION_GRANTED)requestPermissions(new String[]{android.Manifest.permission.CAMERA},80);else capturePhoto();return true;}
                Intent pick=new Intent(Intent.ACTION_OPEN_DOCUMENT);pick.addCategory(Intent.CATEGORY_OPENABLE);boolean video=Arrays.toString(params.getAcceptTypes()).contains("video/");pick.setType(video?"video/*":"image/*");pick.putExtra(Intent.EXTRA_MIME_TYPES,video?new String[]{"video/mp4","video/webm"}:new String[]{"image/jpeg","image/png"});pick.putExtra(Intent.EXTRA_ALLOW_MULTIPLE,params.getMode()==WebChromeClient.FileChooserParams.MODE_OPEN_MULTIPLE);pick.addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION);
                try{startActivityForResult(pick,73);}catch(Exception e){choosingFiles=false;fileCallback.onReceiveValue(null);fileCallback=null;view.evaluateJavascript("if(window.HECMedia)HECMedia.cancel()",null);}return true;
            }
            @Override public void onPermissionRequest(PermissionRequest request) { request.deny(); }
            @Override public void onGeolocationPermissionsShowPrompt(String origin, GeolocationPermissions.Callback callback) { callback.invoke(origin, false, false); }
        });
        web.setWebViewClient(new WebViewClient() {
            @Override public boolean shouldOverrideUrlLoading(WebView view, WebResourceRequest request) {
                if(request.isForMainFrame()&&request.hasGesture()&&trustedPage(view.getUrl())&&isReelShareCommand(request.getUrl())){shareReel(request.getUrl().getFragment());return true;}
                if (request.isForMainFrame() && request.hasGesture() && trustedPage(view.getUrl()) && isShareCommand(request.getUrl())) {
                    shareCart(request.getUrl().getFragment(), "/native-product-share".equals(request.getUrl().getEncodedPath())); return true;
                }
                if (request.isForMainFrame() && request.hasGesture() && trustedPage(view.getUrl()) && isScanCommand(request.getUrl())) {
                    if (!scanning) { scanning=true;try {startActivityForResult(new Intent(MainActivity.this, BarcodeActivity.class),72);} catch (Exception e) { scanning=false;web.evaluateJavascript("if(window.HECScanner)HECScanner.receive(null)",null); } } return true;
                }
                if (allowed(request.getUrl())) return false;
                if (request.isForMainFrame() && request.hasGesture() && externalAllowed(request.getUrl())) {
                    try { startActivity(new Intent(Intent.ACTION_VIEW, request.getUrl())); }
                    catch (ActivityNotFoundException e) { new AlertDialog.Builder(MainActivity.this).setMessage("لا يوجد تطبيق لفتح هذا الرابط").setPositiveButton("حسناً", null).show(); }
                }
                return true; }
            @Override public WebResourceResponse shouldInterceptRequest(WebView view, WebResourceRequest request) {
                Uri u = request.getUrl();
                if (!allowed(u) || !"GET".equals(request.getMethod())) return denied();
                String path = u.getPath();
                if(path.startsWith("/reels-stream/")){WebResourceResponse video=erp.video(path.substring(14),request.getRequestHeaders().get("Range"));return video!=null?video:denied();}
                if ("/".equals(path)) path = "/index.html";
                if(path.matches("/(?:assets|v1/images)/erp-[a-f0-9]{24}\\.jpg")){WebResourceResponse remote=erp.image(path.substring(path.lastIndexOf('/')+1));if(remote!=null)return remote;return denied();}
                String mime = path.endsWith(".js") ? "application/javascript" : path.endsWith(".css") ? "text/css" : path.endsWith(".jpg") ? "image/jpeg" : path.endsWith(".png") ? "image/png" : path.endsWith(".json") ? "application/json" : path.endsWith(".mp4") ? "video/mp4" : path.endsWith(".webm") ? "video/webm" : "text/html";
                Map<String, String> headers = new HashMap<>();
                headers.put("X-Content-Type-Options", "nosniff");
                headers.put("Referrer-Policy", "no-referrer");
                headers.put("Cache-Control", "no-store");
                try { return new WebResourceResponse(mime, "UTF-8", 200, "OK", headers, getAssets().open("web" + path)); }
                catch (IOException exception) { return denied(); }
            }
            @Override public void onReceivedError(WebView view, WebResourceRequest request, WebResourceError error) { if (request.isForMainFrame()) showRecovery(); }
            @Override public void onReceivedHttpError(WebView view, WebResourceRequest request, WebResourceResponse response) { if (request.isForMainFrame()) showRecovery(); }
            @Override public boolean onRenderProcessGone(WebView view, RenderProcessGoneDetail detail) {
                root.removeView(view);
                if (web == view) web = null;
                view.destroy();
                showRecovery();
                return true;
            }
        });
        root.addView(web, new FrameLayout.LayoutParams(-1, -1));
        progress = new ProgressBar(this, null, android.R.attr.progressBarStyleHorizontal);
        progress.setMax(100);
        progress.setContentDescription("جارٍ فتح التطبيق");
        root.addView(progress, new FrameLayout.LayoutParams(-1, 6));
        setContentView(root);
        boolean restored = state != null && web.restoreState(state) != null;
        String incoming = AppMode.ADMIN ? null : incomingCart(getIntent());
        String reel=AppMode.ADMIN?null:incomingReel(getIntent());
        if(reel!=null)web.loadUrl(reelUrl(reel));
        else if (incoming != null) web.loadUrl(cartUrl(incoming));
        else if (!restored) web.loadUrl(AppMode.ADMIN ? START.replace("#home", "#admin") : START);
    }

    static boolean trustedPage(String value) {
        if (value == null) return false;
        Uri u = Uri.parse(value);
        return "https".equals(u.getScheme()) && HOST.equals(u.getHost()) && "/index.html".equals(u.getPath()) && u.getUserInfo() == null && u.getQuery() == null;
    }
    private static boolean isScanCommand(Uri u) { return "https".equals(u.getScheme()) && HOST.equals(u.getHost()) && "/native-scan".equals(u.getEncodedPath()) && u.getUserInfo()==null && u.getQuery()==null && u.getFragment()==null && u.getPort()==-1; }
    private static boolean isReelShareCommand(Uri u){return "https".equals(u.getScheme())&&HOST.equals(u.getHost())&&"/native-reel-share".equals(u.getEncodedPath())&&u.getUserInfo()==null&&u.getQuery()==null&&u.getPort()==-1&&u.getFragment()!=null&&u.getFragment().matches("[A-Za-z0-9_-]{1,80}");}
    private static String reelUrl(String id){return "https://"+HOST+"/index.html#reels/"+id;}
    private static String incomingReel(Intent intent){
        if(AppMode.ADMIN||intent==null)return null;
        if(Intent.ACTION_VIEW.equals(intent.getAction())){Uri u=intent.getData();if(u!=null&&"hec".equals(u.getScheme())&&"reels".equals(u.getHost())&&u.getUserInfo()==null&&u.getQuery()==null&&u.getFragment()==null&&u.getPort()==-1&&u.getEncodedPath()!=null&&u.getEncodedPath().matches("/[A-Za-z0-9_-]{1,80}"))return u.getPath().substring(1);}
        if(Intent.ACTION_SEND.equals(intent.getAction())&&"text/plain".equals(intent.getType())){CharSequence text=intent.getCharSequenceExtra(Intent.EXTRA_TEXT);if(text!=null&&text.length()<=100000){Matcher m=Pattern.compile("(?:hec://reels/|https://hec-service-review\\.fadhel-motaher\\.chatgpt\\.site/customer/index\\.html#reels/)([A-Za-z0-9_-]{1,80})(?![A-Za-z0-9_-])").matcher(text);if(m.find())return m.group(1);}}
        return null;
    }
    private void shareReel(String id){
        if(id==null||!id.matches("[A-Za-z0-9_-]{1,80}"))return;
        String message="شاهد الريلز في متجر الهيثم:\nhttps://hec-service-review.fadhel-motaher.chatgpt.site/customer/index.html#reels/"+id+"\n\nفتح في تطبيق الهيثم المثبّت:\nhec://reels/"+id;
        try{startActivity(Intent.createChooser(new Intent(Intent.ACTION_SEND).setType("text/plain").putExtra(Intent.EXTRA_TEXT,message).putExtra(Intent.EXTRA_TITLE,"ريلز الهيثم"),"مشاركة الريلز عبر"));}catch(ActivityNotFoundException e){new AlertDialog.Builder(this).setMessage("لا يوجد تطبيق متاح للمشاركة").setPositiveButton("حسناً",null).show();}
    }
    private byte[] reportExport;
    void saveReport(byte[] bytes,String name){runOnUiThread(()->{
        if(!AppMode.ADMIN||reportExport!=null)return;
        reportExport=bytes;choosingFiles=true;
        Intent i=new Intent(Intent.ACTION_CREATE_DOCUMENT).addCategory(Intent.CATEGORY_OPENABLE).setType("text/csv").putExtra(Intent.EXTRA_TITLE,name.replaceAll("[^A-Za-z0-9._-]","_"));
        try{startActivityForResult(i,74);}catch(Exception e){reportExport=null;choosingFiles=false;new AlertDialog.Builder(this).setMessage("تعذر فتح نافذة حفظ التقرير.").setPositiveButton("حسناً",null).show();}
    });}
    @Override protected void onActivityResult(int requestCode,int resultCode,Intent data) {
        super.onActivityResult(requestCode,resultCode,data);
        if(requestCode==76||requestCode==77){
            choosingFiles=false;String id=deviceRequest;deviceRequest=null;Uri source=deviceSaveUri;deviceSaveUri=null;
            if(id==null)return;
            if(requestCode==77){device.result(id,true,"عدت من نافذة المشاركة؛ الإرسال يتم من التطبيق الذي اخترته");return;}
            if(resultCode!=RESULT_OK||data==null||data.getData()==null){device.result(id,true,"أُلغي حفظ الصورة");return;}
            try(java.io.InputStream in=getContentResolver().openInputStream(source);java.io.OutputStream out=getContentResolver().openOutputStream(data.getData())){if(in==null||out==null)throw new IOException();byte[] b=new byte[8192];int n;while((n=in.read(b))!=-1)out.write(b,0,n);device.result(id,true,"حُفظ التصميم في المكان المختار");}catch(Exception e){device.result(id,false,"تعذر حفظ الصورة");}return;
        }
        if(requestCode==75){choosingFiles=false;Uri captured=cameraUri;cameraUri=null;if(fileCallback!=null){fileCallback.onReceiveValue(resultCode==RESULT_OK&&captured!=null?new Uri[]{captured}:null);fileCallback=null;}if(captured!=null)revokeUriPermission(captured,Intent.FLAG_GRANT_WRITE_URI_PERMISSION);return;}
        if(requestCode==74){
            choosingFiles=false;byte[] bytes=reportExport;reportExport=null;
            if(resultCode==RESULT_OK&&data!=null&&data.getData()!=null&&bytes!=null){
                try(java.io.OutputStream out=getContentResolver().openOutputStream(data.getData())){if(out==null)throw new java.io.IOException();out.write(bytes);android.widget.Toast.makeText(this,"تم حفظ التقرير",android.widget.Toast.LENGTH_LONG).show();}
                catch(Exception e){new AlertDialog.Builder(this).setMessage("تعذر حفظ التقرير في المكان المختار.").setPositiveButton("حسناً",null).show();}
            }return;
        }
        if(requestCode==73){choosingFiles=false;java.util.ArrayList<Uri> selected=new java.util.ArrayList<>();
            if(resultCode==RESULT_OK&&data!=null&&web!=null&&trustedPage(web.getUrl())){android.content.ClipData clip=data.getClipData();if(clip!=null){for(int i=0;i<Math.min(12,clip.getItemCount());i++){Uri uri=clip.getItemAt(i).getUri();if(validImageUri(uri))selected.add(uri);}}else if(validImageUri(data.getData()))selected.add(data.getData());}
            if(fileCallback!=null){fileCallback.onReceiveValue(selected.isEmpty()?null:selected.toArray(new Uri[0]));fileCallback=null;}if(web!=null)web.evaluateJavascript("if(window.HECMedia)HECMedia.cancel()",null);return;
        }if(requestCode!=72)return;scanning=false;
        if(web==null||errorVisible||!trustedPage(web.getUrl()))return;
        String code=resultCode==RESULT_OK&&data!=null?data.getStringExtra("barcode"):null;
        if(code!=null&&(code.length()>200||code.trim().isEmpty()))code=null;
        web.evaluateJavascript("if(window.HECScanner)HECScanner.receive("+(code==null?"null":JSONObject.quote(code))+")",null);
    }
    private boolean validImageUri(Uri uri){if(uri==null||!"content".equals(uri.getScheme()))return false;try{String type=getContentResolver().getType(uri);return "image/jpeg".equals(type)||"image/png".equals(type)||"video/mp4".equals(type)||"video/webm".equals(type);}catch(Exception e){return false;}}
    private void capturePhoto(){
        try{cameraUri=HECFileProvider.create(this,"HEC-camera.jpg",new byte[0]);Intent i=new Intent(android.provider.MediaStore.ACTION_IMAGE_CAPTURE).putExtra(android.provider.MediaStore.EXTRA_OUTPUT,cameraUri).addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION|Intent.FLAG_GRANT_WRITE_URI_PERMISSION);i.setClipData(android.content.ClipData.newRawUri("صورة الصنف",cameraUri));startActivityForResult(i,75);}catch(Exception e){choosingFiles=false;if(fileCallback!=null){fileCallback.onReceiveValue(null);fileCallback=null;}new AlertDialog.Builder(this).setMessage("تعذر فتح الكاميرا؛ يمكنك اختيار صورة من الهاتف").setPositiveButton("حسناً",null).show();}
    }
    @Override public void onRequestPermissionsResult(int code,String[] permissions,int[] grants){super.onRequestPermissionsResult(code,permissions,grants);if(code==80){if(grants.length>0&&grants[0]==android.content.pm.PackageManager.PERMISSION_GRANTED)capturePhoto();else{choosingFiles=false;if(fileCallback!=null){fileCallback.onReceiveValue(null);fileCallback=null;}}}}
    void deviceFiles(String id,String mode,java.util.ArrayList<Uri> files,String text,String name,String mime){
        if(!AppMode.ADMIN||deviceRequest!=null||!trustedPage(web.getUrl())){device.result(id,false,"انتظر انتهاء نافذة الحفظ أو المشاركة");return;}
        deviceRequest=id;choosingFiles=true;
        try{if(mode.equals("save")){deviceSaveUri=files.get(0);Intent i=new Intent(Intent.ACTION_CREATE_DOCUMENT).addCategory(Intent.CATEGORY_OPENABLE).setType(mime).putExtra(Intent.EXTRA_TITLE,name.replaceAll("[^\\p{L}\\p{N}._-]","_"));startActivityForResult(i,76);}
        else{Intent i=new Intent(files.size()==1?Intent.ACTION_SEND:Intent.ACTION_SEND_MULTIPLE).setType(files.size()==1?mime:"image/*").addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION);if(files.size()==1)i.putExtra(Intent.EXTRA_STREAM,files.get(0));else i.putParcelableArrayListExtra(Intent.EXTRA_STREAM,files);if(!text.isEmpty())i.putExtra(Intent.EXTRA_TEXT,text);android.content.ClipData clip=android.content.ClipData.newRawUri("تصميم الهيثم",files.get(0));for(int n=1;n<files.size();n++)clip.addItem(new android.content.ClipData.Item(files.get(n)));i.setClipData(clip);startActivityForResult(Intent.createChooser(i,"مشاركة التصميم عبر"),77);}}
        catch(Exception e){deviceRequest=null;deviceSaveUri=null;choosingFiles=false;device.result(id,false,"تعذر فتح تطبيق الحفظ أو المشاركة");}
    }
    private static boolean isShareCommand(Uri u) {
        return "https".equals(u.getScheme()) && HOST.equals(u.getHost()) && ("/native-share".equals(u.getEncodedPath()) || "/native-product-share".equals(u.getEncodedPath())) && u.getUserInfo() == null && u.getQuery() == null && u.getPort() == -1;
    }
    private static JSONObject cartPayload(String token) {
        if (token == null || token.length() > 65536 || !token.matches("[A-Za-z0-9_-]+")) return null;
        try {
            byte[] bytes = Base64.decode(token, Base64.URL_SAFE | Base64.NO_WRAP | Base64.NO_PADDING);
            JSONObject object = new JSONObject(new String(bytes, StandardCharsets.UTF_8));
            if (object.getInt("v") != 1) return null;
            JSONArray lines = object.getJSONArray("lines");
            if (lines.length() < 1 || lines.length() > 100) return null;
            java.util.HashSet<String> seen = new java.util.HashSet<>();
            for (int i = 0; i < lines.length(); i++) {
                JSONArray row = lines.getJSONArray(i);
                if (row.length() != 6) return null;
                String id = row.getString(0), variant = row.getString(1), name = row.getString(3), label = row.getString(4);
                double qty = row.getDouble(2), price = row.getDouble(5);
                if (!id.matches("[A-Za-z0-9_-]{1,80}") || !variant.matches("[A-Za-z0-9_-]{0,80}") || !seen.add(id + "~" + variant) || qty < 1 || qty > 999 || qty != Math.floor(qty) || !Double.isFinite(price) || price < 0 || price > 1000000000 || name.length() < 1 || name.length() > 180 || label.length() > 100) return null;
            }
            return object;
        } catch (Exception e) { return null; }
    }
    private static String incomingCart(Intent intent) {
        if (intent == null) return null;
        String token = null;
        try {
            if (Intent.ACTION_VIEW.equals(intent.getAction())) {
                Uri u = intent.getData();
                if (u == null || u.getUserInfo() != null || u.getQuery() != null || u.toString().length() > 66000) return null;
                if ("hec".equals(u.getScheme()) && "cart".equals(u.getHost()) && u.getPort() == -1 && u.getFragment() == null) token = u.getPath().substring(1);
                else if ("https".equals(u.getScheme()) && SHARE_HOST.equals(u.getHost()) && "/".equals(u.getPath()) && (u.getPort() == -1 || u.getPort() == 443) && u.getFragment() != null && u.getFragment().startsWith("cart=")) token = u.getFragment().substring(5);
            } else if (Intent.ACTION_SEND.equals(intent.getAction()) && "text/plain".equals(intent.getType())) {
                CharSequence extra = intent.getCharSequenceExtra(Intent.EXTRA_TEXT);
                if (extra == null || extra.length() > 100000) return null;
                Matcher m = Pattern.compile("(?:https://" + Pattern.quote(SHARE_HOST) + "/#cart=|hec://cart/)([A-Za-z0-9_-]{1,65536})(?![A-Za-z0-9_-])").matcher(extra.toString());
                if (m.find()) token = m.group(1);
            }
        } catch (Exception ignored) { return null; }
        return cartPayload(token) == null ? null : token;
    }
    private static String cartUrl(String token) { return "https://" + HOST + "/index.html#shared/" + token; }
    @Override protected void onNewIntent(Intent intent) {
        super.onNewIntent(intent); setIntent(intent);
        String reel=incomingReel(intent);if(reel!=null&&web!=null&&!errorVisible){web.loadUrl(reelUrl(reel));return;}
        String token = incomingCart(intent);
        if (token != null && web != null && !errorVisible) web.loadUrl(cartUrl(token));
    }
    private void shareCart(String token, boolean productShare) {
        JSONObject value = cartPayload(token);
        if (value == null || productShare && value.optJSONArray("lines").length() != 1) { new AlertDialog.Builder(this).setMessage("تعذر المشاركة؛ تحقق من محتويات الصنف أو السلة.").setPositiveButton("حسناً", null).show(); return; }
        try {
            JSONArray lines = value.getJSONArray("lines");
            StringBuilder message = new StringBuilder(productShare ? "صنف من الهيثم\n" : "سلة التسوق — الهيثم\n");
            double total = 0;
            java.text.NumberFormat number = java.text.NumberFormat.getNumberInstance(java.util.Locale.US);
            number.setMaximumFractionDigits(2);
            for (int i = 0; i < lines.length(); i++) {
                JSONArray row = lines.getJSONArray(i);
                int qty = row.getInt(2); double amount = qty * row.getDouble(5); total += amount;
                message.append(i + 1).append(". ").append(row.getString(3));
                if (productShare) message.append("\nكود الصنف: ").append(row.getString(0));
                if (!row.getString(4).isEmpty()) message.append(" (").append(row.getString(4)).append(")");
                message.append(" × ").append(qty).append(" — ").append(number.format(amount)).append(" ر.ي\n");
            }
            message.append(productShare ? "السعر وقت المشاركة: " : "الإجمالي وقت المشاركة: ").append(number.format(total)).append(productShare ? " ر.ي\nعرض الصنف ومراجعته في الهيثم:\nhttps://" : " ر.ي\nعرض السلة وإضافتها إلى تطبيق الهيثم:\nhttps://").append(SHARE_HOST).append("/#cart=").append(token);
            Intent send = new Intent(Intent.ACTION_SEND).setType("text/plain");
            send.putExtra(Intent.EXTRA_TEXT, message.toString()); send.putExtra(Intent.EXTRA_TITLE, productShare ? "صنف من الهيثم" : "سلة الهيثم المشتركة");
            startActivity(Intent.createChooser(send, productShare ? "مشاركة الصنف عبر" : "مشاركة السلة عبر"));
        } catch (Exception e) { new AlertDialog.Builder(this).setMessage("لا يوجد تطبيق متاح للمشاركة").setPositiveButton("حسناً", null).show(); }
    }

    private static boolean allowed(Uri u) {
        if (!"https".equals(u.getScheme()) || !HOST.equals(u.getHost()) || u.getUserInfo() != null || u.getQuery() != null || (u.getPort() != -1 && u.getPort() != 443)) return false;
        String p = u.getEncodedPath();
        if(p!=null&&p.matches("/(?:reels/[A-Za-z0-9_-]+\\.(?:js|css|json|mp4|webm)|v1/images/erp-[a-f0-9]{24}\\.jpg|native-tools\\.js)"))return true;
        if(AppMode.ADMIN&&p!=null&&p.matches("/(?:studio(?:-source|-engine)?\\.js|studio\\.css|item-media\\.js)"))return true;
        if(AppMode.ADMIN && p != null && p.matches("/(reels-admin\\.js|reels-schema\\.js|delivery-admin\\.js|reports\\.js|integration-panel\\.js|admin-console\\.js|admin-help\\.js|admin-guide-data\\.js|reports\\.css|admin-help\\.css|admin-guide-images/[A-Za-z0-9_-]+\\.png)"))return true;
        return p != null && (p.equals("/") || p.matches("/(reels\\.js|reels\\.css|reels-stream/[A-Za-z0-9_-]{1,80}|build-mode\\.js|erp-client\\.js|erp-admin\\.js|erp\\.css|storefront-config\\.js|default-config\\.js|customer-shell\\.js|index\\.html|engagement\\.js|engagement-editor\\.js|automation\\.js|engagement\\.css|fulfillment\\.js|notifications\\.js|operations\\.css|marketing\\.js|marketing-editor\\.js|slides-editor\\.js|marketing\\.css|media\\.js|scanner\\.js|theme\\.js|item-source\\.js|bundle-order\\.js|management-picker\\.js|refinements\\.css|data\\.js|cart-codec\\.js|offer-engine\\.js|enhancements-data\\.js|commerce\\.js|management-config\\.js|management-preview\\.js|enhancements\\.css|management-api\\.js|management\\.js|management\\.css|experience-data\\.js|experience\\.js|experience\\.css|storage\\.js|courier-live\\.js|courier\\.js|app\\.js|styles\\.css|assets/[A-Za-z0-9_-]+\\.jpg)"));
    }
    private static boolean externalAllowed(Uri u) {
        if (!"https".equals(u.getScheme()) || u.getUserInfo() != null || (u.getPort() != -1 && u.getPort() != 443) || u.toString().length() > 16000) return false;
        String h = u.getHost(), p = u.getPath();
        if ("hec-service-review.fadhel-motaher.chatgpt.site".equals(h)) {
            return u.getQuery() == null && ("/customer/index.html".equals(p)||"/admin/index.html".equals(p));
        }
        return p != null && p.length() > 1 && ("vimeo.com".equals(h) || "www.vimeo.com".equals(h) || "www.youtube.com".equals(h) || "youtube.com".equals(h) || "youtu.be".equals(h) || "www.facebook.com".equals(h) || "facebook.com".equals(h) || "www.instagram.com".equals(h) || "instagram.com".equals(h) || "wa.me".equals(h) || "play.google.com".equals(h));
    }
    private static WebResourceResponse denied() { return new WebResourceResponse("text/plain", "UTF-8", 403, "Forbidden", new HashMap<>(), new ByteArrayInputStream(new byte[0])); }
    private void showRecovery() {
        runOnUiThread(() -> {
            if (isFinishing() || errorVisible) return;
            errorVisible = true;
            LinearLayout panel = new LinearLayout(this);
            panel.setOrientation(LinearLayout.VERTICAL);
            panel.setGravity(android.view.Gravity.CENTER);
            panel.setPadding(32, 32, 32, 32);
            panel.setBackgroundColor(Color.WHITE);
            TextView message = new TextView(this);
            message.setText("تعذر عرض التطبيق\nيمكنك إعادة المحاولة دون مسح بياناتك المحفوظة.");
            message.setTextSize(18);
            message.setGravity(android.view.Gravity.CENTER);
            panel.addView(message);
            Button retry = new Button(this);
            retry.setText("إعادة فتح التطبيق");
            retry.setOnClickListener(v -> openApp(null));
            panel.addView(retry);
            root.removeAllViews();
            root.addView(panel, new FrameLayout.LayoutParams(-1, -1));
        });
    }
    @Override protected void onPause() {
        getWindow().addFlags(WindowManager.LayoutParams.FLAG_SECURE);
        if (web != null && !errorVisible) {
            web.evaluateJavascript("document.querySelectorAll('input[type=password],input[autocomplete=current-password],input[autocomplete=new-password]').forEach(function(e){e.value=''});" + ((scanning||choosingFiles) ? "" : "if(window.Management)Management.revoke();") , null);
            web.onPause();
        }
        super.onPause();
    }
    @Override protected void onResume() {
        super.onResume();
        getWindow().clearFlags(WindowManager.LayoutParams.FLAG_SECURE);
        if (web != null && !errorVisible) web.onResume();
    }
    @Override protected void onSaveInstanceState(Bundle out) { if (web != null && !errorVisible) web.saveState(out); super.onSaveInstanceState(out); }
    @Override public void onBackPressed() {
        if (web == null || errorVisible) { finish(); return; }
        web.evaluateJavascript("(function(){var sheet=document.querySelector('.reel-sheet [data-social-close]');if(sheet){sheet.click();return 'closed'}var d=Array.from(document.querySelectorAll('dialog[open]')).pop();if(d){var e=new Event('cancel',{cancelable:true});if(d.dispatchEvent(e))d.close();return 'closed'}return location.hash})()", value -> {
            if ("\"closed\"".equals(value) || web == null) return;
            if ("\"#home\"".equals(value) || "\"\"".equals(value)) {
                new AlertDialog.Builder(MainActivity.this).setMessage("هل ترغب في إغلاق التطبيق؟")
                    .setPositiveButton("نعم", (dialog, which) -> finish()).setNegativeButton("لا", null).show();
            } else if (web.canGoBack()) web.goBack(); else web.loadUrl(START);
        });
    }
    @Override protected void onDestroy() { if(device!=null)device.close();if(erp!=null)erp.close(); if(fileCallback!=null){fileCallback.onReceiveValue(null);fileCallback=null;} if (web != null) { web.stopLoading(); web.destroy(); web = null; } super.onDestroy(); }
}
