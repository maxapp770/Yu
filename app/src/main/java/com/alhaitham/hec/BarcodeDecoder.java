package com.alhaitham.hec;

import com.google.zxing.*;
import com.google.zxing.common.HybridBinarizer;
import java.util.Arrays;
import java.util.EnumMap;
import java.util.Map;

/** Pure luminance decoder, shared with the deterministic camera-frame tests. */
public final class BarcodeDecoder {
    private final MultiFormatReader reader = new MultiFormatReader();
    public BarcodeDecoder() {
        Map<DecodeHintType,Object> hints = new EnumMap<>(DecodeHintType.class);
        hints.put(DecodeHintType.TRY_HARDER, Boolean.TRUE);
        hints.put(DecodeHintType.POSSIBLE_FORMATS, Arrays.asList(BarcodeFormat.EAN_13, BarcodeFormat.EAN_8, BarcodeFormat.UPC_A, BarcodeFormat.UPC_E, BarcodeFormat.UPC_EAN_EXTENSION, BarcodeFormat.CODE_128, BarcodeFormat.CODE_39, BarcodeFormat.CODE_93, BarcodeFormat.CODABAR, BarcodeFormat.ITF, BarcodeFormat.RSS_14, BarcodeFormat.RSS_EXPANDED, BarcodeFormat.QR_CODE, BarcodeFormat.DATA_MATRIX, BarcodeFormat.AZTEC, BarcodeFormat.PDF_417, BarcodeFormat.MAXICODE));
        reader.setHints(hints);
    }
    public String decode(byte[] pixels, int width, int height) {
        if (pixels == null || width < 1 || height < 1 || pixels.length != width * height) return null;
        try {
            LuminanceSource source=new Gray(pixels,width,height);
            for(int turn=0;turn<4;turn++) {
                try { String value=reader.decodeWithState(new BinaryBitmap(new HybridBinarizer(source))).getText();
                    if(value!=null&&value.trim().length()>0&&value.trim().length()<=200&&!value.trim().matches(".*[\\x00-\\x1f].*"))return value.trim();
                } catch (ReaderException ignored) { }
                source=source.rotateCounterClockwise();
            }
            return null;
        } catch (ReaderException | IllegalArgumentException ignored) { return null; }
        finally { reader.reset(); }
    }
    private static final class Gray extends LuminanceSource {
        private final byte[] data;
        Gray(byte[] bytes,int width,int height) { super(width,height);data=bytes; }
        @Override public byte[] getRow(int y,byte[] row) { if(row==null||row.length<getWidth())row=new byte[getWidth()];System.arraycopy(data,y*getWidth(),row,0,getWidth());return row; }
        @Override public byte[] getMatrix() { return data; }
        @Override public boolean isRotateSupported() { return true; }
        @Override public LuminanceSource rotateCounterClockwise() { int w=getWidth(),h=getHeight();byte[] out=new byte[data.length];for(int y=0;y<h;y++)for(int x=0;x<w;x++)out[(w-x-1)*h+y]=data[y*w+x];return new Gray(out,h,w); }
    }
}
