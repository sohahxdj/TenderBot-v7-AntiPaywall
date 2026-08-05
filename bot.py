import os, requests, json, re, hashlib, random, urllib3, html
from bs4 import BeautifulSoup
from datetime import datetime
from zoneinfo import ZoneInfo
from urllib.parse import urljoin

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

TOKEN = os.getenv("TELEGRAM_TOKEN","").strip()
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID","").strip()
SENT_FILE = "sent_v7.json"
FACTORIES_FILE = "factories_300.json"
ALGIERS = ZoneInfo("Africa/Algiers")
TODAY = datetime.now(ALGIERS)

print(f"🚀 v17 NEAREST + MAP - {TODAY.strftime('%d/%m/%Y')}")

WILAYAS = ["الجزائر","وهران","قسنطينة","عنابة","البليدة","سطيف","باتنة","بسكرة","بشار","تندوف","تمنراست","ورقلة","جانت","تلمسان","تيزي وزو","بجاية","جيجل","سكيكدة","الطارف","سوق أهراس","تبسة","خنشلة","أم البواقي","قالمة","ميلة","برج بوعريريج","البويرة","بومرداس","تيبازة","عين الدفلى","المدية","الجلفة","المسيلة","تيارت","تيسمسيلت","الأغواط","غرداية","الوادي","المغير","أولاد جلال","الشلف","مستغانم","معسكر","سعيدة","سيدي بلعباس","عين تموشنت","غليزان","أدرار","برج البحري","المرادية","خميستي","شرشال","عين الصفراء","النعامة","بني عباس"]

def extract_location_from_tender(txt):
    m = re.search(r"بولاية\s+([^\s،؛.]+)", txt)
    if m: return m.group(1)
    m = re.search(r"ولاية\s+([^\s،؛.]+)", txt)
    if m: return m.group(1)
    m = re.search(r"على مستوى\s+([^\s،؛.()]+)", txt)
    if m: return m.group(1).split()[0]
    m = re.search(r"ب([^\s]+)\/ن ع", txt)
    if m: return m.group(1)
    for w in WILAYAS:
        if w in txt:
            return w
    return None

def get_factory_location(f):
    return " ".join([str(f.get(k,"")) for k in ["wilaya","city","address","name"]]).lower()

def choose_nearest_factories(tender_title, factories, n=3):
    if not factories:
        return []
    loc = extract_location_from_tender(tender_title)
    if not loc:
        return random.sample(factories, min(n, len(factories)))
    scored = []
    loc_low = loc.lower()
    for f in factories:
        f_loc = get_factory_location(f)
        score = 0 if loc_low in f_loc or any(part in f_loc for part in loc_low.split()) else 1
        scored.append((score, f))
    scored.sort(key=lambda x: x[0])
    nearest = [f for s,f in scored if s==0]
    if len(nearest) < n:
        rest = [f for s,f in scored if s==1]
        random.shuffle(rest)
        nearest += rest
    return nearest[:n]

def load_factories():
    try:
        with open(FACTORIES_FILE,"r",encoding="utf-8") as f: return json.load(f)
    except: return []

def load_sent():
    try:
        if os.path.exists(SENT_FILE):
            with open(SENT_FILE,"r",encoding="utf-8") as f:
                return set(json.load(f).get("ids",[]))
    except: pass
    return set()

def save_sent(s):
    with open(SENT_FILE,"w",encoding="utf-8") as f:
        json.dump({"ids": list(s),"last_update": TODAY.isoformat(),"count": len(s)}, f, ensure_ascii=False, indent=2)

def send(text):
    url=f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    data={"chat_id":CHAT_ID,"text":text,"parse_mode":"HTML","disable_web_page_preview":False}
    try: return requests.post(url,data=data,timeout=30).status_code==200
    except: return False

def gen_id(t,s):
    clean = re.sub(r'\s+', ' ', t[:200].lower().strip())[:120]
    return hashlib.md5(f"{clean}|{s}".encode()).hexdigest()

def gen_anep(t): return f"26{abs(hash(t))%900000+100000}"

