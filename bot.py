import os, requests, json, re, hashlib, random, urllib3, html
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from urllib.parse import urljoin

urllib3.disable_warnings()
TOKEN=os.getenv("TELEGRAM_TOKEN","").strip()
CHAT_ID=os.getenv("TELEGRAM_CHAT_ID","").strip()
SENT_FILE="sent_v7.json"
FACTORIES_FILE="factories_300.json"
ALGIERS=ZoneInfo("Africa/Algiers")
TODAY=datetime.now(ALGIERS)

MONTH_MAP={"جانفي":1,"فيفري":2,"مارس":3,"أفريل":4,"ماي":5,"جوان":6,"جويلية":7,"أوت":8,"اوت":8,"سبتمبر":9,"أكتوبر":10,"نوفمبر":11,"ديسمبر":12}

print(f"🚀 v18 MDN ONLY 2-5 Aout - {TODAY.strftime('%d/%m/%Y')}")

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
    with open(SENT_FILE,"w",encoding="utf-8") as f: json.dump({"ids":list(s),"count":len(s),"last":TODAY.isoformat()},f,ensure_ascii=False,indent=2)
def send(t):
    if not TOKEN or not CHAT_ID: return False
    try:
        return requests.post(f"https://api.telegram.org/bot{TOKEN}/sendMessage",data={"chat_id":CHAT_ID,"text":t,"parse_mode":"HTML","disable_web_page_preview":True},timeout=20).status_code==200
    except: return False
def gen_id(t,src): return hashlib.md5(f"{t[:150]}|{src}".encode()).hexdigest()
def gen_anep(t): return f"26{abs(hash(t))%900000+100000}"
def safe_get(url):
    try:
        r=requests.get(url,headers={"User-Agent":"Mozilla/5.0 Chrome/120.0"},timeout=20,verify=False)
        if len(r.text)>500: return r
    except: pass
    return None
def extract_dates(txt):
    dates=[]
    for m in re.finditer(r"(\d{1,2})\s+(جانفي|فيفري|مارس|أفريل|ماي|جوان|جويلية|أوت|اوت|سبتمبر|أكتوبر|نوفمبر|ديسمبر)\s+(202\d)",txt,re.I):
        d=int(m.group(1)); mo=MONTH_MAP.get(m.group(2),8); y=int(m.group(3))
        # فلتر 2 أوت ل 5 أوت
        if mo==8 and 2<=d<=31:
            dates.append((y,mo,d,m.group(0).strip()))
    return dates

def scrape_mdn():
    base="https://www.mdn.dz"
    url="https://www.mdn.dz/site_principal/sommaire/appels/appels_ar.php"
    r=safe_get(url)
    if not r:
        print("[MDN] فشل")
        return []
    print(f"[MDN] {len(r.text)} حرف")
    all_dates=extract_dates(r.text)
    if not all_dates:
        print("[MDN] لا توجد تواريخ 2-5 أوت")
        return []
    # ترتيب من الأحدث للأقدم
    uniq=sorted(set(all_dates),key=lambda x: x[2],reverse=True)
    print(f"[MDN] تواريخ {uniq[:5]}")
    soup=BeautifulSoup(r.text,"html.parser")
    # جرب التاريخ الجديد أولا، إذا مكانش جرب أمس
    for latest in uniq:
        cur=None; seen=set(); tenders=[]
        for el in soup.find_all(['div','p','li','td'],limit=1500):
            txt=el.get_text(" ",strip=True)
            if len(txt)<15: continue
            if len(txt)<120:
                d=extract_dates(txt)
                if d: cur=d[0]; continue
            if "طلب العروض" not in txt: continue
            if not cur or cur[:3]!=latest[:3]: continue
            if not re.search(r"\d{1,4}\s*/\s*202\d",txt): continue
            if txt[:100] in seen: continue
            seen.add(txt[:100])
            link=url
            for a in el.find_all('a',href=True):
                if ".pdf" in a['href'].lower():
                    link=urljoin(base,a['href']); break
            tenders.append({"id":gen_id(txt,"MDN"),"title":txt[:800],"anep":gen_anep(txt),"link":link,"date":f"{latest[2]:02d}/08/{latest[0]}","source":"MDN"})
        if tenders:
            print(f"[MDN] لقى {len(tenders)} لتاريخ {latest}")
            return tenders
        else:
            print(f"[MDN] لا يوجد لتاريخ {latest} نجرب أمس")
    return []

# تشغيل
factories=load_factories()
sent=load_sent()
print(f"مرسلة سابقا {len(sent)} - 300 مصنع")
all_t=scrape_mdn()
print(f"الإجمالي {len(all_t)}")
new=[t for t in all_t if t["id"] not in sent][:10]
print(f"جديدة {len(new)}")
if not new:
    print("لا يوجد جديد - ما يرسل والو")
for t in new:
    picks=random.sample(factories,min(3,len(factories))) if factories else []
    fac=""
    for i,f in enumerate(picks,1):
        name=html.escape(f.get('name','')[:45])
        phone=f.get('phone') or f.get('tel') or ""
        murl=f.get('map') or f.get('maps') or f.get('location') or f"https://www.google.com/maps/search/{name}"
        fac+=f"{i}. 🏭 <b>{name}</b>\n📞 <code>{phone}</code> | <a href='{murl}'>🗺️ خريطة</a>\n"
    msg=f"🛡️ <b>[{t['source']}] {t['date']}</b>\n{t['title'][:700]}\n\n📎 <a href='{t['link']}'>رابط الإعلان الأصلي / PDF</a>\n\n{fac}\n🔖 {t['anep']}"
    if send(msg):
        sent.add(t["id"])
        print(f"✅ {t['anep']}")
save_sent(sent)
os.makedirs("public",exist_ok=True)
with open("public/tenders.json","w",encoding="utf-8") as f: json.dump(all_t,f,ensure_ascii=False,indent=2)
print(f"🏁 انتهى محفوظ {len(sent)}")
