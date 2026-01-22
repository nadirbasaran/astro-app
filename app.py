import streamlit as st
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import ephem
import math
from datetime import datetime, timedelta
import requests
import json
import pytz
import numpy as np
from fpdf import FPDF

# =========================================================
# PAGE / CSS
# =========================================================
st.set_page_config(page_title="Astro-Analiz Pro", layout="wide", page_icon="🔮")

st.markdown("""
<style>
.stApp { background: linear-gradient(to bottom, #0e1117, #24283b); color: #e0e0e0; }
h1, h2, h3 { color: #FFD700 !important; font-family: 'Helvetica', sans-serif; text-shadow: 2px 2px 4px #000000; }
.stButton>button { background-color: #FFD700; color: #000; border-radius: 18px; border: none; font-weight: bold; width: 100%; }
[data-testid="stSidebar"] { background-color: #161a25; border-right: 1px solid #FFD700; }
.metric-box { background-color: #1e2130; padding: 10px; border-radius: 8px; border-left: 4px solid #FFD700; margin-bottom: 8px; font-size: 14px; color: white; }
.metric-box b { color: #FFD700; }
.aspect-box { background-color: #25293c; padding: 5px 10px; margin: 2px; border-radius: 4px; font-size: 13px; border: 1px solid #444; }
.transit-box { background-color: #2d1b2e; border-left: 4px solid #ff4b4b; padding: 8px; margin-bottom: 6px; font-size: 13px; }
.badge { display:inline-block; padding:2px 8px; border-radius:999px; background:#0f172a; border:1px solid #334155; color:#e2e8f0; font-size:12px;}
.small-note { color: #9aa0aa; font-size: 12px; }
hr { border: 0; border-top: 1px solid #333; }
</style>
""", unsafe_allow_html=True)

# =========================================================
# API KEY (Gemini Developer API / AI Studio)
# =========================================================
if "GOOGLE_API_KEY" not in st.secrets:
    st.error("🚨 st.secrets['GOOGLE_API_KEY'] bulunamadı!")
    st.stop()
API_KEY = st.secrets["GOOGLE_API_KEY"]
GEN_API_BASE = "https://generativelanguage.googleapis.com/v1beta"

# =========================================================
# CONSTANTS
# =========================================================
ZODIAC = ["Koç","Boğa","İkizler","Yengeç","Aslan","Başak","Terazi","Akrep","Yay","Oğlak","Kova","Balık"]
ZODIAC_SYMBOLS = ["♈","♉","♊","♋","♌","♍","♎","♏","♐","♑","♒","♓"]

PLANET_SYMBOLS = {
    "Güneş":"☉","Ay":"☽","Merkür":"☿","Venüs":"♀","Mars":"♂",
    "Jüpiter":"♃","Satürn":"♄","Uranüs":"♅","Neptün":"♆","Plüton":"♇",
    "ASC":"ASC","MC":"MC"
}

PLANETS = {
    "Güneş": ephem.Sun(),
    "Ay": ephem.Moon(),
    "Merkür": ephem.Mercury(),
    "Venüs": ephem.Venus(),
    "Mars": ephem.Mars(),
    "Jüpiter": ephem.Jupiter(),
    "Satürn": ephem.Saturn(),
    "Uranüs": ephem.Uranus(),
    "Neptün": ephem.Neptune(),
    "Plüton": ephem.Pluto()
}

HEAVY_TRANSITS = [
    ("Jüpiter", ephem.Jupiter()),
    ("Satürn", ephem.Saturn()),
    ("Uranüs", ephem.Uranus()),
    ("Neptün", ephem.Neptune()),
    ("Plüton", ephem.Pluto()),
]

ELEMENT = {
    "Koç":"Ateş","Aslan":"Ateş","Yay":"Ateş",
    "Boğa":"Toprak","Başak":"Toprak","Oğlak":"Toprak",
    "İkizler":"Hava","Terazi":"Hava","Kova":"Hava",
    "Yengeç":"Su","Akrep":"Su","Balık":"Su"
}
QUALITY = {
    "Koç":"Öncü","Yengeç":"Öncü","Terazi":"Öncü","Oğlak":"Öncü",
    "Boğa":"Sabit","Aslan":"Sabit","Akrep":"Sabit","Kova":"Sabit",
    "İkizler":"Değişken","Başak":"Değişken","Yay":"Değişken","Balık":"Değişken"
}

HOUSE_TOPICS = {
    1:"Kimlik / Dışa yansıma", 2:"Para / Özdeğer", 3:"İletişim / Yakın çevre",
    4:"Ev / Aile / Kökler", 5:"Aşk / Yaratıcılık / Çocuklar", 6:"İş / Sağlık / Düzen",
    7:"İlişkiler / Evlilik / Ortaklık", 8:"Kriz / Ortak para / Dönüşüm",
    9:"Yurt dışı / İnanç / Eğitim", 10:"Kariyer / Statü",
    11:"Sosyal çevre / Hedefler", 12:"Bilinçaltı / Geri planda olanlar"
}

