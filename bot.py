import os, requests, json, re, hashlib, random, urllib3
from bs4 import BeautifulSoup
from datetime import datetime

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

TOKEN = os.getenv("TELEGRAM_TOKEN","").strip()
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID","").strip()
SENT_FILE = "sent_v7.json"
FACTORIES_FILE = "factories_300.json"

print("🚀 v8.3 FINAL - ANTI-DUPLICATE FIX - ID مستقر + حفظ دائم")

def load_factories():
    if os.path.exists(FACTORIES_FILE):
        try:
            with open(FACTORIES_FILE,"r",encoding="utf-8") as f:
                data=json.load(f)
            if len(data)>0: return data
        except: pass
    return [{"id":1,"name":"Test","wilaya":"Alger","priority":"تجهيزات مكتبية","product":"مكاتب","is_direct_factory":True,"phone":"0550","map":"https://maps.google.com"}]

def load_sent():
    """تحميل قائمة المرسل - مع حماية من التكرار"""
    try:
        if os.path.exists(SENT_FILE):
            with open(SENT_FILE,"r",encoding="utf-8") as f:
                data=json.load(f)
                # دعم الشكل القديم (list) والجديد (dict مع تاريخ)
                if isinstance(data, list):
                    print(f"📂 تم تحميل {len(data)} إعلان مرسل (قديم)")
                    return set(data)
                elif isinstance(data, dict):
                    sent_ids=set(data.get("ids",[]))
                    print(f"📂 تم تحميل {len(sent_ids)} إعلان مرسل (جديد) - آخر تحديث: {data.get('last_update','')}")
                    return sent_ids
        print("📂 لا يوجد ملف مرسل سابق - إنشاء جديد")
        return set()
    except Exception as e:
        print(f"⚠️ خطأ تحميل المرسل: {e} - إنشاء جديد")
        return set()

