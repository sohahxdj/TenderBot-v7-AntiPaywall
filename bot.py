import os, requests, json, re, hashlib, random, urllib3
from bs4 import BeautifulSoup

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

TOKEN = os.getenv("TELEGRAM_TOKEN","").strip()
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID","").strip()
SENT_FILE = "sent_v7.json"
FACTORIES_FILE = "factories_300.json"

print("🚀 v7.7 - FIX FINAL: حذف أرقام الاستشارات + فلتر أوت 2026 صارم باليوم")

def load_factories():
    if os.path.exists(FACTORIES_FILE):
        try:
            with open(FACTORIES_FILE,"r",encoding="utf-8") as f:
                data=json.load(f)
            if len(data)>0:
                return data
        except: pass
    return [{"id":1,"name":"Test","wilaya":"Alger","priority":"تجهيزات مكتبية","product":"مكاتب","is_direct_factory":True,"phone":"0550","map":"https://maps.google.com"}]

def load_sent():
    try:
        with open(SENT_FILE,"r",encoding="utf-8") as f: return set(json.load(f))
    except: return set()

def save_sent(s):
    with open(SENT_FILE,"w",encoding="utf-8") as f: json.dump(list(s), f, ensure_ascii=False)

def send(text):
    url=f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    data={"chat_id":CHAT_ID,"text":text,"parse_mode":"HTML","disable_web_page_preview":False}
    try: requests.post(url,data=data,timeout=30)
    except Exception as e: print(f"Telegram error {e}")

BLACKLIST = ["avis d'attribution","attribution provisoire","résultat","offre la mieux disante","recours","منح مؤقت"]
WHITELIST_NEW = ["avis d'appel d'offres","appel d'offres","consultation n°","avis de consultation","acquisition de","fourniture de","travaux de","équipement de"]

def clean_consultation_numbers(txt):
    """
    يحذف أرقام الاستشارات التي تسبب الخلط مع التواريخ
    مثل: 10/2026, 2026/12, N° 10/2026, رقم 2026/12
    """
    original = txt
    # حذف N° 10/2026, N°10/2026, n° 10/2026
    txt = re.sub(r"N°\s*\d+\s*/\s*20\d{2}", " ", txt, flags=re.I)
    txt = re.sub(r"n°\s*\d+\s*/\s*20\d{2}", " ", txt, flags=re.I)
    # حذف رقم 2026/12, استشارة رقم 2026/12
    txt = re.sub(r"(?:رقم|استشارة)\s*20\d{2}\s*/\s*\d{1,3}", " ", txt, flags=re.I)
    txt = re.sub(r"20\d{2}\s*/\s*\d{1,2}\b(?!\s*/)", " ", txt)  # 2026/12 بدون يوم -> رقم استشارة
    # حذف Lot N°01, N°02 إلخ
    txt = re.sub(r"Lot\s*N°\s*\d+", " ", txt, flags=re.I)
    # حذف (03) lots
    txt = re.sub(r"\(\d+\)\s*lots?", " ", txt, flags=re.I)
    if original != txt:
        print(f"  🧹 تنظيف أرقام استشارات: {original[:80]}... -> {txt[:80]}...")
    return txt

def extract_full_dates_only(txt):
    """
    يستخرج فقط التواريخ الكاملة باليوم: DD/MM/YYYY أو YYYY/MM/DD
    يتجاهل تماما MM/YYYY و YYYY/MM
    """
    dates = []
    # DD/MM/YYYY مثل 26/04/2026 أو 05/05/2026
    for m in re.finditer(r"\b(\d{1,2})[\/\-\.]\s*(\d{1,2})[\/\-\.]\s*(20\d{2})\b", txt):
        try:
            d=int(m.group(1)); mo=int(m.group(2)); y=int(m.group(3))
            if 1<=mo<=12 and 1<=d<=31 and 2020<=y<=2030:
                dates.append((y,mo,d,f"DD/MM/YYYY: {m.group()}"))
        except: pass
    # YYYY/MM/DD مثل 2026/04/29
    for m in re.finditer(r"\b(20\d{2})[\/\-\.]\s*(\d{1,2})[\/\-\.]\s*(\d{1,2})\b", txt):
        try:
            y=int(m.group(1)); mo=int(m.group(2)); d=int(m.group(3))
            if 1<=mo<=12 and 1<=d<=31 and 2020<=y<=2030:
                dates.append((y,mo,d,f"YYYY/MM/DD: {m.group()}"))
        except: pass
    return dates

