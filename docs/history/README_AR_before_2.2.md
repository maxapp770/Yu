# تطبيقات الهيثم 2.1

تطبيق Android للعميل وتطبيق مستقل للإدارة، مع خدمة Frappe للنشر وحسابات العملاء والطلبات.

ابدأ بالدليل المصور: docs/HEC-Live-Setup-Guide-2.1-AR.html
حالة التنفيذ والاختبارات والقيود: docs/RELEASE_2.1_AR.md

## البناء

يتطلب JDK 17 وAndroid SDK Platform 35 وBuild Tools 35.0.0.
استخدم HEC_APP_ROLE=customer أو admin مع build-apk.sh.
حدد HEC_SERVICE_ORIGIN بعنوان HTTPS الثابت لخدمة العملاء قبل النشر. القيمة الافتراضية الحالية خادم الاختبار المرفق.
حدد HEC_DEBUG_KEYSTORE خارج المشروع لاستمرار توقيع نسخ المراجعة. لا تضع مفاتيح ERPNext في الكود أو متغيرات البناء.

Gradle يدعم -PhecRole=customer أو admin. تم التحقق من مسار بناء SDK المرفق؛ لم تُشغّل مهمة Gradle في هذا الإصدار.

## الاختبار

python3 tests/bridge20_test.py
python3 tests/release21_test.py
node tests/release21-browser.cjs

اختبار المتصفح يتطلب Playwright وHEC_CHROME_BIN. جهز build/variants للدورين أولاً بواسطة tools/prepare_variant.py.

## الدخول

الإدارة المتصلة: حساب Frappe يملك System Manager، بكلمة مروره أو مفاتيحه الشخصية.
المراجعة المحلية داخل تطبيق الإدارة فقط: admin / 123456. لا تمنح وصولاً إلى النظام.
العميل: حسابه الشخصي الذي تنشئه أو تربطه الإدارة إلى Customer وCompany؛ لا مفاتيح تكامل مشتركة.

## نتائج الاتصال الحي

نجحت قراءة REST بالمفاتيح المرفقة: شركتان، قائمتا أسعار، ستة مخازن. الإضافة غير مثبتة حالياً (HTTP 417). اكتمال الرحلة التجارية يتطلب تركيب الإضافة واختبارها؛ راجع تقرير الإصدار قبل اعتماد تشغيل المتجر.
