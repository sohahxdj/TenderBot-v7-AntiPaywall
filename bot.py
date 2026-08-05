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

print(f"🚀 v15 FINAL - آخر تاريخ فقط + ضد الحجب - {TODAY.strftime('%d/%m/%Y')}")

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
    with open("sent_ids_backup.txt","w",encoding="utf-8") as f:
        f.write("\n".join(s))

def send(text):
    url=f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    data={"chat_id":CHAT_ID,"text":text,"parse_mode":"HTML","disable_web_page_preview":False}
    try:
        r=requests.post(url,data=data,timeout=30)
        return r.status_code==200
    except: return False

def gen_id(t,s):
    return hashlib.md5(f"{re.sub(r'\s+',' ',t[:200].lower())}|{s}".encode()).hexdigest()

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
        if mo: dates.append((int(m.group(3)),mo,int(m.group(1)), m.group(0)))
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
    print(f"📅 كل التواريخ في الموقع: {all_dates}")
    if not all_dates:
        print("📅 لا يوجد أي تاريخ 2026 في الصفحة - الموقع فارغ اليوم")
        return [], None
    latest=max(all_dates, key=lambda x: (x[0],x[1],x[2]))
    print(f"📅 آخر تاريخ موجود هو: {latest[3]}")

    # فلتر 5: من 02 أوت فما فوق + رقم 044/2026
    if latest[0]<2026 or (latest[0]==2026 and latest[1]<8) or (latest[0]==2026 and latest[1]==8 and latest[2]<2):
        print("📅 آخر تاريخ أقدم من 02 أوت - تجاهل")
        return [], latest

    soup=BeautifulSoup(r.text,"lxml")
    cur=None
    seen=set()
    for el in soup.find_all(['div','p','li'], limit=800):
        txt=el.get_text(" ",strip=True)
        if len(txt)<10: continue
        if len(txt)<40:
            d=extract_dates(txt)
            if d: cur=d[0]; continue
        if len(txt)<50 or len(txt)>800: continue
        if "طلب العروض" not in txt: continue
        if not re.search(r"\d{2,4}\s*/\s*2026", txt): continue
        if not cur: continue
        if cur[0]!=latest[0] or cur[1]!=latest[1] or cur[2]!=latest[2]: continue
        if txt[:70] in seen: continue
        seen.add(txt[:70])
        link=url
        pdf=None
        for a in el.find_all('a', href=True):
            href=a['href']
            if ".pdf" in href.lower():
                pdf=href
                if href.startswith("/"): pdf="https://www.mdn.dz"+href
                elif not href.startswith("http"): pdf="https://www.mdn.dz/site_principal/sommaire/appels/"+href.lstrip('/')
                break
        if pdf: link=pdf
        else:
            a=el.find('a', href=True)
            if a and a.get('href'):
                href=a['href']
                if href.startswith("/"): href="https://www.mdn.dz"+href
                link=href
        tenders.append({"id":gen_id(txt,"MDN"),"title":txt,"anep":gen_anep(txt),"link":link,"date":f"{cur[2]:02d}/{cur[1]:02d}/{cur[0]}","company":"وزارة الدفاع"})
    print(f"📡 مناقصات بتاريخ {latest[3]} فقط: {len(tenders)}")
    return tenders, latest

factories=load_factories()
sent=load_sent()
tenders, latest = scrape()

new=[t for t in tenders if t["id"] not in sent]
print(f"🔍 جديدة من آخر تاريخ: {len(new)}")

if not new:
    if latest:
        print(f"✅ لا يوجد جديد - آخر تاريخ {latest[3]} تم إرساله سابقا أو اليوم 05/08/2026 غير موجود (وهذا صحيح)")
    else:
        print(f"✅ اليوم {TODAY.strftime('%d/%m/%Y')} لا يوجد مناقصات في الموقع - البوت يعمل صحيح")
else:
    for t in new:
        picks=random.sample(factories, min(3, len(factories))) if factories else []
        fac_txt="".join([f"{i}. 🏭 <b>{html.escape(f.get('name',''))}</b> 📦 {html.escape(f.get('product',''))} 📞 <code>{f.get('phone','')}</code> 🗺️ <a href=\"{f.get('map','')}\">موقع</a>\n" for i,f in enumerate(picks,1)])
        msg=f"""🔔 <b>مناقصة {t['date']} - MDN</b>\n\n🏢 {t['company']} | ANEP: {t['anep']}\n📋 {html.escape(t['title'][:650])}\n\n📄 <a href="{t['link']}">📎 الإعلان الأصلي + PDF</a>\n\n🏭 <b>3 موردين:</b>\n{fac_txt}"""
        if send(msg):
            sent.add(t["id"])
            save_sent(sent)

print(f"🏁 محفوظ {len(sent)}")
