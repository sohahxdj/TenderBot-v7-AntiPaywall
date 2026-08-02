import os, requests, json, re, hashlib, random, urllib3
from bs4 import BeautifulSoup

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

TOKEN = os.getenv("TELEGRAM_TOKEN","").strip()
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID","").strip()
SENT_FILE = "sent_v7.json"
FACTORIES_FILE = "factories_300.json"

print("🚀 v7.5.1 - AOUT 2026+ STRICT SANS COSIDER (5 SOURCES)")

def load_factories():
    if os.path.exists(FACTORIES_FILE):
        try:
            with open(FACTORIES_FILE,"r",encoding="utf-8") as f:
                data=json.load(f)
            if len(data)>0:
                print(f"✅ {len(data)} مصنع")
                return data
        except: pass
    return [{"id":1,"name":"SARL Test","wilaya":"Alger","priority":"تجهيزات مكتبية","product":"مكاتب","is_direct_factory":True,"phone":"0550 11 22 33","map":"https://maps.google.com"}]

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

MONTHS_FR = {"janvier":1,"février":2,"fevrier":2,"mars":3,"avril":4,"mai":5,"juin":6,"juillet":7,"août":8,"aout":8,"septembre":9,"octobre":10,"novembre":11,"décembre":12,"decembre":12}
MONTHS_AR = {"جانفي":1,"فيفري":2,"مارس":3,"أفريل":4,"افريل":4,"ماي":5,"جوان":6,"جويلية":7,"جويليه":7,"أوت":8,"اوت":8,"سبتمبر":9,"أكتوبر":10,"اكتوبر":10,"نوفمبر":11,"ديسمبر":12}

BLACKLIST = [
    "بلاغ","important avis","communiqué","formulaires","espace privé","mot du directeur","présentation","facebook","linkedin","twitter","accueil","à propos",
    "avis d'attribution","attribution provisoire","attribution du marché","résultat","résultats","offre la mieux disante","recours","contester cet avis","منح مؤقت","المنح المؤقت","إعلان عن المنح","نتائج","أحسن عرض","لجنة فتح الأظرفة وتقييم العروض تم المنح",
    "sous-direction des moyens généraux"
]
WHITELIST_NEW = ["avis d'appel d'offres","appel d'offres ouvert","consultation n°","avis de consultation","acquisition de","fourniture de","travaux de","réalisation de","équipement de","prestation de","étude de"]

def extract_all_dates(txt):
    dates = []
    for m in re.finditer(r"(\d{1,2})[\/\-\.]\s*(\d{1,2})[\/\-\.]\s*(20\d{2})", txt):
        try:
            d=int(m.group(1)); mo=int(m.group(2)); y=int(m.group(3))
            if 1<=mo<=12 and 1<=d<=31:
                dates.append((y,mo,d))
        except: pass
    for m in re.finditer(r"(?:^|[^0-9])(\d{1,2})[\/\-\.]\s*(20\d{2})(?:[^0-9]|$)", txt):
        try:
            mo=int(m.group(1)); y=int(m.group(2))
            if 1<=mo<=12:
                dates.append((y,mo,1))
        except: pass
    for m in re.finditer(r"(20\d{2})[\/\-\.]\s*(\d{1,2})(?:[^0-9]|$)", txt):
        try:
            y=int(m.group(1)); mo=int(m.group(2))
            if 1<=mo<=12:
                dates.append((y,mo,1))
        except: pass
    tl = txt.lower()
    for name, mo in MONTHS_FR.items():
        for m in re.finditer(rf"{name}\s+20\d{{2}}", tl):
            try:
                y = int(re.search(r"20\d{2}", m.group()).group())
                dates.append((y,mo,1))
            except: pass
    for name, mo in MONTHS_AR.items():
        if name in txt:
            for m in re.finditer(rf"{name}.*20\d{{2}}", txt):
                try:
                    y = int(re.search(r"20\d{2}", m.group()).group())
                    dates.append((y,mo,1))
                except: pass
    return dates

