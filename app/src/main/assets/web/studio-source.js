'use strict';
/* Adapted from the user's Share Architect V23.1. Frappe registration, file deletion, price writes and automatic sharing are not executed. */
window.HECStudioSource=(()=>{
const HEC_PROMO_MEMORY_KEY='hec.studio.phrases.v1';
const normalizeUrl=(u,b)=>new URL(u,b).href;
function _getPromoMemory() { try { return JSON.parse(localStorage.getItem(HEC_PROMO_MEMORY_KEY) || '{}'); } catch(e) { return {}; } }
function _savePromoMemory(mem) { try { localStorage.setItem(HEC_PROMO_MEMORY_KEY, JSON.stringify(mem)); } catch(e) {} }
function _recordUsed(itemKey, phraseId) { const mem = _getPromoMemory(); if (!mem[itemKey]) mem[itemKey] = []; mem[itemKey] = [phraseId, ...mem[itemKey].filter(x => x !== phraseId)].slice(0, 40); _savePromoMemory(mem); }
function _wasRecentlyUsed(itemKey, phraseId) { const mem = _getPromoMemory(); return (mem[itemKey] || []).slice(0, 30).includes(phraseId); }
function _pickFresh(itemKey, pool) { const fresh = pool.filter(p => !_wasRecentlyUsed(itemKey, p.id)); const chosen = fresh.length > 0 ? fresh[Math.floor(Math.random() * fresh.length)] : pool[Math.floor(Math.random() * pool.length)]; _recordUsed(itemKey, chosen.id); return chosen.text; }

function _detectOccasion() {
    const now = new Date(); const month = now.getMonth() + 1; const day = now.getDate(); const weekday = now.getDay(); const h = now.getHours();
    if (month === 1 && day <= 5) return 'new_year';
    if (month === 9 && day === 26) return 'sep26';
    if (month === 10 && day === 14) return 'oct14';
    if (month === 5 && day === 22) return 'may22';
    if (month === 11 && day >= 25) return 'year_end';
    if (month === 12 && day >= 20) return 'year_end';
    if (month === 3 && day === 21) return 'spring';
    if (weekday === 5) return 'friday';
    if (h >= 5 && h < 12) return 'morning';
    if (h >= 12 && h < 14) return 'noon';
    if (h >= 14 && h < 17) return 'afternoon';
    if (h >= 17 && h < 20) return 'evening';
    return 'night';
}

const HEC_PHRASE_BANKS = {
    morning: [
        { id: 'mor01', text: 'صباح الخير والبركة ☀️\nيوم جديد يحمل لك فرصاً استثنائية — ابدأه بأفضل الاختيارات.' },
        { id: 'mor02', text: 'صباح التجدد والعطاء 🌅\nمن طلوع الشمس تبدأ الفرص الذهبية — واخترنا لك الأفضل.' },
        { id: 'mor03', text: 'صباحك أجمل 🌼\nهذا الصنف ينتظرك منذ الفجر — لأنك تستحق الأرقى.' },
        { id: 'mor04', text: '🌤️ بصمة الصباح الأولى تحدد جودة يومك\nوهذا الصنف يليق بأفضل بداياتك.' },
        { id: 'mor05', text: 'مع أول خطوة في يومك ✨\nننتقي لك ما يجعل كل لحظة ذات قيمة.' },
        { id: 'mor06', text: '☀️ الصباح فرصة والرزق ببركة الله\nعرضنا لك اليوم ما يستحق اهتمامك.' },
        { id: 'mor07', text: 'كل يوم صفحة جديدة 📖\nونبدأها بعرض لا تجده في كل مكان.' },
        { id: 'mor08', text: 'مع بداية النهار نُقدّم الأفضل 🌟\nلأن وقتك وذوقك يستحقان ما هو أرقى.' },
        { id: 'mor09', text: '🫖 على كوب الصباح — نقدم لك خبر يسعدك:\nعرض مميز يستحق توقفة صغيرة.' },
        { id: 'mor10', text: 'صباح من يحب التميز 💎\nهذا الصنف لمن يعرف قيمة الجودة الحقيقية.' },
        { id: 'mor11', text: 'طلع الفجر وطلعنا معاه 🌄\nبعرض ما تقدر تلاقيه كل يوم — اغتنم اللحظة.' },
        { id: 'mor12', text: '🌺 خير الكلام في بداية النهار:\nوفّرنا لك ما يستحق بريمة الصباح.' },
    ],
    noon: [
        { id: 'non01', text: 'وقت الذروة ووقت الفرص 🔆\nعرضنا الذي ينتظرك في منتصف النهار.' },
        { id: 'non02', text: '🕛 في لحظة الظهيرة — لحظة تُرتّب فيها يومك:\nهذا العرض يستحق مكاناً في قائمتك.' },
        { id: 'non03', text: 'الظهيرة والبركة تجتمعان 🤲\nنقدم لك عرضاً يجمع الجودة والسعر.' },
        { id: 'non04', text: '☀️ حين يبلغ الشمس ذروتها — عرضنا في ذروة جودته.\nلا تفوّت ما أعددناه لك.' },
    ],
    afternoon: [
        { id: 'aft01', text: 'بعد عناء النهار — هدية العصر 🌿\nعرض لطيف يستحق وقفة بعد يوم مثمر.' },
        { id: 'aft02', text: '🌤️ وسط النهار وأنت تحسم خياراتك:\nهذا العرض يستحق أن يكون قرارك اليوم.' },
        { id: 'aft03', text: 'مع رياح العصر اللطيفة 💨\nننسيك عناء النهار بعرض يبهجك.' },
        { id: 'aft04', text: 'العصر وقت الخير والبركة 🙌\nوخيرنا لك موجود — لا تتردد.' },
        { id: 'aft05', text: 'في منتصف الطريق نمنحك الدفع 💫\nعرض يكسر رتابة اليوم بشيء مميز.' },
    ],
    evening: [
        { id: 'eve01', text: 'مساء الخير والبهجة 🌙\nأجمل العروض تنتظرك في ساعة الراحة.' },
        { id: 'eve02', text: '🌆 حين يهدأ اليوم ويبدأ التفكير الهادئ:\nهذا العرض يناسب لحظتك تماماً.' },
        { id: 'eve03', text: 'مساء النور والاختيارات الذكية ✨\nوقتك الآن لا يصلح إلا للأفضل.' },
        { id: 'eve04', text: '🌃 مع غروب الشمس يطلع نجم عرضنا:\nلا تترك الليل يمضي دون أن تحجز.' },
        { id: 'eve05', text: 'وقت الراحة والتسوق الهادئ 🛋️\nأجمل قراراتك تأتي حين تسترخي.' },
        { id: 'eve06', text: '🍃 مع نسمة المساء نُقدّم لك:\nعرضاً ينهي يومك بلمسة تميز.' },
        { id: 'eve07', text: 'مساء الرقي لمن يعرف قيمة وقته ⭐\nعرض انتقيناه خصيصاً لهذه الساعة.' },
        { id: 'eve08', text: '🌙 الليل يقرب والفرصة تمضي:\nاغتنمها قبل أن تصبح ذكرى.' },
    ],
    night: [
        { id: 'ngt01', text: 'في هدأة الليل تأتي أفضل القرارات 🌙\nهذا العرض ينتظر لحظة تأمّلك.' },
        { id: 'ngt02', text: '⭐ حين ينام الضجيج ويصحو العقل:\nقرارات الليل الهادئة هي الأصوب.' },
        { id: 'ngt03', text: 'الليل للتأمل والتخطيط 🔮\nوعرضنا يليق بذوقك الليلي الرفيع.' },
        { id: 'ngt04', text: 'منتجنا لا ينام — كنجوم الليل 🌟\nمتاح لك الآن بكل تفاصيله.' },
        { id: 'ngt05', text: '🌌 في الليل الهادئ تظهر النجوم والفرص:\nهذه واحدة لا تفوّتها.' },
        { id: 'ngt06', text: 'وقت التسوق الليلي الذكي 🛒\nبلا ضغط ولا تسرع — خذ قرارك بهدوء.' },
    ],
    friday: [
        { id: 'fri01', text: '🕌 جمعة مباركة طيبة\nفي أفضل أيام الأسبوع نقدم لك أفضل عروضنا.' },
        { id: 'fri02', text: 'جمعة مباركة على الجميع 🤲\nيوم البركة يستحق عرضاً بمستوى البركة.' },
        { id: 'fri03', text: '✨ في يوم الجمعة المبارك\nشاركنا فرحة اليوم باختيار يليق به.' },
        { id: 'fri04', text: '🕌 نور الجمعة يغمر يومك\nونغتنم بركة اليوم لنقدم لك الأفضل.' },
        { id: 'fri05', text: 'يوم الجمعة — يوم العطاء والخير 💚\nوعرضنا اليوم على مستوى بركته.' },
        { id: 'fri06', text: '🙏 اللهم تقبل وبارك في يوم الجمعة\nونقدم لك اليوم ما يسعدك.' },
    ],
    new_year: [
        { id: 'ny01', text: 'عام جديد ومستقبل أجمل 🎊\nنبدأ معك العام الجديد بأفضل العروض.' },
        { id: 'ny02', text: '🎉 مع مطلع العام الجديد\nأول قراراتك الصحيحة — هذا العرض.' },
        { id: 'ny03', text: 'عام جديد، أهداف جديدة، اختيارات أفضل ✨\nابدأ مشواره معنا.' },
    ],
    year_end: [
        { id: 'ye01', text: 'آخر أيام العام وأفضل العروض 🎁\nاختم عامك بقرار صحيح.' },
        { id: 'ye02', text: '🗓️ العام في رحلته الأخيرة\nولا يزال عندنا ما يجعله لا يُنسى.' },
        { id: 'ye03', text: 'احتفل بختام العام بعرض استثنائي 🎊\nتذكر — الفرص لا تنتظر.' },
    ],
    sep26: [
        { id: 's26a', text: '🇾🇪 في ذكرى ثورة 26 سبتمبر المجيدة\nنحتفل معكم بعرض يليق بعزة اليمن.' },
        { id: 's26b', text: 'ذكرى الثورة ذكرى العزة 🌹\nونقدم في هذا اليوم المجيد عرضاً خاصاً.' },
        { id: 's26c', text: '26 سبتمبر — يوم صنع التاريخ 🏆\nنكرمك اليوم بأفضل ما لدينا.' },
    ],
    oct14: [
        { id: 'o14a', text: '🇾🇪 ذكرى ثورة 14 أكتوبر العظيمة\nنُحيي هذا اليوم التاريخي بعرض استثنائي.' },
        { id: 'o14b', text: 'في ذكرى البطولة والكفاح 🌹\nنُقدّم لك ما يليق بعظمة هذا اليوم.' },
    ],
    may22: [
        { id: 'm22a', text: '🇾🇪 بمناسبة عيد الوحدة اليمنية المجيد\nكل عام والوطن والأهل بخير وسلام.' },
        { id: 'm22b', text: 'يوم الوحدة يوم الفخر 🌹\nوأفضل الهدايا لمن تحب في يوم الوطن.' },
    ],
    spring: [
        { id: 'spr1', text: '🌸 الربيع حلّ وأزهرت الفرص معه\nتجديد الذوق يبدأ بالخيار الصحيح.' },
        { id: 'spr2', text: 'مع أول نسمات الربيع 🌺\nعرض يعكس روح الموسم الجميل.' },
    ],
};

// =========================================================
// بنك عبارات الجوهر الترويجي — 60 عبارة
// =========================================================
const HEC_HOOK_BANK = [
    { id: 'hk01', text: 'وفّرنا لك ما يصعب إيجاده في كل مكان 🎯\nلأن ذوقك لا يقبل إلا الأفضل.' },
    { id: 'hk02', text: 'التفاصيل تصنع الفارق 💎\nوهذا الصنف مصمَّم ليكون مختلفاً من الداخل والخارج.' },
    { id: 'hk03', text: 'لم يبقَ الكثير من الكمية 🔥\nوعندما ينتهي — لن تجده بهذا السعر.' },
    { id: 'hk04', text: 'بين الفخامة والعملية — خيارك الأمثل 🏆\nوفّرنا الاثنين معاً في صنف واحد.' },
    { id: 'hk05', text: 'نحرص على انتقاء ما يناسبك 🌟\nليكون الاختيار سهلاً وموثوقاً.' },
    { id: 'hk06', text: 'صنف يكتسب قيمة كل يوم تستخدمه فيه ⭐\nلأن الجودة الحقيقية لا تُعاش مرة واحدة.' },
    { id: 'hk07', text: 'توقف عن البحث — وجدت ما كنت تبحث عنه ✅\nكل التفاصيل هنا أمامك.' },
    { id: 'hk08', text: 'قيمة حقيقية تستحق الاقتناء 💡\nليس لأنه رخيص — بل لأنه يستحق كل ريال.' },
    { id: 'hk09', text: 'الأذكياء يختارون مرة واحدة ويريحون أنفسهم 🧠\nهذا هو الخيار الذكي أمامك الآن.' },
    { id: 'hk10', text: 'عرض انتقيناه بعناية خصيصاً لك 🎁\nلأن زبائننا يستحقون ما هو أرقى.' },
    { id: 'hk11', text: 'الجودة ليست صدفة — هي قرار 🎯\nواخترنا لك الصنف الذي يجسّد هذا القرار.' },
    { id: 'hk12', text: 'حين يجتمع السعر المناسب والجودة العالية 🤝\nالنتيجة أمامك — احكم بنفسك.' },
    { id: 'hk13', text: 'لمن يرفض التنازل عن الجودة 💪\nهذا الصنف يعرف ذوقك ويلبّيه.' },
    { id: 'hk14', text: 'ليس مجرد منتج — تجربة كاملة ✨\nتبدأ من أول لحظة تحصل عليه.' },
    { id: 'hk15', text: 'الفرص النادرة لا تدقّ الباب مرتين 🚪\nهذه واحدة منها — اقرر الآن.' },
    { id: 'hk16', text: 'من رأى لم يتردد — ومن تردد ندم 😊\nتفاصيل المنتج تتحدث عن نفسها.' },
    { id: 'hk17', text: 'نقدم ما لا يقدمه الجميع 🌐\nلأن رضاك هو مقياس نجاحنا.' },
    { id: 'hk18', text: 'صنف اخترناه بعناية واهتمام 💛\nنسعى دائماً لنكون عند حسن ظنك.' },
    { id: 'hk19', text: 'الفرق الحقيقي يبدو في التفاصيل الصغيرة 🔍\nهذا الصنف ينجح في كل التفاصيل.' },
    { id: 'hk20', text: 'اقتنِ ما يبقى — لا ما يمضي 🏅\nالجودة استثمار لا يخسر.' },
    { id: 'hk21', text: 'لأن وقتك ثمين جداً للتردد 🕐\nالتفاصيل واضحة والقرار بين يديك.' },
    { id: 'hk22', text: 'ما انتقيناه ليس عشوائياً 🧩\nكل تفصيلة في هذا الصنف مدروسة لراحتك.' },
    { id: 'hk23', text: 'يومياً يصلنا ما هو أفضل 📦\nواليوم حصتك من هذا الأفضل جاهزة.' },
    { id: 'hk24', text: 'أسعار تنافسية + جودة لا تتنازل 💰\nالمعادلة التي نُفخر بها.' },
    { id: 'hk25', text: 'شراء ذكي = سعادة دائمة 😊\nوهذا الصنف مُعادلة مضمونة.' },
    { id: 'hk26', text: 'ما يُفرّق بين المشترين الأذكياء وغيرهم: التوقيت ⏱️\nوتوقيتك الآن مثالي.' },
    { id: 'hk27', text: 'لا تتأخر حتى تفاجأ بانتهاء الكمية ⚡\nالفرصة أمامك الآن — افعل شيئاً.' },
    { id: 'hk28', text: 'هذا الصنف يعرف طريقه لقلوب أصحاب الذوق 💝\nهل أنت منهم؟' },
    { id: 'hk29', text: 'نأمل أن يكون هذا الصنف ما تبحث عنه 🔎\nتفضل بالاطلاع على التفاصيل كاملة.' },
    { id: 'hk30', text: 'كل يوم خطوة نحو الأفضل 🚀\nوهذا الصنف هو خطوتك اليوم.' },
    { id: 'hk31', text: 'الخيار يعكس الشخصية 🪞\nاختَر ما يعكس حقيقة ذوقك.' },
    { id: 'hk32', text: 'نحن لا نبيع منتجات — نُقدّم تجارب 🎭\nوهذه التجربة تستحق التجربة.' },
    { id: 'hk33', text: 'ثقتك هي رأسمالنا الحقيقي 🤝\nولذلك لا نقدم إلا ما نرضاه لأنفسنا.' },
    { id: 'hk34', text: 'البضاعة الجيدة تتكلم عن نفسها 🗣️\nاقرأ التفاصيل واتركها تُقنعك.' },
    { id: 'hk35', text: 'الجودة لا تأتي بالصدفة ⚡\nهي نتيجة اهتمام بالتفاصيل والصدق في التعامل.' },
    { id: 'hk36', text: 'صنف بتفاصيله يروي القصة كاملة 📖\nلا تكتفِ بالصورة — اقرأ كل شيء.' },
    { id: 'hk37', text: 'ما يُعطى بسهولة لا يُحفظ طويلاً 🏛️\nما انتقيناه لك جاء بعد تحرٍّ دقيق.' },
    { id: 'hk38', text: 'صنفنا لا يحتاج لمبالغة — تفاصيله تكفي 📋\nتفضّل وقارن بنفسك.' },
    { id: 'hk39', text: 'عرض يستحق أن تتوقف من أجله 🛑\nولو للحظة فكر — ستقرر الاقتناء.' },
    { id: 'hk40', text: 'نحن نُرتّب الفرص لك — أنت فقط تختار 🎯\nوهذه الفرصة الآن بين يديك.' },
    { id: 'hk41', text: 'ليس سعراً فقط — قيمة حقيقية 💎\nالفرق يظهر بعد الاستخدام.' },
    { id: 'hk42', text: 'الأناقة ليست ترفاً — هي أسلوب حياة 🌸\nوهذا الصنف يُعبّر عن أسلوبك.' },
    { id: 'hk43', text: 'كل تفصيل في مكانه الصحيح 🎨\nلأن الصانع الجيد لا يتسامح مع التقصير.' },
    { id: 'hk44', text: 'اشترِ مرة وارتح من إعادة الشراء 🔄\nالجودة الحقيقية لا تحتاج لتكرار قريب.' },
    { id: 'hk45', text: 'رضاك يهمنا فعلاً 🏆\nولذلك نحرص على تقديم تفاصيل صادقة وواضحة.' },
    { id: 'hk46', text: 'لمن يتعب من التسوق الطويل 😌\nوجدنا لك ما تبحث عنه وجهّزناه.' },
    { id: 'hk47', text: 'فخامة لا تُعلَن — تُشعَر 👑\nجرّب وأخبرنا.' },
    { id: 'hk48', text: 'صنفنا يتكلم لغة من يفهم القيمة 🧐\nولا نشك أنك منهم.' },
    { id: 'hk49', text: 'لأن الحياة قصيرة لنختار الرديء 🌺\nاختر الأفضل — اختر بثقة.' },
    { id: 'hk50', text: 'عشرات الخيارات في السوق — ونحن اخترنا أفضلها لك 🔬\nالفلترة انتهت — التفاصيل أمامك.' },
    { id: 'hk51', text: 'صُنع للعمر — ليس للموسم 🏛️\nاستثمار ذكي يظهر أثره مع الوقت.' },
    { id: 'hk52', text: 'أصحاب الذوق الرفيع وجدوا ما يبحثون عنه 🎩\nوأنت التالي.' },
    { id: 'hk53', text: 'نعرض ما نُفخر بعرضه 🌟\nلا غش ولا مبالغة — فقط صدق وجودة.' },
    { id: 'hk54', text: 'حين تشتري من مكان موثوق — ترتاح بالك ✅\nونحن هنا منذ زمن لهذا السبب.' },
    { id: 'hk55', text: 'ما يُقال عنه أقل مما يستحقه 🌠\nتجربته الحقيقية أفضل من أي وصف.' },
    { id: 'hk56', text: 'العقل يحسب — والقلب يختار 💫\nهذا الصنف سيُرضي الاثنين.' },
    { id: 'hk57', text: 'تصميم يعكس الاحترافية 🎯\nوسعر يعكس أمانتنا معك.' },
    { id: 'hk58', text: 'في زمن الغش نُصرّ على الأصل 🛡️\nجودتنا شهادة من زبائننا.' },
    { id: 'hk59', text: 'الأوقات الصعبة تُعلّم — اختر ما يدوم 💪\nوهذا الصنف صُنع للمدى الطويل.' },
    { id: 'hk60', text: 'نقدم الخير وننتظر رضاك 🌸\nرضاك هو ختم النجاح لكل صفقة.' },
];

// =========================================================
// بنك عبارات الدعوة للتصرف (CTA) — 20 عبارة
// =========================================================
const HEC_CTA_BANK = [
    { id: 'cta01', text: '👇 احجز الآن ولا تدع غيرك يسبقك:' },
    { id: 'cta02', text: '📩 تواصل معنا الآن — الكمية محدودة:' },
    { id: 'cta03', text: '⚡ اطلب الآن — التأخير قد يعني الفوات:' },
    { id: 'cta04', text: '🛒 خطوة واحدة تفصلك — اطلب مباشرة:' },
    { id: 'cta05', text: '💬 ابعث لنا ونحن نُرتّب كل شيء:' },
    { id: 'cta06', text: '🤝 تواصل معنا — سنُسعدك بالخدمة:' },
    { id: 'cta07', text: '📦 الطلب سريع والتوصيل في وقته:' },
    { id: 'cta08', text: '🎯 القرار الصح في وقته الصح — اطلب الآن:' },
    { id: 'cta09', text: '✅ للحجز والاستفسار — نحن هنا:' },
    { id: 'cta10', text: '📱 راسلنا الآن ولا تترك الفرصة تمضي:' },
    { id: 'cta11', text: '🔥 الطلب المبكر يضمن لك الأولوية:' },
    { id: 'cta12', text: '💎 عرض بهذا المستوى — لا يتكرر كثيراً:' },
    { id: 'cta13', text: '🙋 نحن في انتظار طلبك:' },
    { id: 'cta14', text: '👋 كلّمنا وخلّنا نكمل لك الفرحة:' },
    { id: 'cta15', text: '🌟 اكتمال السعادة في خطوة واحدة — ابدأها الآن:' },
    { id: 'cta16', text: '⏳ لا تنتظر حتى تُحسد على ما فاتك:' },
    { id: 'cta17', text: '🏃 للطلب السريع — التواصل المباشر أسرع:' },
    { id: 'cta18', text: '🤲 ثق بنا — نحن نُكمل معك باقي الخطوات:' },
    { id: 'cta19', text: '📲 رسالة واحدة منك تكفي — نحن ندير الباقي:' },
    { id: 'cta20', text: '💚 نسعد بخدمتك — تفضل بالتواصل:' },
];

// =========================================================
// محرك التسويق الذكي الجديد — يستبدل النسخة القديمة
// =========================================================
function smartMarketingEngine(customPromoText, companySettings, itemCode) {
    if (customPromoText && customPromoText.trim()) { return { intro: customPromoText.trim(), cta: '📩 للطلب المباشر أو الاستفسار، تواصل معنا:' }; }
    if (companySettings && companySettings.custom_promotional_phrases) {
        const phrases = companySettings.custom_promotional_phrases.split('\n').filter(p => p.trim() !== '');
        if (phrases.length > 0) {
            const memKey = 'company_custom';
            const pool = phrases.map((p, i) => ({ id: 'cust_' + i, text: p.trim() }));
            const fresh = pool.filter(p => !_wasRecentlyUsed(memKey, p.id));
            const chosen = fresh.length > 0 ? fresh[Math.floor(Math.random() * fresh.length)] : pool[Math.floor(Math.random() * pool.length)];
            _recordUsed(memKey, chosen.id);
            return { intro: chosen.text, cta: '📩 للطلب المباشر أو الاستفسار، تواصل معنا:' };
        }
    }
    const memKey = itemCode ? 'item_' + String(itemCode).replace(/\s/g,'_') : 'global';
    const occasion = _detectOccasion();
    const greetingPool = HEC_PHRASE_BANKS[occasion] || HEC_PHRASE_BANKS['morning'];
    const greeting = _pickFresh(memKey + '_greet', greetingPool);
    const hook     = _pickFresh(memKey + '_hook',  HEC_HOOK_BANK);
    const cta      = _pickFresh(memKey + '_cta',   HEC_CTA_BANK);
    return { intro: `${greeting}\n\n${hook}`, cta };
}

class ProductImageGenerator {
    constructor(options = {}) {
        this.canvas = document.createElement('canvas'); this.ctx = this.canvas.getContext('2d');
        this.baseUrl = window.location.origin;
        this.canvasWidth = options.width || 1080; this.canvasHeight = options.height || 1080;
        this.canvas.width = this.canvasWidth; this.canvas.height = this.canvasHeight;
        this.primaryColor = options.primaryColor || '#D4AF37'; this.secondaryColor = options.secondaryColor || '#000000';
        this.nameColor = options.nameColor || '#8B0000';
        this.backgroundColor = options.backgroundColor || '#ffffff';
        this.headerFontSize = 48; this.codeFontSize = 36;
        this._cachedImgUrl = null; this._cachedImg = null;
        this._cachedFrameUrl = null; this._cachedFrame = null;
        this._cachedBgOverlayUrl = null; this._cachedBgOverlay = null;
        this._cachedPlacedImages = {}; 
        this.hitBoxes = { img: null, title: null, price: null, occasion: null, customText: null };
        this.placedItemsHitBoxes = {};
        this.activeItem = null;
        this.transformHandles = {};
        this.handleRadius = 25; // تكبير لتسهيل الضغط
    }
    loadImageSafely(url) { 
        return new Promise(resolve => { 
            const img = new Image(); img.crossOrigin = 'anonymous'; 
            img.onload = () => resolve(img); img.onerror = () => resolve(null); img.src = url; 
        }); 
    }
    fallbackShare(msg, target) { setTimeout(() => { if (target) { window.open(target, '_blank'); } else { window.open(`https://wa.me/?text=${encodeURIComponent(msg)}`, '_blank'); } }, 500); }
    
    drawTransformBox(box) {
        if (!box || !this.activeItem) return;

        const ctx = this.ctx;
        const rot = (this.activeItem.rotation || 0) * Math.PI / 180;
        const cx = box.x + box.w / 2;
        const cy = box.y + box.h / 2;

        ctx.save();
        ctx.translate(cx, cy);
        ctx.rotate(rot);

        const w = box.w;
        const h = box.h;

        // Draw bounding box tighter
        ctx.strokeStyle = '#007bff';
        ctx.lineWidth = 4;
        ctx.setLineDash([10, 10]);
        ctx.strokeRect(-w / 2, -h / 2, w, h);
        ctx.setLineDash([]);
        
        // نقطة الارتكاز في المنتصف لتسهيل التحريك
        const handles = {
            tl: { x: -w / 2, y: -h / 2 },
            tr: { x: w / 2, y: -h / 2 },
            bl: { x: -w / 2, y: h / 2 },
            br: { x: w / 2, y: h / 2 },
            c:  { x: 0, y: 0 }, // Center handle added
            rot: { x: 0, y: -h / 2 - 50 } 
        };

        this.transformHandles = {};
        
        // رسم المقابض
        for (const name in handles) {
            const pos = handles[name];
            
            if (name === 'rot') {
                ctx.beginPath();
                ctx.moveTo(0, -h/2);
                ctx.lineTo(pos.x, pos.y);
                ctx.strokeStyle = '#007bff';
                ctx.stroke();
            }

            ctx.beginPath();
            ctx.arc(pos.x, pos.y, name === 'c' ? 12 : this.handleRadius - 8, 0, 2 * Math.PI);
            ctx.fillStyle = name === 'c' ? 'rgba(0, 123, 255, 0.5)' : '#ffffff';
            ctx.fill();
            ctx.strokeStyle = '#007bff';
            ctx.lineWidth = 3;
            ctx.stroke();
            
            if(name === 'c') {
                ctx.beginPath(); ctx.moveTo(pos.x-5, pos.y); ctx.lineTo(pos.x+5, pos.y); ctx.stroke();
                ctx.beginPath(); ctx.moveTo(pos.x, pos.y-5); ctx.lineTo(pos.x, pos.y+5); ctx.stroke();
            }
            
            const globalX = pos.x * Math.cos(rot) - pos.y * Math.sin(rot) + cx;
            const globalY = pos.x * Math.sin(rot) + pos.y * Math.cos(rot) + cy;
            this.transformHandles[name] = { x: globalX, y: globalY, radius: name === 'c' ? this.handleRadius * 1.5 : this.handleRadius };
        }
        
        ctx.restore();
    }
    
    getHitTarget(x, y) {
        // 1. Check transform handles first (دعم نقطة المنتصف)
        for (const handleName in this.transformHandles) {
            const handle = this.transformHandles[handleName];
            const dist = Math.sqrt(Math.pow(x - handle.x, 2) + Math.pow(y - handle.y, 2));
            if (dist <= handle.radius) {
                return { type: 'handle', name: handleName, item: this.activeItem.id };
            }
        }
        
        // 2. Check placed items
        const placedItemsSorted = [...(this.placedItemsData || [])].reverse();
        for (const item of placedItemsSorted) {
            if (item.hidden) continue;
            const box = this.placedItemsHitBoxes[item.id];
            if (box) {
                const cx = box.x + box.w / 2;
                const cy = box.y + box.h / 2;
                const dx = x - cx;
                const dy = y - cy;
                const rot = (item.rotation || 0) * Math.PI / 180;
                const localX = dx * Math.cos(-rot) - dy * Math.sin(-rot);
                const localY = dx * Math.sin(-rot) + dy * Math.cos(-rot);
                if (Math.abs(localX) <= box.w / 2 && Math.abs(localY) <= box.h / 2) {
                    return { type: 'item', id: item.id };
                }
            }
        }
        
        // 3. Check main elements
        for (const key of ['customText', 'occasion', 'price', 'title', 'img']) { 
            const box = this.hitBoxes[key];
            if (box && x >= box.x && x <= box.x + box.w && y >= box.y && y <= box.y + box.h) { 
                return { type: 'item', id: key }; 
            }
        }
        return null;
    }
    drawStar(ctx, cx, cy, spikes, outerRadius, innerRadius) {
        let rot = Math.PI / 2 * 3; let x = cx; let y = cy; let step = Math.PI / spikes;
        ctx.beginPath(); ctx.moveTo(cx, cy - outerRadius);
        for (let i = 0; i < spikes; i++) {
            x = cx + Math.cos(rot) * outerRadius; y = cy + Math.sin(rot) * outerRadius; ctx.lineTo(x, y); rot += step;
            x = cx + Math.cos(rot) * innerRadius; y = cy + Math.sin(rot) * innerRadius; ctx.lineTo(x, y); rot += step;
        }
        ctx.lineTo(cx, cy - outerRadius); ctx.closePath();
    }
    drawTriangle(ctx, x, y, size) {
        ctx.beginPath(); ctx.moveTo(x, y - size / 2); ctx.lineTo(x + size / 2, y + size / 2); ctx.lineTo(x - size / 2, y + size / 2); ctx.closePath();
    }
    drawBanner(ctx, x, y, w, h) {
        const tail = h * 0.4;
        ctx.beginPath();
        ctx.moveTo(x, y); ctx.lineTo(x + w, y); ctx.lineTo(x + w, y + h); ctx.lineTo(x + w - tail, y + h / 2); ctx.lineTo(x + w, y);
        ctx.moveTo(x, y); ctx.lineTo(x, y + h); ctx.lineTo(x + tail, y + h / 2); ctx.lineTo(x, y); ctx.closePath();
    }
    drawOval(ctx, x, y, w, h) { ctx.beginPath(); ctx.ellipse(x + w/2, y + h/2, w/2, h/2, 0, 0, 2 * Math.PI); ctx.closePath(); }
    drawFlexibleLine(ctx, x1, y1, len, amplitude, frequency, style, curveAmount) {
        ctx.beginPath(); ctx.moveTo(0, 0);
        if (style === 'منحني' || curveAmount !== 0) {
            ctx.quadraticCurveTo(len / 2, curveAmount || 50, len, 0);
            ctx.stroke();
        } else if (style === 'متعرج') {
            for (let i = 0; i < len; i++) { ctx.lineTo(i, Math.sin(i * frequency) * amplitude); }
            ctx.stroke();
        } else {
            ctx.lineTo(len, 0); ctx.stroke();
        }
    }
    async generateNoFrame(productData) {
        if (productData.imageUrl) {
            const img = await this.loadImageSafely(normalizeUrl(productData.imageUrl, this.baseUrl));
            if (img) {
                this.canvas.width = img.width; this.canvas.height = img.height;
                this.ctx.clearRect(0, 0, this.canvas.width, this.canvas.height);
                this.ctx.drawImage(img, 0, 0);
                return this.canvas;
            }
        }
        return await this.generateDefaultFrame(productData); 
    }
    async generateStudioDesign(productData, studioOptions, companySettings, offsets = null, placedItems = []) {
        this.placedItemsData = placedItems; 
        const ctx = this.ctx; const cw = this.canvas.width; const ch = this.canvas.height;
        const off = offsets || { img: {dx:0, dy:0}, title: {dx:0, dy:0}, price: {dx:0, dy:0}, occasion: {dx:0, dy:0}, customText: {dx:0, dy:0} };
        if (productData.imageUrl && this._cachedImgUrl !== productData.imageUrl) { this._cachedImg = await this.loadImageSafely(normalizeUrl(productData.imageUrl, this.baseUrl)); this._cachedImgUrl = productData.imageUrl; }
        let frameUrlPath = null;
        if (studioOptions.frameTemplate && studioOptions.frameTemplate !== 'بلا قالب' && studioOptions.frameTemplate !== 'النمط الافتراضي' && companySettings) {
            if (companySettings.templates && companySettings.templates.length > 0) { const matched = companySettings.templates.find(t => t.template_name === studioOptions.frameTemplate); if (matched && matched.frame_image) frameUrlPath = matched.frame_image; }
            if (!frameUrlPath && studioOptions.frameTemplate === 'إطار مخصص (مركز الهيثم)' && companySettings.custom_frame_image) { frameUrlPath = companySettings.custom_frame_image; }
        }
        if (frameUrlPath && this._cachedFrameUrl !== frameUrlPath) { this._cachedFrame = await this.loadImageSafely(normalizeUrl(frameUrlPath, this.baseUrl)); this._cachedFrameUrl = frameUrlPath; } else if (!frameUrlPath) { this._cachedFrame = null; this._cachedFrameUrl = null; }
        if (studioOptions.bgOverlayUrl && this._cachedBgOverlayUrl !== studioOptions.bgOverlayUrl) { this._cachedBgOverlay = await this.loadImageSafely(studioOptions.bgOverlayUrl); this._cachedBgOverlayUrl = studioOptions.bgOverlayUrl; } else if (!studioOptions.bgOverlayUrl) { this._cachedBgOverlay = null; this._cachedBgOverlayUrl = null; }
        ctx.clearRect(0,0,cw,ch);
        if (studioOptions.useGradient) { const gradient = ctx.createLinearGradient(0, 0, cw, ch); gradient.addColorStop(0, studioOptions.bgColor || '#ffffff'); gradient.addColorStop(1, '#1a1a1a'); ctx.fillStyle = gradient; } 
        else { ctx.fillStyle = studioOptions.bgColor || '#ffffff'; }
        ctx.fillRect(0, 0, cw, ch);
        if (this._cachedBgOverlay) { ctx.save(); ctx.globalAlpha = parseFloat(studioOptions.bgOverlayOpacity) || 0.3; ctx.drawImage(this._cachedBgOverlay, 0, 0, cw, ch); ctx.restore(); }
        const bgBorderW = parseInt(studioOptions.bgBorderWidth) || 0;
        if (bgBorderW > 0 && studioOptions.bgBorderColor !== 'transparent') { ctx.save(); ctx.strokeStyle = studioOptions.bgBorderColor || '#D4AF37'; ctx.lineWidth = bgBorderW; ctx.strokeRect(bgBorderW/2, bgBorderW/2, cw - bgBorderW, ch - bgBorderW); ctx.restore(); }
        if (studioOptions.frameTemplate === 'النمط الافتراضي') { ctx.save(); ctx.strokeStyle = '#000000'; ctx.lineWidth = 20; ctx.strokeRect(10, 10, cw - 20, ch - 20); ctx.strokeStyle = '#D4AF37'; ctx.lineWidth = 8; ctx.strokeRect(30, 30, cw - 60, ch - 60); ctx.restore(); }
        const drawImageFunc = () => { if (this._cachedImg && studioOptions.hideImg !== true) { const scale = parseFloat(studioOptions.imageScale) || 1.0; const rot = parseFloat(studioOptions.imageRotation) || 0; const maxWidth = cw - 140; const maxHeight = ch - 280; let boxW = maxWidth * scale; let boxH = maxHeight * scale; let boxX = (cw - boxW) / 2 + off.img.dx; let boxY = (ch - boxH) / 2 - 20 + off.img.dy; let drawW, drawH, drawX, drawY; if (this._cachedFrame) { const imgScale = Math.min(boxW / this._cachedImg.width, boxH / this._cachedImg.height); drawW = this._cachedImg.width * imgScale; drawH = this._cachedImg.height * imgScale; drawX = boxX + (boxW - drawW) / 2; drawY = boxY + (boxH - drawH) / 2; boxW = drawW; boxH = drawH; boxX = drawX; boxY = drawY; } else { const imgScale = Math.min(boxW / this._cachedImg.width, boxH / this._cachedImg.height); drawW = this._cachedImg.width * imgScale; drawH = this._cachedImg.height * imgScale; boxX = boxX + (boxW - drawW) / 2; boxY = boxY + (boxH - drawH) / 2; boxW = drawW; boxH = drawH; drawX = boxX; drawY = boxY; }
        this.hitBoxes.img = { x: boxX, y: boxY, w: boxW, h: boxH }; ctx.save(); ctx.translate(boxX + boxW/2, boxY + boxH/2); ctx.rotate((rot * Math.PI) / 180); const mBoxX = -boxW/2; const mBoxY = -boxH/2; const mDrawX = drawX - boxX - boxW/2; const mDrawY = drawY - boxY - boxH/2; if (studioOptions.blendModeMultiply) { ctx.globalCompositeOperation = 'multiply'; }
        const maskShape = studioOptions.imageMaskShape || 'مستطيل بحواف دائرية'; ctx.beginPath(); if (maskShape === 'مستطيل بحواف دائرية') { ctx.roundRect(mBoxX, mBoxY, boxW, boxH, 30); } else if (maskShape === 'دائرة') { ctx.arc(0, 0, Math.min(boxW, boxH)/2, 0, Math.PI * 2); } else if (maskShape === 'بيضاوي') { ctx.ellipse(0, 0, boxW/2, boxH/2, 0, 0, Math.PI * 2); } else { ctx.rect(mBoxX, mBoxY, boxW, boxH); }
        if (!studioOptions.blendModeMultiply) { ctx.shadowColor = 'rgba(0,0,0,0.4)'; ctx.shadowBlur = 30; ctx.shadowOffsetY = 15; } if(!studioOptions.blendModeMultiply) { ctx.fillStyle = '#ffffff'; ctx.fill(); } ctx.clip(); ctx.drawImage(this._cachedImg, mDrawX, mDrawY, drawW, drawH); 
        if (!studioOptions.blendModeMultiply && studioOptions.imgMainBorderWidth > 0 && studioOptions.imgMainBorderColor !== 'transparent') { ctx.lineWidth = parseInt(studioOptions.imgMainBorderWidth); ctx.strokeStyle = studioOptions.imgMainBorderColor; ctx.stroke(); } ctx.restore(); } else { this.hitBoxes.img = null; } };
        const drawFrameFunc = () => { if (this._cachedFrame) { ctx.save(); ctx.drawImage(this._cachedFrame, 0, 0, cw, ch); ctx.restore(); } };
        if (studioOptions.layerOrder === 'img_top') { drawFrameFunc(); drawImageFunc(); } else { drawImageFunc(); drawFrameFunc(); }
        this.placedItemsHitBoxes = {}; if (placedItems && placedItems.length > 0) { for (const item of placedItems) { if (item.hidden) continue; if (item.type === 'image') { if (!this._cachedPlacedImages[item.id]) { this._cachedPlacedImages[item.id] = await this.loadImageSafely(normalizeUrl(item.url, this.baseUrl)); } const cImg = this._cachedPlacedImages[item.id]; if (cImg) { const scale = parseFloat(item.scale) || 1.0; const rot = parseFloat(item.rotation) || 0; const baseWidth = item.baseWidth || cImg.width; const baseHeight = item.baseHeight || cImg.height; let drawW = baseWidth * scale; let drawH = baseHeight * scale; ctx.save(); ctx.translate(item.x + drawW/2, item.y + drawH/2); ctx.rotate((rot * Math.PI) / 180); if (item.blendModeMultiply) { ctx.globalCompositeOperation = 'multiply'; }
        const maskShape = item.maskShape || 'مربع'; ctx.beginPath(); if (maskShape === 'مستطيل بحواف دائرية') { ctx.roundRect(-drawW/2, -drawH/2, drawW, drawH, 15); } else if (maskShape === 'دائرة') { ctx.arc(0, 0, Math.min(drawW, drawH)/2, 0, Math.PI * 2); } else if (maskShape === 'بيضاوي') { ctx.ellipse(0, 0, drawW/2, drawH/2, 0, 0, Math.PI * 2); } else { ctx.rect(-drawW/2, -drawH/2, drawW, drawH); }
        if (!item.blendModeMultiply) { ctx.shadowColor = 'rgba(0,0,0,0.3)'; ctx.shadowBlur = 10; ctx.shadowOffsetY = 5; } ctx.clip(); if(!item.blendModeMultiply) { ctx.fillStyle = '#ffffff'; ctx.fill(); } ctx.drawImage(cImg, -drawW/2, -drawH/2, drawW, drawH); if (item.imgBorderWidth && item.imgBorderWidth > 0 && item.imgBorderColor !== 'transparent') { ctx.lineWidth = parseInt(item.imgBorderWidth); ctx.strokeStyle = item.imgBorderColor; ctx.stroke(); } ctx.restore(); this.placedItemsHitBoxes[item.id] = { x: item.x, y: item.y, w: drawW, h: drawH }; } } 
        else if (item.type === 'shape') { const rot = parseFloat(item.rotation) || 0; const scale = parseFloat(item.scale) || 1.0; const boxW = (item.width || 200) * scale; const boxH = (item.height || 200) * scale; ctx.save(); ctx.translate(item.x + boxW/2, item.y + boxH/2); ctx.rotate((rot * Math.PI) / 180); ctx.beginPath(); const sType = item.shapeType || 'مربع'; if (sType === 'مربع') { ctx.rect(-boxW/2, -boxH/2, boxW, boxH); } else if (sType === 'مستطيل') { ctx.rect(-boxW/2, -boxH/2, boxW, boxH/2); } else if (sType === 'مستطيل بحواف دائرية') { ctx.roundRect(-boxW/2, -boxH/2, boxW, boxH, parseInt(item.borderRadius)*scale || 25); } else if (sType === 'بيضاوي') { ctx.ellipse(0, 0, boxW/2, boxH/4, 0, 0, Math.PI * 2); } else if (sType === 'دائرة') { ctx.arc(0, 0, Math.min(boxW, boxH)/2, 0, Math.PI * 2); } else if (sType === 'نجمة') { this.drawStar(ctx, 0, 0, 5, boxW / 2, boxW / 4); } else if (sType === 'مثلث') { this.drawTriangle(ctx, 0, 0, boxW); } else if (sType === 'شريط') { this.drawBanner(ctx, -boxW / 2, -boxH / 2, boxW, boxH); } if (item.bgColor && item.bgColor !== 'transparent' && item.bgColor !== '#00000000') { ctx.fillStyle = item.bgColor; ctx.shadowColor = 'rgba(0,0,0,0.3)'; ctx.shadowBlur = 10 * scale; ctx.shadowOffsetY = 5 * scale; ctx.fill(); } if (item.borderColor && item.borderColor !== 'transparent' && item.borderWidth > 0) { ctx.shadowColor = 'transparent'; ctx.lineWidth = parseInt(item.borderWidth) * scale; ctx.strokeStyle = item.borderColor; const bStyle = item.borderStyle || 'متصل'; if (bStyle === 'متقطع') ctx.setLineDash([15*scale, 15*scale]); else if (bStyle === 'منقط') ctx.setLineDash([5*scale, 10*scale]); else ctx.setLineDash([]); ctx.stroke(); } ctx.restore(); this.placedItemsHitBoxes[item.id] = { x: item.x, y: item.y, w: boxW, h: sType==='مستطيل'||sType==='بيضاوي' ? boxH/2 : boxH }; } 
        else if (item.type === 'line') { const len = parseInt(item.length) || 200; const w = parseInt(item.width) || 5; const rot = parseFloat(item.rotation) || 0; const curve = parseInt(item.curveAmount) || 0; ctx.save(); ctx.translate(item.x, item.y); ctx.rotate((rot * Math.PI) / 180); ctx.strokeStyle = item.color || '#000000'; ctx.lineWidth = w; if (item.lineStyle === 'متقطع') { ctx.setLineDash([w*2, w*2]); } this.drawFlexibleLine(ctx, 0, 0, len, w*2, 0.1, item.lineStyle, curve); ctx.restore(); this.placedItemsHitBoxes[item.id] = { x: item.x - 20, y: item.y - Math.abs(curve) - 20, w: len + 40, h: Math.abs(curve) + w*4 + 40 }; } 
        else if (item.type === 'path') { ctx.save(); ctx.strokeStyle = item.color || '#e74c3c'; ctx.lineWidth = item.width || 5; ctx.lineCap = 'round'; ctx.lineJoin = 'round'; ctx.beginPath(); if(item.points && item.points.length > 0) { ctx.moveTo(item.points[0].x, item.points[0].y); for(let i=1; i<item.points.length; i++) { ctx.lineTo(item.points[i].x, item.points[i].y); } } ctx.stroke(); ctx.restore(); if(item.points && item.points.length > 0) { this.placedItemsHitBoxes[item.id] = {x: item.points[0].x-20, y: item.points[0].y-20, w: 40, h: 40}; } } 
        else if (item.type === 'text') { ctx.save(); const rot = parseFloat(item.rotation) || 0; const scale = parseFloat(item.scale) || 1.0; const lines = (item.text || '').split('\n'); const fontSize = (parseInt(item.fontSize) || 40) * scale; ctx.font = `bold ${fontSize}px "${item.fontFamily || 'Arial Black'}"`; let maxW = 0; lines.forEach(line => { const w = ctx.measureText(line).width; if(w > maxW) maxW = w; }); const padding = 20 * scale; const lineH = fontSize * 1.4; const totalH = lines.length * lineH; const boxW = maxW + (padding * 2); const boxH = totalH + (padding * 2); ctx.translate(item.x + boxW/2, item.y + boxH/2); ctx.rotate((rot * Math.PI) / 180); ctx.beginPath(); ctx.roundRect(-boxW/2, -boxH/2, boxW, boxH, (parseInt(item.borderRadius) || 0) * scale); if (item.bgColor && item.bgColor !== 'transparent' && item.bgColor !== '#00000000') { ctx.fillStyle = item.bgColor; ctx.shadowColor = 'rgba(0,0,0,0.3)'; ctx.shadowBlur = 10 * scale; ctx.shadowOffsetY = 5 * scale; ctx.fill(); } if (item.borderColor && item.borderColor !== 'transparent' && item.borderWidth > 0) { ctx.lineWidth = parseInt(item.borderWidth) * scale; ctx.strokeStyle = item.borderColor; ctx.stroke(); } ctx.shadowColor = 'transparent'; ctx.fillStyle = item.color || '#000000'; ctx.textAlign = item.textAlign || 'center'; ctx.textBaseline = 'top'; if (item.textBorderColor && item.textBorderColor !== 'transparent' && item.textBorderWidth > 0) { ctx.lineWidth = parseInt(item.textBorderWidth) * scale; ctx.strokeStyle = item.textBorderColor; ctx.lineJoin = 'round'; lines.forEach((line, index) => { let txtX = 0; if (item.textAlign === 'left') txtX = -boxW/2 + padding; else if (item.textAlign === 'right') txtX = boxW/2 - padding; const txtY = -boxH/2 + padding + (index * lineH); ctx.strokeText(line, txtX, txtY); }); } lines.forEach((line, index) => { let txtX = 0; if (item.textAlign === 'left') txtX = -boxW/2 + padding; else if (item.textAlign === 'right') txtX = boxW/2 - padding; const txtY = -boxH/2 + padding + (index * lineH); ctx.fillText(line, txtX, txtY); }); ctx.restore(); this.placedItemsHitBoxes[item.id] = { x: item.x, y: item.y, w: boxW, h: boxH }; } } }
        ctx.save(); ctx.textAlign = 'center'; ctx.direction = 'rtl'; let occasionText = studioOptions.customOccasionText || ''; 
        if (occasionText && studioOptions.hideOccasion !== true) { ctx.save(); const rot = parseFloat(studioOptions.occasionRotation) || 0; const scale = parseFloat(studioOptions.occasionScale) || 1.0; const oX = cw / 2 + off.occasion.dx; const oY = 80 + off.occasion.dy; const occFontSize = (parseInt(studioOptions.occasionFontSize) || 50) * scale; ctx.font = `bold ${occFontSize}px "${studioOptions.occasionFontFamily || 'Arial'}", sans-serif`; const lines = occasionText.split('\n'); let maxW = 0; lines.forEach(l => { const w = ctx.measureText(l).width; if(w > maxW) maxW = w; }); const padding = 20 * scale; const lineH = occFontSize * 1.4; const totalH = lines.length * lineH; const boxW = maxW + (padding * 2); const boxH = totalH + (padding * 2); ctx.translate(oX, oY); ctx.rotate((rot * Math.PI) / 180); if (studioOptions.occasionShape && studioOptions.occasionShape !== 'بدون شكل') { if (studioOptions.shapeBgColor && studioOptions.shapeBgColor !== 'transparent') { ctx.fillStyle = studioOptions.shapeBgColor; ctx.shadowColor = 'rgba(0,0,0,0.4)'; ctx.shadowBlur = 15; ctx.shadowOffsetY = 5; } else { ctx.fillStyle = 'transparent'; ctx.shadowColor = 'transparent'; } if (studioOptions.shapeBorderColor && studioOptions.shapeBorderColor !== 'transparent') { ctx.strokeStyle = studioOptions.shapeBorderColor; ctx.lineWidth = parseInt(studioOptions.shapeBorderWidth) * scale || 0; } else { ctx.lineWidth = 0; } const st = studioOptions.occasionShape; if (st === 'مستطيل') { ctx.beginPath(); ctx.rect(-boxW/2, -boxH/2, boxW, boxH); } else if (st === 'مستطيل بحواف دائرية') { ctx.beginPath(); ctx.roundRect(-boxW/2, -boxH/2, boxW, boxH, parseInt(studioOptions.shapeBorderRadius)*scale || 25); } else if (st === 'بيضاوي') { this.drawOval(ctx, -boxW/2 - 20, -boxH/2, boxW + 40, boxH); } else if (st === 'دائرة') { const r = Math.max(boxW, boxH) / 2 + 10; ctx.beginPath(); ctx.arc(0, 0, r, 0, 2 * Math.PI); } else if (st === 'نجمة') { this.drawStar(ctx, 0, 0, 12, boxW/2 + 20, boxW/3); } if(ctx.fillStyle !== 'transparent') ctx.fill(); if (ctx.lineWidth > 0) ctx.stroke(); } ctx.shadowColor = 'transparent'; ctx.fillStyle = studioOptions.customOccasionColor || '#ffffff'; ctx.textAlign = studioOptions.occasionTextAlign || 'center'; ctx.textBaseline = 'top'; if (studioOptions.occasionTextBorderColor && studioOptions.occasionTextBorderColor !== 'transparent' && studioOptions.occasionTextBorderWidth > 0) { ctx.lineWidth = parseInt(studioOptions.occasionTextBorderWidth) * scale; ctx.strokeStyle = studioOptions.occasionTextBorderColor; ctx.lineJoin = 'round'; lines.forEach((line, index) => { let txtX = 0; if (studioOptions.occasionTextAlign === 'left') txtX = -boxW/2 + padding; else if (studioOptions.occasionTextAlign === 'right') txtX = boxW/2 - padding; ctx.strokeText(line, txtX, -boxH/2 + padding + (index * lineH)); }); } lines.forEach((line, index) => { let txtX = 0; if (studioOptions.occasionTextAlign === 'left') txtX = -boxW/2 + padding; else if (studioOptions.occasionTextAlign === 'right') txtX = boxW/2 - padding; ctx.fillText(line, txtX, -boxH/2 + padding + (index * lineH)); }); ctx.restore(); this.hitBoxes.occasion = { x: oX - boxW/2, y: oY - boxH/2, w: boxW, h: boxH }; } else { this.hitBoxes.occasion = null; }
        const prodNameRaw = studioOptions.productNameText !== undefined ? studioOptions.productNameText : (productData.name || ''); if (prodNameRaw && studioOptions.hideTitle !== true) { ctx.save(); const rot = parseFloat(studioOptions.nameRotation) || 0; const scale = parseFloat(studioOptions.nameScale) || 1.0; const nameLines = prodNameRaw.split('\n'); const tX = cw / 2 + off.title.dx; const tY = ch - 180 + off.title.dy; const nameFontSize = (parseInt(studioOptions.nameFontSize) || 45) * scale; ctx.font = `900 ${nameFontSize}px "${studioOptions.nameFontFamily || 'Arial Black'}", sans-serif`; let maxNW = 0; nameLines.forEach(l => { const w = ctx.measureText(l).width; if(w > maxNW) maxNW = w; }); const lineH = nameFontSize * 1.3; const totalH = nameLines.length * lineH; const padding = 20 * scale; const nBoxW = maxNW + (padding * 2); const nBoxH = totalH + (padding * 1.5); ctx.translate(tX, tY); ctx.rotate((rot * Math.PI) / 180); if (studioOptions.nameBgColor && studioOptions.nameBgColor !== 'transparent') { ctx.fillStyle = studioOptions.nameBgColor; ctx.shadowColor = 'rgba(0,0,0,0.3)'; ctx.shadowBlur = 10; ctx.shadowOffsetY = 5; ctx.beginPath(); ctx.roundRect(-nBoxW/2, -nBoxH/2, nBoxW, nBoxH, parseInt(studioOptions.nameBorderRadius)*scale || 10); ctx.fill(); } if (studioOptions.nameBorderColor && studioOptions.nameBorderColor !== 'transparent' && studioOptions.nameBorderWidth > 0) { ctx.shadowColor = 'transparent'; ctx.lineWidth = parseInt(studioOptions.nameBorderWidth) * scale; ctx.strokeStyle = studioOptions.nameBorderColor; ctx.beginPath(); ctx.roundRect(-nBoxW/2, -nBoxH/2, nBoxW, nBoxH, parseInt(studioOptions.nameBorderRadius)*scale || 10); ctx.stroke(); }
        ctx.fillStyle = studioOptions.nameColor || '#8B0000'; ctx.shadowColor = 'transparent'; ctx.textAlign = studioOptions.nameTextAlign || 'center'; ctx.textBaseline = 'top'; if (studioOptions.nameTextBorderColor && studioOptions.nameTextBorderColor !== 'transparent' && studioOptions.nameTextBorderWidth > 0) { ctx.lineWidth = parseInt(studioOptions.nameTextBorderWidth) * scale; ctx.strokeStyle = studioOptions.nameTextBorderColor; ctx.lineJoin = 'round'; nameLines.forEach((line, index) => { let drawTxtX = 0; if (studioOptions.nameTextAlign === 'left') drawTxtX = -nBoxW/2 + padding; else if (studioOptions.nameTextAlign === 'right') drawTxtX = nBoxW/2 - padding; ctx.strokeText(line, drawTxtX, -nBoxH/2 + padding + (index * lineH)); }); } nameLines.forEach((line, index) => { let drawTxtX = 0; if (studioOptions.nameTextAlign === 'left') drawTxtX = -nBoxW/2 + padding; else if (studioOptions.nameTextAlign === 'right') drawTxtX = nBoxW/2 - padding; ctx.fillText(line, drawTxtX, -nBoxH/2 + padding + (index * lineH)); }); ctx.restore(); this.hitBoxes.title = { x: tX - nBoxW/2, y: tY - nBoxH/2, w: nBoxW, h: nBoxH }; } else { this.hitBoxes.title = null; }
        const priceRaw = studioOptions.priceText !== undefined ? studioOptions.priceText : (productData.price ? `${productData.price} ر.ي` : ''); if (priceRaw && studioOptions.showPriceTag && studioOptions.hidePrice !== true) { let defaultPriceX = cw / 2; let defaultPriceY = ch / 2 + 200; if (this.hitBoxes.img) { defaultPriceX = this.hitBoxes.img.x + 105; defaultPriceY = this.hitBoxes.img.y + this.hitBoxes.img.h - 15; } ctx.save(); const rot = parseFloat(studioOptions.priceRotation) || 0; const scale = parseFloat(studioOptions.priceScale) || 1.0; const pX = defaultPriceX + off.price.dx; const pY = defaultPriceY + off.price.dy; const lines = priceRaw.split('\n'); const priceFontSize = (parseInt(studioOptions.priceFontSize) || 35) * scale; ctx.font = `bold ${priceFontSize}px "${studioOptions.priceFontFamily || 'Arial'}"`; let maxW = 0; lines.forEach(l => { const w = ctx.measureText(l).width; if(w > maxW) maxW = w; }); const padding = 20 * scale; const lineH = priceFontSize * 1.4; const totalH = lines.length * lineH; const pBoxW = maxW + (padding * 2); const pBoxH = totalH + (padding * 2); ctx.translate(pX, pY); ctx.rotate((rot * Math.PI) / 180); if (studioOptions.priceStyle === 'بطاقة') { if (studioOptions.priceBgColor && studioOptions.priceBgColor !== 'transparent') { ctx.fillStyle = studioOptions.priceBgColor; ctx.shadowColor = 'rgba(0,0,0,0.3)'; ctx.shadowBlur = 10; ctx.beginPath(); ctx.roundRect(-pBoxW/2, -pBoxH/2, pBoxW, pBoxH, parseInt(studioOptions.priceBorderRadius)*scale || 10); ctx.fill(); } if (studioOptions.priceBorderColor && studioOptions.priceBorderColor !== 'transparent' && studioOptions.priceBorderWidth > 0) { ctx.shadowColor = 'transparent'; ctx.lineWidth = parseInt(studioOptions.priceBorderWidth) * scale; ctx.strokeStyle = studioOptions.priceBorderColor; ctx.beginPath(); ctx.roundRect(-pBoxW/2, -pBoxH/2, pBoxW, pBoxH, parseInt(studioOptions.priceBorderRadius)*scale || 10); ctx.stroke(); } } else if (studioOptions.priceStyle === 'شريط') { if (studioOptions.priceBgColor && studioOptions.priceBgColor !== 'transparent') { ctx.fillStyle = studioOptions.priceBgColor; ctx.shadowColor = 'rgba(0,0,0,0.3)'; ctx.shadowBlur = 10; ctx.beginPath(); ctx.moveTo(-pBoxW/2 - 10*scale, -pBoxH/2); ctx.lineTo(pBoxW/2 + 20*scale, -pBoxH/2); ctx.lineTo(pBoxW/2 + 40*scale, 0); ctx.lineTo(pBoxW/2 + 20*scale, pBoxH/2); ctx.lineTo(-pBoxW/2 - 10*scale, pBoxH/2); ctx.fill(); } if (studioOptions.priceBorderColor && studioOptions.priceBorderColor !== 'transparent' && studioOptions.priceBorderWidth > 0) { ctx.shadowColor = 'transparent'; ctx.lineWidth = parseInt(studioOptions.priceBorderWidth) * scale; ctx.strokeStyle = studioOptions.priceBorderColor; ctx.beginPath(); ctx.moveTo(-pBoxW/2 - 10*scale, -pBoxH/2); ctx.lineTo(pBoxW/2 + 20*scale, -pBoxH/2); ctx.lineTo(pBoxW/2 + 40*scale, 0); ctx.lineTo(pBoxW/2 + 20*scale, pBoxH/2); ctx.lineTo(-pBoxW/2 - 10*scale, pBoxH/2); ctx.closePath(); ctx.stroke(); } }
        ctx.fillStyle = studioOptions.priceColor || '#ffffff'; ctx.shadowColor='transparent'; ctx.textAlign = studioOptions.priceTextAlign || 'center'; ctx.textBaseline = 'top'; if (studioOptions.priceTextBorderColor && studioOptions.priceTextBorderColor !== 'transparent' && studioOptions.priceTextBorderWidth > 0) { ctx.lineWidth = parseInt(studioOptions.priceTextBorderWidth) * scale; ctx.strokeStyle = studioOptions.priceTextBorderColor; ctx.lineJoin = 'round'; lines.forEach((line, index) => { let drawTxtX = 0; if (studioOptions.priceTextAlign === 'left') drawTxtX = -pBoxW/2 + padding; else if (studioOptions.priceTextAlign === 'right') drawTxtX = pBoxW/2 - padding; ctx.strokeText(line, drawTxtX, -pBoxH/2 + padding + (index * lineH)); }); } lines.forEach((line, index) => { let drawTxtX = 0; if (studioOptions.priceTextAlign === 'left') drawTxtX = -pBoxW/2 + padding; else if (studioOptions.priceTextAlign === 'right') drawTxtX = pBoxW/2 - padding; ctx.fillText(line, drawTxtX, -pBoxH/2 + padding + (index * lineH)); }); ctx.restore(); this.hitBoxes.price = { x: pX - pBoxW/2, y: pY - pBoxH/2, w: pBoxW, h: pBoxH }; } else { this.hitBoxes.price = null; }
        if (studioOptions.customText) { const cX = cw / 2 + off.customText.dx; const cY = ch - 100 + off.customText.dy; ctx.font = 'bold 35px Arial'; ctx.fillStyle = studioOptions.textColor || '#f1c40f'; ctx.shadowColor = 'rgba(0,0,0,0.5)'; ctx.shadowBlur = 5; ctx.fillText(studioOptions.customText, cX, cY); this.hitBoxes.customText = { x: cX - 300, y: cY - 35, w: 600, h: 50 }; } else { this.hitBoxes.customText = null; }
        
        if (this.activeItem && this.activeItem.id && !studioOptions.showGridOverlay) {
            let activeBox;
            let itemState;

            if (this.activeItem.type === 'item') {
                 activeBox = this.hitBoxes[this.activeItem.id];
                 if (this.activeItem.id === 'img') itemState = { rotation: studioOptions.imageRotation };
                 if (this.activeItem.id === 'title') itemState = { rotation: studioOptions.nameRotation };
                 if (this.activeItem.id === 'price') itemState = { rotation: studioOptions.priceRotation };
                 if (this.activeItem.id === 'occasion') itemState = { rotation: studioOptions.occasionRotation };
            } else {
                 activeBox = this.placedItemsHitBoxes[this.activeItem.id];
                 itemState = this.placedItemsData.find(p => p.id === this.activeItem.id);
            }
            if (activeBox && itemState) {
                this.activeItem.rotation = itemState.rotation; 
                this.drawTransformBox(activeBox);
            }
        } else {
             this.transformHandles = {};
        }

        if (studioOptions.showGridOverlay) { ctx.save(); ctx.strokeStyle = 'rgba(0, 150, 255, 0.4)'; ctx.lineWidth = 2; ctx.setLineDash([10, 10]); ctx.beginPath(); ctx.moveTo(cw/2, 0); ctx.lineTo(cw/2, ch); ctx.stroke(); ctx.beginPath(); ctx.moveTo(0, ch/2); ctx.lineTo(cw, ch/2); ctx.stroke(); ctx.strokeStyle = 'rgba(0, 0, 0, 0.1)'; ctx.lineWidth = 1; ctx.setLineDash([]); for(let i=0; i<cw; i+=100) { ctx.beginPath(); ctx.moveTo(i, 0); ctx.lineTo(i, ch); ctx.stroke(); } for(let i=0; i<ch; i+=100) { ctx.beginPath(); ctx.moveTo(0, i); ctx.lineTo(cw, i); ctx.stroke(); } ctx.restore(); }
        ctx.restore(); return this.canvas;
    }
    async generateImage(productData, templateType, companySettings) { 
        try { 
            if (templateType === 'بلا قالب') { return await this.generateNoFrame(productData); }
            if (templateType === 'النمط الافتراضي') { return await this.generateDefaultFrame(productData); }
            let frameUrlPath = null; 
            if (companySettings) { 
                if (companySettings.templates && companySettings.templates.length > 0) { const matched = companySettings.templates.find(t => t.template_name === templateType); if (matched && matched.frame_image) frameUrlPath = matched.frame_image; } 
                if (!frameUrlPath && templateType === 'إطار مخصص (مركز الهيثم)' && companySettings.custom_frame_image) { frameUrlPath = companySettings.custom_frame_image; } 
            } 
            if (frameUrlPath) { return await this.generateCustomFrame(productData, frameUrlPath); } 
            else { return await this.generateDefaultFrame(productData); } 
        } catch (e) { return this.canvas; } 
    }
    async generateCustomFrame(productData, frameUrlPath) { 
        const frameUrl = normalizeUrl(frameUrlPath, this.baseUrl); 
        const frameImg = await this.loadImageSafely(frameUrl); 
        if (!frameImg) return await this.generateDefaultFrame(productData); 
        this.canvas.width = 1080; this.canvas.height = 1080; 
        const ctx = this.ctx; 
        ctx.fillStyle = '#ffffff'; ctx.fillRect(0, 0, 1080, 1080); 
        ctx.drawImage(frameImg, 0, 0, 1080, 1080); 
        const safeX = 70; const safeY = 140; const safeW = 1080 - 140; const safeH = 720;        
        if (productData.imageUrl) { 
            const img = await this.loadImageSafely(normalizeUrl(productData.imageUrl, this.baseUrl)); 
            if (img) {
                ctx.save(); ctx.beginPath(); ctx.roundRect(safeX, safeY, safeW, safeH, 40); ctx.shadowColor = 'rgba(0,0,0,0.3)'; ctx.shadowBlur = 15; ctx.shadowOffsetY = 8; ctx.fill(); ctx.shadowColor = 'transparent'; ctx.clip(); 
                const scale = Math.max(safeW / img.width, safeH / img.height);
                const drawW = img.width * scale; const drawH = img.height * scale;
                const drawX = safeX - (drawW - safeW) / 2; const drawY = safeY - (drawH - safeH) / 2;
                ctx.drawImage(img, drawX, drawY, drawW, drawH); ctx.restore(); 
                ctx.save(); ctx.beginPath(); ctx.roundRect(safeX, safeY, safeW, safeH, 40);
                ctx.lineWidth = 5; ctx.strokeStyle = '#ffffff'; ctx.stroke(); ctx.restore();
            }
        } 
        ctx.save(); ctx.textAlign = 'center'; ctx.textBaseline = 'top'; ctx.direction = 'rtl'; 
        const fontSize = Math.floor(1080 * 0.045); ctx.font = `900 ${fontSize}px "Arial Black", "Helvetica Neue", Arial, sans-serif`; 
        let displayText = productData.name || ''; const textX = 1080 / 2; const textY = 1080 * 0.045; 
        const textWidth = ctx.measureText(displayText).width;
        const pad = 20;
        const rectW = textWidth + pad * 2;
        const rectH = fontSize + pad;
        ctx.shadowColor = 'transparent';
        ctx.fillStyle = '#7B0F0F';
        ctx.lineWidth = 6; ctx.strokeStyle = '#ffffff'; ctx.lineJoin = 'round'; ctx.strokeText(displayText, textX, textY);
        ctx.fillText(displayText, textX, textY);
        ctx.restore(); 
        return this.canvas; 
    }
    async generateDefaultFrame(productData) { 
        this.canvas.width = this.canvasWidth; this.canvas.height = this.canvasHeight; 
        this.ctx.fillStyle = this.backgroundColor; this.ctx.fillRect(0, 0, this.canvasWidth, this.canvasHeight); 
        this.ctx.shadowColor = 'rgba(0,0,0,0.2)'; this.ctx.shadowBlur = 20; this.ctx.shadowOffsetY = 5; 
        this.ctx.strokeStyle = this.secondaryColor; this.ctx.lineWidth = 20; this.ctx.strokeRect(10, 10, this.canvasWidth - 20, this.canvasHeight - 20); 
        this.ctx.strokeStyle = this.primaryColor; this.ctx.lineWidth = 8; this.ctx.strokeRect(30, 30, this.canvasWidth - 60, this.canvasHeight - 60); 
        this.ctx.shadowColor = 'transparent'; 
        this.drawFixedHeader((productData && productData.name) || 'منتج'); 
        const headerHeight = 120; const codeBoxHeight = 90; const margin = 40; 
        const availableHeight = this.canvasHeight - headerHeight - codeBoxHeight - (margin * 2); const imageY = headerHeight + margin / 2; 
        if (productData && productData.imageUrl) { 
            const img = await this.loadImageSafely(normalizeUrl(productData.imageUrl, this.baseUrl)); 
            if(img) {
                let drawWidth = img.width; let drawHeight = img.height; const maxWidth = this.canvasWidth - 100; const imgRatio = img.width / img.height; const maxRatio = maxWidth / availableHeight; 
                if (imgRatio > maxRatio) { drawWidth = maxWidth; drawHeight = maxWidth / imgRatio; } else { drawHeight = availableHeight; drawWidth = availableHeight * imgRatio; } 
                const x = (this.canvasWidth - drawWidth) / 2; const y = imageY + (availableHeight - drawHeight) / 2; 
                this.ctx.save(); this.ctx.shadowColor = 'rgba(0,0,0,0.3)'; this.ctx.shadowBlur = 20; this.ctx.shadowOffsetY = 8; 
                this.ctx.beginPath(); this.ctx.roundRect(x, y, drawWidth, drawHeight, 20); this.ctx.closePath(); this.ctx.clip(); 
                this.ctx.fillStyle = '#ffffff'; this.ctx.fill(); this.ctx.drawImage(img, x, y, drawWidth, drawHeight); this.ctx.restore(); 
                this.ctx.strokeStyle = this.primaryColor; this.ctx.lineWidth = 4; this.ctx.beginPath(); this.ctx.roundRect(x, y, drawWidth, drawHeight, 20); this.ctx.stroke(); 
            } else { this.drawPlaceholder(imageY, availableHeight); }
        } 
        else { this.drawPlaceholder(imageY, availableHeight); } 
        this.drawFixedCodeBox((productData && productData.code) || 'غير محدد'); 
        return this.canvas; 
    }
    drawFixedHeader(productName) { const ctx = this.ctx; const maxWidth = this.canvasWidth - 100; const fontSize = this.headerFontSize; ctx.save(); ctx.fillStyle = '#7B0F0F'; ctx.textAlign = 'center'; ctx.textBaseline = 'middle'; ctx.direction = 'rtl'; ctx.font = `bold ${fontSize}px "Arial Black", "Helvetica Neue", Arial, sans-serif`; let displayText = productName; if (ctx.measureText(displayText).width > maxWidth) { while (ctx.measureText(displayText + '...').width > maxWidth && displayText.length > 10) { displayText = displayText.slice(0, -1); } displayText = displayText + '...'; } ctx.fillText(displayText, this.canvasWidth / 2, 70); ctx.strokeStyle = this.primaryColor; ctx.lineWidth = 3; ctx.beginPath(); ctx.moveTo(this.canvasWidth / 2 - 100, 105); ctx.lineTo(this.canvasWidth / 2 + 100, 105); ctx.stroke(); ctx.restore(); }
    drawPlaceholder(startY, height) { const ctx = this.ctx; const w = 400; const h = 300; const x = (this.canvasWidth - w) / 2; const y = startY + (height - h) / 2; ctx.fillStyle = '#ddd'; ctx.shadowColor = 'rgba(0,0,0,0.2)'; ctx.shadowBlur = 10; ctx.shadowOffsetY = 5; ctx.fillRect(x, y, w, h); ctx.shadowColor = 'transparent'; ctx.fillStyle = '#888'; ctx.textAlign = 'center'; ctx.font = '30px Arial'; ctx.fillText('لا توجد صورة', this.canvasWidth / 2, y + h / 2); }
    drawFixedCodeBox(code) { const ctx = this.ctx; const maxBoxWidth = this.canvasWidth - 60; let fontSize = this.codeFontSize; const codeText = 'كود المنتج: ' + code; const boxPadding = 30; ctx.save(); ctx.font = `bold ${fontSize}px Arial`; let textWidth = ctx.measureText(codeText).width; while (textWidth + boxPadding * 2 > maxBoxWidth && fontSize > 18) { fontSize -= 2; ctx.font = `bold ${fontSize}px Arial`; textWidth = ctx.measureText(codeText).width; } const boxWidth = Math.min(Math.max(textWidth + boxPadding * 2, 350), maxBoxWidth); const boxHeight = Math.max(70, fontSize + 40); const boxX = (this.canvasWidth - boxWidth) / 2; const boxY = this.canvasHeight - 100; ctx.shadowColor = 'rgba(0,0,0,0.3)'; ctx.shadowBlur = 15; ctx.shadowOffsetY = 5; ctx.fillStyle = 'rgba(0,0,0,0.85)'; ctx.beginPath(); ctx.roundRect(boxX, boxY, boxWidth, boxHeight, 35); ctx.fill(); ctx.strokeStyle = this.primaryColor; ctx.lineWidth = 4; ctx.stroke(); ctx.shadowColor = 'rgba(0,0,0,0.5)'; ctx.shadowBlur = 4; ctx.shadowOffsetY = 2; ctx.font = `bold ${fontSize}px Arial`; ctx.fillStyle = this.primaryColor; ctx.textAlign = 'left'; ctx.textBaseline = 'middle'; ctx.fillText(codeText, boxX + boxPadding, boxY + boxHeight / 2); ctx.restore(); }
}


return {ProductImageGenerator,phrases:HEC_PHRASE_BANKS,marketing:smartMarketingEngine};
})();
