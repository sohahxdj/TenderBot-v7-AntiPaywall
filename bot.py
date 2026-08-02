import os, requests, json, re, hashlib, random, urllib3
from bs4 import BeautifulSoup

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

TOKEN = os.getenv("TELEGRAM_TOKEN","").strip()
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID","").strip()
SENT_FILE = "sent_v7.json"
FACTORIES_FILE = "factories_300.json"

print("🚀 v8.2 FINAL FIX MDN - appels_ar.php + appels_fr.php - 2 AOUT 2026 - LIEN DIRECT")

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
        with open(SENT_FILE,"r",encoding="utf-8") as f: return set(json.load(f))
    except: return set()

def save_sent(s):
    with open(SENT_FILE,"w",encoding="utf-8") as f: json.dump(list(s), f, ensure_ascii=False)

def send(text):
    url=f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    data={"chat_id":CHAT_ID,"text":text,"parse_mode":"HTML","disable_web_page_preview":False}
    try: requests.post(url,data=data,timeout=30)
    except Exception as e: print(f"Telegram error {e}")

BLACKLIST = ["avis d'attribution","attribution provisoire","résultat","offre la mieux disante","recours","منح مؤقت","إعذار"]

def clean_consultation_numbers(txt):
    # نحذف أرقام الاستشارات فقط، لكن نحتفظ بسنة 2026
    txt = re.sub(r"N°\s*\d+\s*/\s*20\d{2}", " ", txt, flags=re.I)
    txt = re.sub(r"رقم\s*\d+\s*/\s*20\d{2}", " ", txt, flags=re.I)
    # لا نحذف 2026 لوحده
    return txt

def extract_full_dates_only(txt):
    dates = []
    for m in re.finditer(r"\b(\d{1,2})[\/\-\.]\s*(\d{1,2})[\/\-\.]\s*(20\d{2})\b", txt):
        try:
            d=int(m.group(1)); mo=int(m.group(2)); y=int(m.group(3))
            if 1<=mo<=12 and 1<=d<=31 and 2020<=y<=2030:
                dates.append((y,mo,d,f"DD/MM/YYYY: {m.group()}"))
        except: pass
    for m in re.finditer(r"\b(20\d{2})[\/\-\.]\s*(\d{1,2})[\/\-\.]\s*(\d{1,2})\b", txt):
        try:
            y=int(m.group(1)); mo=int(m.group(2)); d=int(m.group(3))
            if 1<=mo<=12 and 1<=d<=31 and 2020<=y<=2030:
                dates.append((y,mo,d,f"YYYY/MM/DD: {m.group()}"))
        except: pass
    # البحث عن تاريخ عربي: 02 أوت 2026 أو 2 أوت 2026
    for m in re.finditer(r"\b(\d{1,2})\s*(?:أوت|اوت|aout|août)\s*(20\d{2})\b", txt, re.I):
        try:
            d=int(m.group(1)); y=int(m.group(2)); mo=8
            dates.append((y,mo,d,f"DD AOUT YYYY: {m.group()}"))
        except: pass
    return dates

def is_after_august_2026_final(txt):
    cleaned = clean_consultation_numbers(txt)
    real_dates = extract_full_dates_only(cleaned)
    if real_dates:
        for y, mo, d, src in real_dates:
            if y < 2026 or (y == 2026 and mo < 8):
                print(f"  ❌ مرفوض قبل أوت: {src}")
                return False
        print(f"  ✅ مقبول >= أوت: {real_dates}")
        return True
    else:
        # MDN: لا يوجد تاريخ كامل باليوم، لكن يوجد رقم 2026/xxx
        # إذا كان النص يحتوي على 2026 ولا يحتوي على 2025/2024، نقبله لأنه من 2026
        # خاصة إذا كان من MDN appels_ar.php الذي يحتوي على عروض أوت 2026
        if "2026" in cleaned:
            # تجاهل الإعذارات والفسخ
            if any(k in cleaned.lower() for k in ["إعذار","اعذار","فسخ","mise en demeure"]):
                return False
            if "2025" not in cleaned and "2024" not in cleaned:
                # تحقق من أنه طلب عروض وليس إعذار
                if any(k in cleaned.lower() for k in ["طلب العروض","طلب عروض","appel d'offres","consultation","acquisition","fourniture","travaux"]):
                    print(f"  ✅ مقبول: 2026 بدون تاريخ كامل لكن مناقصة جديدة (MDN)")
                    return True
        return False

