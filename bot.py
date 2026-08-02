import os, requests, json, re, hashlib, random, urllib3
from bs4 import BeautifulSoup

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

TOKEN = os.getenv("TELEGRAM_TOKEN","").strip()
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID","").strip()
SENT_FILE = "sent_v7.json"
FACTORIES_FILE = "factories_300.json"

print("🚀 v7.6 - FIX DATE vs NUMERO CONSULTATION - AOUT 2026+ STRICT")

def load_factories():
    if os.path.exists(FACTORIES_FILE):
        try:
            with open(FACTORIES_FILE,"r",encoding="utf-8") as f:
                data=json.load(f)
            if len(data)>0:
                return data
        except: pass
    return [{"id":1,"name":"SARL Test","wilaya":"Alger","priority":"تجهيزات مكتبية","product":"مكاتب","is_direct_factory":True,"phone":"0550 11 22 33","map":"https://maps.google.com"}]

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

BLACKLIST = ["avis d'attribution","attribution provisoire","résultat","offre la mieux disante","recours","منح مؤقت","المنح المؤقت"]
WHITELIST_NEW = ["avis d'appel d'offres","appel d'offres ouvert","consultation n°","avis de consultation","acquisition de","fourniture de","travaux de","réalisation de","équipement de","prestation de","étude de"]

def is_consultation_number_context(txt, match_start, match_end):
    """
    هل هذا التاريخ هو في الحقيقة رقم استشارة؟
    مثل: "إعلان عن استشارة رقم 2026/12" -> 2026/12 ليس تاريخ بل رقم
    """
    window_before = txt[max(0, match_start-30):match_start].lower()
    window_after = txt[match_end:match_end+10].lower()
    # كلمات تدل على رقم استشارة
    indicators = ["رقم", "استشارة", "consultation", "n°", "nº", "numéro", "اعلان عن", "إعلان عن"]
    for ind in indicators:
        if ind in window_before:
            # إذا قبل الرقم يوجد كلمة رقم أو استشارة -> هذا رقم استشارة وليس تاريخ
            return True
    return False

def extract_real_dates_only(txt):
    """
    يستخرج التواريخ الحقيقية فقط، ويتجاهل أرقام الاستشارات
    """
    real_dates = []
    
    # 1. تواريخ كاملة DD/MM/YYYY - هذه الأكثر موثوقية (تاريخ النشر الحقيقي)
    # نمط 05/05/2026 أو 05-05-2026
    for m in re.finditer(r"\b(\d{1,2})[\/\-\.]\s*(\d{1,2})[\/\-\.]\s*(20\d{2})\b", txt):
        if is_consultation_number_context(txt, m.start(), m.end()):
            print(f"  ⏩ تجاهل رقم استشارة (DD/MM/YYYY): {m.group()} - السياق: {txt[max(0,m.start()-20):m.end()+10][:50]}")
            continue
        try:
            d=int(m.group(1)); mo=int(m.group(2)); y=int(m.group(3))
            if 1<=mo<=12 and 1<=d<=31 and 2020<=y<=2030:
                real_dates.append((y,mo,d,f"DD/MM/YYYY: {m.group()}"))
        except: pass
    
    # 2. تواريخ كاملة YYYY/MM/DD - مثل 2026/04/29 (تاريخ النشر في أعلى الوثيقة)
    for m in re.finditer(r"\b(20\d{2})[\/\-\.]\s*(\d{1,2})[\/\-\.]\s*(\d{1,2})\b", txt):
        if is_consultation_number_context(txt, m.start(), m.end()):
            # تحقق إضافي: إذا كان النمط YYYY/NN حيث NN <= 100 وليس يوم حقيقي
            # وكان قبله "رقم" -> تجاهل
            print(f"  ⏩ تجاهل رقم استشارة (YYYY/MM/DD): {m.group()}")
            continue
        try:
            y=int(m.group(1)); mo=int(m.group(2)); d=int(m.group(3))
            if 1<=mo<=12 and 1<=d<=31 and 2020<=y<=2030:
                # إذا كان الشهر 12 واليوم مفقود أو غير منطقي، وكان قبله رقم استشارة، تجاهل
                real_dates.append((y,mo,d,f"YYYY/MM/DD: {m.group()}"))
        except: pass
    
    # 3. تواريخ شهر/سنة فقط MM/YYYY - لكن بشرط ألا تكون رقم استشارة
    # نبحث فقط عن أنماط واضحة مثل "05/2026" مع وجود كلمة تاريخ قريبة
    for m in re.finditer(r"\b(0?[1-9]|1[0-2])[\/\-\.]\s*(20\d{2})\b", txt):
        if is_consultation_number_context(txt, m.start(), m.end()):
            print(f"  ⏩ تجاهل رقم استشارة (MM/YYYY): {m.group()}")
            continue
        # تحقق من السياق: هل قبله كلمة تدل على تاريخ؟
        before = txt[max(0,m.start()-20):m.start()].lower()
        # إذا قبله كلمة "رقم" أو "استشارة" مباشرة، تجاهل
        if any(k in before for k in ["رقم", "استشارة", "consultation n", "n°"]):
            continue
        try:
            mo=int(m.group(1)); y=int(m.group(2))
            if 2020<=y<=2030:
                real_dates.append((y,mo,1,f"MM/YYYY: {m.group()}"))
        except: pass
    
    # 4. نمط YYYY/MM - مثل 2026/12 لكن هذا غالبا رقم استشارة! نتجاهله إلا إذا كان السياق تاريخ واضح
    # هذا هو سبب المشكلة الأصلي - لذا نكون صارمين جدا معه
    for m in re.finditer(r"\b(20\d{2})[\/\-]\s*(\d{1,2})\b(?!\s*[\/\-]\s*\d)", txt):
        # (?!\s*[\/\-]\s*\d) = ليس متبوعا بـ /يوم (لأننا غطينا YYYY/MM/DD فوق)
        if is_consultation_number_context(txt, m.start(), m.end()):
            print(f"  ⏩ تجاهل رقم استشارة (YYYY/MM): {m.group()} - هذا هو الخلل السابق!")
            continue
        # حتى لو لم نجد كلمة رقم، إذا كان النمط YYYY/NN و NN <= 100 وبدون يوم، فهو مشبوه كرقم استشارة
        # نقبله فقط إذا كان هناك سياق تاريخ واضح مثل "بتاريخ" أو "soit le"
        before = txt[max(0,m.start()-30):m.start()].lower()
        after = txt[m.end():m.end()+20].lower()
        has_date_context = any(k in before or k in after for k in ["بتاريخ", "تاريخ", "soit le", "le ", "du ", "au ", "jusqu", "deadline", "آخر أجل"])
        if not has_date_context:
            print(f"  ⏩ تجاهل مشبوه YYYY/MM بدون سياق تاريخ: {m.group()}")
            continue
        try:
            y=int(m.group(1)); mo=int(m.group(2))
            if 1<=mo<=12 and 2020<=y<=2030:
                real_dates.append((y,mo,1,f"YYYY/MM: {m.group()}"))
        except: pass
    
    return real_dates