PLANET_MEANING = {
    "Güneş":"kimlik, yaşam yönü", "Ay":"duygusal ihtiyaçlar, iç güvenlik", "Merkür":"zihin ve iletişim",
    "Venüs":"ilişkiler, değerler, estetik", "Mars":"motivasyon, mücadele, enerji",
    "Jüpiter":"büyüme, fırsat, inanç", "Satürn":"sorumluluk, sınav, yapı",
    "Uranüs":"ani değişim, özgürleşme", "Neptün":"sezgi, ideal, belirsizlik", "Plüton":"dönüşüm, güç, arınma"
}

ASPECT_ANGLES = {"Kavuşum":0,"Sekstil":60,"Kare":90,"Üçgen":120,"Karşıt":180}
ASPECT_ORBS   = {"Kavuşum":8,"Sekstil":6,"Kare":8,"Üçgen":8,"Karşıt":8}
ASPECT_MEANING = {
    "Kavuşum":"konuyu büyütür ve görünür kılar.",
    "Sekstil":"fırsat kapısı açar; doğru kullanılırsa destek verir.",
    "Kare":"gerilim üretir; doğru yönetilirse sıçrama yaratır.",
    "Üçgen":"doğal destek verir; yetenekleri açar.",
    "Karşıt":"denge ihtiyacını gösterir; ilişki/karşılık üzerinden çalışır."
}

# =========================================================
# HELPERS
# =========================================================
def normalize(deg): return deg % 360

def angle_diff(a,b):
    d = abs(a-b)
    return min(d, 360-d)

def dec_to_dms(deg):
    d = int(deg)
    m = int(round((deg - d) * 60))
    if m == 60:
        d += 1
        m = 0
    return f"{d:02d}° {m:02d}'"

def sign_name(deg): return ZODIAC[int(deg/30) % 12]
def sign_symbol(deg): return ZODIAC_SYMBOLS[int(deg/30) % 12]
def get_element(sign): return ELEMENT.get(sign, "Bilinmiyor")
def get_quality(sign): return QUALITY.get(sign, "Bilinmiyor")

def clean_text_for_pdf(text: str) -> str:
    replacements = {
        'ğ':'g','Ğ':'G','ş':'s','Ş':'S','ı':'i','İ':'I','ü':'u','Ü':'U','ö':'o','Ö':'O','ç':'c','Ç':'C',
        '–':'-','’':"'",'“':'"','”':'"','…':'...',
        '♈':'Koc','♉':'Boga','♊':'Ikizler','♋':'Yengec','♌':'Aslan','♍':'Basak',
        '♎':'Terazi','♏':'Akrep','♐':'Yay','♑':'Oglak','♒':'Kova','♓':'Balik',
        '☉':'','☽':'','☿':'','♀':'','♂':'','♃':'','♄':'','♅':'','♆':'','♇':''
    }
    for k,v in replacements.items():
        text = text.replace(k,v)
    return text.encode('latin-1','ignore').decode('latin-1')

def city_to_latlon(city: str):
    try:
        r = requests.get(
            "https://nominatim.openstreetmap.org/search",
            params={"q": city, "format":"json", "limit": 1},
            headers={"User-Agent":"astro-analiz-pro"},
            timeout=15
        )
        js = r.json()
        if js:
            return float(js[0]["lat"]), float(js[0]["lon"])
    except Exception:
        pass
    return None, None

# =========================================================
# GEMINI (Model list + auto select 2.5)
# =========================================================
@st.cache_data(ttl=600)
def list_gemini_models():
    url = f"{GEN_API_BASE}/models?key={API_KEY}"
    r = requests.get(url, timeout=20)
    if r.status_code != 200:
        return [], f"Models list HTTP {r.status_code}: {r.text[:300]}"
    data = r.json()
    models = []
    for m in data.get("models", []):
        name = m.get("name", "")  # e.g. "models/gemini-2.5-flash"
        methods = m.get("supportedGenerationMethods", [])
        if "generateContent" in methods and name:
            models.append(name)
    models = sorted(set(models))
    if not models:
        return [], "generateContent destekleyen model bulunamadı."
    return models, None

def pick_default_model(models):
    preferred = [
        "models/gemini-2.5-pro",
        "models/gemini-2.5-flash",
        "models/gemini-2.5-flash-lite",
        "models/gemini-2.0-pro",
        "models/gemini-2.0-flash",
    ]
    for p in preferred:
        if p in models:
            return p
    return models[0] if models else None

def gemini_generate(prompt: str, model_fullname: str) -> str:
    url = f"{GEN_API_BASE}/{model_fullname}:generateContent?key={API_KEY}"
    payload = {"contents": [{"parts": [{"text": prompt}]}]}
    resp = requests.post(
        url,
        headers={"Content-Type":"application/json"},
        data=json.dumps(payload),
        timeout=80
    )
    if resp.status_code != 200:
        return f"AI Servis Hatası: HTTP {resp.status_code}\n{resp.text[:600]}"
    js = resp.json()
    if js.get("candidates"):
        return js["candidates"][0]["content"]["parts"][0]["text"]
    return "AI yanıtı boş döndü."

