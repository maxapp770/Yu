package com.alhaitham.hec;
import android.content.*;
import android.database.Cursor;
import android.database.MatrixCursor;
import android.net.Uri;
import android.os.ParcelFileDescriptor;
import android.provider.OpenableColumns;
import java.io.*;
import java.util.*;

/** Only generated temporary image files can be shared, through explicit URI grants. */
public final class HECFileProvider extends ContentProvider {
 public boolean onCreate(){return true;}
 static Uri create(Context c,String name,byte[] bytes)throws IOException {
  File dir=new File(c.getCacheDir(),"hec-media");dir.mkdirs();
  File[] old=dir.listFiles();if(old!=null)for(File f:old)if(System.currentTimeMillis()-f.lastModified()>86400000L)f.delete();
  String safe=name.replaceAll("[^\\p{L}\\p{N}._-]","_");if(safe.length()>90)safe=safe.substring(safe.length()-90);
  if(!safe.matches(".+\\.(jpg|jpeg|png)"))safe="HEC-image.jpg";
  File file=new File(dir,UUID.randomUUID().toString()+"_"+safe);
  try(FileOutputStream out=new FileOutputStream(file)){out.write(bytes);}
  return new Uri.Builder().scheme("content").authority(c.getPackageName()+".media").appendPath(file.getName()).build();
 }
 private File file(Uri u)throws FileNotFoundException {
  if(!getContext().getPackageName().concat(".media").equals(u.getAuthority())||u.getQuery()!=null||u.getFragment()!=null||u.getPathSegments().size()!=1)throw new FileNotFoundException();
  String n=u.getLastPathSegment();if(n==null||!n.matches("[a-f0-9-]{36}_[\\p{L}\\p{N}._-]{1,90}\\.(jpg|jpeg|png)")||n.contains(".."))throw new FileNotFoundException();
  File f=new File(new File(getContext().getCacheDir(),"hec-media"),n);if(!f.isFile())throw new FileNotFoundException();return f;
 }
 public String getType(Uri u){try{return file(u).getName().endsWith(".png")?"image/png":"image/jpeg";}catch(Exception e){return null;}}
 public ParcelFileDescriptor openFile(Uri u,String mode)throws FileNotFoundException{
  File f=file(u);if(!mode.equals("r")&&!mode.equals("w")&&!mode.equals("rw")&&!mode.equals("wt"))throw new FileNotFoundException();
  return ParcelFileDescriptor.open(f,mode.equals("r")?ParcelFileDescriptor.MODE_READ_ONLY:ParcelFileDescriptor.MODE_READ_WRITE|ParcelFileDescriptor.MODE_TRUNCATE);
 }
 public Cursor query(Uri u,String[] projection,String selection,String[] args,String order){try{File f=file(u);String[] cols=projection==null?new String[]{OpenableColumns.DISPLAY_NAME,OpenableColumns.SIZE}:projection;MatrixCursor cur=new MatrixCursor(cols);Object[] row=new Object[cols.length];for(int i=0;i<cols.length;i++)row[i]=OpenableColumns.DISPLAY_NAME.equals(cols[i])?f.getName().substring(37):OpenableColumns.SIZE.equals(cols[i])?f.length():null;cur.addRow(row);return cur;}catch(Exception e){return null;}}
 public Uri insert(Uri u,ContentValues v){throw new UnsupportedOperationException();}public int update(Uri u,ContentValues v,String w,String[] a){throw new UnsupportedOperationException();}public int delete(Uri u,String w,String[] a){throw new UnsupportedOperationException();}
}
