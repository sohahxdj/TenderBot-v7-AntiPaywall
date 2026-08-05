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
        r=requests.get(url,headers={"User-Agent":"Mozilla/5.0 Chrome/120.0"},timeout=15,verify=False)
        if len(r.text)>400: return r
    except: pass
    return None

def scrape_mdn():
    base="https://www.mdn.dz"
    url=f"{base}/site_principal/sommaire/appels/appels_ar.php"
    r=safe_get(url)
    if not r: return []
    soup=BeautifulSoup(r.text,"html.parser")
    res=[]; seen=set()
    for el in soup.find_all(['div','p','li','td'],limit=1000):
        txt=el.get_text(" ",strip=True)
        if len(txt)<25 or "طلب العروض" not in txt or not re.search(r"\d+/\d{4}",txt): continue
        if txt[:100] in seen: continue
        seen.add(txt[:100])
        link=url
        for a in el.find_all('a',href=True):
            if ".pdf" in a['href'].lower():
                link=urljoin(base,a['href']); break
        res.append({"id":gen_id(txt,"MDN"),"title":txt[:800],"anep":gen_anep(txt),"link":link,"date":TODAY.strftime("%d/%m/%Y"),"source":"MDN"})
    return res[:5]

def scrape_rhino():
    base="https://rhinotenders.com"
    r=safe_get(base+"/")
    if not r: return []
    soup=BeautifulSoup(r.text,"html.parser")
    res=[]; seen=set()
    for h in soup.find_all(['h3','h2'],limit=50):
        txt=h.get_text(" ",strip=True)
        if len(txt)<15 or len(txt)>350 or txt in seen: continue
        if "Ne ratez" in txt: continue
        seen.add(txt)
        link=base+"/"
        pa=h.find_parent('a',href=True)
        if pa: link=urljoin(base,pa['href'])
        res.append({"id":gen_id(txt,"RHINO"),"title":txt,"anep":gen_anep(txt),"link":link,"date":TODAY.strftime("%d/%m/%Y"),"source":"RHINO"})
    return res[:7]

def scrape_bomop():
    base="https://bomop.anep.dz"
    # هذه الفئات فيها كل القطاعات
    cats=["/category/industrie/","/category/batiment-et-travaux-publics/","/category/energie/","/category/equipements-industriels-outillage-et-pieces-detachees/","/category/agriculture-elevage-forets-et-peche/"]
    res=[]; seen=set()
    for cat in cats:
        url=base+cat
        r=safe_get(url)
        if not r: continue
        soup=BeautifulSoup(r.text,"html.parser")
        # BOMOP كل إعلان في article
        for art in soup.find_all('article',limit=15):
            h=art.find(['h2','h3'])
            if not h: continue
            txt=h.get_text(" ",strip=True)
            if len(txt)<20 or txt[:80] in seen: continue
            if "appel" not in txt.lower() and "avis" not in txt.lower(): continue
            seen.add(txt[:80])
            a=art.find('a',href=True)
            link=urljoin(base,a['href']) if a else url
            res.append({"id":gen_id(txt,"BOMOP"),"title":txt[:800],"anep":gen_anep(txt),"link":link,"date":TODAY.strftime("%d/%m/%Y"),"source":"BOMOP"})
        if len(res)>=10: break
    print(f"[BOMOP] {len(res)} ب رابط أصلي")
    return res[:10]

# تشغيل
factories=load_factories()
sent=load_sent()
all_t=[]
all_t.extend(scrape_mdn())
all_t.extend(scrape_rhino())
all_t.extend(scrape_bomop())
print(f"Total {len(all_t)}")
new=[t for t in all_t if t["id"] not in sent][:10]
for t in new:
    picks=random.sample(factories,min(3,len(factories))) if factories else []
    fac=""
    for i,f in enumerate(picks,1):
        name=html.escape(f.get('name','')[:45])
        phone=f.get('phone') or f.get('tel') or ""
        murl=f.get('map') or f.get('maps') or f.get('location') or f"https://www.google.com/maps/search/{name}"
        fac+=f"{i}. 🏭 <b>{name}</b>\n📞 <code>{phone}</code> | <a href='{murl}'>🗺️ موقع الخريطة</a>\n"
    emoji="🏛️" if t["source"]=="BOMOP" else "🛡️" if t["source"]=="MDN" else "🏗️"
    # رابط أصلي + PDF
    msg=f"{emoji} <b>[{t['source']}] {t['date']}</b>\n{t['title'][:700]}\n\n📎 <a href='{t['link']}'>رابط الإعلان الأصلي / PDF</a>\n\n{fac}\n🔖 {t['anep']}"
    if send(msg): sent.add(t["id"])
save_sent(sent)
os.makedirs("public",exist_ok=True)
with open("public/tenders.json","w",encoding="utf-8") as f: json.dump(all_t,f,ensure_ascii=False,indent=2)
