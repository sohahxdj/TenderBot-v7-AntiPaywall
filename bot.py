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

print(f"🚀 v13 FINAL - مضمون - يرسل الجديد فقط - {TODAY.strftime('%d/%m/%Y')}")

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
    print(f"💾 حفظ {len(s)}")

def send(text):
    url=f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    data={"chat_id":CHAT_ID,"text":text,"parse_mode":"HTML","disable_web_page_preview":False}
    try:
        r=requests.post(url,data=data,timeout=30)
        print(f"Telegram {r.status_code}")
        return r.status_code==200
    except Exception as e:
        print(f"Telegram err {e}")
        return False

def gen_id(title, source):
    clean=re.sub(r'\s+',' ',title[:200].lower().strip())[:120]
    return hashlib.md5(f"{clean}|{source}".encode()).hexdigest()

def gen_anep(t):
    return f"26{abs(hash(t))%900000+100000}"

MONTH_MAP={"جانفي":1,"فيفري":2,"مارس":3,"أفريل":4,"افريل":4,"ماي":5,"جوان":6,"جويلية":7,"أوت":8,"اوت":8,"أوث":8,"سبتمبر":9,"أكتوبر":10,"اكتوبر":10,"نوفمبر":11,"ديسمبر":12,"janvier":1,"février":2,"fevrier":2,"avril":4,"juin":6,"juillet":7,"août":8,"aout":8}
MONTH_PAT="|".join(sorted([re.escape(k) for k in MONTH_MAP], key=len, reverse=True))

def get_mo(name):
    name=name.lower()
    for k,v in MONTH_MAP.items():
        if k in name: return v
    return None

def extract_dates(txt):
    dates=[]
    for m in re.finditer(r"\b(\d{1,2})[\/\-\.]\s*(\d{1,2})[\/\-\.]\s*(20\d{2})\b", txt):
        dates.append((int(m.group(3)),int(m.group(2)),int(m.group(1))))
    for m in re.finditer(rf"\b(\d{{1,2}})\s+({MONTH_PAT})\s+(20\d{{2}})\b", txt, flags=re.I):
        mo=get_mo(m.group(2))
        if mo: dates.append((int(m.group(3)),mo,int(m.group(1))))
    return dates

def is_from_2_aout(date_tuple):
    y,m,d=date_tuple
    if y<2026: return False
    if y==2026 and m<8: return False
    if y==2026 and m==8 and d<2: return False
    return True

def safe_get(url):
    try: return requests.get(url, headers={"User-Agent":"Mozilla/5.0"}, timeout=25, verify=False)
    except: return None

def scrape_mdn():
    tenders=[]
    try:
        url="https://www.mdn.dz/site_principal/sommaire/appels/appels_ar.php"
        r=safe_get(url)
        if not r: return tenders
        soup=BeautifulSoup(r.text,"lxml")
        current_date=None
        seen=set()
        for el in soup.find_all(['div','p','li','span'], limit=600):
            txt=el.get_text(" ",strip=True)
            if len(txt)<5: continue
            # هيدر تاريخ
            if len(txt)<35:
                d=extract_dates(txt)
                if d:
                    current_date=d[0]
                    continue
            # فلتر المناقصة الحقيقية
            if len(txt)<50 or len(txt)>800: continue
            if "طلب العروض" not in txt: continue
            if not re.search(r"\d{2,4}\s*/\s*2026", txt): continue
            if "2024" in txt or "2025" in txt: continue
            # تاريخ من 02 أوت فما فوق
            date_to_check=current_date or (extract_dates(txt)[0] if extract_dates(txt) else None)
            if not date_to_check: continue
            if not is_from_2_aout(date_to_check): continue
            if txt[:70] in seen: continue
            seen.add(txt[:70])
            # رابط أصلي + PDF
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
                    elif not href.startswith("http"): href="https://www.mdn.dz/site_principal/sommaire/appels/"+href.lstrip('/')
                    link=href
            tid=gen_id(txt, "MDN")
            tenders.append({"id":tid,"title":txt,"anep":gen_anep(txt),"wilaya":"Algérie","link":link,"source":"MDN","company":"وزارة الدفاع","date":str(date_to_check)})
        print(f"📡 MDN: {len(tenders)} مناقصة من 02 أوت فما فوق")
    except Exception as e:
        print(f"MDN err {e}")
    return tenders

factories=load_factories()
sent=load_sent()
print(f"🔒 مرسلة سابقا: {len(sent)}")

all_tenders=scrape_mdn()
print(f"📊 الخام: {len(all_tenders)}")

unique={}
for t in all_tenders:
    if t["id"] in sent:
        print(f"⏭️ مكرر {t['anep']}")
        continue
    unique[t["id"]]=t

new=list(unique.values())
print(f"🔍 جديدة ترسل الآن: {len(new)}")

if not new:
    print("✅ لا يوجد جديد - البوت يراقب كل يوم")
else:
    for t in new:
        picks=random.sample(factories, min(3, len(factories))) if factories else []
        fac_txt=""
        for i,f in enumerate(picks,1):
            fac_txt+=f"{i}. 🏭 <b>{html.escape(f.get('name',''))}</b>\n📦 {html.escape(f.get('product',''))}\n📞 <code>{f.get('phone','')}</code> | 🗺️ <a href=\"{f.get('map','')}\">موقع</a>\n"
        msg=f"""🔔 <b>مناقصة جديدة - {t['source']}</b> 🔔

🏢 {html.escape(t['company'])} | ANEP: {t['anep']} | 📅 {t['date']}
📋 {html.escape(t['title'][:650])}

📄 <a href="{t['link']}">📎 فتح الإعلان الأصلي PDF</a>

🏭 <b>3 موردين:</b>
{fac_txt}
#Tradium #v13
"""
        if send(msg):
            sent.add(t["id"])
            save_sent(sent)
            print(f"✅ أرسلت {t['anep']}")

print(f"🏁 انتهى - المحفوظ {len(sent)}")
