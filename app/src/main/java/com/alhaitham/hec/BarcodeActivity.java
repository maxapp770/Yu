package com.alhaitham.hec;

import android.Manifest;
import android.app.Activity;
import android.app.AlertDialog;
import android.content.Intent;
import android.content.pm.PackageManager;
import android.graphics.Color;
import android.graphics.ImageFormat;
import android.graphics.Matrix;
import android.graphics.RectF;
import android.graphics.SurfaceTexture;
import android.hardware.camera2.*;
import android.hardware.camera2.params.StreamConfigurationMap;
import android.media.Image;
import android.media.ImageReader;
import android.os.Bundle;
import android.os.Handler;
import android.os.HandlerThread;
import android.util.Size;
import android.view.Gravity;
import android.view.Surface;
import android.view.TextureView;
import android.view.View;
import android.view.WindowManager;
import android.widget.*;
import java.nio.ByteBuffer;
import java.util.Arrays;

/** In-app Camera2 scanner; frames stay in memory and no network/storage permission is used. */
public final class BarcodeActivity extends Activity {
    private TextureView preview; private TextView status; private Button flash;
    private CameraDevice camera; private CameraCaptureSession session; private CaptureRequest.Builder request;
    private ImageReader images; private HandlerThread thread; private Handler worker;
    private int cameraGeneration; private boolean active, opening, torch, hasFlash, delivered; private int sensorOrientation=90;
    private Size size=new Size(640,480); private long lastFrame; private final BarcodeDecoder decoder=new BarcodeDecoder();
    @Override public void onCreate(Bundle state) {
        super.onCreate(state);
        getWindow().setFlags(WindowManager.LayoutParams.FLAG_SECURE,WindowManager.LayoutParams.FLAG_SECURE);
        getWindow().addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON);
        LinearLayout root=new LinearLayout(this);root.setOrientation(LinearLayout.VERTICAL);root.setBackgroundColor(Color.rgb(22,18,23));root.setPadding(16,20,16,20);root.setLayoutDirection(View.LAYOUT_DIRECTION_RTL);
        TextView title=new TextView(this);title.setText("قراءة باركود الصنف");title.setTextSize(22);title.setTextColor(Color.rgb(244,215,147));title.setGravity(Gravity.CENTER);root.addView(title,new LinearLayout.LayoutParams(-1,60));
        status=new TextView(this);status.setText("وجّه الكاميرا نحو الباركود أو QR الخاص بالصنف. لا تُحفظ الصور.");status.setTextColor(Color.WHITE);status.setTextSize(15);status.setGravity(Gravity.CENTER);root.addView(status,new LinearLayout.LayoutParams(-1,90));
        preview=new TextureView(this);root.addView(preview,new LinearLayout.LayoutParams(-1,0,1));
        LinearLayout buttons=new LinearLayout(this);buttons.setGravity(Gravity.CENTER);
        flash=button("الإضاءة",()->{torch=!torch;repeat();flash.setText(torch?"إطفاء الإضاءة":"الإضاءة");});flash.setEnabled(false);buttons.addView(flash,new LinearLayout.LayoutParams(0,56,1));
        buttons.addView(button("إدخال الرمز",this::manual),new LinearLayout.LayoutParams(0,56,1));buttons.addView(button("إلغاء",()->finish()),new LinearLayout.LayoutParams(0,56,1));root.addView(buttons);setContentView(root);
        preview.setSurfaceTextureListener(new TextureView.SurfaceTextureListener(){public void onSurfaceTextureAvailable(SurfaceTexture t,int w,int h){open();}public void onSurfaceTextureSizeChanged(SurfaceTexture t,int w,int h){transform();}public boolean onSurfaceTextureDestroyed(SurfaceTexture t){closeCamera();return true;}public void onSurfaceTextureUpdated(SurfaceTexture t){}});
        if(checkSelfPermission(Manifest.permission.CAMERA)!=PackageManager.PERMISSION_GRANTED)requestPermissions(new String[]{Manifest.permission.CAMERA},71);
    }
    private Button button(String label,Runnable action){Button b=new Button(this);b.setText(label);b.setTextColor(Color.rgb(244,215,147));b.setBackgroundTintList(android.content.res.ColorStateList.valueOf(Color.rgb(78,28,47)));b.setOnClickListener(v->action.run());return b;}
    private void manual(){EditText input=new EditText(this);input.setSingleLine(true);input.setHint("رمز الصنف أو الباركود");input.setFilters(new android.text.InputFilter[]{new android.text.InputFilter.LengthFilter(200)});input.setLayoutDirection(View.LAYOUT_DIRECTION_LTR);new AlertDialog.Builder(this).setTitle("إدخال الباركود").setView(input).setPositiveButton("بحث",(d,w)->finishCode(input.getText().toString())).setNegativeButton("إلغاء",null).show();}
    private void message(String text){runOnUiThread(()->{if(!isFinishing())status.setText(text);});}
    @Override protected void onResume(){super.onResume();active=true;thread=new HandlerThread("HEC-barcode");thread.start();worker=new Handler(thread.getLooper());if(preview.isAvailable())open();}
    @Override public void onRequestPermissionsResult(int code,String[] permissions,int[] grants){super.onRequestPermissionsResult(code,permissions,grants);if(code==71){if(grants.length>0&&grants[0]==PackageManager.PERMISSION_GRANTED)open();else message("لم تسمح بالكاميرا. اضغط «إدخال الرمز» للبحث يدوياً، أو فعّل الإذن من إعدادات التطبيق.");}}
    private void open(){
        if(!active||opening||camera!=null||worker==null||!preview.isAvailable()||checkSelfPermission(Manifest.permission.CAMERA)!=PackageManager.PERMISSION_GRANTED)return;
        try{CameraManager manager=(CameraManager)getSystemService(CAMERA_SERVICE);String selected=null;CameraCharacteristics chars=null;
            for(String id:manager.getCameraIdList()){CameraCharacteristics c=manager.getCameraCharacteristics(id);Integer facing=c.get(CameraCharacteristics.LENS_FACING);if(selected==null||facing!=null&&facing==CameraCharacteristics.LENS_FACING_BACK){selected=id;chars=c;if(facing!=null&&facing==CameraCharacteristics.LENS_FACING_BACK)break;}}
            if(selected==null||chars==null){message("لا توجد كاميرا متاحة؛ أدخل الرمز يدوياً.");return;}
            StreamConfigurationMap map=chars.get(CameraCharacteristics.SCALER_STREAM_CONFIGURATION_MAP);if(map==null)throw new IllegalStateException();Size[] supported=map.getOutputSizes(ImageFormat.YUV_420_888);if(supported==null||supported.length==0)throw new IllegalStateException();size=supported[0];for(Size x:supported)if(Math.abs((long)x.getWidth()*x.getHeight()-640L*480)<Math.abs((long)size.getWidth()*size.getHeight()-640L*480))size=x;
            hasFlash=Boolean.TRUE.equals(chars.get(CameraCharacteristics.FLASH_INFO_AVAILABLE));Integer sensor=chars.get(CameraCharacteristics.SENSOR_ORIENTATION);sensorOrientation=sensor==null?90:sensor;
            images=ImageReader.newInstance(size.getWidth(),size.getHeight(),ImageFormat.YUV_420_888,2);images.setOnImageAvailableListener(reader->{Image image=null;try{image=reader.acquireLatestImage();if(image==null||!active||delivered||android.os.SystemClock.elapsedRealtime()-lastFrame<200)return;lastFrame=android.os.SystemClock.elapsedRealtime();Image.Plane plane=image.getPlanes()[0];ByteBuffer buffer=plane.getBuffer();int w=image.getWidth(),h=image.getHeight(),stride=plane.getRowStride(),step=plane.getPixelStride();byte[] bytes=new byte[w*h];for(int y=0;y<h;y++)for(int x=0;x<w;x++)bytes[y*w+x]=buffer.get(y*stride+x*step);String code=decoder.decode(bytes,w,h);if(code!=null)runOnUiThread(()->finishCode(code));}catch(RuntimeException ignored){}finally{if(image!=null)image.close();}},worker);
            final int generation=++cameraGeneration;opening=true;manager.openCamera(selected,new CameraDevice.StateCallback(){public void onOpened(CameraDevice c){if(generation!=cameraGeneration||!active){c.close();return;}opening=false;camera=c;startPreview();}public void onDisconnected(CameraDevice c){c.close();camera=null;opening=false;message("انقطع اتصال الكاميرا. أعد فتح القارئ أو أدخل الرمز.");}public void onError(CameraDevice c,int error){c.close();camera=null;opening=false;message("تعذر فتح الكاميرا. أغلق أي تطبيق يستخدمها ثم أعد المحاولة.");}},worker);
        }catch(Exception e){opening=false;closeCamera();message("تعذر تشغيل الكاميرا. يمكنك إدخال الرمز يدوياً.");}
    }
    private void startPreview(){try{SurfaceTexture texture=preview.getSurfaceTexture();if(texture==null||images==null||camera==null)return;texture.setDefaultBufferSize(size.getWidth(),size.getHeight());Surface surface=new Surface(texture);request=camera.createCaptureRequest(CameraDevice.TEMPLATE_PREVIEW);request.addTarget(surface);request.addTarget(images.getSurface());request.set(CaptureRequest.CONTROL_AF_MODE,CaptureRequest.CONTROL_AF_MODE_CONTINUOUS_PICTURE);request.set(CaptureRequest.CONTROL_AE_MODE,CaptureRequest.CONTROL_AE_MODE_ON);camera.createCaptureSession(Arrays.asList(surface,images.getSurface()),new CameraCaptureSession.StateCallback(){public void onConfigured(CameraCaptureSession s){if(!active||camera==null){s.close();return;}session=s;repeat();runOnUiThread(()->{transform();flash.setEnabled(hasFlash);});}public void onConfigureFailed(CameraCaptureSession s){message("لم تتم تهيئة الكاميرا؛ يمكنك إدخال الرمز يدوياً.");}},worker);}catch(Exception e){message("تعذر بدء المعاينة؛ يمكنك إدخال الرمز يدوياً.");}}
    private void repeat(){if(session==null||request==null)return;try{request.set(CaptureRequest.FLASH_MODE,torch&&hasFlash?CaptureRequest.FLASH_MODE_TORCH:CaptureRequest.FLASH_MODE_OFF);session.setRepeatingRequest(request.build(),null,worker);}catch(Exception e){message("تعذر تحديث الكاميرا.");}}
    private void transform(){if(preview.getWidth()==0)return;int rotation=getWindowManager().getDefaultDisplay().getRotation()*90,angle=(sensorOrientation-rotation+360)%360;float w=preview.getWidth(),h=preview.getHeight();RectF view=new RectF(0,0,w,h);boolean swap=angle==90||angle==270;RectF buffer=new RectF(0,0,swap?size.getHeight():size.getWidth(),swap?size.getWidth():size.getHeight());buffer.offset(view.centerX()-buffer.centerX(),view.centerY()-buffer.centerY());Matrix matrix=new Matrix();matrix.setRectToRect(view,buffer,Matrix.ScaleToFit.FILL);float scale=Math.max(w/buffer.width(),h/buffer.height());matrix.postScale(scale,scale,view.centerX(),view.centerY());matrix.postRotate(-angle,view.centerX(),view.centerY());preview.setTransform(matrix);}
    private void finishCode(String code){if(delivered||code==null)return;code=code.trim();if(code.length()<1||code.length()>200||code.matches(".*[\\x00-\\x1f].*")){message("أدخل رمزاً صالحاً.");return;}delivered=true;setResult(RESULT_OK,new Intent().putExtra("barcode",code));finish();}
    private void closeCamera(){cameraGeneration++;if(session!=null){session.close();session=null;}if(camera!=null){camera.close();camera=null;}if(images!=null){images.close();images=null;}opening=false;torch=false;}
    @Override protected void onPause(){active=false;closeCamera();if(thread!=null){thread.quitSafely();thread=null;worker=null;}super.onPause();}
}