# =========================================================
# PLACIDUS
# =========================================================
def calculate_placidus_cusps(utc_dt, lat, lon):
    obs = ephem.Observer()
    obs.date = utc_dt
    obs.lat, obs.lon = str(lat), str(lon)

    ramc = float(obs.sidereal_time())
    eps = math.radians(23.44)
    lat_rad = math.radians(lat)

    mc_rad = math.atan2(math.tan(ramc), math.cos(eps))
    mc_deg = normalize(math.degrees(mc_rad))
    if not (0 <= abs(mc_deg - math.degrees(ramc)) <= 90 or 0 <= abs(mc_deg - math.degrees(ramc) - 360) <= 90):
        mc_deg = normalize(mc_deg + 180)

    ic_deg = normalize(mc_deg + 180)

    asc_rad = math.atan2(
        math.cos(ramc),
        -(math.sin(ramc)*math.cos(eps) + math.tan(lat_rad)*math.sin(eps))
    )
    asc_deg = normalize(math.degrees(asc_rad))
    dsc_deg = normalize(asc_deg + 180)

    cusps = {1: asc_deg, 4: ic_deg, 7: dsc_deg, 10: mc_deg}
    diff1 = (asc_deg - mc_deg) % 360
    cusps[11] = (mc_deg + diff1/3) % 360
    cusps[12] = (mc_deg + 2*diff1/3) % 360
    diff2 = (ic_deg - asc_deg) % 360
    cusps[2] = (asc_deg + diff2/3) % 360
    cusps[3] = (asc_deg + 2*diff2/3) % 360
    cusps[5] = (cusps[11] + 180) % 360
    cusps[6] = (cusps[12] + 180) % 360
    cusps[8] = (cusps[2] + 180) % 360
    cusps[9] = (cusps[3] + 180) % 360
    return cusps

def get_house_of_deg(deg, cusps):
    deg = normalize(deg)
    for i in range(1, 13):
        start = cusps[i]
        end = cusps[i+1] if i < 12 else cusps[1]
        if start < end:
            if start <= deg < end:
                return i
        else:
            if start <= deg or deg < end:
                return i
    return 1

# =========================================================
# NATAL POSITIONS + ASPECTS
# =========================================================
def compute_longitudes(utc_dt_str, lat, lon, planet_dict):
    obs = ephem.Observer()
    obs.date = utc_dt_str
    obs.lat, obs.lon = str(lat), str(lon)
    res = []
    for name, body in planet_dict.items():
        body.compute(obs)
        deg = normalize(math.degrees(ephem.Ecliptic(body).lon))
        res.append((name, deg))
    return res

def calculate_aspects(visual_data):
    aspects_str = []
    aspects_raw = []
    planet_list = [(n, d) for n, _, d, _ in visual_data if n not in ("ASC","MC")]
    for i in range(len(planet_list)):
        for j in range(i+1, len(planet_list)):
            p1, d1 = planet_list[i]
            p2, d2 = planet_list[j]
            dd = angle_diff(d1, d2)
            for asp, ang in ASPECT_ANGLES.items():
                orb = ASPECT_ORBS.get(asp, 8)
                if abs(dd - ang) <= orb:
                    aspects_str.append(f"{p1} {asp} {p2} ({round(dd,1)}°)")
                    aspects_raw.append((p1, asp, p2, dd))
                    break
    return aspects_str, aspects_raw

# =========================================================
# TRANSITS: movement + house-based + natal contacts ranked
# =========================================================
def calc_transit_package(natal_visual, natal_cusps, start_dt_str, mid_dt_str, end_dt_str, lat, lon):
    obs = ephem.Observer()
    obs.lat, obs.lon = str(lat), str(lon)

    natal_map = {}
    for n, sign, nd, sym in natal_visual:
        if n in ("ASC","MC"):
            continue
        natal_map[n] = {
            "deg": nd,
            "house": get_house_of_deg(nd, natal_cusps),
            "sign": sign_name(nd)
        }

    movement_lines = []
    house_lines = []
    hits_ranked = []

    def transit_deg_at(date_str, body):
        obs.date = date_str
        body.compute(obs)
        return normalize(math.degrees(ephem.Ecliptic(body).lon))

    for tname, tbody in HEAVY_TRANSITS:
        d1 = transit_deg_at(start_dt_str, tbody)
        d2 = transit_deg_at(mid_dt_str, tbody)
        d3 = transit_deg_at(end_dt_str, tbody)

        s1, s3 = sign_name(d1), sign_name(d3)
        h1, h3 = get_house_of_deg(d1, natal_cusps), get_house_of_deg(d3, natal_cusps)

        movement_lines.append(f"Transit {tname}: {s1} {dec_to_dms(d1%30)} → {s3} {dec_to_dms(d3%30)}")
        if h1 == h3:
            house_lines.append(f"{tname} ağırlıkla {h1}. ev ({HOUSE_TOPICS.get(h1)}) temalarında çalışır.")
        else:
            house_lines.append(f"{tname} {h1}. ev → {h3}. ev geçişi: {HOUSE_TOPICS.get(h1)} temalarından {HOUSE_TOPICS.get(h3)} temalarına kayış.")

        # natal contacts (check start/mid/end)
        checks = [(d1, "başlangıç"), (d2, "orta"), (d3, "bitiş")]
        for natal_p, info in natal_map.items():
            nd = info["deg"]
            nh = info["house"]
            topic = HOUSE_TOPICS.get(nh, "Genel Temalar")

            for dcheck, when in checks:
                delta = angle_diff(dcheck, nd)
                for asp, ang in ASPECT_ANGLES.items():
                    # transit orb tighter
                    orb = 3 if asp in ("Kavuşum","Kare","Karşıt") else 2
                    if abs(delta - ang) <= orb:
                        # score
                        score = 0
                        if tname in ("Satürn","Plüton"): score += 5
                        elif tname in ("Uranüs","Neptün"): score += 4
                        elif tname == "Jüpiter": score += 3

                        if asp in ("Kavuşum","Karşıt"): score += 3
                        elif asp == "Kare": score += 2
                        else: score += 1

                        txt = f"⚠️ {when}: Transit {tname} {asp} natal {natal_p} → {topic} (güç:{score})"
                        hits_ranked.append((score, txt))

    # uniq + sort
    uniq = {}
    for s,t in hits_ranked:
        if (t not in uniq) or (s > uniq[t]):
            uniq[t] = s
    hits_sorted = sorted([(s,t) for t,s in uniq.items()], reverse=True)

    hits_text = "\n".join([f"- {t}" for s,t in hits_sorted[:25]]) if hits_sorted else "Belirgin güçlü transit temas bulunamadı."

    html = "<br><h4>⏳ Transit Hareketleri</h4>"
    for line in movement_lines:
        html += f"<div class='transit-box'>{line}</div>"

    html += "<h4>🪐 Ev Bazlı Transit Temaları</h4>"
    for line in house_lines:
        html += f"<div class='transit-box'>{line}</div>"

    if hits_sorted:
        html += "<h4>⚡ Transit–Natal Temaslar (Öncelikli)</h4>"
        for s,t in hits_sorted[:15]:
            html += f"<div class='transit-box'>{t}</div>"

    return movement_lines, house_lines, hits_text, html

