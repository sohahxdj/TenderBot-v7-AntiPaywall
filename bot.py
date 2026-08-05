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

print(f"🚀 TRADIUM v22 FULL - {TODAY.strftime('%d/%m/%Y %H:%M')}")

# تحميل المصانع
def load_factories():
    try:
        with open(FACTORIES_FILE,"r",encoding="utf-8") as f:
            data = json.load(f)
            print(f"🏭 مصانع {len(data)}")
            return data
    except Exception as e:
        print(f"مصانع 0 - {e}")
        return []

# المرسلة سابقا
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
        print("❌ TOKEN ناقص")
        return False
    try:
        url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
        data = {"chat_id":CHAT_ID,"text":text,"parse_mode":"HTML","disable_web_page_preview":True}
        r = requests.post(url,data=data,timeout=20)
        print(f"Telegram {r.status_code}")
        return r.status_code==200
    except Exception as e:
        print(f"Send error {e}")
        return False

def gen_id(t,src):
    clean = re.sub(r'\s+',' ',t[:200].lower().strip())
    return hashlib.md5(f"{clean}|{src}".encode()).hexdigest()

def gen_anep(t):
    return f"26{abs(hash(t))%900000+100000}"

def safe_get(url,timeout=15):
    headers = {
        "User-Agent":"Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0 Safari/537.36",
        "Accept":"text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language":"ar-DZ,ar;q=0.9,fr;q=0.8"
    }
    try:
        r = requests.get(url,headers=headers,timeout=timeout,verify=False)
        if len(r.text)>400:
            return r
    except Exception as e:
        print(f"GET fail {url} {e}")
    return None

def scrape_mdn():
    url = "https://www.mdn.dz/site_principal/sommaire/appels/appels_ar.php"
    r = safe_get(url)
    if not r:
        print("[MDN] فشل")
        return []
    print(f"[MDN] {len(r.text)} حرف")
    soup = BeautifulSoup(r.text,"html.parser")
    tenders=[]; seen=set()
    for el in soup.find_all(['div','p','li','td'],limit=1000):
        txt = el.get_text(" ",strip=True)
        if len(txt)<20 or len(txt)>900: continue
        if "طلب العروض" not in txt: continue
        if not re.search(r"\d+/\d{4}",txt): continue
        key = txt[:120]
        if key in seen: continue
        seen.add(key)
        link = url
        for a in el.find_all('a',href=True):
            if ".pdf" in a['href'].lower():
                href=a['href']
                link = "https://www.mdn.dz"+href if href.startswith("/") else href
                break
        tenders.append({
            "id":gen_id(txt,"MDN"),
            "title":txt[:800],
            "anep":gen_anep(txt),
            "link":link,
            "date":TODAY.strftime("%d/%m/%Y"),
            "source":"MDN"
        })
        if len(tenders)>=6: break
    print(f"[MDN] {len(tenders)}")
    return tenders

def scrape_rhino():
    url = "https://rhinotenders.com/"
    r = safe_get(url)
    if not r:
        print("[RHINO] فشل")
        return []
    print(f"[RHINO] {len(r.text)}")
    soup = BeautifulSoup(r.text,"html.parser")
    tenders=[]; seen=set()
    for tag in soup.find_all(['h3','h2','h4'],limit=60):
        txt = tag.get_text(" ",strip=True)
        if len(txt)<15 or len(txt)>350: continue
        if txt in seen: continue
        if any(x in txt for x in ["Ne ratez","solution adaptée","Choisissez","plateforme"]): continue
        seen.add(txt)
        tenders.append({
            "id":gen_id(txt,"RHINO"),
            "title":txt[:800],
            "anep":gen_anep(txt),
            "link":url,
            "date":TODAY.strftime("%d/%m/%Y"),
            "source":"RHINO-ALL"
        })
    print(f"[RHINO] {len(tenders)}")
    return tenders[:8]

def scrape_bomop():
    url = "https://bomop.anep.dz/"
    r = safe_get(url)
    if not r: return []
    if "BOMOP" in r.text or "Bulletin Officiel" in r.text:
        print(f"[BOMOP] يعمل")
        return [{
            "id":gen_id("BOMOP","BOMOP"),
            "title":"BOMOP - Bulletin Officiel des Marchés Publics - كل القطاعات BTP, Industrie, Energie, Services",
            "anep":"BOMOP-2026",
            "link":url,
            "date":TODAY.strftime("%d/%m/%Y"),
            "source":"BOMOP"
        }]
    return []

# التشغيل الرئيسي
def main():
    factories = load_factories()
    sent = load_sent()
    print(f"مرسلة سابقا {len(sent)}")
    all_t = []
    all_t.extend(scrape_mdn())
    all_t.extend(scrape_rhino())
    all_t.extend(scrape_bomop())
    print(f"الإجمالي {len(all_t)}")
    new = [t for t in all_t if t["id"] not in sent][:10]
    print(f"جديدة {len(new)}")
    for t in new:
        picks = random.sample(factories,min(3,len(factories))) if factories else []
        fac_txt = ""
        for i,f in enumerate(picks,1):
            name = html.escape(f.get('name','')[:40])
            phone = f.get('phone','')
            fac_txt += f"{i}. 🏭 <b>{name}</b> 📞 <code>{phone}</code>\n"
        emoji = "🛡️" if t["source"]=="MDN" else "🏗️" if "RHINO" in t["source"] else "🏛️"
        msg = f"{emoji} <b>[{t['source']}] {t['date']}</b>\n{t['title'][:700]}\n<a href='{t['link']}'>📎 فتح الإعلان</a>\n\n{fac_txt}🔖 المرجع: {t['anep']}"
        if send(msg):
            sent.add(t["id"])
            print(f"✅ {t['anep']}")
    save_sent(sent)
    os.makedirs("public",exist_ok=True)
    with open("public/tenders.json","w",encoding="utf-8") as f:
        json.dump(all_t,f,ensure_ascii=False,indent=2)
    print(f"🏁 انتهى محفوظ {len(sent)}")

if __name__=="__main__":
    main()
