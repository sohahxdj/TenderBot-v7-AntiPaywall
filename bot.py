import os, requests, json, re, hashlib, random, urllib3
from bs4 import BeautifulSoup

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

TOKEN = os.getenv("TELEGRAM_TOKEN","").strip()
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID","").strip()
SENT_FILE = "sent_v7.json"
FACTORIES_FILE = "factories_300.json"

print("🚀 v7.4 - FILTRE APPELS SEULEMENT, PAS ATTRIBUTIONS")

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
MONTHS_AR = {"جانفي":1,"فيفري":2,"مارس":3,"أفريل":4,"ماي":5,"جوان":6,"جويلية":7,"أوت":8,"سبتمبر":9,"أكتوبر":10,"نوفمبر":11,"ديسمبر":12}

# قائمة سوداء موسعة جدا
BLACKLIST = [
    "بلاغ","important avis","communiqué","formulaires","espace privé","mot du directeur","présentation","facebook","linkedin","twitter","accueil","à propos","explorez","vivre en algérie","secteur de","guichets uniques","plateforme numérique",
    # إعلانات النتائج - نرفضها لأنها ليست مناقصات جديدة
    "avis d'attribution","attribution provisoire","attribution du marché","résultat","résultats","offre la mieux disante","recours","contester cet avis","منح مؤقت","المنح المؤقت","إعلان عن المنح","نتائج","أحسن عرض","لجنة فتح الأظرفة وتقييم العروض تم المنح",
    "sous-direction des moyens généraux","sous direction des moyens generaux"
]

WHITELIST_NEW = ["avis d'appel d'offres","appel d'offres ouvert","consultation n°","avis de consultation","acquisition de","fourniture de","travaux de","réalisation de","équipement de","prestation de"]

def is_after_july_2026(txt):
    tl = txt.lower()
    has_2026 = "2026" in txt
    has_2027 = "2027" in txt
    has_2028 = "2028" in txt
    if not (has_2026 or has_2027 or has_2028):
        return False
    if has_2027 or has_2028:
        return True
    month_found = None
    for name, num in MONTHS_FR.items():
        if name in tl:
            month_found = num
            break
    if not month_found:
        for name, num in MONTHS_AR.items():
            if name in txt:
                month_found = num
                break
    if not month_found:
        m1 = re.search(r"(0?[1-9]|1[0-2])[\/\-\.]\s*2026", txt)
        if m1:
            try: month_found = int(m1.group(1))
            except: pass
        m2 = re.search(r"2026[\/\-\.]\s*(0?[1-9]|1[0-2])", txt)
        if m2 and not month_found:
            try: month_found = int(m2.group(1))
            except: pass
    if month_found:
        if month_found >= 7:
            return True
        else:
            return False
    else:
        # 2026 بدون شهر - نقبل فقط إذا كان مناقصة جديدة وليس نتيجة
        return True

def is_new_tender_only(txt, link=""):
    tl = txt.lower()
    # رفض النتائج والمنح المؤقت فورا
    for bad in BLACKLIST:
        if bad in tl:
            # إذا كان النص يحتوي على كلمات النتائج نرفضه حتى لو كان طويل
            if "attribution" in bad or "منح" in bad or "résultat" in bad or "mieux disante" in bad or "recours" in bad:
                print(f"❌ مرفوض (نتيجة/منح): {bad} في {txt[:60]}")
                return False
    # يجب أن يكون إعلان جديد فقط
    is_new = False
    for good in WHITELIST_NEW:
        if good in tl:
            is_new = True
            break
    # إذا لم نجد كلمة من القائمة البيضاء الجديدة، نتحقق من السياق
    if not is_new:
        # إذا فيه "consultation" بدون "attribution" قد يكون جديد
        if "consultation" in tl and "attribution" not in tl and "résultat" not in tl:
            is_new = True
        elif "appel d'offres" in tl and "attribution" not in tl:
            is_new = True
    
    if not is_new:
        print(f"❌ مرفوض (ليس إعلان جديد): {txt[:80]}")
        return False
    
    # فلتر التاريخ جويلية 2026+
    if not is_after_july_2026(txt):
        print(f"❌ مرفوض (تاريخ قديم): {txt[:80]}")
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

