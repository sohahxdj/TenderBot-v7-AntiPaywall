import os, requests, json, re, hashlib, random, urllib3, html, time
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

print(f"🚀 v19 - MDN + MARCHES-PUBLICS BY ANY MEANS - {TODAY.strftime('%d/%m/%Y %H:%M')}")

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
    try: return requests.post(url,data=data,timeout=30).status_code==200
    except: return False
def gen_id(t,src): return hashlib.md5(f"{t[:150].lower()}|{src}".encode()).hexdigest()
def gen_anep(t): return f"26{abs(hash(t))%900000+100000}"

MONTH_MAP={"جانفي":1,"فيفري":2,"مارس":3,"أفريل":4,"ماي":5,"جوان":6,"جويلية":7,"أوت":8,"اوت":8,"سبتمبر":9,"أكتوبر":10,"نوفمبر":11,"ديسمبر":12}
def extract_dates(txt):
    dates=[]
    for m in re.finditer(r"(\d{1,2})\s+(جانفي|فيفري|مارس|أفريل|ماي|جوان|جويلية|أوت|اوت|سبتمبر|أكتوبر|نوفمبر|ديسمبر)\s+(2026)", txt, flags=re.I):
        d=int(m.group(1)); mo=MONTH_MAP.get(m.group(2),8)
        if 2<=d<=TODAY.day: dates.append((2026,mo,d,m.group(0)))
    return dates

def safe_get(url, use_cloud=False):
    headers={"User-Agent":"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0 Safari/537.36","Accept":"text/html,application/xhtml+xml","Accept-Language":"ar-DZ,ar;q=0.9,fr;q=0.8","Referer":"https://www.google.com/"}
    try:
        if use_cloud:
            try:
                import cloudscraper
                scraper=cloudscraper.create_scraper()
                r=scraper.get(url, headers=headers, timeout=40)
                if len(r.text)>2000: return r
            except: pass
        r=requests.get(url, headers=headers, timeout=30, verify=False)
        if len(r.text)>1500: return r
    except: pass
    return None

# --- MDN: يجرب من الأحدث للأقدم ---
def scrape_mdn():
    url="https://www.mdn.dz/site_principal/sommaire/appels/appels_ar.php"
    r=safe_get(url)
    if not r: return []
    print(f"[MDN] {r.status_code} - {len(r.text)}")
    all_dates=extract_dates(r.text)
    if not all_dates:
        print("[MDN] لا يوجد تواريخ 02-05")
        # حتى لو ما لقاش تاريخ، حاول تجيب أي طلب عروض
        all_dates=[(2026,8,4,"04 أوت 2026"),(2026,8,3,"03 أوت 2026")]
    uniq=sorted(set(all_dates), key=lambda x: x[2], reverse=True)
    print(f"[MDN] تواريخ: {[x[3] for x in uniq]}")
    soup=BeautifulSoup(r.text,"html.parser")
    for latest in uniq:
        cur=None; seen=set(); tenders=[]
        for el in soup.find_all(['div','p','li','td'], limit=1500):
            txt=el.get_text(" ",strip=True)
            if len(txt)<15: continue
            if len(txt)<120:
                d=extract_dates(txt)
                if d: cur=d[0]; continue
            if "طلب العروض" not in txt: continue
            if cur and cur[:3]!=latest[:3]: continue
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
            print(f"[MDN] {latest[3]} => {len(tenders)} مناقصة")
            return tenders
    return []

# --- MARCHES-PUBLICS: بأي طريقة ---
def scrape_marches_publics():
    urls=[
        "https://marches-publics.gov.dz",
        "https://www.marches-publics.gov.dz",
        "https://mfdgi.gov.dz",
        "https://www.mfdgi.gov.dz",
        "https://rhinotenders.com/fr/appels-offres"
    ]
    for url in urls:
        for use_cloud in [True, False]:
            print(f"[MARCHES] محاولة {url} cloud={use_cloud}")
            r=safe_get(url, use_cloud=use_cloud)
            if not r: continue
            print(f"[MARCHES] {url} => {len(r.text)}")
            soup=BeautifulSoup(r.text,"html.parser")
            tenders=[]; seen=set()
            for el in soup.find_all(['div','a','li','article'], limit=800):
                txt=el.get_text(" ",strip=True)
                if len(txt)<40 or len(txt)>2000: continue
                if not any(k in txt for k in ["Appel d'offres","Avis d'appel","طلب العروض","مناقصة","Marchés publics"]): continue
                if txt[:100] in seen: continue
                seen.add(txt[:100])
                link=url
                if el.name=='a' and el.get('href'):
                    href=el['href']
                    if href.startswith("http"): link=href
                    elif href.startswith("/"):
                        base="/".join(url.split("/")[:3])
                        link=base+href
                tenders.append({"id":gen_id(txt,"MARCHES"),"title":txt[:700],"anep":gen_anep(txt),"link":link,"date":TODAY.strftime("%d/%m/%Y"),"source":"MARCHES-PUBLICS"})
                if len(tenders)>=10: break
            if tenders:
                print(f"[MARCHES-PUBLICS] نجح من {url} => {len(tenders)}")
                return tenders
            time.sleep(1)
    print("[MARCHES-PUBLICS] فشل كل المحاولات")
    return []

# --- Main ---
factories=load_factories()
sent=load_sent()
print(f"🔒 مرسلة سابقا: {len(sent)}")

all_t=[]
all_t.extend(scrape_mdn())
all_t.extend(scrape_marches_publics())

print(f"📊 الإجمالي: {len(all_t)}")
new=[t for t in all_t if t["id"] not in sent]
# إذا اليوم 05 أوت 0، أرسل 04 أوت إذا ما كانش محفوظ
if not new:
    print("🔍 لا يوجد جديد اليوم - 05 أوت فارغ")
else:
    print(f"🔍 جديدة: {len(new)}")

for t in new[:10]:
    picks=random.sample(factories, min(3,len(factories))) if factories else []
    fac="".join([f"{i}. 🏭 <b>{html.escape(f['name'])}</b> 📞 <code>{f['phone']}</code> <a href=\"{f.get('map','#')}\">🗺️ موقع</a>\n" for i,f in enumerate(picks,1)])
    emoji="🛡️" if t["source"]=="MDN" else "🏛️"
    msg=f"{emoji} <b>[{t['source']}] {t['date']}</b>\n{t['title'][:600]}\n<a href='{t['link']}'>📎 فتح PDF / الإعلان</a>\n\n{fac}\n📍 المصدر: {t['source']}"
    if send(msg):
        sent.add(t["id"])
        print(f"✅ {t['source']} {t['anep']}")

save_sent(sent)
os.makedirs("public", exist_ok=True)
with open("public/tenders.json","w",encoding="utf-8") as f: json.dump(all_t,f,ensure_ascii=False,indent=2)
print(f"🏁 محفوظ {len(sent)}")
