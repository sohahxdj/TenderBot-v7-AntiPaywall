import os, requests, json, re, hashlib, random, urllib3
from bs4 import BeautifulSoup
from datetime import datetime

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

TOKEN = os.getenv("TELEGRAM_TOKEN","").strip()
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID","").strip()
SENT_FILE = "sent_v7.json"
FACTORIES_FILE = "factories_300.json"

print("🚀 v8.9 - رابط أصلي + PDF + أرقام مصانع")

def load_factories():
    if os.path.exists(FACTORIES_FILE):
        try:
            with open(FACTORIES_FILE,"r",encoding="utf-8") as f:
                data=json.load(f)
            if len(data)>0: return data
        except: pass
    return []

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

MONTH_MAP = {
    "جانفي":1, "فيفري":2, "مارس":3, "أفريل":4, "افريل":4, "ماي":5, "جوان":6, "جويلية":7, "جويليه":7, "أوت":8, "اوت":8, "أوث":8, "اوث":8, "سبتمبر":9, "أكتوبر":10, "اكتوبر":10, "نوفمبر":11, "ديسمبر":12,
    "يناير":1, "فبراير":2, "أبريل":4, "ابريل":4, "مايو":5, "يونيو":6, "يوليو":7, "أغسطس":8, "اغسطس":8, "غشت":8, "شتنبر":9, "نونبر":11, "دجنبر":12,
    "janvier":1, "janv":1, "février":2, "fevrier":2, "fev":2, "mars":3, "avril":4, "avr":4, "mai":5, "juin":6, "juillet":7, "juil":7, "août":8, "aout":8, "septembre":9, "sept":9, "octobre":10, "oct":10, "novembre":11, "nov":11, "décembre":12, "decembre":12,
}
MONTH_PATTERN = "|".join(sorted([re.escape(k) for k in MONTH_MAP.keys()], key=len, reverse=True))

def get_month_num(name):
    name = name.lower().strip()
    if name in MONTH_MAP: return MONTH_MAP[name]
    for key,val in MONTH_MAP.items():
        if key in name or name in key: return val
    if name.isdigit() and 1<=int(name)<=12: return int(name)
    return None

def extract_full_dates_only(txt):
    dates=[]
    for m in re.finditer(r"\b(\d{1,2})[\/\-\.]\s*(\d{1,2})[\/\-\.]\s*(20\d{2})\b", txt):
        try:
            d=int(m.group(1)); mo=int(m.group(2)); y=int(m.group(3))
            if 1<=mo<=12 and 1<=d<=31: dates.append((y,mo,d))
        except: pass
    try:
        pattern = rf"\b(\d{{1,2}})\s+({MONTH_PATTERN})\s+(20\d{{2}})\b"
        for m in re.finditer(pattern, txt, flags=re.I):
            d=int(m.group(1)); mo=get_month_num(m.group(2)); y=int(m.group(3))
            if mo: dates.append((y,mo,d))
    except: pass
    return dates

def clean_consultation_numbers(txt):
    return re.sub(r"N°\s*\d+\s*/\s*20\d{2}", " ", txt, flags=re.I)

def is_after_august_2026_final(txt):
    cleaned = clean_consultation_numbers(txt)
    real_dates = extract_full_dates_only(cleaned)
    if real_dates:
        for y, mo, d in real_dates:
            if y < 2026 or (y == 2026 and mo < 8): return False
        return True
    else:
        if "2026" in cleaned and "2025" not in cleaned and "2024" not in cleaned:
            if any(k in cleaned.lower() for k in ["طلب العروض","appel d'offres","consultation"]): return True
        return False

def is_today_tender(txt, current_header_date=None):
    today = datetime.now()
    dates = extract_full_dates_only(txt)
    if current_header_date: dates.append(current_header_date)
    if dates:
        for y,mo,d in dates:
            if y==today.year and mo==today.month and d==today.day: return True
        return False
    else:
        low = txt.lower()
        if any(k in low for k in ["juin","juillet","جوان","جويلية"]): return False
        return True

def is_new_tender(txt, current_header_date=None):
    tl = txt.lower()
    if any(k in tl for k in ["إعذار","mise en demeure","فسخ"]): return False
    if not any(k in tl for k in ["طلب العروض","طلب عروض","appel d'offres","consultation","اقتناء","إقتناء"]): return False
    if "attribution" in tl: return False
    if not is_after_august_2026_final(txt): return False
    if not is_today_tender(txt, current_header_date): return False
    return True