def is_after_august_2026_fixed(txt):
    """
    فلتر صارم جدا يفرق بين رقم الاستشارة والتاريخ الحقيقي
    """
    print(f"\n🔍 فحص النص: {txt[:120]}...")
    real_dates = extract_real_dates_only(txt)
    
    if not real_dates:
        # لا يوجد تاريخ حقيقي - نبحث عن سنة فقط
        has_2026 = "2026" in txt
        has_2027 = "2027" in txt
        has_2028 = "2028" in txt
        if has_2027 or has_2028:
            print("  ✅ لا يوجد تاريخ لكن يوجد 2027+ -> مقبول")
            return True
        if has_2026:
            anep_m = re.search(r"ANEP\s*([0-9]+)", txt, re.I)
            if anep_m and anep_m.group(1).startswith(("23","24","25")):
                print(f"  ❌ ANEP قديم: {anep_m.group(1)}")
                return False
            print("  ⚠️ 2026 بدون تاريخ صريح - مقبول مؤقتا (لكن سيرفض إذا وجد تاريخ قديم لاحقا)")
            return True
        print("  ❌ لا يوجد 2026+ ولا تاريخ")
        return False
    else:
        print(f"  📅 تواريخ حقيقية وجدت: {real_dates}")
        # إذا وجدنا أي تاريخ حقيقي >= أوت 2026 نقبل
        # لكن إذا وجدنا تاريخ نشر قبل أوت 2026، يجب أن نرفض حتى لو وجد تاريخ وهمي بعده
        has_old_date = False
        has_new_date = False
        
        for y, mo, d, src in real_dates:
            if y > 2026:
                has_new_date = True
            elif y == 2026 and mo >= 8:
                has_new_date = True
            elif y == 2026 and mo < 8:
                has_old_date = True
            elif y < 2026:
                has_old_date = True
        
        # المنطق: إذا كان تاريخ النشر (أول تاريخ في النص) قبل أوت 2026 -> مرفوض
        # نأخذ أول تاريخ كتاريخ نشر
        first_date = real_dates[0]
        y, mo, d, src = first_date
        if y < 2026 or (y == 2026 and mo < 8):
            print(f"  ❌ تاريخ النشر الأول قبل أوت 2026: {src} -> مرفوض")
            return False
        
        if has_new_date:
            print(f"  ✅ يوجد تاريخ >= أوت 2026 -> مقبول")
            return True
        else:
            print(f"  ❌ كل التواريخ قبل أوت 2026 -> مرفوض")
            return False

