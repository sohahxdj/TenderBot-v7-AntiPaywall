import os, requests, json, re, hashlib, random, urllib3, html
from bs4 import BeautifulSoup
from datetime import datetime
from zoneinfo import ZoneInfo
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
TOKEN=os.getenv("TELEGRAM_TOKEN","").strip()
CHAT_ID=os.getenv("TELEGRAM_CHAT_ID","").strip()
SENT_FILE="sent_v7.json"
FACTORIES_FILE="factories_300.json"
ALGIERS=ZoneInfo("Africa/Algiers")
TODAY=datetime.now(ALGIERS)
print(f"v22 - {TODAY.strftime('%d/%m/%Y')}")

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
def send(text):
    if not TOKEN or not CHAT_ID: return False
    url=f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    data={"chat_id":CHAT_ID,"text":text,"parse_mode":"HTML"}
    try: return requests.post(url,data=data,timeout=20).status_code==200
    except: return False
def gen_id(t,src): return hashlib.md5(f"{t[:120].lower()}|{src}".encode()).hexdigest()
def gen_anep(t): return f"26{abs(hash(t))%900000+100000}"
def safe_get(url):
    headers={"User-Agent":"Mozilla/5.0 Chrome/120.0"}
    try:
        r=requests.get(url,headers=headers,timeout=15,verify=False)
        if len(r.text)>500: return r
    except: pass
    return None

def scrape_mdn():
    url="https://www.mdn.dz/site_principal/sommaire/appels/appels_ar.php"
    r=safe_get(url)
    if not r: return []
    soup=BeautifulSoup(r.text,"html.parser")
    tenders=[]; seen=set()
    for el in soup.find_all(['div','p','li'],limit=800):
        txt=el.get_text(" ",strip=True)
        if len(txt)<20 or len(txt)>800: continue
        if "طلب العروض" not in txt: continue
        if txt[:100] in seen: continue
        seen.add(txt[:100])
        tenders.append({"id":gen_id(txt,"MDN"),"title":txt,"anep":gen_anep(txt),"link":url,"date":TODAY.strftime("%d/%m/%Y"),"source":"MDN"})
        if len(tenders)>=5: break
    return tenders

def scrape_rhino():
    url="https://rhinotenders.com/"
    r=safe_get(url)
    if not r: return []
    soup=BeautifulSoup(r.text,"html.parser")
    tenders=[]; seen=set()
    for h in soup.find_all(['h3','h2'],limit=40):
        txt=h.get_text(" ",strip=True)
        if len(txt)<15 or len(txt)>300: continue
        if txt in seen: continue
        if "Appels d'Offres" in txt: continue
        seen.add(txt)
        tenders.append({"id":gen_id(txt,"RHINO"),"title":txt,"anep":gen_anep(txt),"link":url,"date":TODAY.strftime("%d/%m/%Y"),"source":"RHINO"})
    return tenders[:8]

factories=load_factories()
sent=load_sent()
all_t=[]
all_t.extend(scrape_mdn())
all_t.extend(scrape_rhino())
print(f"Total {len(all_t)}")
new=[t for t in all_t if t["id"] not in sent][:10]
for t in new:
    picks=random.sample(factories,min(3,len(factories))) if factories else []
    fac="".join([f"{i}. {f['name']} {f['phone']}\n" for i,f in enumerate(picks,1)])
    msg=f"[{t['source']}] {t['date']}\n{t['title'][:600]}\n{t['link']}\n\n{fac}"
    if send(f"<b>{msg}</b>"): sent.add(t["id"])
save_sent(sent)
os.makedirs("public",exist_ok=True)
with open("public/tenders.json","w",encoding="utf-8") as f: json.dump(all_t,f,ensure_ascii=False,indent=2)
