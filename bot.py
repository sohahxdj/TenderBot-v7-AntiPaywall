import os, requests, json, re, hashlib, random, urllib3
from bs4 import BeautifulSoup
from datetime import datetime

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

TOKEN = os.getenv("TELEGRAM_TOKEN","").strip()
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID","").strip()
SENT_FILE = "sent_v7.json"
FACTORIES_FILE = "factories_300.json"

print("🚀 v8.8 - يفهم كل التواريخ عربي/فرنسي/أرقام")

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
        if os.path.exists(SENT_FILE):
            with open(SENT_FILE,"r",encoding="utf-8") as f:
                data=json.load(f)
                if isinstance(data, list): return set(data)
                elif isinstance(data, dict): return set(data.get("ids",[]))
        return set()
    except: return set()

def save_sent(sent_set):
    try:
        data={"ids": list(sent_set),"last_update": datetime.now().isoformat(),"count": len(sent_set)}
        with open(SENT_FILE,"w",encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        with open("sent_ids_backup.txt","w",encoding="utf-8") as f:
            for sid in sent_set: f.write(sid+"\n")
        print(f"💾 حفظ {len(sent_set)}")
    except Exception as e: print(f"❌ {e}")

def send(text):
    url=f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    data={"chat_id":CHAT_ID,"text":text,"parse_mode":"HTML","disable_web_page_preview":False}
    try:
        r=requests.post(url,data=data,timeout=30)
        return r.status_code==200
    except: return False

def generate_stable_id_fixed(title, source):
    clean = re.sub(r'\s+', ' ', title[:200].lower().strip())[:120]
    base = f"{clean}|{source}"
    return hashlib.md5(base.encode('utf-8')).hexdigest()

def generate_anep_deterministic(title):
    h = abs(hash(title)) % 900000 + 100000
    return f"26{h}"

# === خريطة شاملة لكل الشهور ===
MONTH_MAP = {
    # عربي جزائري
    "جانفي":1, "فيفري":2, "مارس":3, "أفريل":4, "افريل":4, "ماي":5, "جوان":6, "جويلية":7, "جويليه":7, "أوت":8, "اوت":8, "أوث":8, "اوث":8, "سبتمبر":9, "أكتوبر":10, "اكتوبر":10, "نوفمبر":11, "ديسمبر":12,
    # عربي فصحى
    "يناير":1, "فبراير":2, "مارس":3, "أبريل":4, "ابريل":4, "مايو":5, "يونيو":6, "يوليو":7, "أغسطس":8, "اغسطس":8, "غشت":8, "أوت":8, "شتنبر":9, "أكتوبر":10, "نونبر":11, "دجنبر":12,
    "كانون الثاني":1, "شباط":2, "آذار":3, "نيسان":4, "أيار":5, "حزيران":6, "تموز":7, "آب":8, "أيلول":9, "تشرين الأول":10, "تشرين الاول":10, "تشرين الثاني":11, "كانون الأول":12, "كانون الاول":12,
    # فرنسي
    "janvier":1, "janv":1, "février":2, "fevrier":2, "fev":2, "fév":2, "mars":3, "avril":4, "avr":4, "mai":5, "juin":6, "juillet":7, "juil":7, "août":8, "aout":8, "aou":8, "septembre":9, "sept":9, "octobre":10, "oct":10, "novembre":11, "nov":11, "décembre":12, "decembre":12, "dec":12,
}

# بناء regex للشهور (الأطول أولا)
MONTH_PATTERN = "|".join(sorted([re.escape(k) for k in MONTH_MAP.keys()], key=len, reverse=True))

def get_month_num(name):
    name = name.lower().strip()
    name = re.sub(r'[^a-z\u0600-\u06FFéèêàâîôû]+', ' ', name).strip()
    if name in MONTH_MAP: return MONTH_MAP[name]
    for key,val in MONTH_MAP.items():
        if key in name or name in key:
            return val
    # أرقام
    if name.isdigit():
        n=int(name)
        if 1<=n<=12: return n
    return None

def extract_full_dates_only(txt):
    dates=[]
    # 1- أرقام: 04/08/2026, 04-08-2026, 04.08.2026
    for m in re.finditer(r"\b(\d{1,2})[\/\-\.]\s*(\d{1,2})[\/\-\.]\s*(20\d{2})\b", txt):
        try:
            d=int(m.group(1)); mo=int(m.group(2)); y=int(m.group(3))
            if 1<=mo<=12 and 1<=d<=31 and 2020<=y<=2030:
                dates.append((y,mo,d))
        except: pass
    # 2- نصي مع سنة: 04 أوت 2026, 4 Aout 2026
    try:
        pattern = rf"\b(\d{{1,2}})\s+({MONTH_PATTERN})\s+(20\d{{2}})\b"
        for m in re.finditer(pattern, txt, flags=re.I):
            try:
                d=int(m.group(1)); mo_name=m.group(2); y=int(m.group(3))
                mo=get_month_num(mo_name)
                if mo and 1<=d<=31:
                    dates.append((y,mo,d))
            except: pass
    except Exception as e: print(f"regex error {e}")
    # 3- نصي بدون سنة: 04 أوت (نفترض 2026)
    try:
        pattern2 = rf"\b(\d{{1,2}})\s+({MONTH_PATTERN})\b"
        for m in re.finditer(pattern2, txt, flags=re.I):
            try:
                d=int(m.group(1)); mo_name=m.group(2)
                # تجنب التكرار مع اللي فيه سنة
                if any(str(d) in txt and mo_name in txt and "2026" in txt for _ in [1]): pass
                mo=get_month_num(mo_name)
                if mo and 1<=d<=31:
                    # إذا بدون سنة، نفترض 2026 إذا اليوم 2026
                    if len(dates)==0 or not any(dd==d and mm==mo for _,mm,dd in dates):
                        dates.append((2026,mo,d))
            except: pass
    except: pass
    return dates

def clean_consultation_numbers(txt):
    txt = re.sub(r"N°\s*\d+\s*/\s*20\d{2}", " ", txt, flags=re.I)
    txt = re.sub(r"رقم\s*\d+\s*/\s*20\d{2}", " ", txt, flags=re.I)
    return txt

def is_after_august_2026_final(txt):
    cleaned = clean_consultation_numbers(txt)
    real_dates = extract_full_dates_only(cleaned)
    if real_dates:
        for y, mo, d in real_dates:
            if y < 2026 or (y == 2026 and mo < 8):
                return False
        return True
    else:
        if "2026" in cleaned:
            if any(k in cleaned.lower() for k in ["إعذار","mise en demeure","فسخ"]): return False
            if "2025" not in cleaned and "2024" not in cleaned:
                if any(k in cleaned.lower() for k in ["طلب العروض","appel d'offres","consultation"]): return True
        return False

def is_today_tender(txt, current_header_date=None):
    today = datetime.now()
    dates = extract_full_dates_only(txt)
    if current_header_date: dates.append(current_header_date)
    if dates:
        for y,mo,d in dates:
            if y==today.year and mo==today.month and d==today.day:
                return True
        return False
    else:
        low = txt.lower()
        if any(k in low for k in ["juin","juillet","جوان","جويلية","06/2026","07/2026"]): return False
        return True

def is_new_tender(txt, current_header_date=None):
    tl = txt.lower()
    if any(k in tl for k in ["إعذار","mise en demeure","فسخ"]): return False
    if not any(k in tl for k in ["طلب العروض","طلب عروض","appel d'offres","consultation","اقتناء","إقتناء"]): return False
    if "attribution" in tl or "résultat" in tl: return False
    if not is_after_august_2026_final(txt): return False
    if not is_today_tender(txt, current_header_date): return False
    return True

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
        for t in soup.find_all('table'): rows.extend(t.find_all('tr'))
        if not rows: rows=soup.find_all('article', limit=50)
        for el in rows:
            txt=el.get_text(" ",strip=True)
            if len(txt)<80 or len(txt)>1500: continue
            if not is_new_tender(txt): continue
            link_tag=el.find("a", href=True)
            link=link_tag["href"] if link_tag else url
            if link.startswith("/"): link="https://aapi.dz"+link
            tid=generate_stable_id_fixed(txt, "AAPI")
            tenders.append({"id":tid,"title":txt[:600],"anep":generate_anep_deterministic(txt),"wilaya":"Alger","link":link,"source":"AAPI","company":"AAPI"})
        print(f"📡 AAPI: {len(tenders)}")
    except: pass
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
            if not is_new_tender(txt): continue
            link_tag=el.find('a', href=True)
            if not link_tag: continue
            link=link_tag['href']
            if link.startswith("/"): link="https://www.safqatic.dz"+link
            tid=generate_stable_id_fixed(txt, "SAFQATIC")
            tenders.append({"id":tid,"title":txt[:600],"anep":generate_anep_deterministic(txt),"wilaya":"Algérie","link":link,"source":"Safqatic","company":"Algérie Télécom"})
        print(f"📡 Safqatic: {len(tenders)}")
    except: pass
    return tenders

def scrape_mdn_fixed():
    tenders=[]
    try:
        url="https://www.mdn.dz/site_principal/sommaire/appels/appels_ar.php"
        r=safe_get(url)
        if not r or r.status_code!=200: return tenders
        soup=BeautifulSoup(r.text,"lxml")
        current_date=None
        for el in soup.find_all(['div','p','h3','h4','li','span'], limit=600):
            txt=el.get_text(" ",strip=True)
            if len(txt)<5: continue
            # هل هذا هيدر تاريخ؟
            if len(txt)<40:
                dlist=extract_full_dates_only(txt)
                if dlist:
                    current_date=dlist[0]
                    print(f"📅 هيدر: {txt} -> {current_date}")
                    continue
            if len(txt)<30 or len(txt)>1000: continue
            if not is_new_tender(txt, current_date): continue
            link=url
            a_tag=el.find('a', href=True)
            if a_tag and a_tag.get('href'):
                link=a_tag['href']
                if link.startswith("/"): link="https://www.mdn.dz"+link
            tid=generate_stable_id_fixed(txt, "MDN")
            if any(t['id']==tid for t in tenders): continue
            tenders.append({"id":tid,"title":txt[:700],"anep":generate_anep_deterministic(txt),"wilaya":"Algérie","link":link,"source":"MDN","company":"وزارة الدفاع"})
        print(f"📡 MDN: {len(tenders)} اليوم فقط")
    except Exception as e: print(f"MDN error {e}")
    return tenders

def find_factories(all_factories, title, wilaya, limit=3):
    return random.sample(all_factories, min(limit, len(all_factories)))

factories=load_factories()
sent=load_sent()
print(f"🔒 المرسلة: {len(sent)} - اليوم {datetime.now().strftime('%d/%m/%Y')}")

all_tenders=[]
all_tenders.extend(scrape_aapi())
all_tenders.extend(scrape_safqatic_fixed())
all_tenders.extend(scrape_mdn_fixed())

print(f"📊 الخام اليوم: {len(all_tenders)}")
unique={}
for t in all_tenders:
    if t["id"] in sent: continue
    if any(t["title"][:90]==e["title"][:90] for e in unique.values()): continue
    unique[t["id"]]=t

new_tenders=list(unique.values())
print(f"🔍 جديدة اليوم: {len(new_tenders)}")

if not new_tenders:
    print("✅ لا يوجد جديدة اليوم")
else:
    for t in new_tenders[:15]:
        matched=find_factories(factories, t["title"], t["wilaya"], limit=3)
        factories_text="".join([f"{i}. 🏭 <b>{f['name']}</b>\n" for i,f in enumerate(matched,1)])
        msg=f"""🔔 <b>مناقصة {datetime.now().strftime('%d/%m/%Y')} - {t['source']}</b> 🔔

🏢 {t['company']}
📋 {t['title']}

📄 <a href="{t['link']}">فتح الإعلان</a>

{factories_text}
#Tradium #v88
"""
        if send(msg): sent.add(t["id"])
    save_sent(sent)
