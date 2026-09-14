/* Local catalog adapter. No server calls or credentials in phase 1. Prices are reference fixtures. */
'use strict';
window.HEC = {
 products: [
  {id:'A79234',name:'مكينة حلاقة DSP90314 وات 3',price:6000,image:'clipper.jpg',detail:'clipper-detail.jpg',category:'العناية الشخصية',brand:'دي إس بي',offer:true,fresh:true,unit:'حبة',description:'مكينة حلاقة DSP 90314 مع ملحقات للعناية بالشعر.'},
  {id:'KJ3052',name:'قطاعة شيبس شرائح وخضار دي إس بي 3 في 1',price:6000,image:'slicer.jpg',category:'أدوات المطبخ',brand:'دي إس بي',fresh:true,noNewBadge:true,unit:'حبة',description:'قطاعة شرائح وخضار 3 في 1، مع ثلاثة ملحقات لتحضير الخضار.'},
  {id:'CA015',name:'طقم حلل 12 قطعة دي إس بي',price:50000,image:'pots.jpg',category:'أدوات المطبخ',brand:'دي إس بي',unit:'طقم',description:'طقم أواني طبخ من 12 قطعة بأغطية زجاجية.'},
  {id:'P1001',name:'طقم صواني دائري',price:3000,image:'pans.jpg',category:'أدوات المطبخ',brand:'الهيثم',unit:'طقم',description:'مجموعة صوانٍ دائرية بأحجام متعددة.'},
  {id:'K0650',name:'طقم سكين مع رافعة كيك',price:650,image:'knives.jpg',category:'أدوات المطبخ',brand:'الهيثم',unit:'طقم',description:'طقم تقديم للحلويات يتكون من سكين ورافعة كيك.'},
  {id:'J0350',name:'قوالب كعك استيل 3 × 1 باكت',price:350,image:'jars.jpg',category:'أدوات المطبخ',brand:'الهيثم',unit:'حبة',description:'قوالب لتحضير الكعك والحلويات.'}
  ,{id:'TR006',name:'صحن ميلامين مربع 006',price:200,image:'tray.jpg',category:'أدوات المطبخ',subcategory:'سيراميك وميلامين',brand:'الهيثم',unit:'حبة',description:'صحن ميلامين مربع موديل 006.'}
  ,{id:'KT50B',name:'فرن كهرباء 50 لتر KT50B دي إس بي',price:61000,image:'oven.jpg',category:'أجهزة كهربائية',subcategory:'مايكروويف وأفران',brand:'دي إس بي',unit:'حبة',description:'فرن كهربائي دي إس بي KT50B بسعة 50 لتراً.'}
  ,{id:'TH903',name:'ثلاجة شاي لتر 903 ملون',price:4000,image:'thermos.jpg',category:'أدوات المطبخ',subcategory:'أدوات مساعدة للمطبخ',brand:'الهيثم',unit:'حبة',description:'ثلاجة شاي ملونة موديل 903 بسعة لتر.'}
  ,{id:'FLASK',name:'ثلاجات شاي ملون أبو فيل',price:2500,image:'flask.jpg',category:'أدوات المطبخ',subcategory:'أدوات مساعدة للمطبخ',brand:'أبو فيل',unit:'حبة',variants:[{id:'small',label:'أبيض - صغير',price:2500},{id:'large',label:'أبيض - 1.3 لتر',price:5000}],description:'ثلاجة شاي أبو فيل باللون الأبيض. اختر الحجم المناسب قبل الإضافة إلى السلة.'}
  ,{id:'SO1929',name:'ملمس 230 درجة سوكاني 1929',price:8712,image:'straightener.jpg',category:'العناية الشخصية',brand:'سوكاني',unit:'حبة',description:'ملمس شعر سوكاني 1929 بدرجة حرارة حتى 230 درجة.'}
  ,{id:'M1010',name:'ميلامين صحي حراري 1010',price:650,image:'hec-product.jpg',category:'أدوات المطبخ',subcategory:'سيراميك وميلامين',brand:'غير مصنف',unit:'حبة',description:'ميلامين صحي حراري موديل 1010.'}
 ],
 categories:['الكل','أدوات المطبخ','العناية الشخصية','أجهزة كهربائية','سيراميك وميلامين','زجاجيات','أدوات الهدايا والزينة','وصل حديثاً'],
 money:n=>new Intl.NumberFormat('en-US').format(n)+' ر.ي',
 repository:{async listProducts(){return window.HEC.products},async submitOrder(){throw new Error('الطلبات الحقيقية غير متاحة قبل ربط المتجر.')}}
};

HEC.products.forEach(p=>{if(!p.subcategory)p.subcategory=p.id==='J0350'?'أدوات الكيك':p.category==='أدوات المطبخ'?'متعلق بالمعدن':p.category==='العناية الشخصية'?'العناية الشخصية':'أجهزة خفيفة'});
HEC.departments=[
 {name:'أدوات المطبخ',image:'cat-kitchen.jpg',banner:'banner-kitchen.jpg',children:[['وصل حديثاً','cat-new.jpg'],['سيراميك وميلامين','cat-ceramic.jpg'],['زجاجيات','cat-glass.jpg'],['أدوات البهارات والزيت','cat-spices.jpg'],['بلاستيكية','cat-plasticware.jpg'],['أدوات مساعدة للمطبخ','cat-kitchen-tools.jpg'],['علب الزيت والعسل','cat-honey.jpg'],['متعلق بالمعدن','cat-metal.jpg']]},
 {name:'منتجات على المتجر',image:'cat-global.jpg',banner:'washers.jpg',children:[['كل المنتجات','cat-global.jpg']]},
 {name:'وصل حديثاً',image:'cat-new.jpg',banner:'banner-discount.jpg',children:[['وصل حديثاً','cat-new.jpg']]},
 {name:'أجهزة وإلكترونيات',image:'cat-electronics.jpg',banner:'banner-electronics.jpg',children:[['وصل حديثاً','cat-new.jpg'],['مراوح ومكيفات','cat-fans.jpg'],['شاشات وأفران','cat-screens.jpg'],['كنسات وكوايات','cat-irons.jpg'],['العناية الشخصية','cat-personal.jpg'],['أجهزة خفيفة','cat-small.jpg'],['مايكروويف وأفران','cat-ovens.jpg'],['غسالات وثلاجات','cat-washers.jpg']]},
 {name:'أدوات الكيك',image:'cat-baking.jpg',banner:'banner-cookware.jpg',children:[['أدوات الكيك','jars.jpg']]},
 {name:'بلاستيكية',image:'cat-plastic.jpg',banner:'banner-kitchen.jpg',children:[['بلاستيكية','cat-plasticware.jpg']]},
 {name:'ألعاب',image:'cat-toys.jpg',banner:'banner-kitchen.jpg',children:[['ألعاب','cat-toys.jpg']]}
];