def is_new_tender(txt):
    tl = txt.lower()
    # رفض الإعذارات
    if any(k in tl for k in ["إعذار","اعذار","mise en demeure","فسخ"]):
        return False
    for bad in BLACKLIST:
        if bad in tl and ("attribution" in bad or "منح" in bad or "résultat" in bad or "إعذار" in bad):
            return False
    if not any(k in tl for k in ["طلب العروض","طلب عروض","appel d'offres","consultation","acquisition","fourniture","travaux","équipement","prestation","تموين","إنجاز","اقتناء"]):
        return False
    if "attribution" in tl or "résultat" in tl:
        return False
    if not is_after_august_2026_final(txt):
        return False
    return True

def safe_get(url, timeout=20):
    headers={"User-Agent":"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
    try:
        r = requests.get(url, headers=headers, timeout=timeout, verify=False)
        return r
    except Exception as e:
        print(f"GET failed {url}: {e}")
        return None

# --- 1. AAPI (works) ---
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
            anep="26"+str(random.randint(100000,999999))
            tid=hashlib.md5((link+txt[:50]).encode()).hexdigest()
            tenders.append({"id":tid,"title":txt[:600],"anep":anep,"wilaya":"Alger","link":link,"source":"AAPI","company":"AAPI"})
        print(f"📡 AAPI: {len(tenders)}")
    except Exception as e: print(f"AAPI error {e}")
    return tenders

# --- 2. Safqatic FIXED (direct PDF) ---
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
            if not any(k in txt.lower() for k in ["appel d'offres","consultation","acquisition"]): continue
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
            anep="26"+str(random.randint(100000,999999))
            tid=hashlib.md5((link+txt[:80]).encode()).hexdigest()
            tenders.append({"id":tid,"title":txt[:600],"anep":anep,"wilaya":"Algérie","link":link,"source":"Safqatic AT","company":"Algérie Télécom"})
        print(f"📡 Safqatic direct PDF: {len(tenders)}")
    except Exception as e: print(f"Safqatic error {e}")
    return tenders

# --- 3. MDN FIXED - الرابط الصحيح الذي أرسلته ---
def scrape_mdn_fixed():
    """
    الرابط الصحيح: https://www.mdn.dz/site_principal/sommaire/appels/appels_ar.php
    و https://www.mdn.dz/site_principal/sommaire/appels/appels_fr.php
    """
    tenders=[]
    try:
        urls=[
            "https://www.mdn.dz/site_principal/sommaire/appels/appels_ar.php",
            "https://www.mdn.dz/site_principal/sommaire/appels/appels_fr.php",
            "https://www.mdn.dz/site_principal/sommaire/appels/appels_ar.php?lang=ar"
        ]
        for url in urls:
            r=safe_get(url)
            if not r or r.status_code!=200:
                print(f"MDN {url} failed: {r.status_code if r else 'no response'}")
                continue
            soup=BeautifulSoup(r.text,"lxml")
            print(f"MDN page length: {len(r.text)}")
            # الصفحة تحتوي على قائمة طويلة من العروض، كل عرض هو رابط
            # نبحث عن كل الروابط التي تحتوي على نص طلب عروض
            count=0
            for el in soup.find_all(['a','div','p','tr','li'], limit=300):
                txt=el.get_text(" ",strip=True)
                if len(txt)<30 or len(txt)>1000: continue
                # يجب أن يحتوي على كلمة طلب عروض و 2026
                if "2026" not in txt: continue
                if not any(k in txt.lower() for k in ["طلب العروض","طلب عروض","appel d'offres","consultation"]): continue
                # تجاهل الإعذارات
                if any(k in txt.lower() for k in ["إعذار","اعذار","mise en demeure","فسخ"]): continue
                
                if not is_new_tender(txt): continue
                
                # رابط مباشر
                link=url
                if el.name=='a' and el.get('href'):
                    link=el['href']
                    if link.startswith("/"): link="https://www.mdn.dz"+link
                    if not link.startswith("http"):
                        link="https://www.mdn.dz/site_principal/sommaire/appels/"+link.lstrip('/')
                else:
                    # ابحث عن رابط داخل العنصر
                    a_tag=el.find('a', href=True)
                    if a_tag and a_tag.get('href'):
                        link=a_tag['href']
                        if link.startswith("/"): link="https://www.mdn.dz"+link
                        if not link.startswith("http"):
                            link="https://www.mdn.dz/site_principal/sommaire/appels/"+link.lstrip('/')
                
                # إذا كان PDF مباشر
                if ".pdf" in link.lower():
                    pass # رابط PDF جاهز
                else:
                    # إذا كان الرابط هو نفس صفحة القائمة، نحاول نجيب PDF قريب
                    # لكن نترك رابط الصفحة كمرجع
                    pass
                
                # استخراج رقم العرض
                num_m=re.search(r"(\d+\s*/\s*2026\s*/\s*\d+)",txt)
                anep=num_m.group(1) if num_m else "26"+str(random.randint(100000,999999))
                
                tid=hashlib.md5((txt[:100]+link).encode()).hexdigest()
                # تجنب التكرار
                if any(t['id']==tid for t in tenders): continue
                
                tenders.append({
                    "id":tid,
                    "title":txt[:700],
                    "anep":anep,
                    "wilaya":"Algérie",
                    "link":link,
                    "source":"MDN",
                    "company":"وزارة الدفاع الوطني"
                })
                count+=1
                if count>=20: break
            
            print(f"MDN {url}: وجد {count} عرض 2026")
            if len(tenders)>0:
                break
        
        # طريقة ثانية: البحث عن كل الروابط PDF التي تحتوي على 2026
        if len(tenders)==0:
            for url in urls:
                r=safe_get(url)
                if not r: continue
                soup=BeautifulSoup(r.text,"lxml")
                for a in soup.find_all('a', href=True):
                    href=a['href']
                    txt=a.get_text(" ",strip=True)
                    if "2026" not in txt and "2026" not in href: continue
                    if len(txt)<20: continue
                    if any(k in txt.lower() for k in ["إعذار","mise en demeure"]): continue
                    if not any(k in txt.lower() for k in ["طلب العروض","appel"]): continue
                    link=href
                    if link.startswith("/"): link="https://www.mdn.dz"+link
                    if not link.startswith("http"): link="https://www.mdn.dz/site_principal/sommaire/appels/"+link.lstrip('/')
                    tid=hashlib.md5((txt[:100]+link).encode()).hexdigest()
                    tenders.append({"id":tid,"title":txt[:700],"anep":"26"+str(random.randint(100000,999999)),"wilaya":"Algérie","link":link,"source":"MDN","company":"وزارة الدفاع"})
        
        print(f"📡 MDN FIXED (appels_ar.php - عرض 2 أوت): {len(tenders)}")
        for t in tenders[:3]:
            print(f"  - {t['title'][:80]}... -> {t['link'][:80]}")
    except Exception as e:
        print(f"MDN error {e}")
        import traceback
        traceback.print_exc()
    return tenders

def find_factories(all_factories, title, wilaya, limit=3):
    tl=title.lower()
    if any(k in tl for k in ["mobilier","meuble","bureau","informatique","فيديو","سمعي","عرض"]): prio="تجهيزات مكتبية"
    elif any(k in tl for k in ["plomberie","sanitaire","chauffage","تدفئة","شبكة المياه"]): prio="ترصيص وتدفئة"
    elif any(k in tl for k in ["electricite","كهرباء","كهربائي","مولد","كابل"]): prio="كهرباء"
    elif any(k in tl for k in ["piece","قطع الغيار","صيانة","بطارية"]): prio="قطع غيار"
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

all_tenders=[]
all_tenders.extend(scrape_aapi())
all_tenders.extend(scrape_safqatic_fixed())
all_tenders.extend(scrape_mdn_fixed())

print(f"📊 المجموع (3 مصادر تعمل - MDN صحيح): {len(all_tenders)}")

unique={}
for t in all_tenders:
    if t["id"] not in unique and t["id"] not in sent:
        dup=False
        for e in unique.values():
            if t["title"][:90]==e["title"][:90]:
                dup=True
                break
        if not dup:
            unique[t["id"]]=t

new_tenders=list(unique.values())
print(f"🔍 جديدة أوت 2026+ (بما فيها عرض 2 أوت): {len(new_tenders)}")

if not new_tenders:
    print("✅ لا يوجد جديدة")
else:
    for t in new_tenders[:15]:
        matched=find_factories(factories, t["title"], t["wilaya"], limit=3)
        factories_text=""
        for i,f in enumerate(matched,1):
            factories_text+=f"{i}. 🏭 <b>{f['name']}</b> 📦 {f['product']} 📞 {f['phone']}\n   📍 <a href=\"{f['map']}\">خريطة</a>\n"
        msg=f"""🔔 <b>مناقصة جديدة - {t['source']} - أوت 2026+</b> 🔔

🏢 <b>{t['company']}</b>
📍 {t['wilaya']} | ANEP: {t['anep']}
📋 {t['title']}

📄 <a href="{t['link']}">فتح الإعلان الأصلي</a>

🏭 <b>أقرب 3 مصانع:</b>
{factories_text}
#Tradium #v82 #MDN #2Aout
"""
        send(msg)
        sent.add(t["id"])
    save_sent(sent)
    print(f"✅ أرسلت {len(new_tenders[:15])}")
                                                      