# =========================================================
# ELEMENT / QUALITY
# =========================================================
def element_quality_counts(visual_data):
    elem = {"Ateş":0,"Toprak":0,"Hava":0,"Su":0}
    qual = {"Öncü":0,"Sabit":0,"Değişken":0}
    for n, sign, deg, sym in visual_data:
        if n in ("ASC","MC"):
            continue
        e = get_element(sign)
        q = get_quality(sign)
        if e in elem: elem[e] += 1
        if q in qual: qual[q] += 1
    return elem, qual

# =========================================================
# VISUAL CHART
# =========================================================
def draw_chart_visual(bodies_data, cusps):
    fig = plt.figure(figsize=(10, 10), facecolor='#0e1117')
    ax = fig.add_subplot(111, projection='polar')
    ax.set_facecolor('#1a1c24')

    asc_deg = cusps[1]
    ax.set_theta_offset(np.pi - math.radians(asc_deg))
    ax.set_theta_direction(1)
    ax.set_yticklabels([]); ax.set_xticklabels([])
    ax.grid(False); ax.spines['polar'].set_visible(False)

    # Houses
    for i in range(1, 13):
        angle = math.radians(cusps[i])
        ax.plot([angle, angle], [0, 1.2], color='#444', linewidth=1, linestyle='--')
        nxt = cusps[i+1] if i < 12 else cusps[1]
        d = (nxt - cusps[i]) % 360
        mid = math.radians(cusps[i] + d/2)
        ax.text(mid, 0.42, str(i), color='#888', ha='center', fontsize=11, fontweight='bold')

    # Zodiac ring
    circles = np.linspace(0, 2*np.pi, 120)
    ax.plot(circles, [1.2]*120, color='#FFD700', linewidth=2)

    for i in range(12):
        deg = i * 30 + 15
        rad = math.radians(deg)
        ax.text(rad, 1.3, ZODIAC_SYMBOLS[i], ha='center', color='#FFD700', fontsize=16, rotation=deg-180)
        sep = math.radians(i*30)
        ax.plot([sep, sep], [1.15, 1.25], color='#FFD700')

    # Planets
    for name, sign, deg, sym in bodies_data:
        rad = math.radians(deg)
        color = '#FF4B4B' if name in ('ASC','MC') else 'white'
        size = 14 if name in ('ASC','MC') else 11
        ax.plot(rad, 1.05, 'o', color=color, markersize=size, markeredgecolor='#FFD700')
        ax.text(rad, 1.17, sym, color=color, fontsize=12, ha='center')

    return fig

