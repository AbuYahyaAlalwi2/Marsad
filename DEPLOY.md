# نشر marsad-agent-loop على Cloudflare Workers (من Termux)

## 0. المتطلبات (مرة واحدة فقط)
```bash
pkg install nodejs -y      # لو node غير مثبّت أصلاً
cd ~/marsad-cf-worker       # بعد نقل المجلد كاملاً لهنا (راجع تعليمات النقل أدناه)
npm install
npx wrangler login          # يفتح رابطاً — سجّل دخول بحساب Cloudflare (مجاني)
```

## 1. إنشاء مساحة KV (لتخزين حالة محرك التصعيد بدل الذاكرة)
```bash
npx wrangler kv namespace create MARSAD_KV
```
سيعطيك سطراً فيه `id = "...."` — انسخ القيمة والصقها في `wrangler.toml` مكان
`REPLACE_WITH_KV_NAMESPACE_ID`.

## 2. ضبط الأسرار (كل مفتاح تملكه فعلاً — لا حاجة لكل المزوّدين معاً)
```bash
npx wrangler secret put E2B_API_KEY
npx wrangler secret put DEEPSEEK_API_KEY
npx wrangler secret put GROQ_API_KEY
npx wrangler secret put OPENROUTER_API_KEY
npx wrangler secret put GOOGLE_API_KEY
npx wrangler secret put HF_API_KEY
npx wrangler secret put RAILWAY_INGEST_URL
```
كل أمر يسألك عن القيمة في سطر منفصل (آمن — لا تُحفظ في أي ملف أو تاريخ أوامر).
لو مزوّد ما غير متاح لديك الآن، تجاهل سطره — المنطق يتخطى تلقائياً أي مزوّد
بلا مفتاح (نفس سلوك `available` في النسخة الأصلية).

## 3. التحقق محلياً قبل النشر (اختياري لكن موصى به)
```bash
npx tsc --noEmit    # تأكيد خلو الكود من أخطاء الأنواع
```

## 4. النشر الفعلي
```bash
npx wrangler deploy
```
بعدها الـ Worker يعمل تلقائياً كل دقيقة عبر Cron Trigger — بلا أي حاجة لإبقاء
Termux أو الهاتف مفتوحاً، بعكس Kaggle تماماً. هذا يحل مشكلة القتل القسري
جذرياً لأنه لا يوجد process طويل العمر يمكن أن "يُقتل" أصلاً — كل تشغيل دورة
واحدة قصيرة ومستقلة، تماماً كما صُممت Workers لتُستخدم.

## 5. المراقبة الحية (بديل Telegram/اللوغ اليدوي)
```bash
npx wrangler tail
```
يعرض كل سطر `console.log` من كل دورة لحظياً — هذا يحل محل سحب لوغ Kaggle يدوياً.

## 6. اختبار دورة واحدة فورية بدون انتظار الدقيقة القادمة
```bash
curl https://marsad-agent-loop.<اسم-حسابك-في-cloudflare>.workers.dev/
```
(الرابط الدقيق يظهر في مخرجات `wrangler deploy`)

## تعديل وتيرة التشغيل
غيّر `crons = ["* * * * *"]` في `wrangler.toml` حسب الحاجة، ثم أعد `wrangler deploy`:
- `"*/2 * * * *"` كل دقيقتين
- `"*/5 * * * *"` كل 5 دقائق

## ملاحظة Workers المجانية مقابل المدفوعة
الخطة المجانية (Free) تكفي للتجربة ولمعدل منخفض من الدورات — القيد الوحيد هو
وقت CPU الفعلي لكل استدعاء (لا وقت الانتظار الشبكي، وهذا معظم وقت كل دورة
هنا). لو واجهت رسالة "Exceeded CPU time limit" في `wrangler tail`، فهذا مؤشر
للترقية لخطة Workers Paid ($5/شهر) التي ترفع الحد بشكل كبير — غير مرتبط إطلاقاً
بخطر الحظر الذي كان يحدث مع Kaggle، هذا مجرد حد موارد عادي وشفاف.
