import os, requests, json, re, hashlib, random, urllib3, html
from bs4 import BeautifulSoup
from datetime import datetime
from zoneinfo import ZoneInfo

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

TOKEN = os.getenv("TELEGRAM_TOKEN","").strip()
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID","").strip()
TRENDS_COOKIE = os.getenv("TRENDS_COOKIE","").strip()
SENT_FILE = "sent_v7.json"
FACTORIES_FILE = "factories_300.json"
ALGIERS = ZoneInfo("Africa/Algiers")
TODAY = datetime.now(ALGIERS)

print(f"🚀 v21 FINAL - MDN 02-05 + TRENDS - {TODAY.strftime('%d/%m/%Y %H:%M')}")

MONTH_MAP={"جانفي":1,"فيفري":2,"مارس":3,"أفريل":4,"ماي":5,"جوان":6,"جويلية":7,"أوت":8,"اوت":8,"سبتمبر":9,"أكتوبر":10,"نوفمبر":11,"ديسمبر":12}

def load_factories():
    try:
        with open(FACTORIES_FILE,"r",encoding="utf-8") as f:
            return json.load(f)
    except:
        return []

def load_sent():
    try:
        if os.path.exists(SENT_FILE):
            with open(SENT_FILE,"r",encoding="utf-8") as f:
                return set(json.load(f).get("ids",[]))
    except:
        pass
    return set()

def save_sent(s):
    with open(SENT_FILE,"w",encoding="utf-8") as f:
        json.dump({"ids":list(s),"last_update":TODAY.isoformat(),"count":len(s)},f,ensure_ascii=False,indent=2)

def send(text):
    if not TOKEN or not CHAT_ID:
        print("❌ TOKEN/CHAT_ID ناقص")
        return False
    url=f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    data={"chat_id":CHAT_ID,"text":text,"parse_mode":"HTML","disable_web_page_preview":True}
    try:
        r=requests.post(url,data=data,timeout=20)
        return r.status_code==200
    except Exception as e:
        print(f"Send fail {e}")
        return False

def gen_id(t,src):
    clean=re.sub(r'\s+',' ',t[:200].lower().strip())[:120]
    return hashlib.md5(f"{clean}|{src}".encode()).hexdigest()

def gen_anep(t):
    return f"26{abs(hash(t))%900000+100000}"

def extract_dates(txt):
    dates=[]
    for m in re.finditer(r"(\d{1,2})\s+(جانفي|فيفري|مارس|أفريل|ماي|جوان|جويلية|أوت|اوت|سبتمبر|أكتوبر|نوفمبر|ديسمبر)\s+(2026)", txt, flags=re.I):
        d=int(m.group(1))
        mo=MONTH_MAP.get(m.group(2),8)
        if mo==8 and 2<=d<=31:
            dates.append((2026,mo,d,m.group(0)))
    return dates

def safe_get(url, timeout=12, extra_headers=None):
    headers={
        "User-Agent":"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0 Safari/537.36",
        "Referer":"https://marches-publics.gov.dz/",
        "Accept":"text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language":"ar-DZ,ar;q=0.9,fr;q=0.8"
    }
    if extra_headers:
        headers.update(extra_headers)
    try:
        r=requests.get(url, headers=headers, timeout=timeout, verify=False)
        if len(r.text)>500:
            return r
    except:
        pass
    return None

def scrape_mdn():
    url="https://www.mdn.dz/site_principal/sommaire/appels/appels_ar.php"
    r=safe_get(url, 15)
    if not r:
        print("[MDN] فشل الجلب")
        return []
    print(f"[MDN] {r.status_code} - {len(r.text)} حرف")
    all_dates=extract_dates(r.text)
    if not all_dates:
        print("[MDN] لا يوجد تواريخ 02-05 أوت")
        return []
    uniq=sorted(set(all_dates), key=lambda x: x[2], reverse=True)
    print(f"[MDN] تواريخ: {[x[3] for x in uniq]}")
    soup=BeautifulSoup(r.text,"html.parser")
    for latest in uniq:
        cur=None
        seen=set()
        tenders=[]
        for el in soup.find_all(['div','p','li','td'], limit=1200):
            txt=el.get_text(" ",strip=True)
            if len(txt)<15:
                continue
            if len(txt)<120:
                d=extract_dates(txt)
                if d:
                    cur=d[0]
                    continue
            if "طلب العروض" not in txt:
                continue
            if not cur or cur[:3]!=latest[:3]:
                continue
            if not re.search(r"\d{1,4}\s*/\s*2026", txt):
                continue
            if txt[:120] in seen:
                continue
            seen.add(txt[:120])
            link=url
            for a in el.find_all('a', href=True):
                if ".pdf" in a['href'].lower():
                    href=a['href']
                    link="https://www.mdn.dz"+href if href.startswith("/") else href
                    break
            tenders.append({"id":gen_id(txt,"MDN"),"title":txt[:800],"anep":gen_anep(txt),"link":link,"date":f"{latest[2]:02d}/08/2026","source":"MDN"})
        if tenders:
            print(f"[MDN] {latest[3]} => {len(tenders)}")
            return tenders
    print("[MDN] 0 مناقصة مطابقة 02-05 أوت")
    return []

