import os, requests, json, re, hashlib, random, urllib3, html
from bs4 import BeautifulSoup
from datetime import datetime
from zoneinfo import ZoneInfo

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

TOKEN = os.getenv("TELEGRAM_TOKEN","").strip()
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID","").strip()
SENT_FILE = "sent_v7.json"
FACTORIES_FILE = "factories_300.json"
ALGIERS = ZoneInfo("Africa/Algiers")
TODAY = datetime.now(ALGIERS)

print(f"🚀 v15.4 FINAL - يجيب الطويلة - {TODAY.strftime('%d/%m/%Y')}")

def load_factories():
    try:
        with open(FACTORIES_FILE,"r",encoding="utf-8") as f:
            return json.load(f)
    except: return []

def load_sent():
    try:
        if os.path.exists(SENT_FILE):
            with open(SENT_FILE,"r",encoding="utf-8") as f:
                data=json.load(f)
                return set(data.get("ids",[])) if isinstance(data, dict) else set(data)
    except: pass
    return set()

def save_sent(s):
    with open(SENT_FILE,"w",encoding="utf-8") as f:
        json.dump({"ids": list(s),"last_update": TODAY.isoformat(),"count": len(s)}, f, ensure_ascii=False, indent=2)

def send(text):
    url=f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    data={"chat_id":CHAT_ID,"text":text,"parse_mode":"HTML","disable_web_page_preview":False}
    try:
        r=requests.post(url,data=data,timeout=30)
        print(f"Telegram {r.status_code}")
        return r.status_code==200
    except: return False

def gen_id(t,s):
    clean = re.sub(r'\s+', ' ', t[:200].lower().strip())[:120]
    return hashlib.md5(f"{clean}|{s}".encode()).hexdigest()

def gen_anep(t): return f"26{abs(hash(t))%900000+100000}"

MONTH_MAP={"جانفي":1,"فيفري":2,"مارس":3,"أفريل":4,"افريل":4,"ماي":5,"جوان":6,"جويلية":7,"أوت":8,"اوت":8,"سبتمبر":9,"أكتوبر":10,"اكتوبر":10,"نوفمبر":11,"ديسمبر":12}
MONTH_PAT="|".join(sorted([re.escape(k) for k in MONTH_MAP], key=len, reverse=True))

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
        if y!=2026 or mo!=8 or d<2 or d>TODAY.day: continue
        dates.append((y,mo,d, m.group(0)))
    return dates

def safe_get(url):
    headers={"User-Agent":"Mozilla/5.0 Chrome/120.0.0","Referer":"https://www.mdn.dz/"}
    try:
        r=requests.get(url, headers=headers, timeout=30, verify=False)
        print(f"HTTP {r.status_code} - {len(r.text)} حرف")
        return r
    except: return None

def scrape():
    tenders=[]
    url="https://www.mdn.dz/site_principal/sommaire/appels/appels_ar.php"
    r=safe_get(url)
    if not r: return [], None
    all_dates=extract_dates(r.text)
    print(f"📅 تواريخ: {all_dates}")
    if not all_dates: return [], None
    latest=max(all_dates, key=lambda x: (x[0],x[1],x[2]))
    print(f"📅 آخر تاريخ: {latest[3]}")

    soup=BeautifulSoup(r.text,"lxml")
    cur=None
    seen=set()
    all_p = soup.find_all(['div','p','li','td','tr'], limit=1500)
    cnt_tender=0
    for el in all_p:
        txt=el.get_text(" ",strip=True)
        if len(txt)<10: continue
        # هيدر تاريخ حتى لو طوله 100
        if len(txt)<100:
            d=extract_dates(txt)
            if d: cur=d[0]; continue
        if len(txt)<40 or len(txt)>4000: continue
        if "طلب العروض" not in txt: continue
        cnt_tender+=1
        if not re.search(r"\d{1,4}\s*/\s*2026", txt): continue
        if not cur:
            # لو ما لقيناش هيدر، استخدم آخر تاريخ
            cur=latest
        if txt[:100] in seen: continue
        seen.add(txt[:100])
        link=url
        for a in el.find_all('a', href=True):
            href=a['href']
            if ".pdf" in href.lower():
                if href.startswith("/"): href="https://www.mdn.dz"+href
                elif not href.startswith("http"): href="https://www.mdn.dz/site_principal/sommaire/appels/"+href.lstrip('/')
                link=href
                break
        tenders.append({"id":gen_id(txt,"MDN"),"title":txt,"anep":gen_anep(txt),"link":link,"date":f"{cur[2]:02d}/{cur[1]:02d}/{cur[0]}"})
    print(f"📡 وجد {cnt_tender} فقرة فيها طلب العروض، بعد الفلترة: {len(tenders)}")
    print(f"📡 مناقصات {latest[3]} فقط: {len(tenders)}")
    return tenders, latest

factories=load_factories()
sent=load_sent()
print(f"🔒 مرسلة سابقا: {len(sent)}")
tenders, latest = scrape()
new=[t for t in tenders if t["id"] not in sent]
print(f"🔍 جديدة: {len(new)}")

if not new:
    print(f"✅ اليوم {TODAY.strftime('%d/%m/%Y')} - لا يوجد جديد")
else:
    for t in new[:5]:
        picks=random.sample(factories, min(3, len(factories))) if factories else []
        fac_txt="".join([f"{i}. 🏭 <b>{html.escape(f.get('name',''))}</b> 📞 <code>{f.get('phone','')}</code> 🗺️ <a href=\"{f.get('map','')}\">موقع</a>\n" for i,f in enumerate(picks,1)])
        msg=f"""🔔 <b>مناقصة {t['date']} - وزارة الدفاع</b>\n\nANEP: {t['anep']}\n📋 {html.escape(t['title'][:700])}\n\n📄 <a href="{t['link']}">📎 الإعلان الأصلي + PDF</a>\n\n🏭 <b>3 موردين:</b>\n{fac_txt}"""
        if send(msg):
            sent.add(t["id"])
            save_sent(sent)
print(f"🏁 محفوظ {len(sent)}")
