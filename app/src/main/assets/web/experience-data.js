'use strict';
/* Video-derived catalog additions. Existing IDs remain stable across updates. */
HEC.products.push(...[
 ['N681012','صحن مدور مشرّم 681012','plate-white.jpg',1000,'سيراميك وميلامين'],
 ['N009','صحن ميلامين بيج حزام 009','plate-floral.jpg',250,'سيراميك وميلامين'],
 ['N12','طقم ملاعق طبخ سيليكون 12 قطعة','utensils.jpg',5000,'أدوات مساعدة للمطبخ'],
 ['N250','فرش تقشير وتنظيف متعدد الاستخدام','peeler.jpg',250,'أدوات مساعدة للمطبخ'],
 ['N8051','سلة صحون صغيرة دورين استيل MONSOON','rack-metal.jpg',4000,'متعلق بالمعدن'],
 ['N27','صحن تقديم أكريليك مع الغطاء 27 سم','dish-cover.jpg',1400,'زجاجيات'],
 ['N8235','مقص ممتاز ملون مسمار نحاس 8235','scissors.jpg',700,'أدوات مساعدة للمطبخ']
].map(([id,name,image,price,subcategory])=>({id,name,image,price,subcategory,category:'أدوات المطبخ',brand:id==='N8051'?'MONSOON':'الهيثم',fresh:true,offer:id==='N250',unit:'حبة',description:name+' — من تشكيلة المنتجات الظاهرة في المرجع.'})));
HEC.campaigns=[
 {id:'golden',title:'الساعة الذهبية',image:'golden-plates.jpg',ids:['N681012','N009','N27','TR006','K0650','J0350'],duration:51*86400000},
 {id:'kitchen',title:'عروض أدوات المطبخ',image:'banner-discount.jpg',ids:['CA015','P1001','N12','N8051','FLASK','KJ3052'],duration:7*86400000},
 {id:'care',title:'العروض المميزة',image:'banner-grooming.jpg',ids:['A79234','SO1929','N250'],duration:14*86400000}
];
HEC.homeCampaigns=[
 ['campaign-new.jpg','وصل حديثاً','catalog/new'],['campaign-shop.jpg','تسوق الآن','shop'],
 ['campaign-limited.jpg','عروض لفترة محدودة','offers'],['campaign-affiliate.jpg','التسويق بالعمولة','affiliate'],
 ['campaign-growth.jpg','ضاعف مبيعاتك','affiliate'],['campaign-global.jpg','منتجات على المتجر','innovative']
];
HEC.homeSections=[
 {name:'أدوات المطبخ',banner:'banner-kitchen.jpg',children:HEC.departments[0].children.filter(x=>x[0]!=='وصل حديثاً')},
 {name:'منتجات على المتجر',banner:'campaign-global.jpg',children:[['مبتكرة','cat-innovative.jpg']]},
 {name:'أجهزة وإلكترونيات',banner:'banner-vacuum.jpg',children:HEC.departments[3].children.filter(x=>x[0]!=='وصل حديثاً')},
 {name:'أدوات الكيك',banner:'banner-kitchen.jpg',children:[['أدوات الكيك','cat-baking.jpg'],['قوالب الكيك','jars.jpg'],['أدوات التقديم','knives.jpg']]},
 {name:'بلاستيكية',banner:'banner-scrub.jpg',children:[['سلات بلاستيك كبيرة','cat-basket.jpg'],['سلات خضار أربع طبقات','cat-rack-plastic.jpg'],['كراسي مطبخ','hec-product.jpg']]},
 {name:'دراجات هوائية وسيارات كهربائية',banner:'banner-bikes.jpg',children:[['اسكوتر','cat-scooter.jpg'],['دراجات أطفال','hec-product.jpg'],['سيارات أطفال','cat-toys.jpg']]},
 {name:'منظفات',banner:'banner-cleaning.jpg',children:[['منظفات بلاط وأرضيات','cat-floor-cleaner.jpg'],['منظفات الملابس','hec-product.jpg'],['منظفات الزجاج','hec-product.jpg']]},
 {name:'مفروشات',banner:'banner-fragrance.jpg',children:[['دعسات مطبخ','hec-product.jpg'],['دعسات متنوعة','cat-rug.jpg'],['دعسات أبواب','hec-product.jpg']]}
];
for(const s of HEC.homeSections)if(!HEC.departments.some(d=>d.name===s.name))HEC.departments.push({name:s.name,image:s.children[0][1],banner:s.banner,children:s.children});
HEC.categories=[...new Set([...HEC.categories,...HEC.homeSections.map(s=>s.name),...HEC.products.map(p=>p.subcategory)])];
/* Replace only with owner-verified destinations before distribution. Never infer account URLs. */
HEC.externalLinks={youtube:'',facebook:'https://www.facebook.com/HaithemEkhwanCenter/',instagram:'',whatsapp:'',play:''};
HEC.notifications=[{id:'welcome',title:'أهلاً بك في متجر الهيثم',body:'تصفح الأقسام والعروض واحفظ منتجاتك المفضلة. هذه معاينة محلية؛ الطلبات لا تُرسل بعد.',route:'home'}];

HEC.promoGroups={'أدوات المطبخ':['banner-kitchen.jpg','banner-cookware.jpg','banner-discount.jpg'],'أجهزة وإلكترونيات':['banner-vacuum.jpg','banner-irons.jpg'],'دراجات هوائية وسيارات كهربائية':['banner-bikes.jpg','banner-kids-cars.jpg']};