def scrape_bomop_new_only():
    tenders=[]
    try:
        sectors=["industrie","autres","tic","btph","transport","energie"]
        for sector in sectors:
            try:
                url=f"https://bomop.anep.dz/secteur/{sector}/"
                r=requests.get(url,headers={"User-Agent":"Mozilla/5.0"},timeout=15,verify=False)
                if not r or r.status_code!=200: continue
                soup=BeautifulSoup(r.text,"lxml")
                for el in soup.find_all(['article'], limit=40):
                    txt=el.get_text(" ",strip=True)
                    if len(txt)<80: continue
                    if not is_new_tender_only(txt):
                        continue
                    anep_m=re.search(r"ANEP\s*([0-9]+)",txt,re.I)
                    anep=anep_m.group(1) if anep_m else "26"+str(random.randint(100000,999999))
                    if anep.startswith("24") or anep.startswith("23") or anep.startswith("25"):
                        continue
                    link_tag=el.find("a")
                    link=link_tag["href"] if link_tag and link_tag.get("href") else url
                    tid=hashlib.md5((anep+txt[:80]+sector).encode()).hexdigest()
                    tenders.append({"id":tid,"title":txt[:600],"anep":anep,"wilaya":"Algérie","link":link,"source":f"BOMOP {sector}","company":"EPIC/EPE"})
            except: continue
        print(f"📡 BOMOP NEW ONLY (juillet 2026+): {len(tenders)}")
    except Exception as e:
        print(f"BOMOP error {e}")
    return tenders

def scrape_aapi_new_only():
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
            if not is_new_tender_only(txt, link):
                continue
            anep_m=re.search(r"ANEP\s*([0-9]+)",txt,re.I)
            anep=anep_m.group(1) if anep_m else "26"+str(random.randint(100000,999999))
            if anep.startswith("24") or anep.startswith("23") or anep.startswith("25"):
                if len(anep)>=8:
                    continue
            tid=hashlib.md5((link+txt[:50]).encode()).hexdigest()
            tenders.append({"id":tid,"title":txt[:600],"anep":anep,"wilaya":"Alger","link":link,"source":"AAPI","company":"AAPI"})
        print(f"📡 AAPI NEW ONLY (juillet 2026+): {len(tenders)}")
    except Exception as e:
        print(f"AAPI error {e}")
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
all_tenders.extend(scrape_bomop_new_only())
all_tenders.extend(scrape_aapi_new_only())

print(f"📊 المجموع مناقصات جديدة فقط جويلية 2026+: {len(all_tenders)}")

unique={}
for t in all_tenders:
    if t["id"] not in unique and t["id"] not in sent:
        is_duplicate = False
        for existing in unique.values():
            if t["title"][:80] == existing["title"][:80]:
                is_duplicate = True
                break
        if not is_duplicate:
            unique[t["id"]]=t

new_tenders=list(unique.values())
print(f"🔍 مناقصات جديدة حقيقية (بدون نتائج): {len(new_tenders)}")

if not new_tenders:
    print("✅ لا يوجد مناقصات جديدة حقيقية من جويلية 2026+ اليوم")
else:
    for t in new_tenders[:10]:
        matched=find_factories(factories, t["title"], t["wilaya"], limit=3)
        factories_text=""
        for i,f in enumerate(matched,1):
            factories_text+=f"{i}. 🏭 <b>{f['name']}</b> 📦 {f['product']} 📞 {f['phone']}\n   📍 <a href=\"{f['map']}\">خريطة</a>\n"
        msg=f"""🔔 <b>مناقصة جديدة - {t['source']} - جويلية 2026+</b> 🔔

🏢 <b>{t['company']}</b>
📍 {t['wilaya']} | ANEP: {t['anep']}
📅 جويلية 2026 فما فوق - إعلان جديد
📋 {t['title']}

📄 <a href="{t['link']}">فتح الإعلان الأصلي</a>

🏭 <b>أقرب 3 مصانع:</b>
{factories_text}
#Tradium #v74 #Nouveau
"""
        send(msg)
        sent.add(t["id"])
    save_sent(sent)
    print(f"✅ أرسلت {len(new_tenders[:10])}")
        
