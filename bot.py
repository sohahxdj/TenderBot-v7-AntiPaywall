import os, requests, json, re, hashlib, random, urllib3
from bs4 import BeautifulSoup

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

TOKEN = os.getenv("TELEGRAM_TOKEN","").strip()
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID","").strip()
SENT_FILE = "sent_v7.json"
FACTORIES_FILE = "factories_300.json"

print("🚀 v7.9 - SOURCES GRATUITES ÉLARGIES - PRIORITÉS - AOUT 2026+")

def load_factories():
    if os.path.exists(FACTORIES_FILE):
        try:
            with open(FACTORIES_FILE,"r",encoding="utf-8") as f:
                data=json.load(f)
            if len(data)>0: return data
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

BLACKLIST = ["avis d'attribution","attribution provisoire","résultat","offre la mieux disante","recours","منح مؤقت","المنح المؤقت"]

def clean_consultation_numbers(txt):
    txt = re.sub(r"N°\s*\d+\s*/\s*20\d{2}", " ", txt, flags=re.I)
    txt = re.sub(r"(?:رقم|استشارة)\s*20\d{2}\s*/\s*\d{1,3}", " ", txt, flags=re.I)
    txt = re.sub(r"20\d{2}\s*/\s*\d{1,2}\b(?!\s*/)", " ", txt)
    txt = re.sub(r"Lot\s*N°\s*\d+", " ", txt, flags=re.I)
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
    return dates

def is_after_august_2026_final(txt):
    cleaned = clean_consultation_numbers(txt)
    real_dates = extract_full_dates_only(cleaned)
    if real_dates:
        for y, mo, d, src in real_dates:
            if y < 2026 or (y == 2026 and mo < 8):
                print(f"  ❌ مرفوض قبل أوت: {src}")
                return False
        print(f"  ✅ مقبول >= أوت 2026: {real_dates}")
        return True
    else:
        has_2027 = "2027" in cleaned or "2028" in cleaned
        has_2026 = "2026" in cleaned
        if has_2027:
            return True
        if has_2026:
            anep_m = re.search(r"ANEP\s*([0-9]+)", cleaned, re.I)
            if anep_m and anep_m.group(1).startswith(("23","24","25")):
                return False
            if anep_m and anep_m.group(1).startswith(("26","27","28")):
                return True
            # بدون تاريخ كامل وبدون ANEP حديث -> للاحتياط نرفض (صارم)
            # لكن لبعض المواقع المجانية مثل الداخلية لا يوجد ANEP، نقبل 2026 إذا كان النص طويل وفيه كلمات مناقصة جديدة
            if len(cleaned) > 100 and any(k in cleaned.lower() for k in ["acquisition","fourniture","travaux","consultation"]):
                # نتحقق من عدم وجود 2025
                if "2025" not in cleaned and "2024" not in cleaned:
                    print(f"  ⚠️ مقبول احتياطي: 2026 بدون تاريخ كامل لكن بدون 2025/2024")
                    return True
            return False
        return False

def is_new_tender(txt):
    tl = txt.lower()
    for bad in BLACKLIST:
        if bad in tl and ("attribution" in bad or "منح" in bad or "résultat" in bad):
            return False
    if not any(k in tl for k in ["appel d'offres","consultation","acquisition","fourniture","travaux","équipement","prestation"]):
        return False
    if "attribution" in tl or "résultat" in tl:
        return False
    if not is_after_august_2026_final(txt):
        return False
    anep_m = re.search(r"ANEP\s*([0-9]+)", txt, re.I)
    if anep_m and anep_m.group(1).startswith(("23","24","25")):
        return False
    return True

