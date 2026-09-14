#!/usr/bin/env bash
# Reproducible SDK-only build. Uses the same manifest, Java, resources and assets as Gradle.
set -euo pipefail
cd "$(dirname "$0")"
SDK="${ANDROID_SDK_ROOT:-${ANDROID_HOME:-}}"
if [[ -z "$SDK" ]]; then echo 'Set ANDROID_SDK_ROOT to an SDK with platform 35 and build-tools 35.0.0.' >&2; exit 1; fi
BT="$SDK/build-tools/35.0.0"
PLATFORM="$SDK/platforms/android-35/android.jar"
MODE="${HEC_APP_ROLE:-customer}"
if [[ "$MODE" != customer && "$MODE" != admin ]]; then echo 'HEC_APP_ROLE must be customer or admin' >&2; exit 1; fi
python3 tools/prepare_variant.py "$MODE"
PKG=com.alhaitham.hec.preview
if [[ "$MODE" == admin ]]; then PKG=com.alhaitham.hec.admin; fi
rm -rf build/classes build/dex build/res
mkdir -p build/classes build/dex build/res
cp "build/variants/$MODE/AndroidManifest.xml" build/AndroidManifest.xml
"$BT/aapt2" compile --dir app/src/main/res -o build/res.zip
"$BT/aapt2" link -o build/base.apk -I "$PLATFORM" --manifest build/AndroidManifest.xml build/res.zip -A "build/variants/$MODE/assets" --java build/res --min-sdk-version 29 --target-sdk-version 35
javac -encoding UTF-8 -source 8 -target 8 -bootclasspath "$PLATFORM:$BT/core-lambda-stubs.jar" -cp app/libs/zxing-core-3.5.3.jar -d build/classes app/src/main/java/com/alhaitham/hec/BarcodeActivity.java app/src/main/java/com/alhaitham/hec/BarcodeDecoder.java app/src/main/java/com/alhaitham/hec/ERPBridge.java app/src/main/java/com/alhaitham/hec/HECDevice.java app/src/main/java/com/alhaitham/hec/HECFileProvider.java app/src/main/java/com/alhaitham/hec/MainActivity.java "build/variants/$MODE/AppMode.java"
jar cf build/classes.jar -C build/classes .
"$BT/d8" --lib "$PLATFORM" --min-api 29 --output build/dex build/classes.jar app/libs/zxing-core-3.5.3.jar
cp build/base.apk build/unsigned.apk
(cd build/dex && zip -q -u ../unsigned.apk classes.dex)
"$BT/zipalign" -f -p 4 build/unsigned.apk build/aligned.apk
# Test signing key stays outside the deliverable repository.
KEY="${HEC_DEBUG_KEYSTORE:-$HOME/.android/hec-preview-debug.keystore}"
mkdir -p "$(dirname "$KEY")"
if [[ ! -f "$KEY" ]]; then keytool -genkeypair -keystore "$KEY" -storepass android -keypass android -alias androiddebugkey -dname 'CN=Android Debug,O=Android,C=US' -keyalg RSA -keysize 2048 -validity 10000; fi
"$BT/apksigner" sign --ks "$KEY" --ks-pass pass:android --ks-key-alias androiddebugkey --out build/HEC-phase1-debug.apk build/aligned.apk
cp build/HEC-phase1-debug.apk "build/HEC-$MODE-2.6.0.apk"
"$BT/apksigner" verify --verbose "build/HEC-$MODE-2.6.0.apk"
printf 'Built: %s/build/HEC-phase1-debug.apk\n' "$PWD"