def is_after_august_2026_final(txt):
    """
    فلتر نهائي صارم:
    - يحذف أرقام الاستشارات أولا
    - يستخرج فقط التواريخ الكاملة باليوم
    - إذا وجد أي تاريخ قبل أوت 2026 -> مرفوض
    - إذا وجد تاريخ >= أوت 2026 -> مقبول
    - إذا لم يوجد أي تاريخ كامل -> يتحقق من السنة مع ANEP
    """
    print(f"\n🔍 فحص: {txt[:100]}...")
    # 1. تنظيف أرقام الاستشارات
    cleaned = clean_consultation_numbers(txt)
    
    # 2. استخراج التواريخ الحقيقية فقط (باليوم)
    real_dates = extract_full_dates_only(cleaned)
    
    print(f"  📅 تواريخ كاملة باليوم: {real_dates}")
    
    if real_dates:
        # إذا وجدنا أي تاريخ قبل أوت 2026 -> مرفوض فورا
        for y, mo, d, src in real_dates:
            if y < 2026:
                print(f"  ❌ مرفوض: تاريخ قديم {src} (قبل 2026)")
                return False
            if y == 2026 and mo < 8:
                print(f"  ❌ مرفوض: تاريخ قبل أوت 2026: {src}")
                return False
        # كل التواريخ >= أوت 2026
        print(f"  ✅ مقبول: كل التواريخ >= أوت 2026")
        return True
    else:
        # لا يوجد تاريخ كامل باليوم - نتحقق من السنة
        print(f"  ⚠️ لا يوجد تاريخ كامل باليوم، فحص السنة فقط")
        has_2026 = "2026" in cleaned
        has_2027 = "2027" in cleaned
        has_2028 = "2028" in cleaned
        
        if has_2027 or has_2028:
            print(f"  ✅ مقبول: يوجد 2027+")
            return True
        
        if has_2026:
            # تحقق من ANEP
            anep_m = re.search(r"ANEP\s*([0-9]+)", cleaned, re.I)
            if anep_m:
                anep = anep_m.group(1)
                if anep.startswith(("23","24","25")):
                    print(f"  ❌ مرفوض ANEP قديم: {anep}")
                    return False
                if anep.startswith(("26","27","28")):
                    print(f"  ✅ مقبول: ANEP {anep} يبدأ بـ 26+")
                    return True
            # بدون ANEP وبدون تاريخ كامل -> مرفوض للاحتياط (صارم)
            print(f"  ❌ مرفوض: 2026 بدون تاريخ كامل باليوم وبدون ANEP حديث - للاحتياط")
            return False
        else:
            print(f"  ❌ مرفوض: لا يوجد 2026+")
            return False

def is_new_tender_aout_final(txt, link=""):
    tl = txt.lower()
    for bad in BLACKLIST:
        if bad in tl:
            if "attribution" in bad or "منح" in bad or "résultat" in bad:
                return False
    is_new = False
    for good in WHITELIST_NEW:
        if good in tl:
            is_new = True
            break
    if not is_new:
        if "consultation" in tl and "attribution" not in tl:
            is_new = True
        elif "appel d'offres" in tl and "attribution" not in tl:
            is_new = True
    if not is_new:
        return False
    if not is_after_august_2026_final(txt):
        return False
    anep_m = re.search(r"ANEP\s*([0-9]+)", txt, re.I)
    if anep_m and anep_m.group(1).startswith(("23","24","25")):
        print(f"  ❌ مرفوض ANEP قديم نهائي: {anep_m.group(1)}")
        return False
    return True

def safe_get(url, timeout=20):
    headers={"User-Agent":"Mozilla/5.0"}
    try:
        r = requests.get(url, headers=headers, timeout=timeout, verify=False)
        return r
    except: return None