def is_after_august_2026_strict(txt):
    dates = extract_all_dates(txt)
    if not dates:
        has_2026 = "2026" in txt
        has_2027 = "2027" in txt
        has_2028 = "2028" in txt
        if has_2027 or has_2028:
            return True
        if has_2026:
            anep_m = re.search(r"ANEP\s*([0-9]+)", txt, re.I)
            if anep_m:
                anep = anep_m.group(1)
                if anep.startswith("25") or anep.startswith("24") or anep.startswith("23"):
                    print(f"❌ مرفوض ANEP قديم: {anep}")
                    return False
            return True
        else:
            return False
    else:
        for y, mo, d in dates:
            if y > 2026:
                print(f"✅ تاريخ مقبول: {d:02d}/{mo:02d}/{y}")
                return True
            if y == 2026 and mo >= 8:
                print(f"✅ تاريخ مقبول: {d:02d}/{mo:02d}/{y} (>= أوت 2026)")
                return True
        print(f"❌ كل التواريخ قبل أوت 2026: {dates}")
        return False

def is_new_tender_strict_august(txt, link=""):
    tl = txt.lower()
    for bad in BLACKLIST:
        if bad in tl:
            if "attribution" in bad or "منح" in bad or "résultat" in bad or "mieux disante" in bad or "recours" in bad:
                return False
    is_new = False
    for good in WHITELIST_NEW:
        if good in tl:
            is_new = True
            break
    if not is_new:
        if "consultation" in tl and "attribution" not in tl and "résultat" not in tl:
            is_new = True
        elif "appel d'offres" in tl and "attribution" not in tl:
            is_new = True
    if not is_new:
        return False
    if not is_after_august_2026_strict(txt):
        return False
    anep_m = re.search(r"ANEP\s*([0-9]+)", txt, re.I)
    if anep_m:
        anep = anep_m.group(1)
        if anep.startswith("23") or anep.startswith("24") or anep.startswith("25"):
            return False
    return True