MONTH_MAP={"جانفي":1,"فيفري":2,"مارس":3,"أفريل":4,"ماي":5,"جوان":6,"جويلية":7,"أوت":8,"اوت":8,"سبتمبر":9,"أكتوبر":10,"نوفمبر":11,"ديسمبر":12}
MONTH_PAT="|".join([re.escape(k) for k in MONTH_MAP])

def get_mo(n):
    n=n.lower()
    for k,v in MONTH_MAP.items():
        if k in n: return v
    return None

def extract_dates(txt):
    dates=[]
    for m in re.finditer(rf"(\d{{1,2}})\s+({MONTH_PAT})\s+(20\d{{2}})", txt, flags=re.I):
        mo=get_mo(m.group(2))
        if not mo: continue
        y=int(m.group(3)); d=int(m.group(1))
        if y==2026 and mo==8 and 2<=d<=TODAY.day:
            dates.append((y,mo,d,m.group(0)))
    return dates

def safe_get(url):
    for _ in range(3):
        try:
            r=requests.get(url, headers={"User-Agent":"Mozilla/5.0"}, timeout=30, verify=False)
            if len(r.text)>10000: return r
        except: pass
    return None

def scrape():
    r=safe_get("https://www.mdn.dz/site_principal/sommaire/appels/appels_ar.php")
    if not r: return [], None
    print(f"HTTP {r.status_code} - {len(r.text)}")
    all_dates=extract_dates(r.text)
    if not all_dates: return [], None
    latest=max(all_dates, key=lambda x: x[:3])
    print(f"📅 آخر تاريخ: {latest[3]}")
    soup=BeautifulSoup(r.text,"lxml")
    cur=None; seen=set(); tenders=[]
    for el in soup.find_all(['div','p','li','td'], limit=1200):
        txt=el.get_text(" ",strip=True)
        if len(txt)<15: continue
        if len(txt)<120:
            d=extract_dates(txt)
            if d: cur=d[0]; continue
        if "طلب العروض" not in txt: continue
        if not cur: continue
        if cur[:3]!=latest[:3]: continue
        if not re.search(r"\d{1,4}\s*/\s*2026", txt): continue
        if txt[:120] in seen: continue
        seen.add(txt[:120])
        link="https://www.mdn.dz/site_principal/sommaire/appels/appels_ar.php"
        for a in el.find_all('a', href=True):
            if ".pdf" in a['href'].lower():
                link=urljoin("https://www.mdn.dz", a['href'])
                break
        tenders.append({"id":gen_id(txt,"MDN"),"title":txt,"anep":gen_anep(txt),"link":link,"date":f"{cur[2]:02d}/{cur[1]:02d}/{cur[0]}"})
    print(f"📡 مناقصات {latest[3]} فقط: {len(tenders)}")
    return tenders, latest

factories=load_factories()
sent=load_sent()
print(f"🔒 مرسلة سابقا: {len(sent)} - مصانع {len(factories)}")
tenders,_=scrape()
new=[t for t in tenders if t["id"] not in sent][:10]
print(f"🔍 جديدة: {len(new)}")
if not os.path.exists(SENT_FILE): save_sent(sent)

for t in new:
    nearest = choose_nearest_factories(t['title'], factories, 3)
    fac=""
    loc = extract_location_from_tender(t['title']) or "الجزائر"
    for i,f in enumerate(nearest,1):
        name=html.escape(f.get('name','')[:45])
        phone=f.get('phone') or f.get('tel') or ""
        murl=f.get('map') or f.get('maps') or f.get('location') or f"https://www.google.com/maps/search/{name}+{loc}"
        fac+=f"{i}. 🏭 <b>{name}</b> ({loc})\n📞 <code>{phone}</code> | <a href='{murl}'>🗺️ خريطة الموقع</a>\n"
    msg=f"🔔 <b>{t['date']} - {loc}</b>\n{t['title'][:600]}\n<a href='{t['link']}'>📎 رابط الإعلان الأصلي / PDF</a>\n\n{fac}🔖 {t['anep']}"
    if send(msg):
        sent.add(t["id"])
        print(f"✅ {t['anep']} -> {loc}")

save_sent(sent)
print(f"🏁 محفوظ {len(sent)}")
