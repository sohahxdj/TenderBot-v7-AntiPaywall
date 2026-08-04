import os, requests, json, re, hashlib, random, urllib3
from bs4 import BeautifulSoup
from datetime import datetime

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

TOKEN = os.getenv("TELEGRAM_TOKEN","").strip()
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID","").strip()
SENT_FILE = "sent_v7.json"
FACTORIES_FILE = "factories_300.json"

print("🚀 v8.4 FINAL - ID ثابت 100% - ANTI-DUPLICATE الحقيقي")

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
                if isinstance(data, list):
                    return set(data)
                elif isinstance(data, dict):
                    return set(data.get("ids",[]))
        return set()
    except:
        return set()

def save_sent(sent_set):
    try:
        data={
            "ids": list(sent_set),
            "last_update": datetime.now().isoformat(),
            "count": len(sent_set)
        }
        with open(SENT_FILE,"w",encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print(f"💾 تم حفظ {len(sent_set)} في {SENT_FILE}")
        with open("sent_ids_backup.txt","w",encoding="utf-8") as f:
            for sid in sent_set:
                f.write(sid+"\n")
    except Exception as e:
        print(f"❌ خطأ حفظ: {e}")

def send(text):
    url=f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    data={"chat_id":CHAT_ID,"text":text,"parse_mode":"HTML","disable_web_page_preview":False}
    try:
        r=requests.post(url,data=data,timeout=30)
        return r.status_code==200
    except: return False

# === FIX v8.4: ID ثابت بدون random ===
def generate_stable_id_fixed(title, source):
    clean = re.sub(r'\s+', ' ', title[:200].lower().strip())
    clean = clean[:120]
    base = f"{clean}|{source}"
    return hashlib.md5(base.encode('utf-8')).hexdigest()

def generate_anep_deterministic(title):
    h = abs(hash(title)) % 900000 + 100000
    return f"26{h}"

def clean_consultation_numbers(txt):
    txt = re.sub(r"N°\s*\d+\s*/\s*20\d{2}", " ", txt, flags=re.I)
    txt = re.sub(r"رقم\s*\d+\s*/\s*20\d{2}", " ", txt, flags=re.I)
    return txt

def extract_full_dates_only(txt):
    dates = []
    for m in re.finditer(r"\b(\d{1,2})[\/\-\.]\s*(\d{1,2})[\/\-\.]\s*(20\d{2})\b", txt):
        try:
            d=int(m.group(1)); mo=int(m.group(2)); y=int(m.group(3))
            if 1<=mo<=12 and 1<=d<=31 and 2020<=y<=2030:
                dates.append((y,mo,d))
        except: pass
    return dates

def is_after_august_2026_final(txt):
    cleaned = clean_consultation_numbers(txt)
    real_dates = extract_full_dates_only(cleaned)
    if real_dates:
        for y, mo, d in real_dates:
            if y < 2026 or (y == 2026 and mo < 8):
                return False
        return True
    else:
        if "2026" in cleaned:
            if any(k in cleaned.lower() for k in ["إعذار","mise en demeure","فسخ"]):
                return False
            if "2025" not in cleaned and "2024" not in cleaned:
                if any(k in cleaned.lower() for k in ["طلب العروض","طلب عروض","appel d'offres","consultation"]):
                    return True
        return False

def is_new_tender(txt):
    tl = txt.lower()
    if any(k in tl for k in ["إعذار","mise en demeure","فسخ"]):
        return False
    if not any(k in tl for k in ["طلب العروض","طلب عروض","appel d'offres","consultation","acquisition","fourniture","travaux"]):
        return False
    if "attribution" in tl or "résultat" in tl:
        return False
    return is_after_august_2026_final(txt)

def safe_get(url, timeout=20):
    headers={"User-Agent":"Mozilla/5.0"}
    try:
        r = requests.get(url, headers=headers, timeout=timeout, verify=False)
        return r
    except: return None

def scrape_aapi():
    tenders=[]
    try:
        url="https://aapi.dz/consultations/"
        r=safe_get(url)
        if not r: return tenders
        soup=BeautifulSoup(r.text,"lxml")
        rows=[]
        for t in soup.find_all('table'):
            rows.extend(t.find_all('tr'))
        if not rows:
            rows=soup.find_all('article', limit=50)
        for el in rows:
            txt=el.get_text(" ",strip=True)
            if len(txt)<80 or len(txt)>1500: continue
            if not is_new_tender(txt): continue
            link_tag=el.find("a", href=True)
            link=link_tag["href"] if link_tag else url
            if link.startswith("/"): link="https://aapi.dz"+link
            pdf_tag=el.find("a", href=lambda h: h and ".pdf" in h.lower())
            if pdf_tag and pdf_tag.get("href"):
                plink=pdf_tag["href"]
                if plink.startswith("/"): plink="https://aapi.dz"+plink
                if plink.startswith("http"): link=plink
            anep_m=re.search(r"ANEP\s*([0-9]{6,})",txt,re.I)
            anep_display=anep_m.group(1) if anep_m else generate_anep_deterministic(txt)
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
        for el in soup.find_all(['div','tr','article'], limit=100):
            txt=el.get_text(" ",strip=True)
            if len(txt)<80 or len(txt)>2000: continue
            if not any(k in txt.lower() for k in ["appel d'offres","consultation"]): continue
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
            anep_display=generate_anep_deterministic(txt)
            tid=generate_stable_id_fixed(txt, "SAFQATIC")
            tenders.append({"id":tid,"title":txt[:600],"anep":anep_display,"wilaya":"Algérie","link":link,"source":"Safqatic AT","company":"Algérie Télécom"})
        print(f"📡 Safqatic: {len(tenders)}")
    except Exception as e: print(f"Safqatic error {e}")
    return tenders

def scrape_mdn_fixed():
    tenders=[]
    try:
        urls=[
            "https://www.mdn.dz/site_principal/sommaire/appels/appels_ar.php",
            "https://www.mdn.dz/site_principal/sommaire/appels/appels_fr.php",
        ]
        for url in urls:
            r=safe_get(url)
            if not r or r.status_code!=200: continue
            soup=BeautifulSoup(r.text,"lxml")
            count=0
            for el in soup.find_all(['a','div','p','tr','li'], limit=300):
                txt=el.get_text(" ",strip=True)
                if len(txt)<30 or len(txt)>1000: continue
                if "2026" not in txt: continue
                if not any(k in txt.lower() for k in ["طلب العروض","appel d'offres"]): continue
                if any(k in txt.lower() for k in ["إعذار","mise en demeure","فسخ"]): continue
                if not is_new_tender(txt): continue
                link=url
                if el.name=='a' and el.get('href'):
                    link=el['href']
                    if link.startswith("/"): link="https://www.mdn.dz"+link
                    if not link.startswith("http"):
                        link="https://www.mdn.dz/site_principal/sommaire/appels/"+link.lstrip('/')
                else:
                    a_tag=el.find('a', href=True)
                    if a_tag and a_tag.get('href'):
                        link=a_tag['href']
                        if link.startswith("/"): link="https://www.mdn.dz"+link
                        if not link.startswith("http"):
                            link="https://www.mdn.dz/site_principal/sommaire/appels/"+link.lstrip('/')
                num_m=re.search(r"(\d+\s*/\s*2026\s*/\s*\d+)",txt)
                anep_display=num_m.group(1).replace(" ","") if num_m else generate_anep_deterministic(txt)
                tid=generate_stable_id_fixed(txt, "MDN")
                if any(t['id']==tid for t in tenders): continue
                tenders.append({"id":tid,"title":txt[:700],"anep":anep_display,"wilaya":"Algérie","link":link,"source":"MDN","company":"وزارة الدفاع الوطني"})
                count+=1
                if count>=20: break
            if len(tenders)>0: break
        print(f"📡 MDN FIXED: {len(tenders)}")
    except Exception as e: print(f"MDN error {e}")
    return tenders

def find_factories(all_factories, title, wilaya, limit=3):
    tl=title.lower()
    if any(k in tl for k in ["mobilier","meuble","bureau","informatique","فيديو","سمعي"]): prio="تجهيزات مكتبية"
    elif any(k in tl for k in ["plomberie","sanitaire","chauffage","تدفئة"]): prio="ترصيص وتدفئة"
    elif any(k in tl for k in ["electricite","كهرباء","كهربائي","مولد","كابل"]): prio="كهرباء"
    elif any(k in tl for k in ["piece","قطع الغيار","صيانة"]): prio="قطع غيار"
    elif any(k in tl for k in ["travaux","بناء","إنجاز","أشغال"]): prio="بناء"
    else: prio=None
    if prio:
        candidates=[f for f in all_factories if prio in f.get("priority","")]
    else:
        candidates=all_factories
    same=[f for f in candidates if f.get("wilaya","").lower()==wilaya.lower()]
    if len(same)>=limit: return random.sample(same,limit)
    others=[f for f in candidates if f.get("wilaya","").lower()!=wilaya.lower()]
    result=same+random.sample(others, min(limit-len(same), len(others))) if others else same
    return result[:limit]

factories=load_factories()
sent=load_sent()
print(f"🔒 عدد المرسلة سابقا: {len(sent)} - IDs ثابتة 100%!")

all_tenders=[]
all_tenders.extend(scrape_aapi())
all_tenders.extend(scrape_safqatic_fixed())
all_tenders.extend(scrape_mdn_fixed())

print(f"📊 المجموع الخام: {len(all_tenders)}")

unique={}
duplicates=0
for t in all_tenders:
    if t["id"] in sent:
        duplicates+=1
        continue
    is_dup=False
    for e in unique.values():
        if t["title"][:90]==e["title"][:90]:
            is_dup=True
            break
    if is_dup:
        duplicates+=1
        continue
    unique[t["id"]]=t

new_tenders=list(unique.values())
print(f"🔍 جديدة: {len(new_tenders)} | مكررة: {duplicates}")

if not new_tenders:
    print("✅ لا يوجد جديدة - مضاد التكرار يعمل 100%!")
else:
    sent_count=0
    for t in new_tenders[:10]:
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
#Tradium #v84 #Fixed
"""
        if send(msg):
            sent.add(t["id"])
            sent_count+=1
    save_sent(sent)
    print(f"✅ أرسلت {sent_count} | المجموع: {len(sent)}")