# =========================================================
# RULE-BASED COMMENTARY (AI yoksa da çalışır)
# =========================================================
def rule_based_report(name, q, city, placements, aspects_raw, elem_counts, qual_counts, transit_hits_text=None, transit_house_lines=None):
    # placements: list of dict {planet, sign, deg, house}
    # aspects_raw: list tuples (p1, asp, p2, angle)
    # Build focused, readable narrative
    # Find key anchors: ASC, Sun, Moon, MC
    asc = next((p for p in placements if p["planet"]=="ASC"), None)
    mc  = next((p for p in placements if p["planet"]=="MC"), None)
    sun = next((p for p in placements if p["planet"]=="Güneş"), None)
    moon= next((p for p in placements if p["planet"]=="Ay"), None)

    # dominant element/quality
    dom_elem = max(elem_counts.items(), key=lambda x: x[1])[0]
    dom_qual = max(qual_counts.items(), key=lambda x: x[1])[0]

    lines = []
    lines.append(f"## Genel Özet")
    if asc:
        lines.append(f"- **Yükselen {asc['sign']}**: dışa yansıyan tarz, yaklaşım ve ilk izlenim bu burcun doğasıyla çalışır.")
    if sun:
        lines.append(f"- **Güneş {sun['sign']} ({sun['house']}. ev)**: kimlik ve hedefler ağırlıkla **{HOUSE_TOPICS.get(sun['house'])}** alanında görünür olur.")
    if moon:
        lines.append(f"- **Ay {moon['sign']} ({moon['house']}. ev)**: duygusal güvenlik ve ihtiyaçlar **{HOUSE_TOPICS.get(moon['house'])}** başlığında tetiklenir.")
    if mc:
        lines.append(f"- **MC {mc['sign']}**: kariyer/statü yönü bu burcun stilini taşır.")

    lines.append("")
    lines.append("## Element & Nitelik")
    lines.append(f"- Baskın element: **{dom_elem}** (genel motivasyon ve enerji akışı burada yoğunlaşır).")
    lines.append(f"- Baskın nitelik: **{dom_qual}** (olayları başlatma/sürdürme/değiştirme biçimi).")

    # aspects highlight: pick hard aspects involving Sun/Moon/ASC ruler not available; we keep Sun/Moon aspects
    hard = [a for a in aspects_raw if a[1] in ("Kare","Karşıt")]
    soft = [a for a in aspects_raw if a[1] in ("Üçgen","Sekstil")]
    conj = [a for a in aspects_raw if a[1] == "Kavuşum"]

    def fmt_aspect(a):
        p1, asp, p2, ang = a
        return f"- **{p1} {asp} {p2}** ({round(ang,1)}°): {ASPECT_MEANING.get(asp,'')}"

    lines.append("")
    lines.append("## Öne Çıkan Açılar")
    if conj[:3]:
        lines.append("**Kavuşumlar:**")
        for a in conj[:3]:
            lines.append(fmt_aspect(a))
    if hard[:4]:
        lines.append("\n**Zorlayıcı açılar (gelişim):**")
        for a in hard[:4]:
            lines.append(fmt_aspect(a))
    if soft[:4]:
        lines.append("\n**Destekleyici açılar (kolaylık):**")
        for a in soft[:4]:
            lines.append(fmt_aspect(a))

    lines.append("")
    lines.append("## Soru Odaklı Yorum (kural tabanlı çerçeve)")
    lines.append(f"- Soru: **{q}**")
    lines.append("- Bu soruyu yanıtlarken ilgili temayı temsil eden eve ve o evin yöneticisi/yerleşimlerine bakılır. (Uygulama içinde teknik veriler mevcut.)")
    lines.append("- En etkili yaklaşım: **soru teması → ilgili ev → o evdeki gezegenler / açıları → transit temasları** sıralamasıdır.")

    if transit_house_lines or transit_hits_text:
        lines.append("")
        lines.append("## Transit Özeti (kural tabanlı)")
        if transit_house_lines:
            for t in transit_house_lines[:6]:
                lines.append(f"- {t}")
        if transit_hits_text and "Bulunamadı" not in transit_hits_text:
            lines.append("\n**Öncelikli temaslar:**")
            for ln in transit_hits_text.splitlines()[:10]:
                lines.append(ln)

    lines.append("")
    lines.append("## Özet & Tavsiye")
    lines.append("- Güçlü transit teması çıkan başlıkları (özellikle Satürn/Plüton) ‘sınav–yapılandırma’ olarak ele al; hızlı sonuç yerine sağlam adım planla.")
    lines.append("- Destekleyici açılar (sekstil/üçgen) fırsat penceresi verir; somut adım atılmadığında pasif kalabilir.")
    lines.append("- Kişisel denge için baskın elementin gölgesine düşmemek (aşırılık) kritik olur.")

    return "\n".join(lines)

# =========================================================
# PDF (Professional layout with sections)
# =========================================================
def create_pdf_report(title, meta_lines, body_text, tech_lines):
    try:
        pdf = FPDF()
        pdf.add_page()
        pdf.set_auto_page_break(auto=True, margin=14)

        pdf.set_font("Arial", "B", 16)
        pdf.cell(0, 10, clean_text_for_pdf(title), ln=True, align="C")

        pdf.ln(2)
        pdf.set_font("Arial", "", 11)
        for m in meta_lines:
            pdf.multi_cell(0, 6, clean_text_for_pdf(m))

        pdf.ln(2)
        pdf.set_font("Arial", "B", 12)
        pdf.cell(0, 8, "TEKNIK OZET", ln=True)
        pdf.set_font("Arial", "", 10)
        for t in tech_lines:
            pdf.multi_cell(0, 5, clean_text_for_pdf(t))

        pdf.ln(2)
        pdf.set_font("Arial", "B", 12)
        pdf.cell(0, 8, "YORUM & ONGORU", ln=True)
        pdf.set_font("Arial", "", 11)
        pdf.multi_cell(0, 6.5, clean_text_for_pdf(body_text))

        return pdf.output(dest="S").encode("latin-1", "ignore")
    except Exception:
        return None

