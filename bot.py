import os, requests, json, re, hashlib, random, urllib3
from bs4 import BeautifulSoup
from datetime import datetime

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

TOKEN = os.getenv("TELEGRAM_TOKEN","").strip()
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID","").strip()
SENT_FILE = "sent_v7.json"
FACTORIES_FILE = "factories_300.json"

print("🚀 v10 FINAL - احترافي - من 2 أوت 2026 فقط")

def load_factories():
    try:
        with open(FACTORIES_FILE,"r",encoding="utf-8") as f:
            data=json.load(f)
            return data if len(data)>0 else []
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
        json.dump({"ids": list(s),"last_update": datetime.now().isoformat(),"count": len(s)}, f, ensure_ascii=False, indent=2)
    with open("sent_ids_backup.txt","w",encoding="utf-8") as f:
        f.write("\n".join(s))

def send(text):
    url=f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    data={"chat_id":CHAT_ID,"text":text,"parse_mode":"HTML","disable_web_page_preview":True}
    try: return requests.post(url,data=data,timeout=30).status_code==200
    except: return False

def gen_id(title, source):
    clean=re.sub(r'\s+',' ',title[:200].lower().strip())[:120]
    return hashlib.md5(f"{clean}|{source}".encode()).hexdigest()

def gen_anep(title):
    return f"26{abs(hash(title))%900000+100000}"

# === تواريخ شاملة ===
MONTH_MAP={"جانفي":1,"فيفري":2,"مارس":3,"أفريل":4,"افريل":4,"ماي":5,"جوان":6,"جويلية":7,"أوت":8,"اوت":8,"سبتمبر":9,"أكتوبر":10,"اكتوبر":10,"نوفمبر":11,"ديسمبر":12,"janvier":1,"février":2,"fevrier":2,"avril":4,"juin":6,"juillet":7,"août":8,"aout":8,"septembre":9,"octobre":10,"novembre":11,"décembre":12}
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

def is_from_2_aout(txt, header_date=None):
    dates=extract_dates(txt)
    if header_date: dates.append(header_date)
    if not dates:
        # بدون تاريخ، اقبل فقط إذا فيه 2026 وما فيهش 2024/2025
        return "2026" in txt and "2024" not in txt and "2025" not in txt
    for y,m,d in dates:
        if y<2026: return False
        if y==2026 and m<8: return False
        if y==2026 and m==8 and d<2: return False
    return True

def is_real_tender(txt):
    if len(txt)<50 or len(txt)>800: return False
    if "طلب العروض" not in txt and "تمديد" not in txt: return False
    if "رقم" not in txt: return False
    if not re.search(r"\d{2,4}\s*/\s*2026", txt): return False # يجب أن يحتوي رقم مثل 044/2026
    if any(k in txt.lower() for k in ["إعذار","فسخ","attribution"]): return False
    return True

def safe_get(url):
    try: return requests.get(url, headers={"User-Agent":"Mozilla/5.0"}, timeout=20, verify=False)
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
        for el in soup.find_all(['div','p','li'], limit=500):
            txt=el.get_text(" ",strip=True)
            if len(txt)<5: continue
            # هيدر تاريخ
            if len(txt)<30:
                d=extract_dates(txt)
                if d:
                    current_date=d[0]
                    continue
            if not is_real_tender(txt): continue
            if not is_from_2_aout(txt, current_date): continue
            if txt[:80] in seen: continue
            seen.add(txt[:80])
            link=url
            a=el.find('a', href=True)
            if a and a.get('href'):
                href=a['href']
                if href.startswith("/"): href="https://www.mdn.dz"+href
                if not href.startswith("http"): href="https://www.mdn.dz/site_principal/sommaire/appels/"+href.lstrip('/')
                link=href
            pdf=el.find('a', href=lambda h: h and '.pdf' in h.lower())
            if pdf and pdf.get('href'):
                href=pdf['href']
                if href.startswith("/"): href="https://www.mdn.dz"+href
                link=href
            tid=gen_id(txt, "MDN")
            tenders.append({"id":tid,"title":txt,"anep":gen_anep(txt),"wilaya":"Algérie","link":link,"source":"MDN","company":"وزارة الدفاع"})
        print(f"📡 MDN: {len(tenders)} مناقصة حقيقية من 2 أوت")
    except Exception as e: print(f"MDN error {e}")
    return tenders

factories=load_factories()
sent=load_sent()
print(f"🔒 المرسلة: {len(sent)} | مصانع: {len(factories)} | اليوم {datetime.now().strftime('%d/%m/%Y')}")

all_tenders=scrape_mdn() # نركز على MDN لأنه المصدر الحقيقي حاليا

# إزالة المكرر
unique={}
for t in all_tenders:
    if t["id"] in sent: continue
    unique[t["id"]]=t

new=list(unique.values())
print(f"📊 الخام: {len(all_tenders)} | جديدة: {len(new)}")

if not new:
    print("✅ لا يوجد جديد - مضاد التكرار يعمل!")
else:
    # أرسل كل الجديد مرة واحدة (وليس 15 فقط)
    for t in new:
        # 3 مصانع مع أرقام
        picks=random.sample(factories, min(3, len(factories))) if factories else []
        fac_txt=""
        for i,f in enumerate(picks,1):
            fac_txt+=f"{i}. 🏭 <b>{f.get('name','')}</b>\n📦 {f.get('product','')} | 📞 <code>{f.get('phone','')}</code>\n🗺️ <a href=\"{f.get('map','')}\">خريطة</a>\n"
        msg=f"""🔔 <b>مناقصة جديدة - {t['source']}</b>

🏢 {t['company']} | ANEP: {t['anep']}
📋 {t['title']}

📄 <a href="{t['link']}">📎 فتح الإعلان الأصلي PDF</a>

🏭 <b>موردين مقترحين:</b>
{fac_txt}
#Tradium #v10
"""
        if send(msg):
            sent.add(t["id"])
            print(f"✅ أرسلت: {t['title'][:50]}")
    save_sent(sent)
    print(f"💾 حفظ {len(sent)} - لن يكرر أبدا")