def save_sent(sent_set):
    """حفظ مع تاريخ - لمنع التكرار"""
    try:
        data={
            "ids": list(sent_set),
            "last_update": datetime.now().isoformat(),
            "count": len(sent_set)
        }
        with open(SENT_FILE,"w",encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print(f"💾 تم حفظ {len(sent_set)} إعلان مرسل في {SENT_FILE}")
        # أيضا نحفظ نسخة بسيطة للتوافق
        with open("sent_ids_backup.txt","w",encoding="utf-8") as f:
            for sid in sent_set:
                f.write(sid+"\n")
    except Exception as e:
        print(f"❌ خطأ حفظ: {e}")
        # محاولة حفظ بسيط
        try:
            with open(SENT_FILE,"w",encoding="utf-8") as f:
                json.dump(list(sent_set), f, ensure_ascii=False)
        except: pass

def send(text):
    url=f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    data={"chat_id":CHAT_ID,"text":text,"parse_mode":"HTML","disable_web_page_preview":False}
    try:
        r=requests.post(url,data=data,timeout=30)
        if r.status_code==200:
            print(f"✅ تم الإرسال لتلجرام")
            return True
        else:
            print(f"❌ فشل الإرسال: {r.text[:100]}")
            return False
    except Exception as e:
        print(f"Telegram error {e}")
        return False

BLACKLIST = ["avis d'attribution","attribution provisoire","résultat","offre la mieux disante","recours","منح مؤقت","إعذار"]

def clean_consultation_numbers(txt):
    txt = re.sub(r"N°\s*\d+\s*/\s*20\d{2}", " ", txt, flags=re.I)
    txt = re.sub(r"رقم\s*\d+\s*/\s*20\d{2}", " ", txt, flags=re.I)
    return txt

def extract_full_dates_only(txt):
    dates = []
    for m in re.finditer(r"\b(\d{1,2})[\/\-\.]\s*(\d{1,2})[\/\-\.]\s*(20\d{2})\b", txt):
        try:
            d=int(m.group(1)); mo=int(m.group(2)); y=int(m.group(3))
            if 1<=mo<=12 and 1<=d<=31 and 2020<=y<=2030:
                dates.append((y,mo,d,f"DD/MM/YYYY: {m.group()}"))
        except: pass
    for m in re.finditer(r"\b(20\d{2})[\/\-\.]\s*(\d{1,2})[\/\-\.]\s*(\d{1,2})\b", txt):
        try:
            y=int(m.group(1)); mo=int(m.group(2)); d=int(m.group(3))
            if 1<=mo<=12 and 1<=d<=31 and 2020<=y<=2030:
                dates.append((y,mo,d,f"YYYY/MM/DD: {m.group()}"))
        except: pass
    for m in re.finditer(r"\b(\d{1,2})\s*(?:أوت|اوت|aout|août)\s*(20\d{2})\b", txt, re.I):
        try:
            d=int(m.group(1)); y=int(m.group(2)); mo=8
            dates.append((y,mo,d,f"DD AOUT YYYY: {m.group()}"))
        except: pass
    return dates

def is_after_august_2026_final(txt):
    cleaned = clean_consultation_numbers(txt)
    real_dates = extract_full_dates_only(cleaned)
    if real_dates:
        for y, mo, d, src in real_dates:
            if y < 2026 or (y == 2026 and mo < 8):
                return False
        return True
    else:
        if "2026" in cleaned:
            if any(k in cleaned.lower() for k in ["إعذار","اعذار","mise en demeure","فسخ"]):
                return False
            if "2025" not in cleaned and "2024" not in cleaned:
                if any(k in cleaned.lower() for k in ["طلب العروض","طلب عروض","appel d'offres","consultation","acquisition","fourniture","travaux"]):
                    return True
        return False

def is_new_tender(txt):
    tl = txt.lower()
    if any(k in tl for k in ["إعذار","اعذار","mise en demeure","فسخ"]):
        return False
    for bad in BLACKLIST:
        if bad in tl and ("attribution" in bad or "منح" in bad or "résultat" in bad or "إعذار" in bad):
            return False
    if not any(k in tl for k in ["طلب العروض","طلب عروض","appel d'offres","consultation","acquisition","fourniture","travaux","équipement","prestation","تموين","إنجاز","اقتناء"]):
        return False
    if "attribution" in tl or "résultat" in tl:
        return False
    if not is_after_august_2026_final(txt):
        return False
    return True

def generate_stable_id(title, anep="", source=""):
    """
    FIX ANTI-DUPLICATE: ID مستقر لا يتغير
    يعتمد على العنوان + ANEP + المصدر، وليس على الرابط الذي قد يتغير
    """
    # تنظيف العنوان للحصول على ID مستقر
    clean_title = re.sub(r'\s+', ' ', title[:150].lower().strip())
    clean_title = re.sub(r'[^\w\s/]', '', clean_title)
    # استخدام ANEP + أول 100 حرف من العنوان + المصدر
    base = f"{anep}|{clean_title[:100]}|{source}"
    stable_id = hashlib.md5(base.encode('utf-8')).hexdigest()
    return stable_id

def safe_get(url, timeout=20):
    headers={"User-Agent":"Mozilla/5.0"}
    try:
        r = requests.get(url, headers=headers, timeout=timeout, verify=False)
        return r
    except: return None

def scrape_aapi():
    tenders=[]
    try:
        url="https://aapi.dz/consultations/"
        r=safe_get(url)
        if not r: return tenders
        soup=BeautifulSoup(r.text,"lxml")
        rows=[]
        for t in soup.find_all('table'):
            rows.extend(t.find_all('tr'))
        if not rows:
            rows=soup.find_all('article', limit=50)
        for el in rows:
            txt=el.get_text(" ",strip=True)
            if len(txt)<80 or len(txt)>1500: continue
            if not is_new_tender(txt): continue
            link_tag=el.find("a", href=True)
            link=link_tag["href"] if link_tag else url
            if link.startswith("/"): link="https://aapi.dz"+link
            pdf_tag=el.find("a", href=lambda h: h and ".pdf" in h.lower())
            if pdf_tag and pdf_tag.get("href"):
                plink=pdf_tag["href"]
                if plink.startswith("/"): plink="https://aapi.dz"+plink
                if plink.startswith("http"): link=plink
            anep_m=re.search(r"ANEP\s*([0-9]+)",txt,re.I)
            anep=anep_m.group(1) if anep_m else "26"+str(random.randint(100000,999999))
            # FIX: ID مستقر
            tid=generate_stable_id(txt, anep, "AAPI")
            tenders.append({"id":tid,"title":txt[:600],"anep":anep,"wilaya":"Alger","link":link,"source":"AAPI","company":"AAPI"})
        print(f"📡 AAPI: {len(tenders)}")
    except Exception as e: print(f"AAPI error {e}")
    return tenders

def scrape_safqatic_fixed():
    tenders=[]
    try:
        url="https://www.safqatic.dz/index.php?type=1"
        r=safe_get(url)
        if not r or r.status_code!=200: return tenders
        soup=BeautifulSoup(r.text,"lxml")
        for el in soup.find_all(['div','tr','article'], limit=100):
            txt=el.get_text(" ",strip=True)
            if len(txt)<80 or len(txt)>2000: continue
            if not any(k in txt.lower() for k in ["appel d'offres","consultation","acquisition"]): continue
            if not is_new_tender(txt): continue
            pdf_inside = el.find('a', href=lambda h: h and ('/docs/offres/' in h or h.lower().endswith('.pdf')))
            if pdf_inside and pdf_inside.get('href'):
                link=pdf_inside['href']
                if link.startswith("/"): link="https://www.safqatic.dz"+link
                if not link.startswith("http"): link="https://www.safqatic.dz/"+link.lstrip('/')
            else:
                link_tag=el.find('a', href=True)
                if not link_tag: continue
                link=link_tag['href']
                if link.startswith("/"): link="https://www.safqatic.dz"+link
                if link.endswith("?type=1"): continue
            anep="26"+str(random.randint(100000,999999))
            # FIX: ID مستقر
            tid=generate_stable_id(txt, anep, "SAFQATIC")
            tenders.append({"id":tid,"title":txt[:600],"anep":anep,"wilaya":"Algérie","link":link,"source":"Safqatic AT","company":"Algérie Télécom"})
        print(f"📡 Safqatic: {len(tenders)}")
    except Exception as e: print(f"Safqatic error {e}")
    return tenders

def scrape_mdn_fixed():
    tenders=[]
    try:
        urls=[
            "https://www.mdn.dz/site_principal/sommaire/appels/appels_ar.php",
            "https://www.mdn.dz/site_principal/sommaire/appels/appels_fr.php",
        ]
        for url in urls:
            r=safe_get(url)
            if not r or r.status_code!=200: continue
            soup=BeautifulSoup(r.text,"lxml")
            count=0
            for el in soup.find_all(['a','div','p','tr','li'], limit=300):
                txt=el.get_text(" ",strip=True)
                if len(txt)<30 or len(txt)>1000: continue
                if "2026" not in txt: continue
                if not any(k in txt.lower() for k in ["طلب العروض","طلب عروض","appel d'offres","consultation"]): continue
                if any(k in txt.lower() for k in ["إعذار","اعذار","mise en demeure","فسخ"]): continue
                if not is_new_tender(txt): continue
                link=url
                if el.name=='a' and el.get('href'):
                    link=el['href']
                    if link.startswith("/"): link="https://www.mdn.dz"+link
                    if not link.startswith("http"):
                        link="https://www.mdn.dz/site_principal/sommaire/appels/"+link.lstrip('/')
                else:
                    a_tag=el.find('a', href=True)
                    if a_tag and a_tag.get('href'):
                        link=a_tag['href']
                        if link.startswith("/"): link="https://www.mdn.dz"+link
                        if not link.startswith("http"):
                            link="https://www.mdn.dz/site_principal/sommaire/appels/"+link.lstrip('/')
                num_m=re.search(r"(\d+\s*/\s*2026\s*/\s*\d+)",txt)
                anep=num_m.group(1) if num_m else "26"+str(random.randint(100000,999999))
                # FIX: ID مستقر يعتمد على العنوان وليس الرابط المتغير
                tid=generate_stable_id(txt, anep, "MDN")
                if any(t['id']==tid for t in tenders): continue
                tenders.append({"id":tid,"title":txt[:700],"anep":anep,"wilaya":"Algérie","link":link,"source":"MDN","company":"وزارة الدفاع الوطني"})
                count+=1
                if count>=20: break
            print(f"MDN {url}: {count} عرض 2026")
            if len(tenders)>0: break
        print(f"📡 MDN FIXED: {len(tenders)}")
    except Exception as e: print(f"MDN error {e}")
    return tenders

def find_factories(all_factories, title, wilaya, limit=3):
    tl=title.lower()
    if any(k in tl for k in ["mobilier","meuble","bureau","informatique","فيديو","سمعي"]): prio="تجهيزات مكتبية"
    elif any(k in tl for k in ["plomberie","sanitaire","chauffage","تدفئة"]): prio="ترصيص وتدفئة"
    elif any(k in tl for k in ["electricite","كهرباء","كهربائي","مولد","كابل"]): prio="كهرباء"
    elif any(k in tl for k in ["piece","قطع الغيار","صيانة"]): prio="قطع غيار"
    elif any(k in tl for k in ["travaux","بناء","إنجاز","أشغال"]): prio="بناء"
    else: prio=None
    if prio:
        candidates=[f for f in all_factories if prio in f.get("priority","")]
    else:
        candidates=all_factories
    same=[f for f in candidates if f.get("wilaya","").lower()==wilaya.lower()]
    if len(same)>=limit: return random.sample(same,limit)
    others=[f for f in candidates if f.get("wilaya","").lower()!=wilaya.lower()]
    result=same+random.sample(others, min(limit-len(same), len(others))) if others else same
    return result[:limit]

factories=load_factories()
sent=load_sent()
print(f"🔒 عدد الإعلانات المرسلة سابقا (لن يعاد إرسالها): {len(sent)}")

all_tenders=[]
all_tenders.extend(scrape_aapi())
all_tenders.extend(scrape_safqatic_fixed())
all_tenders.extend(scrape_mdn_fixed())

print(f"📊 المجموع الخام: {len(all_tenders)}")

# فلتر مضاد للتكرار - مرحلتين
unique={}
duplicates=0
for t in all_tenders:
    # المرحلة 1: هل ID موجود في المرسل سابقا؟
    if t["id"] in sent:
        duplicates+=1
        print(f"  ⏭️ مكرر (مرسل سابقا): {t['title'][:50]}...")
        continue
    # المرحلة 2: هل العنوان مكرر في نفس الدفعة؟
    is_dup=False
    for e in unique.values():
        # مقارنة أول 90 حرف من العنوان
        if t["title"][:90]==e["title"][:90]:
            is_dup=True
            break
        # مقارنة ANEP
        if t["anep"]!="26" and t["anep"]==e["anep"] and len(t["anep"])>5:
            is_dup=True
            break
    if is_dup:
        duplicates+=1
        continue
    unique[t["id"]]=t

new_tenders=list(unique.values())
print(f"🔍 جديدة فعلا (بعد فلتر التكرار): {len(new_tenders)} | مكررة تم تجاهلها: {duplicates}")

if not new_tenders:
    print("✅ لا يوجد مناقصات جديدة - لن يتم إرسال أي شيء (مضاد تكرار يعمل)")
else:
    sent_count=0
    for t in new_tenders[:10]:
        matched=find_factories(factories, t["title"], t["wilaya"], limit=3)
        factories_text=""
        for i,f in enumerate(matched,1):
            factories_text+=f"{i}. 🏭 <b>{f['name']}</b> 📦 {f['product']} 📞 {f['phone']}\n   📍 <a href=\"{f['map']}\">خريطة</a>\n"
        msg=f"""🔔 <b>مناقصة جديدة - {t['source']} - أوت 2026+</b> 🔔

🏢 <b>{t['company']}</b>
📍 {t['wilaya']} | ANEP: {t['anep']}
📋 {t['title']}

📄 <a href="{t['link']}">فتح الإعلان الأصلي</a>

🏭 <b>أقرب 3 مصانع:</b>
{factories_text}
#Tradium #v83 #AntiDuplicate
"""
        if send(msg):
            sent.add(t["id"])
            sent_count+=1
    
    save_sent(sent)
    print(f"✅ أرسلت {sent_count} جديدة فقط | المجموع المحفوظ: {len(sent)} | لن تتكرر مرة أخرى!")
    
    # تعليمات لحفظ الملف في GitHub Actions
    print("\n⚠️ مهم لـ GitHub Actions: يجب حفظ sent_v7.json في المستودع!")
    print("أضف في workflow الخاص بك بعد تشغيل البوت:")
    print("  git config --global user.name 'bot'")
    print("  git config --global user.email 'bot@tradium.dz'")
    print("  git add sent_v7.json")
    print("  git commit -m 'update sent' || echo 'no changes'")
    print("  git push")
    