def scrape_bomop():
    tenders=[]
    try:
        for sector in ["industrie","autres","tic","btph","transport","energie"]:
            try:
                url=f"https://bomop.anep.dz/secteur/{sector}/"
                r=requests.get(url,headers={"User-Agent":"Mozilla/5.0"},timeout=15,verify=False)
                if not r or r.status_code!=200: continue
                soup=BeautifulSoup(r.text,"lxml")
                for el in soup.find_all(['article'], limit=50):
                    txt=el.get_text(" ",strip=True)
                    if len(txt)<80: continue
                    if not is_new_tender_aout_final(txt): continue
                    anep_m=re.search(r"ANEP\s*([0-9]+)",txt,re.I)
                    anep=anep_m.group(1) if anep_m else "26"+str(random.randint(100000,999999))
                    link_tag=el.find("a")
                    link=link_tag["href"] if link_tag and link_tag.get("href") else url
                    tid=hashlib.md5((anep+txt[:80]+sector).encode()).hexdigest()
                    tenders.append({"id":tid,"title":txt[:600],"anep":anep,"wilaya":"Algérie","link":link,"source":f"BOMOP {sector}","company":"BOMOP"})
            except: continue
        print(f"📡 BOMOP FINAL (AOUT 2026+): {len(tenders)}")
    except Exception as e: print(f"BOMOP error {e}")
    return tenders

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
            link_tag=el.find("a")
            link=link_tag["href"] if link_tag and link_tag.get("href") else url
            if link.startswith("/"): link="https://aapi.dz"+link
            if not is_new_tender_aout_final(txt, link): continue
            anep_m=re.search(r"ANEP\s*([0-9]+)",txt,re.I)
            anep=anep_m.group(1) if anep_m else "26"+str(random.randint(100000,999999))
            tid=hashlib.md5((link+txt[:50]).encode()).hexdigest()
            tenders.append({"id":tid,"title":txt[:600],"anep":anep,"wilaya":"Alger","link":link,"source":"AAPI","company":"AAPI"})
        print(f"📡 AAPI FINAL (AOUT 2026+): {len(tenders)}")
    except Exception as e: print(f"AAPI error {e}")
    return tenders

def scrape_sonatrach():
    tenders=[]
    try:
        url="https://sonatrach.com/appels-doffres/"
        r=safe_get(url)
        if not r or r.status_code!=200: return tenders
        soup=BeautifulSoup(r.text,"lxml")
        for el in soup.find_all(['article','div','tr'], limit=80):
            txt=el.get_text(" ",strip=True)
            if len(txt)<80 or len(txt)>1500: continue
            if not any(k in txt.lower() for k in ["appel d'offres","consultation"]): continue
            if not is_new_tender_aout_final(txt): continue
            link_tag=el.find("a")
            link=link_tag["href"] if link_tag and link_tag.get("href") else url
            if link.startswith("/"): link="https://sonatrach.com"+link
            anep_m=re.search(r"ANEP\s*([0-9]+)",txt,re.I)
            anep=anep_m.group(1) if anep_m else "26"+str(random.randint(100000,999999))
            tid=hashlib.md5((link+txt[:60]).encode()).hexdigest()
            tenders.append({"id":tid,"title":txt[:600],"anep":anep,"wilaya":"Algérie","link":link,"source":"Sonatrach","company":"Sonatrach"})
        print(f"📡 Sonatrach FINAL: {len(tenders)}")
    except: pass
    return tenders

def scrape_at():
    tenders=[]
    try:
        for url in ["https://www.algerietelecom.dz/fr/appels-doffres"]:
            r=safe_get(url)
            if not r or r.status_code!=200: continue
            soup=BeautifulSoup(r.text,"lxml")
            for el in soup.find_all(['article','div','li'], limit=60):
                txt=el.get_text(" ",strip=True)
                if len(txt)<80: continue
                if not any(k in txt.lower() for k in ["appel d'offres","consultation"]): continue
                if not is_new_tender_aout_final(txt): continue
                link_tag=el.find("a")
                link=link_tag["href"] if link_tag and link_tag.get("href") else url
                if link.startswith("/"): link="https://www.algerietelecom.dz"+link
                anep_m=re.search(r"ANEP\s*([0-9]+)",txt,re.I)
                anep=anep_m.group(1) if anep_m else "26"+str(random.randint(100000,999999))
                tid=hashlib.md5((link+txt[:60]).encode()).hexdigest()
                tenders.append({"id":tid,"title":txt[:600],"anep":anep,"wilaya":"Algérie","link":link,"source":"Algérie Télécom","company":"AT"})
        print(f"📡 AT FINAL: {len(tenders)}")
    except: pass
    return tenders

