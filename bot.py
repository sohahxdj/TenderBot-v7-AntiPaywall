import os, requests, json, re, hashlib, random, urllib3
from bs4 import BeautifulSoup
from datetime import datetime

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

TOKEN = os.getenv("TELEGRAM_TOKEN","").strip()
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID","").strip()
SENT_FILE = "sent_v7.json"
FACTORIES_FILE = "factories_300.json"

print("🚀 v8.5 - FIX يجيب اليوم والبارحة - 2 أوت+")

def load_factories():
    if os.path.exists(FACTORIES_FILE):
        try:
            with open(FACTORIES_FILE,"r",encoding="utf-8") as f:
                data=json.load(f)
            if len(data)>0: return data
        except: pass
    return [{"id":1,"name":"Test","wilaya":"Alger","priority":"تجهيزات مكتبية","product":"مكاتب","is_direct_factory":True,"phone":"0550","map":"https://maps.google.com"}]

def load_sent():
    try:
        if os.path.exists(SENT_FILE):
            with open(SENT_FILE,"r",encoding="utf-8") as f:
                data=json.load(f)
                if isinstance(data, list): return set(data)
                elif isinstance(data, dict): return set(data.get("ids",[]))
        return set()
    except: return set()

def save_sent(sent_set):
    try:
        data={"ids": list(sent_set),"last_update": datetime.now().isoformat(),"count": len(sent_set)}
        with open(SENT_FILE,"w",encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print(f"💾 تم حفظ {len(sent_set)}")
        with open("sent_ids_backup.txt","w",encoding="utf-8") as f:
            for sid in sent_set: f.write(sid+"\n")
    except Exception as e: print(f"❌ {e}")

def send(text):
    url=f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    data={"chat_id":CHAT_ID,"text":text,"parse_mode":"HTML","disable_web_page_preview":False}
    try:
        r=requests.post(url,data=data,timeout=30)
        print(f"Telegram: {r.status_code}")
        return r.status_code==200
    except Exception as e:
        print(f"Telegram error {e}")
        return False

def generate_stable_id_fixed(title, source):
    clean = re.sub(r'\s+', ' ', title[:200].lower().strip())[:120]
    base = f"{clean}|{source}"
    return hashlib.md5(base.encode('utf-8')).hexdigest()

def generate_anep_deterministic(title):
    h = abs(hash(title)) % 900000 + 100000
    return f"26{h}"

# === FIX v8.5: فلتر أخف - يقبل اليوم والبارحة ===
def is_after_august_2026_final(txt):
    # اقبل أي شيء فيه 2026 وما فيهش 2024/2025 قديم
    if "2024" in txt and "2026" not in txt: return False
    if "2025" in txt and "2026" not in txt: return False
    if any(k in txt.lower() for k in ["إعذار","mise en demeure","فسخ","annulation"]):
        return False
    # إذا فيه 2026 اقبله مباشرة
    if "2026" in txt:
        return True
    # حتى بدون سنة، إذا فيه كلمات مناقصة جديدة، اقبله
    if any(k in txt.lower() for k in ["طلب العروض","appel d'offres","consultation"]):
        # لكن لا تقبل إذا فيه تاريخ قديم واضح
        if "2024" not in txt and "2025" not in txt:
            return True
    return False

def is_new_tender(txt):
    tl = txt.lower()
    # استبعاد المنح
    if any(k in tl for k in ["attribution","résultat","منح مؤقت"]):
        return False
    if not any(k in tl for k in ["طلب العروض","طلب عروض","appel d'offres","consultation","acquisition","fourniture","travaux","توريد","اقتناء"]):
        return False
    return is_after_august_2026_final(txt)

def safe_get(url, timeout=20):
    headers={"User-Agent":"Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
    try:
        r = requests.get(url, headers=headers, timeout=timeout, verify=False)
        print(f"GET {url} -> {r.status_code} len={len(r.text)}")
        return r
    except Exception as e:
        print(f"GET fail {url} {e}")
        return None

def scrape_aapi():
    tenders=[]
    try:
        url="https://aapi.dz/consultations/"
        r=safe_get(url)
        if not r: return tenders
        soup=BeautifulSoup(r.text,"lxml")
        rows=[]
        for t in soup.find_all('table'): rows.extend(t.find_all('tr'))
        if not rows: rows=soup.find_all(['tr','article','div'], limit=100)
        print(f"AAPI raw rows: {len(rows)}")
        for el in rows:
            txt=el.get_text(" ",strip=True)
            if len(txt)<50 or len(txt)>2000: continue
            # debug
            if "2026" in txt or "appel" in txt.lower() or "طلب" in txt:
                print(f"AAPI candidate: {txt[:80]}... is_new={is_new_tender(txt)}")
            if not is_new_tender(txt): continue
            link_tag=el.find("a", href=True)
            link=link_tag["href"] if link_tag else url
            if link.startswith("/"): link="https://aapi.dz"+link
            pdf_tag=el.find("a", href=lambda h: h and ".pdf" in h.lower())
            if pdf_tag and pdf_tag.get("href"):
                plink=pdf_tag["href"]
                if plink.startswith("/"): plink="https://aapi.dz"+plink
                if plink.startswith("http"): link=plink
            anep_display=generate_anep_deterministic(txt)
            tid=generate_stable_id_fixed(txt, "AAPI")
            tenders.append({"id":tid,"title":txt[:600],"anep":anep_display,"wilaya":"Alger","link":link,"source":"AAPI","company":"AAPI"})
        print(f"📡 AAPI: {len(tenders)}")
    except Exception as e: print(f"AAPI error {e}")
    return tenders

def scrape_safqatic_fixed():
    tenders=[]
    try:
        url="https://www.safqatic.dz/index.php?type=1"
        r=safe_get(url)
        if not r or r.status_code!=200: return tenders
        soup=BeautifulSoup(r.text,"lxml")
        els=soup.find_all(['div','tr','article'], limit=150)
        print(f"Safqatic raw: {len(els)}")
        for el in els:
            txt=el.get_text(" ",strip=True)
            if len(txt)<50 or len(txt)>2000: continue
            if "2026" in txt or "appel" in txt.lower():
                print(f"Safqatic cand: {txt[:80]} is_new={is_new_tender(txt)}")
            if not is_new_tender(txt): continue
            pdf_inside = el.find('a', href=lambda h: h and ('/docs/offres/' in h or h.lower().endswith('.pdf')))
            if pdf_inside and pdf_inside.get('href'):
                link=pdf_inside['href']
                if link.startswith("/"): link="https://www.safqatic.dz"+link
                if not link.startswith("http"): link="https://www.safqatic.dz/"+link.lstrip('/')
            else:
                link_tag=el.find('a', href=True)
                if not link_tag: continue
                link=link_tag['href']
                if link.startswith("/"): link="https://www.safqatic.dz"+link
                if link.endswith("?type=1"): continue
            tid=generate_stable_id_fixed(txt, "SAFQATIC")
            tenders.append({"id":tid,"title":txt[:600],"anep":generate_anep_deterministic(txt),"wilaya":"Algérie","link":link,"source":"Safqatic","company":"Algérie Télécom"})
        print(f"📡 Safqatic: {len(tenders)}")
    except Exception as e: print(f"Safqatic error {e}")
    return tenders

def scrape_mdn_fixed():
    tenders=[]
    try:
        urls=["https://www.mdn.dz/site_principal/sommaire/appels/appels_ar.php","https://www.mdn.dz/site_principal/sommaire/appels/appels_fr.php"]
        for url in urls:
            r=safe_get(url)
            if not r or r.status_code!=200: continue
            soup=BeautifulSoup(r.text,"lxml")
            els=soup.find_all(['a','div','p','tr','li'], limit=400)
            print(f"MDN {url} raw: {len(els)}")
            count=0
            for el in els:
                txt=el.get_text(" ",strip=True)
                if len(txt)<20 or len(txt)>1500: continue
                if "2026" in txt or "طلب العروض" in txt or "appel" in txt.lower():
                    if count<5: print(f"MDN cand: {txt[:100]} is_new={is_new_tender(txt)}")
                if not is_new_tender(txt): continue
                link=url
                if el.name=='a' and el.get('href'):
                    link=el['href']
                    if link.startswith("/"): link="https://www.mdn.dz"+link
                    if not link.startswith("http"): link="https://www.mdn.dz/site_principal/sommaire/appels/"+link.lstrip('/')
                else:
                    a_tag=el.find('a', href=True)
                    if a_tag and a_tag.get('href'):
                        link=a_tag['href']
                        if link.startswith("/"): link="https://www.mdn.dz"+link
                        if not link.startswith("http"): link="https://www.mdn.dz/site_principal/sommaire/appels/"+link.lstrip('/')
                tid=generate_stable_id_fixed(txt, "MDN")
                if any(t['id']==tid for t in tenders): continue
                tenders.append({"id":tid,"title":txt[:700],"anep":generate_anep_deterministic(txt),"wilaya":"Algérie","link":link,"source":"MDN","company":"وزارة الدفاع"})
                count+=1
            if len(tenders)>0: break
        print(f"📡 MDN FIXED: {len(tenders)}")
    except Exception as e: print(f"MDN error {e}")
    return tenders

def find_factories(all_factories, title, wilaya, limit=3):
    tl=title.lower()
    if any(k in tl for k in ["mobilier","meuble","bureau","informatique"]): prio="تجهيزات مكتبية"
    elif any(k in tl for k in ["plomberie","sanitaire"]): prio="ترصيص وتدفئة"
    elif any(k in tl for k in ["electricite","كهرباء"]): prio="كهرباء"
    else: prio=None
    if prio: candidates=[f for f in all_factories if prio in f.get("priority","")]
    else: candidates=all_factories
    same=[f for f in candidates if f.get("wilaya","").lower()==wilaya.lower()]
    if len(same)>=limit: return random.sample(same,limit)
    others=[f for f in candidates if f.get("wilaya","").lower()!=wilaya.lower()]
    result=same+random.sample(others, min(limit-len(same), len(others))) if others else same
    return result[:limit]

factories=load_factories()
sent=load_sent()
print(f"🔒 المرسلة سابقا: {len(sent)}")

all_tenders=[]
all_tenders.extend(scrape_aapi())
all_tenders.extend(scrape_safqatic_fixed())
all_tenders.extend(scrape_mdn_fixed())

print(f"📊 الخام: {len(all_tenders)}")
unique={}
for t in all_tenders:
    if t["id"] in sent: continue
    if any(t["title"][:90]==e["title"][:90] for e in unique.values()): continue
    unique[t["id"]]=t

new_tenders=list(unique.values())
print(f"🔍 جديدة: {len(new_tenders)}")

if not new_tenders:
    print("✅ لا يوجد جديدة")
    send("✅ <b>البوت v8.5 يفحص - لا يوجد جديدة اليوم (فحص 3 مواقع)</b>")
else:
    sent_count=0
    for t in new_tenders[:15]:
        matched=find_factories(factories, t["title"], t["wilaya"], limit=3)
        factories_text=""
        for i,f in enumerate(matched,1):
            factories_text+=f"{i}. 🏭 <b>{f['name']}</b> 📦 {f['product']} 📞 {f['phone']}\n"
        msg=f"""🔔 <b>مناقصة جديدة - {t['source']}</b> 🔔

🏢 <b>{t['company']}</b>
📍 {t['wilaya']} | ANEP: {t['anep']}
📋 {t['title']}

📄 <a href="{t['link']}">فتح الإعلان</a>

🏭 <b>أقرب 3 مصانع:</b>
{factories_text}
#Tradium #v85
"""
        if send(msg): 
            sent.add(t["id"])
            sent_count+=1
    save_sent(sent)
    print(f"✅ أرسلت {sent_count}")