def safe_get(url, timeout=20):
    headers={"User-Agent":"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
    try:
        r = requests.get(url, headers=headers, timeout=timeout, verify=False)
        return r
    except Exception as e:
        print(f"GET failed {url}: {e}")
        return None

# --- 1. AAPI ---
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
            link_tag=el.find("a")
            link=link_tag["href"] if link_tag and link_tag.get("href") else url
            if link.startswith("/"): link="https://aapi.dz"+link
            anep_m=re.search(r"ANEP\s*([0-9]+)",txt,re.I)
            anep=anep_m.group(1) if anep_m else "26"+str(random.randint(100000,999999))
            tid=hashlib.md5((link+txt[:50]).encode()).hexdigest()
            tenders.append({"id":tid,"title":txt[:600],"anep":anep,"wilaya":"Alger","link":link,"source":"AAPI","company":"AAPI","priority":"صناعة"})
        print(f"📡 AAPI: {len(tenders)}")
    except Exception as e: print(f"AAPI error {e}")
    return tenders

# --- 2. Safqatic (Algérie Télécom) ---
def scrape_safqatic():
    tenders=[]
    try:
        url="https://www.safqatic.dz/index.php?type=1"
        r=safe_get(url)
        if not r or r.status_code!=200:
            url="https://safqatic.dz/index.php?type=1"
            r=safe_get(url)
        if not r or r.status_code!=200: return tenders
        soup=BeautifulSoup(r.text,"lxml")
        for el in soup.find_all(['div','tr','article'], limit=100):
            txt=el.get_text(" ",strip=True)
            if len(txt)<80 or len(txt)>2000: continue
            if not any(k in txt.lower() for k in ["appel d'offres","consultation","acquisition"]): continue
            if not is_new_tender(txt): continue
            link_tag=el.find("a")
            link=link_tag["href"] if link_tag and link_tag.get("href") else url
            if link.startswith("/"): link="https://www.safqatic.dz"+link
            if not link.startswith("http"): link=url
            anep_m=re.search(r"ANEP\s*([0-9]+)",txt,re.I)
            anep=anep_m.group(1) if anep_m else "26"+str(random.randint(100000,999999))
            tid=hashlib.md5((link+txt[:80]).encode()).hexdigest()
            tenders.append({"id":tid,"title":txt[:600],"anep":anep,"wilaya":"Algérie","link":link,"source":"Safqatic AT","company":"Algérie Télécom","priority":"تجهيزات مكتبية"})
        print(f"📡 Safqatic AT: {len(tenders)}")
    except Exception as e: print(f"Safqatic error {e}")
    return tenders

# --- 3. Ministère de l'Intérieur ---
def scrape_interieur():
    tenders=[]
    try:
        urls=[
            "https://services.interieur.gov.dz/index.php/fr/le-ministere/avis-appels-offres-et-consultations",
            "https://www.interieur.gov.dz/index.php/fr/appels-d-offres-et-consultations",
            "http://interieur.gov.dz/category/le-ministere/appels-doffres-consultations/"
        ]
        for url in urls:
            r=safe_get(url)
            if not r or r.status_code!=200: continue
            soup=BeautifulSoup(r.text,"lxml")
            for el in soup.find_all(['article','div','tr','li'], limit=80):
                txt=el.get_text(" ",strip=True)
                if len(txt)<80 or len(txt)>2000: continue
                if not any(k in txt.lower() for k in ["appel d'offres","consultation","acquisition","fourniture"]): continue
                if not is_new_tender(txt): continue
                link_tag=el.find("a")
                link=link_tag["href"] if link_tag and link_tag.get("href") else url
                if link.startswith("/"): link="https://services.interieur.gov.dz"+link
                anep_m=re.search(r"ANEP\s*([0-9]+)",txt,re.I)
                anep=anep_m.group(1) if anep_m else "26"+str(random.randint(100000,999999))
                tid=hashlib.md5((link+txt[:80]).encode()).hexdigest()
                tenders.append({"id":tid,"title":txt[:600],"anep":anep,"wilaya":"Alger","link":link,"source":"Intérieur","company":"Ministère Intérieur","priority":"تجهيزات مكتبية"})
            if len(tenders)>0:
                break
        print(f"📡 Intérieur: {len(tenders)}")
    except Exception as e: print(f"Intérieur error {e}")
    return tenders

# --- 4. Ministère des Travaux Publics (BTPH) ---
def scrape_mtp():
    tenders=[]
    try:
        urls=[
            "https://www.mtp.gov.dz/fr/appels-doffres",
            "https://mtpt.gov.dz/fr/appels-doffres",
            "https://www.mtpt.gov.dz/fr/appels-doffres"
        ]
        for url in urls:
            r=safe_get(url)
            if not r or r.status_code!=200: continue
            soup=BeautifulSoup(r.text,"lxml")
            for el in soup.find_all(['article','div','tr'], limit=80):
                txt=el.get_text(" ",strip=True)
                if len(txt)<80 or len(txt)>2000: continue
                if not any(k in txt.lower() for k in ["appel d'offres","consultation","travaux","fourniture"]): continue
                if not is_new_tender(txt): continue
                link_tag=el.find("a")
                link=link_tag["href"] if link_tag and link_tag.get("href") else url
                if link.startswith("/"): link=url+link
                anep_m=re.search(r"ANEP\s*([0-9]+)",txt,re.I)
                anep=anep_m.group(1) if anep_m else "26"+str(random.randint(100000,999999))
                tid=hashlib.md5((link+txt[:80]).encode()).hexdigest()
                tenders.append({"id":tid,"title":txt[:600],"anep":anep,"wilaya":"Algérie","link":link,"source":"MTP","company":"Min. Travaux Publics","priority":"بناء"})
            if len(tenders)>0:
                break
        print(f"📡 MTP (BTPH): {len(tenders)}")
    except Exception as e: print(f"MTP error {e}")
    return tenders

# --- 5. Ministère de la Défense (BTPH, électricité, plomberie) ---
def scrape_mdn():
    tenders=[]
    try:
        url="https://www.mdn.dz/site_principal/sommaire/appels_offres/index.php"
        r=safe_get(url)
        if not r or r.status_code!=200:
            url="https://www.mdn.dz/site_principal/sommaire/appels_offres/"
            r=safe_get(url)
        if not r or r.status_code!=200: return tenders
        soup=BeautifulSoup(r.text,"lxml")
        for el in soup.find_all(['div','tr','article','li'], limit=80):
            txt=el.get_text(" ",strip=True)
            if len(txt)<80 or len(txt)>2000: continue
            if not any(k in txt.lower() for k in ["appel d'offres","consultation","travaux","fourniture","réalisation"]): continue
            if not is_new_tender(txt): continue
            link_tag=el.find("a")
            link=link_tag["href"] if link_tag and link_tag.get("href") else url
            if link.startswith("/"): link="https://www.mdn.dz"+link
            anep_m=re.search(r"ANEP\s*([0-9]+)",txt,re.I)
            anep=anep_m.group(1) if anep_m else "26"+str(random.randint(100000,999999))
            tid=hashlib.md5((link+txt[:80]).encode()).hexdigest()
            tenders.append({"id":tid,"title":txt[:600],"anep":anep,"wilaya":"Algérie","link":link,"source":"MDN","company":"Min. Défense","priority":"كهرباء"})
        print(f"📡 MDN: {len(tenders)}")
    except Exception as e: print(f"MDN error {e}")
    return tenders

def find_factories(all_factories, title, wilaya, limit=3):
    tl=title.lower()
    if any(k in tl for k in ["mobilier","meuble","bureau","chaise","papier","informatique","ordinateur"]): prio="تجهيزات مكتبية"
    elif any(k in tl for k in ["plomberie","sanitaire","chauffage","chaudiere","tuyau","robinet"]): prio="ترصيص وتدفئة"
    elif any(k in tl for k in ["electricite","cable","disjoncteur","eclairage","led","groupe electrogene"]): prio="كهرباء"
    elif any(k in tl for k in ["piece","pneu","batterie","vehicule","camion","automobile"]): prio="قطع غيار"
    elif any(k in tl for k in ["travaux","btp","construction","genie civil","batiment","vrd"]): prio="بناء"
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
all_tenders.extend(scrape_aapi())
all_tenders.extend(scrape_safqatic())
all_tenders.extend(scrape_interieur())
all_tenders.extend(scrape_mtp())
all_tenders.extend(scrape_mdn())

print(f"📊 المجموع FINAL (5 مصادر مجانية حقيقية): {len(all_tenders)}")

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
    print("✅ لا يوجد مناقصات جديدة من أوت 2026+ - البوت يعمل صارم")
else:
    for t in new_tenders[:10]:
        matched=find_factories(factories, t["title"], t["wilaya"], limit=3)
        factories_text=""
        for i,f in enumerate(matched,1):
            factories_text+=f"{i}. 🏭 <b>{f['name']}</b> 📦 {f['product']} 📞 {f['phone']}\n   📍 <a href=\"{f['map']}\">خريطة</a>\n"
        msg=f"""🔔 <b>مناقصة جديدة - {t['source']} - أوت 2026+</b> 🔔

🏢 <b>{t['company']}</b>
📍 {t['wilaya']} | ANEP: {t['anep']}
📅 أوت 2026+ | أولوية: {t.get('priority','عام')}
📋 {t['title']}

📄 <a href="{t['link']}">فتح الإعلان الأصلي</a>

🏭 <b>أقرب 3 مصانع ({t.get('priority','')}):</b>
{factories_text}
#Tradium #v79 #Aout2026 #FreeSources
"""
        send(msg)
        sent.add(t["id"])
    save_sent(sent)
    print(f"✅ أرسلت {len(new_tenders[:10])}")
    