def scrape_trends():
    url="https://marches-publics.gov.dz/trends"
    headers={
        "User-Agent":"Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0",
        "Referer":"https://marches-publics.gov.dz/",
        "Accept-Language":"ar-DZ,ar;q=0.9,fr;q=0.8"
    }
    if TRENDS_COOKIE:
        headers["Cookie"]=TRENDS_COOKIE
        print("[TRENDS] نستعمل Cookie من Secrets")

    html_text=None

    # محاولة 1 requests
    try:
        r=requests.get(url, headers=headers, timeout=20, verify=False)
        print(f"[TRENDS] requests {r.status_code} - {len(r.text)}")
        if len(r.text)>2000:
            html_text=r.text
    except Exception as e:
        print(f"[TRENDS] requests خطأ {e}")

    # محاولة 2 cloudscraper
    if not html_text:
        try:
            import cloudscraper
            scraper=cloudscraper.create_scraper()
            r=scraper.get(url, headers=headers, timeout=25)
            print(f"[TRENDS] cloudscraper {r.status_code} - {len(r.text)}")
            if len(r.text)>2000:
                html_text=r.text
        except Exception as e:
            print(f"[TRENDS] cloudscraper خطأ {e}")

    if not html_text:
        print("[TRENDS] فشل - الموقع محجوب من GitHub، سيعمل فقط مع TRENDS_COOKIE")
        return []

    soup=BeautifulSoup(html_text,"html.parser")
    tenders=[]
    seen=set()

    # الطريقة الجديدة حسب صورك: نبحث عن "الرقم المرجعي" و "تاريخ النشر"
    for el in soup.find_all(string=re.compile("الرقم المرجعي")):
        try:
            card=el.parent
            for _ in range(4):
                if card and len(card.get_text(" ",strip=True))<300:
                    card=card.parent
                else:
                    break
            if not card:
                continue
            full=card.get_text(" ",strip=True)
            # نطلع لفوق باش نجيب العنوان الكبير (إنجاز ثانوية...)
            container=card
            for _ in range(3):
                if container.parent:
                    container=container.parent
            container_text=container.get_text(" ",strip=True)

            m_ref=re.search(r"(ao\d+/\d{4}|[a-z0-9]{2,}\d+/\d{4})", full, re.I)
            ref=m_ref.group(1) if m_ref else ""

            # فلترة تاريخ 05 أوت 2026 مثل صورتك
            if "05 أوت 2026" in container_text or "05 أوت" in full:
                date_str="05/08/2026"
            elif "04 أوت" in container_text:
                date_str="04/08/2026"
            elif "03 أوت" in container_text:
                date_str="03/08/2026"
            elif "02 أوت" in container_text:
                date_str="02/08/2026"
            else:
                # إذا فيه 2026 أوت نقبل
                if "أوت 2026" not in container_text and "أوت" not in full:
                    continue
                date_str=TODAY.strftime("%d/%m/%Y")

            # العنوان
            title_match=re.search(r"(إنجاز ثانوية.*?منفصلة|إنجاز.*?وجبة.*?|طلب عروض.*?|إعلان عن.*?2026)", container_text, re.I)
            title=title_match.group(1) if title_match else container_text[:600]

            if not title or len(title)<20:
                continue
            if ref and ref in seen:
                continue
            if ref:
                seen.add(ref)

            tenders.append({
                "id":gen_id(title+ref,"TRENDS"),
                "title":title[:800],
                "anep":ref if ref else gen_anep(title),
                "link":url,
                "date":date_str,
                "source":"MARCHES-PUBLICS"
            })
        except Exception as e:
            continue

    # fallback بسيط إذا الطريقة الأولى ما لقتش
    if not tenders:
        for div in soup.find_all(['div','article'], limit=500):
            txt=div.get_text(" ",strip=True)
            if len(txt)<80 or len(txt)>2000:
                continue
            if "إنجاز" in txt and ("أوت 2026" in txt or "2026" in txt) and "الرقم المرجعي" in txt:
                if txt[:100] in seen:
                    continue
                seen.add(txt[:100])
                tenders.append({
                    "id":gen_id(txt,"TRENDS"),
                    "title":txt[:800],
                    "anep":gen_anep(txt),
                    "link":url,
                    "date":"05/08/2026",
                    "source":"MARCHES-PUBLICS"
                })
                if len(tenders)>=10:
                    break

    print(f"[TRENDS] لقى {len(tenders)} مناقصة")
    return tenders

# --- تشغيل ---
factories=load_factories()
sent=load_sent()
print(f"🔒 مرسلة سابقا: {len(sent)}")

all_t=[]
all_t.extend(scrape_mdn())
all_t.extend(scrape_trends())

print(f"📊 الإجمالي: {len(all_t)}")
new=[t for t in all_t if t["id"] not in sent][:10]
print(f"🔍 جديدة: {len(new)}")

for t in new:
    picks=random.sample(factories, min(3,len(factories))) if factories else []
    fac="".join([f"{i}. 🏭 <b>{html.escape(f['name'])}</b> 📞 <code>{f['phone']}</code> <a href=\"{f.get('map','#')}\">🗺️ موقع</a>\n" for i,f in enumerate(picks,1)])
    emoji="🛡️" if t["source"]=="MDN" else "🏛️"
    msg=f"{emoji} <b>[{t['source']}] {t['date']}</b>\n{t['title'][:700]}\n<a href='{t['link']}'>📎 فتح الإعلان</a>\n\n{fac}📍 المصدر: {t['source']}\n🔖 المرجع: {t['anep']}"
    if send(msg):
        sent.add(t["id"])
        print(f"✅ أرسلت {t['anep']}")

save_sent(sent)
os.makedirs("public", exist_ok=True)
with open("public/tenders.json","w",encoding="utf-8") as f:
    json.dump(all_t,f,ensure_ascii=False,indent=2)
print(f"🏁 محفوظ {len(sent)}")
