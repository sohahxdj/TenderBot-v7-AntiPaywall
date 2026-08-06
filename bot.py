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

print(f"🚀 v17 ACCORDION 05 AOUT - {TODAY.strftime('%d/%m/%Y')}")

WILAYAS = ["الجزائر","المرادية","خميستي","جيجل","شرشال","وهران","قسنطينة","بشار","تندوف","ورقلة","بومرداس","تيبازة","البويرة","البليدة","بجاية","سكيكدة","عنابة","سطيف","باتنة","تلمسان","الشلف","مستغانم","سيدي بلعباس"]

def extract_location(txt):
    m=re.search(r"بولاية\s+([^\s،؛.]+)", txt)
    if m: return m.group(1)
    m=re.search(r"على مستوى\s+([^\s،؛./]+)", txt)
    if m: return m.group(1).split()[0]
    m=re.search(r"الوحدة الواقعة ب([^\s،.]+)", txt)
    if m: return m.group(1)
    for w in WILAYAS:
        if w in txt: return w
    return "الجزائر"

def choose_nearest(title, factories, n=3):
    if not factories: return []
    loc = extract_location(title).lower()
    scored=[]
    for f in factories:
        f_txt = " ".join([str(f.get(k,"")) for k in ["wilaya","city","address","name"]]).lower()
        score = 0 if loc in f_txt else 1
        scored.append((score,f))
    scored.sort(key=lambda x: x[0])
    nearest = [f for s,f in scored if s==0][:n]
    if len(nearest)<n:
        rest=[f for s,f in scored if s==1]
        random.shuffle(rest)
        nearest+=rest[:n-len(nearest)]
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
        json.dump({"ids":list(s),"last_update":TODAY.isoformat(),"count":len(s)},f,ensure_ascii=False,indent=2)
def send(t):
    url=f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    data={"chat_id":CHAT_ID,"text":t,"parse_mode":"HTML","disable_web_page_preview":False}
    try: return requests.post(url,data=data,timeout=30).status_code==200
    except: return False
def gen_id(t,s): return hashlib.md5(f"{re.sub(r'\s+',' ',t[:200].lower())[:120]}|{s}".encode()).hexdigest()
def gen_anep(t): return f"26{abs(hash(t))%900000+100000}"

MONTH_MAP={"جانفي":1,"فيفري":2,"مارس":3,"أفريل":4,"ماي":5,"جوان":6,"جويلية":7,"أوت":8,"اوت":8,"سبتمبر":9,"أكتوبر":10,"نوفمبر":11,"ديسمبر":12}
MONTH_PAT="|".join([re.escape(k) for k in MONTH_MAP])
def get_mo(n):
    for k,v in MONTH_MAP.items():
        if k in n.lower(): return v
    return None
def extract_dates(txt):
    dates=[]
    for m in re.finditer(rf"(\d{{1,2}})\s+({MONTH_PAT})\s+(20\d{{2}})", txt, flags=re.I):
        mo=get_mo(m.group(2))
        if not mo: continue
        y=int(m.group(3)); d=int(m.group(1))
        dates.append((y,mo,d,m.group(0).strip()))
    return dates

def safe_get(url):
    try:
        r=requests.get(url, headers={"User-Agent":"Mozilla/5.0"}, timeout=30, verify=False)
        if len(r.text)>5000: return r
    except: pass
    return None

def scrape():
    url="https://www.mdn.dz/site_principal/sommaire/appels/appels_ar.php"
    r=safe_get(url)
    if not r: return []
    soup=BeautifulSoup(r.text,"lxml")
    all_dates=extract_dates(r.text)
    # فلتر 2-5 أوت كما طلبت
    filtered=[d for d in all_dates if d[1]==8 and 2<=d[2]<=TODAY.day]
    if not filtered: filtered=all_dates
    latest=max(filtered, key=lambda x: x[:3]) if filtered else (2026,8,5,"05 أوت 2026")
    print(f"📅 آخر تاريخ موجود: {latest[3]} - كل التواريخ {len(all_dates)}")

    seen=set(); tenders=[]
    cur=None

    # نقرا الصفحة بالترتيب - كل ما نلقى تاريخ نحدث cur
    for el in soup.find_all(True):
        txt=el.get_text(" ",strip=True)
        if not txt: continue
        d=extract_dates(txt)
        # إذا النص هو تاريخ فقط (مثل صورتك الثانية)
        if d and len(txt)<35:
            cur=max(d, key=lambda x: x[:3])
            print(f" -> تاريخ جديد: {cur[3]}")
            continue
        if "طلب العروض" not in txt and "طلب عروض" not in txt: continue
        if "2026" not in txt: continue
        if len(txt)<25: continue
        # نتجنب الحاويات الكبيرة اللي فيها عدة مناقصات
        if len(txt)>1200: continue
        if txt[:120] in seen: continue
        seen.add(txt[:120])

        # لازم يكون تاريخه هو آخر تاريخ أو ضمن 2-5 أوت
        if not cur: cur=latest
        if cur[2]!=latest[2]: continue

        link=url
        for a in el.find_all('a', href=True):
            if ".pdf" in a['href'].lower():
                link=urljoin("https://www.mdn.dz", a['href']); break

        date_str=f"{cur[2]:02d}/{cur[1]:02d}/{cur[0]}"
        tenders.append({"id":gen_id(txt,"MDN"),"title":txt,"anep":gen_anep(txt),"link":link,"date":date_str,"loc":extract_location(txt)})

    print(f"📡 مناقصات {latest[3]} فقط: {len(tenders)}")
    return tenders

factories=load_factories()
sent=load_sent()
print(f"🔒 مرسلة سابقا: {len(sent)}")
tenders=scrape()
new=[t for t in tenders if t["id"] not in sent][:10]
print(f"🔍 جديدة: {len(new)}")

for t in new:
    nearest=choose_nearest(t['title'], factories, 3)
    fac=""
    for i,f in enumerate(nearest,1):
        name=html.escape(f.get('name','')[:45])
        phone=f.get('phone') or ""
        murl=f.get('map') or f"https://www.google.com/maps/search/{name}+{t['loc']}"
        fac+=f"{i}. 🏭 <b>{name}</b> ({t['loc']})\n📞 <code>{phone}</code> | <a href='{murl}'>🗺️ خريطة الموقع</a>\n"
    msg=f"🔔 <b>{t['date']} - {t['loc']}</b>\n{t['title'][:650]}\n<a href='{t['link']}'>📎 رابط الإعلان الأصلي / PDF</a>\n\n{fac}🔖 {t['anep']}"
    if send(msg):
        sent.add(t["id"])
        print(f"✅ {t['anep']} {t['loc']}")

save_sent(sent)
print(f"🏁 محفوظ {len(sent)}")