# =========================================================
# MAIN CALC PIPELINE
# =========================================================
def calculate_all(name, city, d_date, d_time, lat, lon, tz_mode, utc_offset, transit_enabled, start_date, end_date):
    local_dt = datetime.combine(d_date, d_time)

    if tz_mode == "manual_gmt":
        utc_dt = local_dt - timedelta(hours=int(utc_offset))
        tz_label = f"Manuel GMT{int(utc_offset):+d}"
    else:
        tz = pytz.timezone("Europe/Istanbul")
        utc_dt = tz.localize(local_dt).astimezone(pytz.utc).replace(tzinfo=None)
        tz_label = "Europe/Istanbul"

    cusps = calculate_placidus_cusps(utc_dt, lat, lon)

    asc_sign = sign_name(cusps[1])
    mc_sign  = sign_name(cusps[10])

    info_html = f"<div class='metric-box'>🌍 <b>Doğum (UTC):</b> {utc_dt.strftime('%Y-%m-%d %H:%M')} <span class='small-note'>({tz_label})</span></div>"
    info_html += f"<div class='metric-box'>🚀 <b>Yükselen:</b> {asc_sign} {dec_to_dms(cusps[1]%30)} | <b>MC:</b> {mc_sign} {dec_to_dms(cusps[10]%30)}</div>"

    # Ephem wants string
    utc_dt_str = utc_dt.strftime("%Y/%m/%d %H:%M:%S")

    # Natal planets
    longs = compute_longitudes(utc_dt_str, lat, lon, PLANETS)

    # Visual data + placements structured
    visual_data = [("ASC", asc_sign, cusps[1], "ASC"), ("MC", mc_sign, cusps[10], "MC")]
    placements = [
        {"planet":"ASC","sign":asc_sign,"deg":cusps[1],"house":1},
        {"planet":"MC","sign":mc_sign,"deg":cusps[10],"house":10},
    ]

    ai_data = "SİSTEM: PLACIDUS\n"
    ai_data += f"Şehir: {city}\n"
    ai_data += f"Doğum UTC: {utc_dt.strftime('%Y-%m-%d %H:%M')} ({tz_label})\n"
    ai_data += f"ASC: {asc_sign} {dec_to_dms(cusps[1]%30)}\n"
    ai_data += f"MC: {mc_sign} {dec_to_dms(cusps[10]%30)}\n\n"

    for pname, deg in longs:
        sign = sign_name(deg)
        idx = int(deg/30) % 12
        house = get_house_of_deg(deg, cusps)
        visual_data.append((pname, sign, deg, PLANET_SYMBOLS.get(pname,"")))
        placements.append({"planet":pname,"sign":sign,"deg":deg,"house":house})

        info_html += f"<div class='metric-box'><b>{pname}</b>: {ZODIAC_SYMBOLS[idx]} {ZODIAC[idx]} {dec_to_dms(deg%30)} | <b>{house}. Ev</b></div>"
        ai_data += f"{pname}: {sign} {dec_to_dms(deg%30)} ({house}. Ev) | Tema: {HOUSE_TOPICS.get(house)} | Anlam: {PLANET_MEANING.get(pname,'')}\n"

    # Aspects
    aspect_strings, aspect_raw = calculate_aspects(visual_data)
    ai_data += "\nNATAL AÇILAR:\n" + (", ".join(aspect_strings) if aspect_strings else "Yok / Zayıf") + "\n"

    # Element / Quality
    elem_counts, qual_counts = element_quality_counts(visual_data)
    ai_data += "\nELEMENT DAĞILIMI:\n" + "\n".join([f"{k}: {v}" for k,v in elem_counts.items()]) + "\n"
    ai_data += "\nNİTELİK DAĞILIMI:\n" + "\n".join([f"{k}: {v}" for k,v in qual_counts.items()]) + "\n"

    # Transit package
    transit_html = ""
    transit_hits_text = ""
    transit_house_lines = []
    transit_move_lines = []

    if transit_enabled:
        if tz_mode == "manual_gmt":
            tr_start_utc = datetime.combine(start_date, d_time) - timedelta(hours=int(utc_offset))
            tr_end_utc   = datetime.combine(end_date, d_time)   - timedelta(hours=int(utc_offset))
        else:
            tz = pytz.timezone("Europe/Istanbul")
            tr_start_utc = tz.localize(datetime.combine(start_date, d_time)).astimezone(pytz.utc).replace(tzinfo=None)
            tr_end_utc   = tz.localize(datetime.combine(end_date, d_time)).astimezone(pytz.utc).replace(tzinfo=None)

        tr_mid_utc = tr_start_utc + (tr_end_utc - tr_start_utc)/2

        start_str = tr_start_utc.strftime("%Y/%m/%d %H:%M:%S")
        mid_str   = tr_mid_utc.strftime("%Y/%m/%d %H:%M:%S")
        end_str   = tr_end_utc.strftime("%Y/%m/%d %H:%M:%S")

        transit_move_lines, transit_house_lines, transit_hits_text, transit_html = calc_transit_package(
            natal_visual=visual_data,
            natal_cusps=cusps,
            start_dt_str=start_str,
            mid_dt_str=mid_str,
            end_dt_str=end_str,
            lat=lat, lon=lon
        )

        ai_data += f"\n\nTRANSIT DÖNEMİ: {start_date} - {end_date}\n"
        ai_data += "GEZEGEN HAREKETLERİ:\n" + "\n".join(transit_move_lines) + "\n"
        ai_data += "EV BAZLI TEMALAR:\n" + "\n".join(transit_house_lines) + "\n"
        ai_data += "ÖNCELİKLİ TEMASLAR:\n" + transit_hits_text + "\n"

    rule_summary = "KISA TEKNİK ÖZET:\n"
    rule_summary += f"- ASC {asc_sign}, MC {mc_sign} ekseni temel yaşam yönünü verir.\n"
    rule_summary += "- Element/Nitelik baskınlıkları karakter stilini gösterir.\n"
    rule_summary += "- Soru için: ilgili ev → o evdeki gezegenler → yöneticiler → açılar → transit temasları sıralaması kullanılır.\n"
    if transit_enabled:
        rule_summary += "- Transitlerde güç puanı yüksek temasları önce yorumla (Satürn/Plüton daha ağır)."

    return {
        "utc_dt": utc_dt,
        "tz_label": tz_label,
        "cusps": cusps,
        "info_html": info_html,
        "ai_data": ai_data,
        "visual_data": visual_data,
        "placements": placements,
        "aspects": aspect_strings,
        "aspects_raw": aspect_raw,
        "elem_counts": elem_counts,
        "qual_counts": qual_counts,
        "transit_html": transit_html,
        "transit_hits_text": transit_hits_text,
        "transit_house_lines": transit_house_lines,
        "rule_summary": rule_summary
    }

