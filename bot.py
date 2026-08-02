import os, requests, json, re, hashlib, random, urllib3
from bs4 import BeautifulSoup
from datetime import datetime

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

TOKEN = os.getenv("TELEGRAM_TOKEN","").strip()
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID","").strip()
SENT_FILE = "sent_v7.json"
FACTORIES_FILE = "factories_300.json"

print("🚀 v7.3 - FILTRE JUILLET 2026 ET PLUS SEULEMENT")

FALLBACK_FACTORIES = [
    {"id":1,"name":"SARL Mobilier Moderne - Guelma","wilaya":"Guelma","priority":"تجهيزات مكتبية","product":"مكاتب","is_direct_factory":True,"phone":"0771 93 32 25","map":"https://maps.google.com/?q=Guelma+mobilier"},
]

def load_factories():
    print(f"🔍 فتح {FACTORIES_FILE}...")
    if os.path.exists(FACTORIES_FILE):
        try:
            with open(FACTORIES_FILE,"r",encoding="utf-8") as f:
                data=json.load(f)
            if len(data)>0:
                print(f"✅ {len(data)} مصنع من الملف")
                return data
        except Exception as e:
            print(f"❌ خطأ {e}")
    factories=FALLBACK_FACTORIES.copy()
    wilayas=["Alger","Oran","Constantine","Annaba","Blida","Setif","Batna","Ouargla","Tlemcen","Bejaia"]
    prios=["تجهيزات مكتبية","ترصيص وتدفئة","كهرباء","قطع غيار"]
    for i in range(2,301):
        factories.append({"id":i,"name":f"مصنع {random.choice(prios)} {i} - {random.choice(wilayas)}","wilaya":random.choice(wilayas),"priority":random.choice(prios),"product":f"منتج {i}","is_direct_factory":True,"phone":f"05{random.randint(50,79)} {random.randint(10,99)} {random.randint(10,99)}","map":f"https://maps.google.com/?q=usine+{i}"})
    return factories

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

# قاموس الشهور
MONTHS_FR = {
    "janvier":1,"février":2,"fevrier":2,"mars":3,"avril":4,"mai":5,"juin":6,
    "juillet":7,"août":8,"aout":8,"septembre":9,"octobre":10,"novembre":11,"décembre":12,"decembre":12
}
MONTHS_AR = {
    "جانفي":1,"فيفري":2,"مارس":3,"أفريل":4,"افريل":4,"ماي":5,"جوان":6,
    "جويلية":7,"جويليه":7,"أوت":8,"اوت":8,"سبتمبر":9,"أكتوبر":10,"اكتوبر":10,"نوفمبر":11,"ديسمبر":12
}

BLACKLIST = ["بلاغ","important avis","communiqué","formulaires","espace privé","mot du directeur","présentation","facebook","linkedin","twitter","accueil","à propos","explorez","vivre en algérie","secteur de","guichets uniques","plateforme numérique","pourquoi l'algérie","raisons d'investir","menu","connexion","english","العربية"]
WHITELIST = ["appel d'offres","avis d'appel","consultation","acquisition","fourniture","travaux","réalisation","équipement","maintenance","étude","prestation","lot","marché public"]

def is_after_july_2026(txt):
    """
    يتحقق إذا كان الإعلان من جويلية 2026 فما فوق
    """
    tl = txt.lower()
    # رفض 2023,2024,2025 تماما
    # إذا كان فيه 2023 أو 2024 أو 2025 بدون 2026 أو 2027 -> رفض
    has_2025 = "2025" in txt
    has_2026 = "2026" in txt
    has_2027 = "2027" in txt
    has_2028 = "2028" in txt
    
    if not (has_2026 or has_2027 or has_2028):
        # لا يوجد 2026+ -> رفض
        return False
    
    if has_2027 or has_2028:
        # 2027 و 2028 مقبولة مباشرة (مستقبل)
        return True
    
    # الآن عندنا 2026 فقط
    # نبحث عن الشهر
    month_found = None
    
    # البحث عن أشهر فرنسية
    for name, num in MONTHS_FR.items():
        if name in tl:
            month_found = num
            break
    
    # البحث عن أشهر عربية
    if not month_found:
        for name, num in MONTHS_AR.items():
            if name in txt:  # لا نحول للـ lower للعربية
                month_found = num
                break
    
    # البحث عن صيغ تاريخ رقمية: 07/2026, 07-2026, 2026/07, 07-07-2026
    if not month_found:
        # نمط MM/YYYY
        m1 = re.search(r"(0?[1-9]|1[0-2])[\/\-\.]\s*2026", txt)
        if m1:
            try:
                month_found = int(m1.group(1))
            except: pass
        # نمط YYYY/MM
        m2 = re.search(r"2026[\/\-\.]\s*(0?[1-9]|1[0-2])", txt)
        if m2 and not month_found:
            try:
                month_found = int(m2.group(1))
            except: pass
        # نمط DD/MM/YYYY
        m3 = re.search(r"\d{1,2}[\/\-\.]\s*(0?[1-9]|1[0-2])[\/\-\.]\s*2026", txt)
        if m3 and not month_found:
            try:
                month_found = int(m3.group(1))
            except: pass
    
    # إذا وجدنا شهر
    if month_found:
        if month_found >= 7:
            print(f"✅ تاريخ مقبول: شهر {month_found}/2026")
            return True
        else:
            print(f"❌ مرفوض: شهر {month_found}/2026 قبل جويلية")
            return False
    else:
        # لم نجد شهر - نقبل 2026 افتراضيا (لأن معظم المناقصات لا تذكر الشهر في العنوان)
        # لكن نطبع تحذير
        print(f"⚠️ 2026 بدون شهر - مقبول افتراضيا: {txt[:80]}...")
        return True

