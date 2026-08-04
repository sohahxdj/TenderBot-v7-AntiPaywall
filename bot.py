import os, requests, json, re, hashlib, random, urllib3, html
from bs4 import BeautifulSoup
from datetime import datetime

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

TOKEN = os.getenv("TELEGRAM_TOKEN","").strip()
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID","").strip()
SENT_FILE = "sent_v7.json"
FACTORIES_FILE = "factories_300.json"

print("🚀 v11 FINAL - اليوم فقط + ضد التكرار الحديدي")

def load_factories():
    try:
        with open(FACTORIES_FILE,"r",encoding="utf-8") as f:
            data=json.load(f)
            print(f"🏭 مصانع: {len(data)}")
            return data
    except Exception as e:
        print(f"مصانع error {e}")
        return []

def load_sent():
    try:
        if os.path.exists(SENT_FILE):
            with open(SENT_FILE,"r",encoding="utf-8") as f:
                data=json.load(f)
                ids=set(data.get("ids",[])) if isinstance(data, dict) else set(data)
                print(f"🔒 محملة {len(ids)} مرسلة سابقا")
                return ids
    except: pass
    print("🔒 لا يوجد سجل سابق - بداية جديدة")
    return set()

def save_sent(s):
    try:
        with open(SENT_FILE,"w",encoding="utf-8") as f:
            json.dump({"ids": list(s),"last_update": datetime.now().isoformat(),"count": len(s)}, f, ensure_ascii=False, indent=2)
        with open("sent_ids_backup.txt","w",encoding="utf-8") as f:
            f.write("\n".join(s))
        print(f"💾 حفظ حديدي {len(s)}")
    except Exception as e:
        print(f"حفظ error {e}")

def send(text):
    url=f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    data={"chat_id":CHAT_ID,"text":text,"parse_mode":"HTML","disable_web_page_preview":False}
    try:
        r=requests.post(url,data=data,timeout=30)
        print(f"Telegram: {r.status_code}")
        if r.status_code!=200:
            print(f"Telegram error: {r.text[:500]}")
        return r.status_code==200
    except Exception as e:
        print(f"Telegram exception {e}")
        return False

def gen_id(title, source):
    clean=re.sub(r'\s+',' ',title[:200].lower().strip())[:120]
    return hashlib.md5(f"{clean}|{source}".encode()).hexdigest()

def gen_anep(title):
    return f"26{abs(hash(title))%900000+100000}"

# كل الشهور
MONTH_MAP={"جانفي":1,"فيفري":2,"مارس":3,"أفريل":4,"افريل":4,"ماي":5,"جوان":6,"جويلية":7,"أوت":8,"اوت":8,"أوث":8,"سبتمبر":9,"أكتوبر":10,"اكتوبر":10,"نوفمبر":11,"ديسمبر":12,"janvier":1,"février":2,"fevrier":2,"avril":4,"juin":6,"juillet":7,"août":8,"aout":8,"septembre":9,"octobre":10,"novembre":11,"décembre":12}
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

def is_today(date_tuple):
    today=datetime.now()
    y,m,d=date_tuple
    return y==today.year and m==today.month and d==today.day

def safe_get(url):
    try: return requests.get(url, headers={"User-Agent":"Mozilla/5.0"}, timeout=20, verify=False)
    except: return None