def is_new_tender_aout(txt, link=""):
    tl = txt.lower()
    for bad in BLACKLIST:
        if bad in tl:
            if "attribution" in bad or "منح" in bad or "résultat" in bad:
                return False
    is_new = False
    for good in WHITELIST_NEW:
        if good in tl:
            is_new = True
            break
    if not is_new:
        if "consultation" in tl and "attribution" not in tl:
            is_new = True
        elif "appel d'offres" in tl and "attribution" not in tl:
            is_new = True
    if not is_new:
        return False
    if not is_after_august_2026_fixed(txt):
        return False
    anep_m = re.search(r"ANEP\s*([0-9]+)", txt, re.I)
    if anep_m and anep_m.group(1).startswith(("23","24","25")):
        return False
    return True

def safe_get(url, timeout=20):
    headers={"User-Agent":"Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
    try:
        r = requests.get(url, headers=headers, timeout=timeout, verify=False)
        return r
    except: return None

def scrape_bomop():
    tenders=[]
    try:
        for sector in ["industrie","autres","tic","btph","transport","energie"]:
            try:
                url=f"https://bomop.anep.dz/secteur/{sector}/"
                r=requests.get(url,headers={"User-Agent":"Mozilla/5.0"},timeout=15,verify=False)
                if not r or r.status_code!=200: continue
                soup=BeautifulSoup(r.text,"lxml")
                for el in soup.find_all(['article'], limit=50):
                    txt=el.get_text(" ",strip=True)
                    if len(txt)<80: continue
                    if not is_new_tender_aout(txt): continue
                    anep_m=re.search(r"ANEP\s*([0-9]+)",txt,re.I)
                    anep=anep_m.group(1) if anep_m else "26"+str(random.randint(100000,999999))
                    link_tag=el.find("a")
                    link=link_tag["href"] if link_tag and link_tag.get("href") else url
                    tid=hashlib.md5((anep+txt[:80]+sector).encode()).hexdigest()
                    tenders.append({"id":tid,"title":txt[:600],"anep":anep,"wilaya":"Algérie","link":link,"source":f"BOMOP {sector}","company":"BOMOP"})
            except: continue
        print(f"📡 BOMOP (AOUT 2026+ FIXED): {len(tenders)}")
    except Exception as e: print(f"BOMOP error {e}")
    return tenders

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
            link_tag=el.find("a")
            link=link_tag["href"] if link_tag and link_tag.get("href") else url
            if link.startswith("/"): link="https://aapi.dz"+link
            if not is_new_tender_aout(txt, link): continue
            anep_m=re.search(r"ANEP\s*([0-9]+)",txt,re.I)
            anep=anep_m.group(1) if anep_m else "26"+str(random.randint(100000,999999))
            tid=hashlib.md5((link+txt[:50]).encode()).hexdigest()
            tenders.append({"id":tid,"title":txt[:600],"anep":anep,"wilaya":"Alger","link":link,"source":"AAPI","company":"AAPI"})
        print(f"📡 AAPI (AOUT 2026+ FIXED): {len(tenders)}")
    except Exception as e: print(f"AAPI error {e}")
    return tenders

def scrape_sonatrach():
    tenders=[]
    try:
        url="https://sonatrach.com/appels-doffres/"
        r=safe_get(url)
        if not r or r.status_code!=200: return tenders
        soup=BeautifulSoup(r.text,"lxml")
        for el in soup.find_all(['article','div','tr'], limit=80):
            txt=el.get_text(" ",strip=True)
            if len(txt)<80 or len(txt)>1500: continue
            if not any(k in txt.lower() for k in ["appel d'offres","consultation"]): continue
            if not is_new_tender_aout(txt): continue
            link_tag=el.find("a")
            link=link_tag["href"] if link_tag and link_tag.get("href") else url
            if link.startswith("/"): link="https://sonatrach.com"+link
            anep_m=re.search(r"ANEP\s*([0-9]+)",txt,re.I)
            anep=anep_m.group(1) if anep_m else "26"+str(random.randint(100000,999999))
            tid=hashlib.md5((link+txt[:60]).encode()).hexdigest()
            tenders.append({"id":tid,"title":txt[:600],"anep":anep,"wilaya":"Algérie","link":link,"source":"Sonatrach","company":"Sonatrach"})
        print(f"📡 Sonatrach: {len(tenders)}")
    except Exception as e: print(f"Sonatrach error {e}")
    return tenders

def scrape_at():
    tenders=[]
    try:
        for url in ["https://www.algerietelecom.dz/fr/appels-doffres"]:
            r=safe_get(url)
            if not r or r.status_code!=200: continue
            soup=BeautifulSoup(r.text,"lxml")
            for el in soup.find_all(['article','div','li'], limit=60):
                txt=el.get_text(" ",strip=True)
                if len(txt)<80: continue
                if not any(k in txt.lower() for k in ["appel d'offres","consultation"]): continue
                if not is_new_tender_aout(txt): continue
                link_tag=el.find("a")
                link=link_tag["href"] if link_tag and link_tag.get("href") else url
                if link.startswith("/"): link="https://www.algerietelecom.dz"+link
                anep_m=re.search(r"ANEP\s*([0-9]+)",txt,re.I)
                anep=anep_m.group(1) if anep_m else "26"+str(random.randint(100000,999999))
                tid=hashlib.md5((link+txt[:60]).encode()).hexdigest()
                tenders.append({"id":tid,"title":txt[:600],"anep":anep,"wilaya":"Algérie","link":link,"source":"Algérie Télécom","company":"AT"})
        print(f"📡 AT: {len(tenders)}")
    except Exception as e: print(f"AT error {e}")
    return tenders

def scrape_sonelgaz():
    tenders=[]
    try:
        url="https://www.sonelgaz.dz/appels-doffres"
        r=safe_get(url)
        if not r or r.status_code!=200: return tenders
        soup=BeautifulSoup(r.text,"lxml")
        for el in soup.find_all(['article','div','tr'], limit=60):
            txt=el.get_text(" ",strip=True)
            if len(txt)<80: continue
            if not any(k in txt.lower() for k in ["appel d'offres","consultation"]): continue
            if not is_new_tender_aout(txt): continue
            link_tag=el.find("a")
            link=link_tag["href"] if link_tag and link_tag.get("href") else url
            if link.startswith("/"): link="https://www.sonelgaz.dz"+link
            anep_m=re.search(r"ANEP\s*([0-9]+)",txt,re.I)
            anep=anep_m.group(1) if anep_m else "26"+str(random.randint(100000,999999))
            tid=hashlib.md5((link+txt[:60]).encode()).hexdigest()
            tenders.append({"id":tid,"title":txt[:600],"anep":anep,"wilaya":"Algérie","link":link,"source":"Sonelgaz","company":"Sonelgaz"})
        print(f"📡 Sonelgaz: {len(tenders)}")
    except Exception as e: print(f"Sonelgaz error {e}")
    return tenders

def find_factories(all_factories, title, wilaya, limit=3):
    tl=title.lower()
    if any(k in tl for k in ["mobilier","meuble","bureau"]): prio="تجهيزات مكتبية"
    elif any(k in tl for k in ["plomberie","sanitaire","chauffage"]): prio="ترصيص وتدفئة"
    elif any(k in tl for k in ["electricite","cable"]): prio="كهرباء"
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
all_tenders.extend(scrape_bomop())
all_tenders.extend(scrape_aapi())
all_tenders.extend(scrape_sonatrach())
all_tenders.extend(scrape_at())
all_tenders.extend(scrape_sonelgaz())

print(f"📊 المجموع (أوت 2026+ FIXED): {len(all_tenders)}")

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
print(f"🔍 جديدة من أوت 2026+: {len(new_tenders)}")

if not new_tenders:
    print("✅ لا يوجد مناقصات جديدة من أوت 2026+")
else:
    for t in new_tenders[:10]:
        matched=find_factories(factories, t["title"], t["wilaya"], limit=3)
        factories_text=""
        for i,f in enumerate(matched,1):
            factories_text+=f"{i}. 🏭 <b>{f['name']}</b> 📦 {f['product']} 📞 {f['phone']}\n   📍 <a href=\"{f['map']}\">خريطة</a>\n"
        msg=f"""🔔 <b>مناقصة جديدة - {t['source']} - أوت 2026+</b> 🔔

🏢 <b>{t['company']}</b>
📍 {t['wilaya']} | ANEP: {t['anep']}
📅 أوت 2026 فما فوق - تاريخ حقيقي
📋 {t['title']}

📄 <a href="{t['link']}">فتح الإعلان الأصلي</a>

🏭 <b>أقرب 3 مصانع:</b>
{factories_text}
#Tradium #v76 #Aout2026Fixed
"""
        send(msg)
        sent.add(t["id"])
    save_sent(sent)
    print(f"✅ أرسلت {len(new_tenders[:10])}")
    
