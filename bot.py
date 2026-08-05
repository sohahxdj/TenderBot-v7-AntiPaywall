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

# 4 مصادر مجانية 100% - بلا اشتراك - بلا حجب
SOURCES = {
    "MDN": "https://www.mdn.dz/site_principal/sommaire/appels/appels_ar.php",
    "MARCHES-PUBLICS": "https://www.marches-publics.gov.dz",
    "INTERIEUR": "https://www.interieur.gov.dz/index.php/fr/appels-d-offres.html",
    "MHUV": "https://www.mhuv.gov.dz/fr/appels-d-offres/"
}

print(f"🚀 v18 - 4 SOURCES - {TODAY.strftime('%d/%m/%Y %H:%M')}")

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
                return set(data.get("ids",[]))
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

def gen_id(t,s,source):
    clean = re.sub(r'\s+', ' ', t[:200].lower().strip())[:120]
    return hashlib.md5(f"{clean}|{s}|{source}".encode()).hexdigest()

def gen_anep(t): return f"26{abs(hash(t))%900000+100000}"

MONTH_MAP={
    "جانفي":1,"فيفري":2,"مارس":3,"أفريل":4,"ماي":5,"جوان":6,"جويلية":7,"أوت":8,"اوت":8,"سبتمبر":9,"أكتوبر":10,"نوفمبر":11,"ديسمبر":12,
    "janvier":1,"février":2,"fevrier":2,"mars":3,"avril":4,"mai":5,"juin":6,"juillet":7,"aout":8,"août":8,"septembre":9,"octobre":10,"novembre":11,"décembre":12,"decembre":12
}
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
    headers={"User-Agent":"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0","Referer":"https://www.google.com/"}
    for _ in range(3):
        try:
            r=requests.get(url, headers=headers, timeout=30, verify=False)
            if len(r.text)>3000: return r
        except: pass
    return None

# --- مصدر 1: MDN (الكود القديم المستقر) ---
def scrape_mdn():
    r=safe_get(SOURCES["MDN"])
    if not r: return []
    print(f"[MDN] HTTP {r.status_code} - {len(r.text)} حرف")
    all_dates=extract_dates(r.text)
    if not all_dates:
        print("[MDN] لا يوجد تاريخ")
        return []
    latest=max(all_dates, key=lambda x: x[:3])
    print(f"[MDN] آخر تاريخ: {latest[3]}")
    soup=BeautifulSoup(r.text,"html.parser")
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
                href=a['href']
                link="https://www.mdn.dz"+href if href.startswith("/") else href
                break
        tenders.append({"id":gen_id(txt,"MDN","MDN"),"title":txt,"anep":gen_anep(txt),"link":link,"date":f"{cur[2]:02d}/{cur[1]:02d}/{cur[0]}","source":"MDN"})
    print(f"[MDN] مناقصات: {len(tenders)}")
    return tenders

# --- مصدر 2-4: Generic (ANEP, Interior, MHUV) ---
def scrape_generic(source_name, url):
    r=safe_get(url)
    if not r:
        print(f"[{source_name}] فشل الاتصال")
        return []
    print(f"[{source_name}] HTTP {r.status_code} - {len(r.text)}")
    soup=BeautifulSoup(r.text,"html.parser")
    seen=set(); tenders=[]
    keywords=["طلب العروض","Avis d'appel","Appel d'offres","مناقصة"]
    for el in soup.find_all(['div','article','li','tr','p'], limit=800):
        txt=el.get_text(" ",strip=True)
        if len(txt)<30 or len(txt)>2000: continue
        if not any(k in txt for k in keywords): continue
        if txt[:120] in seen: continue
        seen.add(txt[:120])
        if not re.search(r"\d{2,4}\s*/\s*20\d{2}", txt) and "Avis" not in txt and "طلب" not in txt:
            continue
        link=url
        for a in el.find_all('a', href=True):
            href=a['href']
            if href.startswith("http"): link=href; break
            if href.startswith("/"):
                base="/".join(url.split("/")[:3])
                link=base+href; break
        clean_title = txt[:600]
        tenders.append({"id":gen_id(clean_title,source_name,source_name),"title":clean_title,"anep":gen_anep(clean_title),"link":link,"date":TODAY.strftime("%d/%m/%Y"),"source":source_name})
        if len(tenders)>=15: break
    print(f"[{source_name}] مناقصات: {len(tenders)}")
    return tenders

def scrape_all():
    all_t=[]
    # 1 MDN
    try: all_t.extend(scrape_mdn())
    except Exception as e: print(f"[MDN] خطأ: {e}")
    # 2 MARCHES-PUBLICS
    try: all_t.extend(scrape_generic("MARCHES-PUBLICS", SOURCES["MARCHES-PUBLICS"]))
    except Exception as e: print(f"[MARCHES-PUBLICS] خطأ: {e}")
    # 3 INTERIEUR
    try: all_t.extend(scrape_generic("INTERIEUR", SOURCES["INTERIEUR"]))
    except Exception as e: print(f"[INTERIEUR] خطأ: {e}")
    # 4 MHUV
    try: all_t.extend(scrape_generic("MHUV", SOURCES["MHUV"]))
    except Exception as e: print(f"[MHUV] خطأ: {e}")
    return all_t

# --- Main ---
factories=load_factories()
sent=load_sent()
print(f"🔒 مرسلة سابقا: {len(sent)}")

tenders = scrape_all()
print(f"📊 الإجمالي من 4 مصادر: {len(tenders)}")

# فلترة جديدة فقط
new=[t for t in tenders if t["id"] not in sent]
# ترتيب: MDN أولا ثم الباقي
new_sorted = sorted(new, key=lambda x: (0 if x["source"]=="MDN" else 1, x["date"]), reverse=False)
to_send = new_sorted[:10]

print(f"🔍 جديدة للإرسال: {len(to_send)}")

if not os.path.exists(SENT_FILE):
    save_sent(sent)

for t in to_send:
    picks=random.sample(factories, min(3,len(factories))) if factories else []
    fac="".join([f"{i}. 🏭 <b>{html.escape(f['name'])}</b> 📞 <code>{f['phone']}</code> <a href=\"{f.get('map','#')}\">موقع</a>\n" for i,f in enumerate(picks,1)])
    source_emoji = {"MDN":"🛡️","MARCHES-PUBLICS":"🏛️","INTERIEUR":"🏢","MHUV":"🏗️"}.get(t["source"],"📋")
    msg=f"{source_emoji} <b>[{t['source']}] {t['date']}</b>\n{t['title'][:600]}\n<a href='{t['link']}'>📎 فتح الإعلان الأصلي + PDF</a>\n\n{fac}\n\n📍 المصدر: {t['source']}"
    if send(msg):
        sent.add(t["id"])
        print(f"✅ أرسل {t['source']} {t['anep']}")

save_sent(sent)

# تحديث ملف التطبيق Netlify
os.makedirs("public", exist_ok=True)
with open("public/tenders.json","w",encoding="utf-8") as f:
    json.dump(tenders, f, ensure_ascii=False, indent=2)
with open("public/stats.json","w",encoding="utf-8") as f:
    json.dump({"last_update": TODAY.isoformat(),"total": len(tenders),"sent": len(sent),"sources": list(SOURCES.keys())}, f, ensure_ascii=False, indent=2)

print(f"🏁 محفوظ {len(sent)} - تم تحديث public/tenders.json")