# =========================================================
# UI
# =========================================================
st.title("🌌 Astro-Analiz Pro (Full – Hibrit)")

models, models_err = list_gemini_models()

with st.sidebar:
    st.header("Giriş Paneli")
    name = st.text_input("İsim", "Ziyaretçi")
    city = st.text_input("Şehir", "İstanbul")

    d_date = st.date_input("Doğum Tarihi", value=datetime(1980, 11, 26))
    d_time = st.time_input("Doğum Saati", value=datetime.strptime("16:00", "%H:%M"), step=60)

    st.write("---")
    st.subheader("Saat Dilimi")
    tz_mode = st.radio(
        "Hesap yöntemi",
        options=["manual_gmt", "istanbul_tz"],
        format_func=lambda x: "Manuel GMT (önerilir)" if x=="manual_gmt" else "Europe/Istanbul (pytz)",
        index=0
    )
    utc_offset = st.number_input("GMT Farkı (Manuel)", value=3, min_value=-12, max_value=12, step=1)
    st.caption("Not: 2016 ve benzeri yıllarda DST/offset değişimleri için 'Manuel GMT' daha tutarlı sonuç verebilir.")

    st.write("---")
    st.subheader("Koordinat")
    use_city = st.checkbox("Şehirden otomatik koordinat al", value=False)
    c1, c2 = st.columns(2)
    lat = c1.number_input("Enlem", value=41.00, format="%.6f")
    lon = c2.number_input("Boylam", value=29.00, format="%.6f")

    st.write("---")
    st.subheader("Transit (Öngörü)")
    transit_mode = st.checkbox("Transit Modu Aç ⏳", value=False)
    start_date = datetime.now().date()
    end_date = (datetime.now() + timedelta(days=180)).date()
    if transit_mode:
        t1, t2 = st.columns(2)
        start_date = t1.date_input("Başlangıç", value=start_date)
        end_date = t2.date_input("Bitiş", value=end_date)

    st.write("---")
    st.subheader("AI (Gemini 2.5)")
    if models_err:
        st.warning(models_err)
        model_fullname = "models/gemini-2.5-flash"
        st.caption("Model listesi okunamadı; varsayılan denenecek: models/gemini-2.5-flash")
    else:
        default_model = pick_default_model(models)
        model_fullname = st.selectbox(
            "Model seç",
            options=models,
            index=models.index(default_model) if default_model in models else 0
        )
        st.caption(f"Seçili model: {model_fullname}")

    if st.button("🧪 AI Test (OK)"):
        st.info(gemini_generate("Sadece OK yaz.", model_fullname))

    st.write("---")
    q = st.text_area("Sorunuz", "Genel yorum")
    btn = st.button("Analiz Et ✨")