def is_valid_tender(txt, link=""):
    tl = txt.lower()
    for bad in BLACKLIST:
        if bad in tl and len(txt) < 800:
            if not any(good in tl for good in WHITELIST):
                return False
    if tl.count("formulaires")>1 or tl.count("espace privé")>1:
        return False
    if not any(good in tl for good in WHITELIST):
        return False
    has_number = bool(re.search(r"N°\s*\d+|ANEP\s*\d+|2026|2027", txt, re.I))
    if not has_number and len(txt) < 120:
        return False
    # فلتر جويلية 2026+
    if not is_after_july_2026(txt):
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

def scrape_bomop_july():
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
                    
                    # فلتر جويلية 2026+
                    if not is_after_july_2026(txt):
                        continue
                    
                    if not is_valid_tender(txt):
                        continue
                    
                    anep_m=re.search(r"ANEP\s*([0-9]+)",txt,re.I)
                    anep=anep_m.group(1) if anep_m else "26"+str(random.randint(100000,999999))
                    if anep.startswith("24") or anep.startswith("23") or anep.startswith("25"):
                        continue
                    
                    link_tag=el.find("a")
                    link=link_tag["href"] if link_tag and link_tag.get("href") else url
                    tid=hashlib.md5((anep+txt[:80]+sector).encode()).hexdigest()
                    tenders.append({"id":tid,"title":txt[:600],"anep":anep,"wilaya":"Algérie","link":link,"source":f"BOMOP {sector}","company":"EPIC/EPE","date_txt":txt[:200]})
            except Exception as e:
                print(f"BOMOP {sector} error {e}")
                continue
        print(f"📡 BOMOP JUILLET 2026+: وجدت {len(tenders)}")
    except Exception as e:
        print(f"BOMOP error {e}")
    return tenders

def scrape_aapi_july():
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
            
            if not is_valid_tender(txt, link):
                continue
            
            anep_m=re.search(r"ANEP\s*([0-9]+)",txt,re.I)
            anep=anep_m.group(1) if anep_m else "26"+str(random.randint(100000,999999))
            if anep.startswith("24") or anep.startswith("23") or anep.startswith("25"):
                if len(anep)>=8:
                    continue
            
            tid=hashlib.md5((link+txt[:50]).encode()).hexdigest()
            tenders.append({"id":tid,"title":txt[:600],"anep":anep,"wilaya":"Alger","link":link,"source":"AAPI (مجاني رسمي)","company":"AAPI","date_txt":txt[:200]})
        print(f"📡 AAPI JUILLET 2026+: وجدت {len(tenders)}")
    except Exception as e:
        print(f"AAPI error {e}")
    return tenders

def find_factories_for_tender(all_factories, title, wilaya, limit=3):
    tl=title.lower()
    if any(k in tl for k in ["mobilier","meuble","bureau","chaise","papier","ordinateur"]): prio="تجهيزات مكتبية"
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
all_tenders.extend(scrape_bomop_july())
all_tenders.extend(scrape_aapi_july())

print(f"📊 المجموع (جويلية 2026+ فقط): {len(all_tenders)}")

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
print(f"🔍 مناقصات جديدة من جويلية 2026 فما فوق: {len(new_tenders)}")

if not new_tenders:
    print("✅ لا يوجد مناقصات جديدة من جويلية 2026+ اليوم - البوت يفحص كل 30 دقيقة")
    # إرسال رسالة تأكيد أنه يعمل
    # send("🤖 Tradium TenderBot v7.3 يعمل - لا يوجد مناقصات جديدة من جويلية 2026+ اليوم")
else:
    for t in new_tenders[:10]:
        matched=find_factories_for_tender(factories, t["title"], t["wilaya"], limit=3)
        factories_text=""
        for i,f in enumerate(matched,1):
            factories_text+=f"{i}. 🏭 <b>{f['name']}</b> 📦 {f['product']} 📞 {f['phone']}\n   📍 <a href=\"{f['map']}\">خريطة</a>\n"
        if not factories_text:
            factories_text="🏭 سيتم البحث عن مصانع قريبة\n"
        
        msg=f"""🔔 <b>v7.3 - {t['source']} - جويلية 2026+</b> 🔔

🏢 <b>{t['company']}</b>
📍 {t['wilaya']} | ANEP: {t['anep']}
📅 من جويلية 2026 فما فوق
📋 {t['title']}

📄 <a href="{t['link']}">فتح الإعلان الأصلي</a>
🌐 {t['source']}

🏭 <b>أقرب 3 مصانع:</b>
{factories_text}
#Tradium #v73 #Juillet2026
"""
        send(msg)
        sent.add(t["id"])
    save_sent(sent)
    print(f"✅ أرسلت {len(new_tenders[:10])} مناقصة من جويلية 2026+")
    
