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

print(f"🚀 v20 - MDN (02-05 أوت) + MARCHES - {TODAY.strftime('%d/%m/%Y %H:%M')}")

def load_factories():
    try:
        with open(FACTORIES_FILE,"r",encoding="utf-8") as f: return json.load(f)
    except: return []
def load_sent():
    try:
        if os.path.exists(SENT_FILE):
            with open(SENT_FILE,"r",encoding="utf-8") as f: return set(json.load(f).get("ids",[]))
    except: pass
    return set()
def save_sent(s):
    with open(SENT_FILE,"w",encoding="utf-8") as f: json.dump({"ids":list(s),"last_update":TODAY.isoformat(),"count":len(s)},f,ensure_ascii=False,indent=2)
def send(text):
    url=f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    data={"chat_id":CHAT_ID,"text":text,"parse_mode":"HTML"}
    try: return requests.post(url,data=data,timeout=20).status_code==200
    except: return False
def gen_id(t,src):
    clean=re.sub(r'\s+',' ',t[:200].lower().strip())[:120]
    return hashlib.md5(f"{clean}|{src}".encode()).hexdigest()
def gen_anep(t): return f"26{abs(hash(t))%900000+100000}"

MONTH_MAP={"جانفي":1,"فيفري":2,"مارس":3,"أفريل":4,"ماي":5,"جوان":6,"جويلية":7,"أوت":8,"اوت":8,"سبتمبر":9,"أكتوبر":10,"نوفمبر":11,"ديسمبر":12}
def extract_dates(txt):
    dates=[]
    for m in re.finditer(r"(\d{1,2})\s+(جانفي|فيفري|مارس|أفريل|ماي|جوان|جويلية|أوت|اوت|سبتمبر|أكتوبر|نوفمبر|ديسمبر)\s+(2026)", txt, flags=re.I):
        d=int(m.group(1)); mo=MONTH_MAP.get(m.group(2),8)
        if mo==8 and 2<=d<=TODAY.day: dates.append((2026,mo,d,m.group(0)))
    return dates
def safe_get(url, timeout=12):
    headers={"User-Agent":"Mozilla/5.0 Chrome/120.0"}
    try:
        r=requests.get(url, headers=headers, timeout=timeout, verify=False)
        if len(r.text)>1500: return r
    except: pass
    return None

def scrape_mdn():
    url="https://www.mdn.dz/site_principal/sommaire/appels/appels_ar.php"
    r=safe_get(url, 15)
    if not r: return []
    print(f"[MDN] {r.status_code} - {len(r.text)}")
    all_dates=extract_dates(r.text)
    if not all_dates:
        print("[MDN] لا يوجد 02-05 أوت اليوم")
        return []
    uniq=sorted(set(all_dates), key=lambda x: x[2], reverse=True)
    print(f"[MDN] تواريخ: {[x[3] for x in uniq]}")
    soup=BeautifulSoup(r.text,"html.parser")
    for latest in uniq:
        cur=None; seen=set(); tenders=[]
        for el in soup.find_all(['div','p','li','td'], limit=1200):
            txt=el.get_text(" ",strip=True)
            if len(txt)<15: continue
            if len(txt)<120:
                d=extract_dates(txt)
                if d: cur=d[0]; continue
            if "طلب العروض" not in txt: continue
            if not cur or cur[:3]!=latest[:3]: continue
            if not re.search(r"\d{1,4}\s*/\s*2026", txt): continue
            if txt[:120] in seen: continue
            seen.add(txt[:120])
            link=url
            for a in el.find_all('a', href=True):
                if ".pdf" in a['href'].lower():
                    href=a['href']
                    link="https://www.mdn.dz"+href if href.startswith("/") else href
                    break
            tenders.append({"id":gen_id(txt,"MDN"),"title":txt,"anep":gen_anep(txt),"link":link,"date":f"{latest[2]:02d}/08/2026","source":"MDN"})
        if tenders:
            print(f"[MDN] {latest[3]} => {len(tenders)}")
            return tenders
    return []

def scrape_marches():
    # محاولة سريعة 8 ثواني فقط، إذا فشل نكمل
    urls=["https://marches-publics.gov.dz","https://www.mfdgi.gov.dz"]
    for url in urls:
        print(f"[MARCHES] {url}")
        r=safe_get(url, timeout=8)
        if not r: continue
        print(f"[MARCHES] {len(r.text)} حرف")
        soup=BeautifulSoup(r.text,"html.parser")
        tenders=[]; seen=set()
        for el in soup.find_all(['a','div'], limit=400):
            txt=el.get_text(" ",strip=True)
            if len(txt)<40: continue
            if "Appel" not in txt and "Marché" not in txt and "مناقصة" not in txt: continue
            if txt[:80] in seen: continue
            seen.add(txt[:80])
            tenders.append({"id":gen_id(txt,"MARCHES"),"title":txt[:600],"anep":gen_anep(txt),"link":url,"date":TODAY.strftime("%d/%m/%Y"),"source":"MARCHES-PUBLICS"})
            if len(tenders)>=5: break
        if tenders:
            print(f"[MARCHES] نجح {len(tenders)}")
            return tenders
    print("[MARCHES] محجوب - نكمل بـ MDN فقط")
    return []

factories=load_factories()
sent=load_sent()
print(f"🔒 مرسلة سابقا: {len(sent)}")

all_t=[]
all_t.extend(scrape_mdn())
all_t.extend(scrape_marches())

print(f"📊 الإجمالي: {len(all_t)}")
new=[t for t in all_t if t["id"] not in sent][:10]
print(f"🔍 جديدة: {len(new)}")

for t in new:
    picks=random.sample(factories, min(3,len(factories))) if factories else []
    fac="".join([f"{i}. 🏭 <b>{html.escape(f['name'])}</b> 📞 <code>{f['phone']}</code> <a href=\"{f.get('map','#')}\">🗺️ موقع</a>\n" for i,f in enumerate(picks,1)])
    emoji="🛡️" if t["source"]=="MDN" else "🏛️"
    msg=f"{emoji} <b>[{t['source']}] {t['date']}</b>\n{t['title'][:600]}\n<a href='{t['link']}'>📎 فتح PDF</a>\n\n{fac}📍 المصدر: {t['source']}"
    if send(msg):
        sent.add(t["id"])
        print(f"✅ أرسل {t['anep']}")

save_sent(sent)
os.makedirs("public", exist_ok=True)
with open("public/tenders.json","w",encoding="utf-8") as f: json.dump(all_t,f,ensure_ascii=False,indent=2)
print(f"🏁 محفوظ {len(sent)}")