if btn:
    try:
        # Geocode if requested
        if use_city:
            lt, ln = city_to_latlon(city)
            if lt is not None and ln is not None:
                lat, lon = lt, ln
            else:
                st.warning("Şehirden koordinat bulunamadı; manuel koordinatlar kullanılacak.")

        data = calculate_all(
            name=name, city=city,
            d_date=d_date, d_time=d_time,
            lat=lat, lon=lon,
            tz_mode=tz_mode, utc_offset=utc_offset,
            transit_enabled=transit_mode,
            start_date=start_date, end_date=end_date
        )

        tab1, tab2, tab3, tab4 = st.tabs(["📝 Yorum & Öngörü", "🗺️ Harita", "📊 Teknik Veriler", "📈 Element/Nitelik"])

        # Build AI prompt
        prompt_text = f"""
Sen uzman bir astrologsun ve profesyonel danışman diliyle yazıyorsun.
Kişi: {name} | Şehir: {city}
Soru: {q}

Kurallar:
- Teknik veriye sadık kal, uydurma.
- Önce net bir genel özet (ASC/MC + Güneş + Ay + element/nitelik).
- Sonra soru odaklı analiz: ilgili ev/gezegen/açı mantığıyla.
- Transit modu açıksa: {start_date} - {end_date} için öngörü yap.
  'güç' puanı yüksek transit temaslarını öne çıkar.
- En sonda "Özet & Tavsiye" maddeleri ver.

TEKNİK VERİ:
{data["ai_data"]}

KISA TEKNİK ÖZET:
{data["rule_summary"]}
""".strip()

        with st.spinner("Yorum hazırlanıyor..."):
            ai_reply = gemini_generate(prompt_text, model_fullname)

        # Fallback to rule-based if AI failed
        ai_failed = ai_reply.startswith("AI Servis Hatası")
        if ai_failed:
            fallback = rule_based_report(
                name=name, q=q, city=city,
                placements=data["placements"],
                aspects_raw=data["aspects_raw"],
                elem_counts=data["elem_counts"],
                qual_counts=data["qual_counts"],
                transit_hits_text=data["transit_hits_text"] if transit_mode else None,
                transit_house_lines=data["transit_house_lines"] if transit_mode else None
            )
            final_text = f"⚠️ AI erişim sorunu nedeniyle rule-based rapor gösteriliyor.\n\n{fallback}"
        else:
            # Blend AI + short rule-based appendix
            appendix = rule_based_report(
                name=name, q=q, city=city,
                placements=data["placements"],
                aspects_raw=data["aspects_raw"],
                elem_counts=data["elem_counts"],
                qual_counts=data["qual_counts"],
                transit_hits_text=data["transit_hits_text"] if transit_mode else None,
                transit_house_lines=data["transit_house_lines"] if transit_mode else None
            )
            final_text = ai_reply.strip() + "\n\n---\n\n### 🔎 Rule-based Ek (Kontrol Listesi)\n" + appendix

        # PDF build
        meta_lines = [
            f"Tarih/Saat: {d_date} {d_time}",
            f"Şehir: {city} | Koordinat: {lat:.6f}, {lon:.6f}",
            f"Ev Sistemi: Placidus | Zaman: UTC ({data['tz_label']})",
            f"Soru: {q}"
        ]
        tech_lines = [
            f"ASC: {sign_name(data['cusps'][1])} {dec_to_dms(data['cusps'][1]%30)} | MC: {sign_name(data['cusps'][10])} {dec_to_dms(data['cusps'][10]%30)}",
            "Element: " + ", ".join([f"{k}:{v}" for k,v in data["elem_counts"].items()]),
            "Nitelik: " + ", ".join([f"{k}:{v}" for k,v in data["qual_counts"].items()]),
            "Açılar: " + (", ".join(data["aspects"][:12]) if data["aspects"] else "Yok/Zayıf"),
        ]
        if transit_mode:
            tech_lines.append(f"Transit Dönemi: {start_date} - {end_date}")
            if data["transit_hits_text"]:
                tech_lines.append("Öncelikli Transit Temaslar:\n" + data["transit_hits_text"])

        pdf_bytes = create_pdf_report(
            title=f"ASTRO RAPOR - {name}",
            meta_lines=meta_lines,
            body_text=final_text,
            tech_lines=tech_lines
        )

        with tab1:
            if ai_failed:
                st.error(ai_reply.splitlines()[0])
            st.markdown(final_text)
            if pdf_bytes:
                st.download_button("📄 PDF İndir", pdf_bytes, "astro_rapor.pdf", "application/pdf")
            else:
                st.warning("PDF oluşturulamadı.")

        with tab2:
            st.pyplot(draw_chart_visual(data["visual_data"], data["cusps"]))

        with tab3:
            c_a, c_b = st.columns(2)
            with c_a:
                st.markdown("### 🪐 Doğum Haritası")
                st.markdown(data["info_html"], unsafe_allow_html=True)
            with c_b:
                st.markdown("### 📐 Açılar")
                for asp in data["aspects"]:
                    st.markdown(f"<div class='aspect-box'>{asp}</div>", unsafe_allow_html=True)
                if transit_mode:
                    st.markdown(data["transit_html"], unsafe_allow_html=True)

        with tab4:
            st.markdown("### 📊 Element & Nitelik Dağılımı")
            c1, c2 = st.columns(2)
            with c1:
                fig = plt.figure()
                ax = fig.add_subplot(111)
                ax.bar(list(data["elem_counts"].keys()), list(data["elem_counts"].values()))
                ax.set_title("Element Dağılımı")
                st.pyplot(fig)
            with c2:
                fig2 = plt.figure()
                ax2 = fig2.add_subplot(111)
                ax2.bar(list(data["qual_counts"].keys()), list(data["qual_counts"].values()))
                ax2.set_title("Nitelik Dağılımı")
                st.pyplot(fig2)

    except Exception as e:
        st.error("Bir hata oluştu (detay aşağıda).")
        st.exception(e)