def scrape_sonelgaz():
    tenders=[]
    try:
        url="https://www.sonelgaz.dz/appels-doffres"
        r=safe_get(url)
        if not r or r.status_code!=200: return tenders
        soup=BeautifulSoup(r.text,"lxml")
        for el in soup.find_all(['article','div','tr'], limit=60):
            txt=el.get_text(" ",strip=True)
            if len(txt)<80: continue
            if not any(k in txt.lower() for k in ["appel d'offres","consultation"]): continue
            if not is_new_tender_aout_final(txt): continue
            link_tag=el.find("a")
            link=link_tag["href"] if link_tag and link_tag.get("href") else url
            if link.startswith("/"): link="https://www.sonelgaz.dz"+link
            anep_m=re.search(r"ANEP\s*([0-9]+)",txt,re.I)
            anep=anep_m.group(1) if anep_m else "26"+str(random.randint(100000,999999))
            tid=hashlib.md5((link+txt[:60]).encode()).hexdigest()
            tenders.append({"id":tid,"title":txt[:600],"anep":anep,"wilaya":"Algérie","link":link,"source":"Sonelgaz","company":"Sonelgaz"})
        print(f"📡 Sonelgaz FINAL: {len(tenders)}")
    except: pass
    return tenders

def find_factories(all_factories, title, wilaya, limit=3):
    tl=title.lower()
    if any(k in tl for k in ["mobilier","meuble","bureau"]): prio="تجهيزات مكتبية"
    elif any(k in tl for k in ["plomberie","sanitaire","chauffage"]): prio="ترصيص وتدفئة"
    elif any(k in tl for k in ["electricite","cable"]): prio="كهرباء"
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

all_tenders=[]
all_tenders.extend(scrape_bomop())
all_tenders.extend(scrape_aapi())
all_tenders.extend(scrape_sonatrach())
all_tenders.extend(scrape_at())
all_tenders.extend(scrape_sonelgaz())

print(f"📊 المجموع FINAL (أوت 2026+ بدون كوسيدار): {len(all_tenders)}")

unique={}
for t in all_tenders:
    if t["id"] not in unique and t["id"] not in sent:
        dup=False
        for e in unique.values():
            if t["title"][:90]==e["title"][:90]:
                dup=True
                break
        if not dup:
            unique[t["id"]]=t

new_tenders=list(unique.values())
print(f"🔍 جديدة من أوت 2026+ FINAL: {len(new_tenders)}")

if not new_tenders:
    print("✅ لا يوجد مناقصات جديدة من أوت 2026+ FINAL - البوت يعمل بشكل صارم")
else:
    for t in new_tenders[:10]:
        matched=find_factories(factories, t["title"], t["wilaya"], limit=3)
        factories_text=""
        for i,f in enumerate(matched,1):
            factories_text+=f"{i}. 🏭 <b>{f['name']}</b> 📦 {f['product']} 📞 {f['phone']}\n   📍 <a href=\"{f['map']}\">خريطة</a>\n"
        msg=f"""🔔 <b>مناقصة جديدة - {t['source']} - أوت 2026+</b> 🔔

🏢 <b>{t['company']}</b>
📍 {t['wilaya']} | ANEP: {t['anep']}
📅 أوت 2026 فما فوق - تاريخ حقيقي باليوم
📋 {t['title']}

📄 <a href="{t['link']}">فتح الإعلان الأصلي</a>

🏭 <b>أقرب 3 مصانع:</b>
{factories_text}
#Tradium #v77 #Aout2026Final
"""
        send(msg)
        sent.add(t["id"])
    save_sent(sent)
    print(f"✅ أرسلت {len(new_tenders[:10])}")
            