def safe_get(url, timeout=20):
    headers={"User-Agent":"Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
    try:
        r = requests.get(url, headers=headers, timeout=timeout, verify=False)
        return r
    except Exception as e:
        print(f"Request failed {url}: {e}")
        return None

def scrape_bomop():
    tenders=[]
    try:
        sectors=["industrie","autres","tic","btph","transport","energie"]
        for sector in sectors:
            try:
                url=f"https://bomop.anep.dz/secteur/{sector}/"
                r=requests.get(url,headers={"User-Agent":"Mozilla/5.0"},timeout=15,verify=False)
                if not r or r.status_code!=200: continue
                soup=BeautifulSoup(r.text,"lxml")
                for el in soup.find_all(['article'], limit=50):
                    txt=el.get_text(" ",strip=True)
                    if len(txt)<80: continue
                    if not is_new_tender_strict_august(txt):
                        continue
                    anep_m=re.search(r"ANEP\s*([0-9]+)",txt,re.I)
                    anep=anep_m.group(1) if anep_m else "26"+str(random.randint(100000,999999))
                    link_tag=el.find("a")
                    link=link_tag["href"] if link_tag and link_tag.get("href") else url
                    tid=hashlib.md5((anep+txt[:80]+sector).encode()).hexdigest()
                    tenders.append({"id":tid,"title":txt[:600],"anep":anep,"wilaya":"Algérie","link":link,"source":f"BOMOP {sector}","company":"BOMOP"})
            except: continue
        print(f"📡 BOMOP (AOUT 2026+): {len(tenders)}")
    except Exception as e:
        print(f"BOMOP error {e}")
    return tenders

def scrape_aapi():
    tenders=[]
    try:
        url="https://aapi.dz/consultations/"
        r=safe_get(url)
        if not r: return tenders
        soup=BeautifulSoup(r.text,"lxml")
        tables = soup.find_all('table')
        rows = []
        for t in tables:
            rows.extend(t.find_all('tr'))
        if not rows:
            rows = soup.find_all('article', limit=50)
        for el in rows:
            txt=el.get_text(" ",strip=True)
            if len(txt)<80 or len(txt)>1500: continue
            link_tag=el.find("a")
            link=link_tag["href"] if link_tag and link_tag.get("href") else url
            if link.startswith("/"): link="https://aapi.dz"+link
            if not is_new_tender_strict_august(txt, link):
                continue
            anep_m=re.search(r"ANEP\s*([0-9]+)",txt,re.I)
            anep=anep_m.group(1) if anep_m else "26"+str(random.randint(100000,999999))
            tid=hashlib.md5((link+txt[:50]).encode()).hexdigest()
            tenders.append({"id":tid,"title":txt[:600],"anep":anep,"wilaya":"Alger","link":link,"source":"AAPI","company":"AAPI"})
        print(f"📡 AAPI (AOUT 2026+): {len(tenders)}")
    except Exception as e:
        print(f"AAPI error {e}")
    return tenders

def scrape_sonatrach():
    tenders=[]
    try:
        url="https://sonatrach.com/appels-doffres/"
        r=safe_get(url)
        if not r or r.status_code!=200:
            return tenders
        soup=BeautifulSoup(r.text,"lxml")
        for el in soup.find_all(['article','div','tr'], limit=80):
            txt=el.get_text(" ",strip=True)
            if len(txt)<80 or len(txt)>1500: continue
            if not any(k in txt.lower() for k in ["appel d'offres","consultation","acquisition","fourniture"]): continue
            if not is_after_august_2026_strict(txt):
                continue
            if any(bad in txt.lower() for bad in ["attribution","résultat","mieux disante"]): continue
            link_tag=el.find("a")
            link=link_tag["href"] if link_tag and link_tag.get("href") else url
            if link.startswith("/"): link="https://sonatrach.com"+link
            anep_m=re.search(r"ANEP\s*([0-9]+)",txt,re.I)
            anep=anep_m.group(1) if anep_m else "26"+str(random.randint(100000,999999))
            tid=hashlib.md5((link+txt[:60]).encode()).hexdigest()
            tenders.append({"id":tid,"title":txt[:600],"anep":anep,"wilaya":"Algérie","link":link,"source":"Sonatrach","company":"Sonatrach"})
        print(f"📡 Sonatrach (AOUT 2026+): {len(tenders)}")
    except Exception as e:
        print(f"Sonatrach error {e}")
    return tenders

def scrape_algerie_telecom():
    tenders=[]
    try:
        urls=["https://www.algerietelecom.dz/fr/appels-doffres","https://www.algerietelecom.dz/ar/appels-doffres"]
        for url in urls:
            r=safe_get(url)
            if not r or r.status_code!=200: continue
            soup=BeautifulSoup(r.text,"lxml")
            for el in soup.find_all(['article','div','li'], limit=60):
                txt=el.get_text(" ",strip=True)
                if len(txt)<80: continue
                if not any(k in txt.lower() for k in ["appel d'offres","consultation","acquisition"]): continue
                if not is_after_august_2026_strict(txt): continue
                if any(bad in txt.lower() for bad in ["attribution","résultat"]): continue
                link_tag=el.find("a")
                link=link_tag["href"] if link_tag and link_tag.get("href") else url
                if link.startswith("/"): link="https://www.algerietelecom.dz"+link
                anep_m=re.search(r"ANEP\s*([0-9]+)",txt,re.I)
                anep=anep_m.group(1) if anep_m else "26"+str(random.randint(100000,999999))
                tid=hashlib.md5((link+txt[:60]).encode()).hexdigest()
                tenders.append({"id":tid,"title":txt[:600],"anep":anep,"wilaya":"Algérie","link":link,"source":"Algérie Télécom","company":"AT"})
        print(f"📡 Algérie Télécom (AOUT 2026+): {len(tenders)}")
    except Exception as e:
        print(f"AT error {e}")
    return tenders

def scrape_sonelgaz():
    tenders=[]
    try:
        url="https://www.sonelgaz.dz/appels-doffres"
        r=safe_get(url)
        if not r or r.status_code!=200:
            return tenders
        soup=BeautifulSoup(r.text,"lxml")
        for el in soup.find_all(['article','div','tr'], limit=60):
            txt=el.get_text(" ",strip=True)
            if len(txt)<80: continue
            if not any(k in txt.lower() for k in ["appel d'offres","consultation"]): continue
            if not is_after_august_2026_strict(txt): continue
            if any(bad in txt.lower() for bad in ["attribution","résultat"]): continue
            link_tag=el.find("a")
            link=link_tag["href"] if link_tag and link_tag.get("href") else url
            if link.startswith("/"): link="https://www.sonelgaz.dz"+link
            anep_m=re.search(r"ANEP\s*([0-9]+)",txt,re.I)
            anep=anep_m.group(1) if anep_m else "26"+str(random.randint(100000,999999))
            tid=hashlib.md5((link+txt[:60]).encode()).hexdigest()
            tenders.append({"id":tid,"title":txt[:600],"anep":anep,"wilaya":"Algérie","link":link,"source":"Sonelgaz","company":"Sonelgaz"})
        print(f"📡 Sonelgaz (AOUT 2026+): {len(tenders)}")
    except Exception as e:
        print(f"Sonelgaz error {e}")
    return tenders

def find_factories(all_factories, title, wilaya, limit=3):
    tl=title.lower()
    if any(k in tl for k in ["mobilier","meuble","bureau","chaise","papier"]): prio="تجهيزات مكتبية"
    elif any(k in tl for k in ["plomberie","sanitaire","chauffage","chaudiere","tuyau"]): prio="ترصيص وتدفئة"
    elif any(k in tl for k in ["electricite","cable","disjoncteur","eclairage","led"]): prio="كهرباء"
    elif any(k in tl for k in ["piece","pneu","batterie","vehicule","camion"]): prio="قطع غيار"
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
all_tenders.extend(scrape_algerie_telecom())
all_tenders.extend(scrape_sonelgaz())

print(f"📊 المجموع من 5 مصادر (أوت 2026+ بدون كوسيدار): {len(all_tenders)}")

unique={}
for t in all_tenders:
    if t["id"] not in unique and t["id"] not in sent:
        is_duplicate=False
        for existing in unique.values():
            if t["title"][:90]==existing["title"][:90]:
                is_duplicate=True
                break
        if not is_duplicate:
            unique[t["id"]]=t

new_tenders=list(unique.values())
print(f"🔍 مناقصات جديدة حقيقية من أوت 2026+: {len(new_tenders)}")

if not new_tenders:
    print("✅ لا يوجد مناقصات جديدة من أوت 2026+ اليوم")
else:
    for t in new_tenders[:10]:
        matched=find_factories(factories, t["title"], t["wilaya"], limit=3)
        factories_text=""
        for i,f in enumerate(matched,1):
            factories_text+=f"{i}. 🏭 <b>{f['name']}</b> 📦 {f['product']} 📞 {f['phone']}\n   📍 <a href=\"{f['map']}\">خريطة</a>\n"
        msg=f"""🔔 <b>مناقصة جديدة - {t['source']} - أوت 2026+</b> 🔔

🏢 <b>{t['company']}</b>
📍 {t['wilaya']} | ANEP: {t['anep']}
📅 أوت 2026 فما فوق - إعلان جديد فقط
📋 {t['title']}

📄 <a href="{t['link']}">فتح الإعلان الأصلي</a>

🏭 <b>أقرب 3 مصانع:</b>
{factories_text}
#Tradium #v751 #Aout2026
"""
        send(msg)
        sent.add(t["id"])
    save_sent(sent)
    print(f"✅ أرسلت {len(new_tenders[:10])} مناقصة أوت 2026+")
    
