import os, requests, json, re, hashlib, random, urllib3, html
from bs4 import BeautifulSoup
from datetime import datetime
from zoneinfo import ZoneInfo
from urllib.parse import urljoin

urllib3.disable_warnings()
TOKEN=os.getenv("TELEGRAM_TOKEN","").strip()
CHAT_ID=os.getenv("TELEGRAM_CHAT_ID","").strip()
SENT_FILE="sent_v7.json"
FACTORIES_FILE="factories_300.json"
TODAY=datetime.now(ZoneInfo("Africa/Algiers"))

# فلتر القطاعات للثاني فقط
SECTEURS_INTERET = [
    "btp","batiment","construction","travaux","amenagement","rehabilitation",
    "industrie","industriel","fourniture","equipement","outillage","acquisition",
    "energie","electrique","maintenance","pieces","rechange","sonatrach","sonelgaz"
]

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
    with open(SENT_FILE,"w",encoding="utf-8") as f: json.dump({"ids":list(s),"count":len(s)},f,ensure_ascii=False,indent=2)
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
def match_secteur(title):
    tl=title.lower()
    return any(k in tl for k in SECTEURS_INTERET)

# 1- MDN بدون فلتر - يجيب كلشي
def scrape_mdn():
    base="https://www.mdn.dz"
    url="https://www.mdn.dz/site_principal/sommaire/appels/appels_ar.php"
    r=safe_get(url)
    if not r: return []
    soup=BeautifulSoup(r.text,"html.parser")
    res=[]; seen=set()
    for el in soup.find_all(['div','p','li','td'],limit=1200):
        txt=el.get_text(" ",strip=True)
        if len(txt)<25 or "طلب العروض" not in txt: continue
        if txt[:100] in seen: continue
        seen.add(txt[:100])
        link=url
        for a in el.find_all('a',href=True):
            if ".pdf" in a['href'].lower():
                link=urljoin(base,a['href']); break
        if link==url and el.parent:
            for a in el.parent.find_all('a',href=True):
                if ".pdf" in a['href'].lower():
                    link=urljoin(base,a['href']); break
        res.append({"id":gen_id(txt,"MDN"),"title":txt[:800],"anep":gen_anep(txt),"link":link,"date":TODAY.strftime("%d/%m/%Y"),"source":"MDN"})
    print(f"[MDN] {len(res)} بدون فلتر")
    return res[:10]

# 2- RHINO مع فلتر 4 قطاعات فقط
def scrape_rhino():
    base="https://rhinotenders.com"
    url="https://rhinotenders.com/tenders?tender_type=National"
    r=safe_get(url)
    if not r: return []
    soup=BeautifulSoup(r.text,"html.parser")
    res=[]; seen=set()
    for a in soup.find_all('a',href=True,limit=250):
        href=a['href']
        if "/tenders/" not in href and "appel" not in href.lower(): continue
        txt=a.get_text(" ",strip=True)
        if len(txt)<15 or len(txt)>400: continue
        if txt[:80] in seen: continue
        if not match_secteur(txt): continue
        seen.add(txt[:80])
        full_link=urljoin(base,href)
        res.append({"id":gen_id(txt,"RHINO"),"title":txt[:800],"anep":gen_anep(txt),"link":full_link,"date":TODAY.strftime("%d/%m/%Y"),"source":"RHINO"})
    print(f"[RHINO] {len(res)} بعد فلتر 4 قطاعات")
    return res[:10]

factories=load_factories()
sent=load_sent()
all_t=[]
all_t.extend(scrape_mdn())
all_t.extend(scrape_rhino())
print(f"Total {len(all_t)}")
new=[t for t in all_t if t["id"] not in sent][:10]
for t in new:
    picks=random.sample(factories,min(3,len(factories))) if factories else []
    fac=""
    for i,f in enumerate(picks,1):
        name=html.escape(f.get('name','')[:45])
        phone=f.get('phone') or f.get('tel') or ""
        murl=f.get('map') or f.get('maps') or f.get('location') or f"https://www.google.com/maps/search/{name}"
        fac+=f"{i}. 🏭 <b>{name}</b>\n📞 <code>{phone}</code> | <a href='{murl}'>🗺️ خريطة الموقع</a>\n"
    msg=f"🏗️ <b>[{t['source']}] {t['date']}</b>\n{t['title'][:700]}\n\n📎 <a href='{t['link']}'>رابط الإعلان الأصلي / PDF</a>\n\n{fac}\n🔖 {t['anep']}"
    if send(msg): sent.add(t["id"])
save_sent(sent)
os.makedirs("public",exist_ok=True)
with open("public/tenders.json","w",encoding="utf-8") as f: json.dump(all_t,f,ensure_ascii=False,indent=2)