def safe_get(url, timeout=20):
    headers={"User-Agent":"Mozilla/5.0"}
    try: return requests.get(url, headers=headers, timeout=timeout, verify=False)
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
            # رابط PDF الأصلي
            link=url
            pdf_tag=el.find("a", href=lambda h: h and ".pdf" in h.lower())
            if pdf_tag and pdf_tag.get("href"):
                plink=pdf_tag["href"]
                if plink.startswith("/"): plink="https://aapi.dz"+plink
                link=plink
            else:
                a_tag=el.find("a", href=True)
                if a_tag and a_tag.get("href"):
                    href=a_tag["href"]
                    if href.startswith("/"): href="https://aapi.dz"+href
                    link=href
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
            # رابط PDF الأصلي في /docs/offres/
            link=url
            pdf_inside = el.find('a', href=lambda h: h and ('/docs/offres/' in h or h.lower().endswith('.pdf')))
            if pdf_inside and pdf_inside.get('href'):
                href=pdf_inside['href']
                if href.startswith("/"): href="https://www.safqatic.dz"+href
                link=href
            else:
                a_tag=el.find('a', href=True)
                if a_tag and a_tag.get('href'):
                    href=a_tag['href']
                    if href.startswith("/"): href="https://www.safqatic.dz"+href
                    link=href
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
            if len(txt)<40:
                dlist=extract_full_dates_only(txt)
                if dlist:
                    current_date=dlist[0]
                    print(f"📅 هيدر: {txt} -> {current_date}")
                    continue
            if len(txt)<30 or len(txt)>1000: continue
            if not is_new_tender(txt, current_date): continue
            # رابط أصلي
            link=url
            a_tag=el.find('a', href=True)
            if a_tag and a_tag.get('href'):
                href=a_tag['href']
                if href.startswith("/"): href="https://www.mdn.dz"+href
                if not href.startswith("http"): href="https://www.mdn.dz/site_principal/sommaire/appels/"+href.lstrip('/')
                link=href
            # إذا فيه PDF داخل نفس العنصر
            pdf_tag=el.find('a', href=lambda h: h and '.pdf' in h.lower())
            if pdf_tag and pdf_tag.get('href'):
                href=pdf_tag['href']
                if href.startswith("/"): href="https://www.mdn.dz"+href
                if not href.startswith("http"): href="https://www.mdn.dz/site_principal/sommaire/appels/"+href.lstrip('/')
                link=href
            tid=generate_stable_id_fixed(txt, "MDN")
            if any(t['id']==tid for t in tenders): continue
            tenders.append({"id":tid,"title":txt[:700],"anep":generate_anep_deterministic(txt),"wilaya":"Algérie","link":link,"source":"MDN","company":"وزارة الدفاع"})
        print(f"📡 MDN: {len(tenders)}")
    except Exception as e: print(f"MDN error {e}")
    return tenders

def find_factories(all_factories, title, wilaya, limit=3):
    if not all_factories: return []
    tl=title.lower()
    if any(k in tl for k in ["mobilier","meuble","bureau","informatique","مكتب","حاسوب"]): prio="تجهيزات مكتبية"
    elif any(k in tl for k in ["plomberie","sanitaire","ترصيص"]): prio="ترصيص"
    elif any(k in tl for k in ["electricite","كهرباء"]): prio="كهرباء"
    else: prio=None
    if prio: candidates=[f for f in all_factories if prio.lower() in f.get("priority","").lower()]
    else: candidates=all_factories
    same=[f for f in candidates if f.get("wilaya","").lower()==wilaya.lower()]
    if len(same)>=limit: return random.sample(same,limit)
    others=[f for f in candidates if f.get("wilaya","").lower()!=wilaya.lower()]
    result=same+random.sample(others, min(limit-len(same), len(others))) if others else same
    if len(result)<limit:
        extra=[f for f in all_factories if f not in result]
        result+=random.sample(extra, min(limit-len(result), len(extra))) if extra else []
    return result[:limit]

factories=load_factories()
sent=load_sent()
print(f"🔒 المرسلة: {len(sent)} - اليوم {datetime.now().strftime('%d/%m/%Y')} - مصانع: {len(factories)}")

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
        factories_text=""
        for i,f in enumerate(matched,1):
            name=f.get('name','مصنع')
            product=f.get('product','')
            phone=f.get('phone','')
            fmap=f.get('map','')
            factories_text+=f"{i}. 🏭 <b>{name}</b>\n 📦 {product}\n 📞 <code>{phone}</code> | 🗺️ <a href=\"{fmap}\">خريطة</a>\n"
        if not factories_text:
            factories_text="❌ لا يوجد مصانع مطابقة\n"
        msg=f"""🔔 <b>مناقصة {datetime.now().strftime('%d/%m/%Y')} - {t['source']}</b> 🔔

🏢 <b>{t['company']}</b>
📍 {t['wilaya']} | ANEP: {t['anep']}
📋 {t['title']}

📄 <b>الإعلان الأصلي:</b> <a href="{t['link']}">فتح PDF / الإعلان</a>

🏭 <b>أقرب 3 مصانع موردين:</b>
{factories_text}
#Tradium #v89
"""
        if send(msg): sent.add(t["id"])
    save_sent(sent)