def scrape_mdn():
    tenders=[]
    try:
        url="https://www.mdn.dz/site_principal/sommaire/appels/appels_ar.php"
        r=safe_get(url)
        if not r or r.status_code!=200:
            print("MDN لا يمكن الوصول")
            return tenders
        soup=BeautifulSoup(r.text,"lxml")
        current_date=None
        today=datetime.now()
        print(f"📅 اليوم المطلوب: {today.strftime('%d/%m/%Y')}")
        seen=set()
        for el in soup.find_all(['div','p','li','h3'], limit=500):
            txt=el.get_text(" ",strip=True)
            if len(txt)<5: continue
            # هيدر تاريخ
            if len(txt)<35:
                d=extract_dates(txt)
                if d:
                    current_date=d[0]
                    print(f"📅 هيدر: {txt} -> {current_date}")
                    continue
            # فلتر صارم جدا
            if len(txt)<50 or len(txt)>800: continue
            if "طلب العروض" not in txt: continue
            if not re.search(r"\d{2,4}\s*/\s*2026", txt): continue
            if "2024" in txt or "2025" in txt: continue
            # شرط اليوم فقط
            if not current_date: continue
            if not is_today(current_date): continue
            if txt[:70] in seen: continue
            seen.add(txt[:70])
            # رابط أصلي + PDF
            link=url
            pdf_link=None
            for a in el.find_all('a', href=True):
                href=a['href']
                if ".pdf" in href.lower():
                    pdf_link=href
                    if href.startswith("/"): pdf_link="https://www.mdn.dz"+href
                    elif not href.startswith("http"): pdf_link="https://www.mdn.dz/site_principal/sommaire/appels/"+href.lstrip('/')
                    break
            if pdf_link: link=pdf_link
            else:
                a=el.find('a', href=True)
                if a and a.get('href'):
                    href=a['href']
                    if href.startswith("/"): href="https://www.mdn.dz"+href
                    elif not href.startswith("http"): href="https://www.mdn.dz/site_principal/sommaire/appels/"+href.lstrip('/')
                    link=href
            tid=gen_id(txt, "MDN")
            tenders.append({"id":tid,"title":txt,"anep":gen_anep(txt),"wilaya":"Algérie","link":link,"source":"MDN","company":"وزارة الدفاع"})
        print(f"📡 MDN: {len(tenders)} مناقصة اليوم فقط")
    except Exception as e: print(f"MDN error {e}")
    return tenders

def find_factories(all_factories, title, limit=3):
    if not all_factories: return []
    tl=title.lower()
    if any(k in tl for k in ["مكتب","اثاث","mobilier","bureau"]): prio="مكتب"
    elif any(k in tl for k in ["مطبخ","اعاشة","اكل"]): prio="مطبخ"
    else: prio=None
    if prio:
        cand=[f for f in all_factories if prio in f.get("priority","").lower() or prio in f.get("product","").lower()]
    else: cand=all_factories
    if len(cand)<limit: cand=all_factories
    return random.sample(cand, min(limit, len(cand)))

factories=load_factories()
sent=load_sent()

all_tenders=scrape_mdn()
print(f"📊 الخام: {len(all_tenders)}")

unique={}
for t in all_tenders:
    if t["id"] in sent:
        print(f"⏭️ تخطي مكرر: {t['anep']}")
        continue
    unique[t["id"]]=t

new=list(unique.values())
print(f"🔍 جديدة اليوم: {len(new)}")

if not new:
    print("✅ لا يوجد جديد - لن يكرر أبدا")
else:
    for t in new[:10]:
        picks=find_factories(factories, t["title"], limit=3)
        fac_txt=""
        for i,f in enumerate(picks,1):
            name=html.escape(f.get('name','مصنع'))
            prod=html.escape(f.get('product',''))
            phone=f.get('phone','')
            fmap=f.get('map','')
            fac_txt+=f"{i}. 🏭 <b>{name}</b>\n📦 {prod}\n📞 <code>{phone}</code> | 🗺️ <a href=\"{fmap}\">موقع</a>\n"
        safe_title=html.escape(t['title'][:600])
        msg=f"""🔔 <b>مناقصة اليوم {datetime.now().strftime('%d/%m/%Y')} - {t['source']}</b> 🔔

🏢 <b>{html.escape(t['company'])}</b> | ANEP: {t['anep']}
📋 {safe_title}

📄 <b>الإعلان الأصلي:</b> <a href="{t['link']}">فتح PDF / الإعلان</a>

🏭 <b>3 موردين:</b>
{fac_txt}
#Tradium #اليوم_فقط
"""
        if send(msg):
            sent.add(t["id"])
            save_sent(sent) # حفظ فوري بعد كل إرسال - أقوى ضد التكرار
            print(f"✅ أرسلت وحفظت {t['anep']}")
        else:
            print(f"❌ فشل {t['anep']}")

print(f"🏁 انتهى - المجموع المحفوظ {len(sent)}")
