# app.py
import streamlit as st
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import ephem
import math
from datetime import datetime, timedelta, date, time
import requests
import json
import pytz
import numpy as np
from fpdf import FPDF

# =========================
# PAGE / CSS
# =========================
st.set_page_config(page_title="Astro Natal + Transit", layout="wide", page_icon="🔮")

st.markdown("""
<style>
.stApp { background: linear-gradient(to bottom, #0e1117, #24283b); color: #e0e0e0; }
h1, h2, h3 { color: #FFD700 !important; font-family: 'Helvetica', sans-serif; text-shadow: 2px 2px 4px #000000; }
[data-testid="stSidebar"] { background-color: #161a25; border-right: 1px solid #FFD700; }
.stButton>button { background-color: #FFD700; color:#000; border-radius: 18px; border:none; font-weight:700; width:100%; height:48px; }
.metric-box { background-color: #1e2130; padding: 10px; border-radius: 8px; border-left: 4px solid #FFD700; margin-bottom: 8px; font-size: 14px; color: white; }
.metric-box b { color: #FFD700; }
.aspect-box { background-color: #25293c; padding: 6px 10px; margin: 3px 0; border-radius: 6px; font-size: 13px; border: 1px solid #444; }
.transit-box { background-color: #2d1b2e; border-left: 4px solid #ff4b4b; padding: 8px; margin-bottom: 6px; font-size: 13px; border-radius: 6px; }
.small-note { color: #9aa0aa; font-size: 12px; }
.bad { background:#ff4b4b22; border-left:4px solid #ff4b4b; padding:10px; border-radius:8px; }
.good { background:#22c55e22; border-left:4px solid #22c55e; padding:10px; border-radius:8px; }
table.puan { width:100%; border-collapse: collapse; font-size: 14px; }
table.puan th, table.puan td { border: 1px solid #3b3f55; padding: 8px; text-align:center; }
table.puan th { background:#1e2130; color:#FFD700; }
table.puan td { background:#121424; }
.kpi { font-size: 13px; color:#cbd5e1; }
</style>
""", unsafe_allow_html=True)

# =========================
# API KEY (Gemini Developer API)
# =========================
if "GOOGLE_API_KEY" not in st.secrets:
    st.error("🚨 st.secrets içinde GOOGLE_API_KEY yok. Streamlit Secrets'e ekleyin.")
    st.stop()
API_KEY = st.secrets["GOOGLE_API_KEY"]
GEN_API_BASE = "https://generativelanguage.googleapis.com/v1beta"

# =========================
# CONSTANTS
# =========================
ZODIAC = ["Koç","Boğa","İkizler","Yengeç","Aslan","Başak","Terazi","Akrep","Yay","Oğlak","Kova","Balık"]
ZODIAC_SYMBOLS = ["♈","♉","♊","♋","♌","♍","♎","♏","♐","♑","♒","♓"]

PLANET_SYMBOLS = {
    "Güneş":"☉","Ay":"☽","Merkür":"☿","Venüs":"♀","Mars":"♂",
    "Jüpiter":"♃","Satürn":"♄","Uranüs":"♅","Neptün":"♆","Plüton":"♇",
    "ASC":"ASC","MC":"MC"
}

# Element/Nitelik matrisi (paylaştığın tablo ile birebir)
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
    7:"İlişkiler / Ortaklık", 8:"Kriz / Ortak para / Dönüşüm",
    9:"Yurt dışı / İnanç / Eğitim", 10:"Kariyer / Statü",
    11:"Sosyal çevre / Hedefler", 12:"Bilinçaltı / Kapanış"
}

PLANET_MEANING = {
    "Güneş":"kimlik, yaşam yönü",
    "Ay":"duygusal ihtiyaçlar, iç güvenlik",
    "Merkür":"zihin, iletişim",
    "Venüs":"ilişkiler, değerler",
    "Mars":"motivasyon, enerji",
    "Jüpiter":"büyüme, fırsat",
    "Satürn":"sorumluluk, sınav",
    "Uranüs":"ani değişim, özgürleşme",
    "Neptün":"sezgi, ideal, belirsizlik",
    "Plüton":"dönüşüm, güç"
}

ASPECT_ANGLES = {"Kavuşum":0,"Sekstil":60,"Kare":90,"Üçgen":120,"Karşıt":180}
ASPECT_ORBS   = {"Kavuşum":8,"Sekstil":6,"Kare":8,"Üçgen":8,"Karşıt":8}
ASPECT_MEANING = {
    "Kavuşum":"konuyu büyütür ve görünür kılar.",
    "Sekstil":"fırsat verir; doğru kullanılırsa destek olur.",
    "Kare":"gerilim üretir; doğru yönetilirse sıçrama getirir.",
    "Üçgen":"doğal kolaylık ve akış sağlar.",
    "Karşıt":"denge ihtiyacı doğurur; ilişki/karşılık üzerinden çalışır."
}

def get_planet_objects():
    return {
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

# =========================
# HELPERS
# =========================
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
def get_element(sign): return ELEMENT.get(sign, "-")
def get_quality(sign): return QUALITY.get(sign, "-")

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
    return text.encode("latin-1","ignore").decode("latin-1")

def city_to_latlon(city: str):
    try:
        r = requests.get(
            "https://nominatim.openstreetmap.org/search",
            params={"q": city, "format":"json", "limit": 1},
            headers={"User-Agent":"astro-natal-transit"},
            timeout=15
        )
        js = r.json()
        if js:
            return float(js[0]["lat"]), float(js[0]["lon"])
    except Exception:
        pass
    return None, None

# =========================
# GEMINI (model list + pick 2.5)
# =========================
@st.cache_data(ttl=600)
def list_gemini_models():
    url = f"{GEN_API_BASE}/models?key={API_KEY}"
    r = requests.get(url, timeout=20)
    if r.status_code != 200:
        return [], f"Models list HTTP {r.status_code}: {r.text[:300]}"
    data = r.json()
    models = []
    for m in data.get("models", []):
        name = m.get("name","")
        methods = m.get("supportedGenerationMethods", [])
        if "generateContent" in methods and name:
            models.append(name)
    models = sorted(set(models))
    return models, None

def pick_default_model(models):
    preferred = [
        "models/gemini-2.5-pro",
        "models/gemini-2.5-flash",
        "models/gemini-2.5-flash-lite",
        "models/gemini-2.0-flash",
        "models/gemini-1.5-flash",
    ]
    for p in preferred:
        if p in models:
            return p
    return models[0] if models else "models/gemini-2.5-flash"

def gemini_generate(prompt: str, model_fullname: str) -> str:
    url = f"{GEN_API_BASE}/{model_fullname}:generateContent?key={API_KEY}"
    payload = {"contents":[{"parts":[{"text":prompt}]}]}
    resp = requests.post(url, headers={"Content-Type":"application/json"}, data=json.dumps(payload), timeout=80)
    if resp.status_code != 200:
        return f"AI Servis Hatası: HTTP {resp.status_code}\n{resp.text[:800]}"
    js = resp.json()
    if js.get("candidates"):
        return js["candidates"][0]["content"]["parts"][0]["text"]
    return "AI yanıtı boş döndü."

# =========================
# PLACIDUS-LIKE CUSPS + HOUSE FINDER
# =========================
def calculate_placidus_cusps(utc_dt, lat, lon):
    """
    Not: Swiss Ephemeris kadar hassas değil.
    Ama cusp/ev yerleştirme mantığı tutarlı çalışır.
    """
    obs = ephem.Observer()
    obs.lat, obs.lon = str(lat), str(lon)
    obs.date = utc_dt.strftime("%Y/%m/%d %H:%M:%S")

    ramc = float(obs.sidereal_time())  # radians
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

    diff = (asc_deg - mc_deg) % 360
    cusps[11] = normalize(mc_deg + diff/3)
    cusps[12] = normalize(mc_deg + 2*diff/3)

    diff2 = (ic_deg - asc_deg) % 360
    cusps[2] = normalize(asc_deg + diff2/3)
    cusps[3] = normalize(asc_deg + 2*diff2/3)

    cusps[5] = normalize(cusps[11] + 180)
    cusps[6] = normalize(cusps[12] + 180)
    cusps[8] = normalize(cusps[2] + 180)
    cusps[9] = normalize(cusps[3] + 180)
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
            if deg >= start or deg < end:
                return i
    return 1

# =========================
# ELEMENT/NITELIK PUANLAMA (senin kuralın)
# =========================
def build_points_config(include_outer_as_1: bool):
    # Paylaştığın puan kuralı:
    # Güneş/Ay/ASC = 3
    # MC = 1
    # Merkür/Venüs/Mars/Jüpiter/Satürn = 1
    # Dış gezegenler: varsayılan 0 (isteğe bağlı 1)
    points = {
        "Güneş": 3,
        "Ay": 3,
        "ASC": 3,
        "MC": 1,
        "Merkür": 1,
        "Venüs": 1,
        "Mars": 1,
        "Jüpiter": 1,
        "Satürn": 1,
        "Uranüs": 1 if include_outer_as_1 else 0,
        "Neptün": 1 if include_outer_as_1 else 0,
        "Plüton": 1 if include_outer_as_1 else 0,
    }
    return points

def compute_element_quality_scored(placements, points_cfg):
    """
    placements: [{'planet','sign','deg','house'}, ...]  ASC/MC dahil
    çıktı:
      elem_scores dict, qual_scores dict,
      matrix (quality->element->score),
      totals, dominant labels
    """
    elements = ["Ateş","Hava","Toprak","Su"]
    qualities = ["Öncü","Sabit","Değişken"]
    matrix = {q:{e:0 for e in elements} for q in qualities}

    elem_scores = {e:0 for e in elements}
    qual_scores = {q:0 for q in qualities}
    total = 0

    for p in placements:
        planet = p["planet"]
        sign = p["sign"]
        w = points_cfg.get(planet, 0)
        if w <= 0:
            continue
        e = get_element(sign)
        q = get_quality(sign)
        if e in elem_scores and q in qual_scores:
            elem_scores[e] += w
            qual_scores[q] += w
            matrix[q][e] += w
            total += w

    dom_elem = max(elem_scores.items(), key=lambda x: x[1])[0] if total > 0 else "-"
    dom_qual = max(qual_scores.items(), key=lambda x: x[1])[0] if total > 0 else "-"

    return elem_scores, qual_scores, matrix, total, dom_elem, dom_qual

def render_score_table_html(matrix):
    cols = ["Ateş","Hava","Toprak","Su"]
    rows = ["Öncü","Sabit","Değişken"]

    # row totals
    row_tot = {r: sum(matrix[r][c] for c in cols) for r in rows}
    col_tot = {c: sum(matrix[r][c] for r in rows) for c in cols}
    grand = sum(row_tot.values())

    html = "<table class='puan'>"
    html += "<tr><th>Nitelik \\ Element</th>" + "".join([f"<th>{c}</th>" for c in cols]) + "<th>Toplam</th></tr>"
    for r in rows:
        html += f"<tr><td><b>{r}</b></td>"
        for c in cols:
            html += f"<td>{matrix[r][c]}</td>"
        html += f"<td><b>{row_tot[r]}</b></td></tr>"
    html += "<tr><td><b>Toplam</b></td>"
    for c in cols:
        html += f"<td><b>{col_tot[c]}</b></td>"
    html += f"<td><b>{grand}</b></td></tr>"
    html += "</table>"
    return html, col_tot, row_tot, grand

# =========================
# NATAL POSITIONS + ASPECTS
# =========================
def compute_natal(utc_dt, lat, lon):
    obs = ephem.Observer()
    obs.lat, obs.lon = str(lat), str(lon)
    obs.date = utc_dt.strftime("%Y/%m/%d %H:%M:%S")
    obs.epoch = obs.date

    cusps = calculate_placidus_cusps(utc_dt, lat, lon)
    asc_sign = sign_name(cusps[1])
    mc_sign  = sign_name(cusps[10])

    visual_data = [
        ("ASC", asc_sign, cusps[1], "ASC"),
        ("MC",  mc_sign,  cusps[10], "MC"),
    ]

    placements = [
        {"planet":"ASC","sign":asc_sign,"deg":cusps[1],"house":1},
        {"planet":"MC","sign":mc_sign,"deg":cusps[10],"house":10},
    ]

    planet_objs = get_planet_objects()
    for pname, body in planet_objs.items():
        body.compute(obs)
        deg = normalize(math.degrees(ephem.Ecliptic(body).lon))
        sign = sign_name(deg)
        house = get_house_of_deg(deg, cusps)
        visual_data.append((pname, sign, deg, PLANET_SYMBOLS.get(pname,"")))
        placements.append({"planet":pname,"sign":sign,"deg":deg,"house":house})

    aspects_str = []
    aspects_raw = []
    p_list = [x for x in visual_data if x[0] not in ("ASC","MC")]
    for i in range(len(p_list)):
        for j in range(i+1, len(p_list)):
            n1, _, d1, _ = p_list[i]
            n2, _, d2, _ = p_list[j]
            dd = angle_diff(d1, d2)
            for asp, ang in ASPECT_ANGLES.items():
                if abs(dd - ang) <= ASPECT_ORBS.get(asp, 8):
                    aspects_str.append(f"{n1} {asp} {n2} ({round(dd,1)}°)")
                    aspects_raw.append((n1, asp, n2, dd))
                    break

    # (eski sayım bazlı) -> ayrı tutuyoruz ama özet artık PUANLI kullanacak
    elem_count = {"Ateş":0,"Toprak":0,"Hava":0,"Su":0}
    qual_count = {"Öncü":0,"Sabit":0,"Değişken":0}
    for p in placements:
        if p["planet"] in ("ASC","MC"):
            continue
        e = get_element(p["sign"])
        q = get_quality(p["sign"])
        if e in elem_count: elem_count[e]+=1
        if q in qual_count: qual_count[q]+=1

    return cusps, visual_data, placements, aspects_str, aspects_raw, elem_count, qual_count

# =========================
# TRANSITS (range) + natal hits + house themes
# =========================
def transit_degree_at(obs, body, dt_utc):
    obs.date = dt_utc.strftime("%Y/%m/%d %H:%M:%S")
    body.compute(obs)
    return normalize(math.degrees(ephem.Ecliptic(body).lon))

def compute_transits(natal_placements, natal_cusps, lat, lon, tr_start_utc, tr_end_utc):
    obs = ephem.Observer()
    obs.lat, obs.lon = str(lat), str(lon)
    tr_mid_utc = tr_start_utc + (tr_end_utc - tr_start_utc)/2

    natal_map = {p["planet"]: p for p in natal_placements if p["planet"] not in ("ASC","MC")}

    movement = []
    house_themes = []
    hits = []

    for tname, tbody in HEAVY_TRANSITS:
        d1 = transit_degree_at(obs, tbody, tr_start_utc)
        d2 = transit_degree_at(obs, tbody, tr_mid_utc)
        d3 = transit_degree_at(obs, tbody, tr_end_utc)

        s1 = sign_name(d1); s3 = sign_name(d3)
        h1 = get_house_of_deg(d1, natal_cusps)
        h3 = get_house_of_deg(d3, natal_cusps)

        movement.append(f"{tname}: {s1} {dec_to_dms(d1%30)} → {s3} {dec_to_dms(d3%30)}")

        if h1 == h3:
            house_themes.append(f"{tname} ağırlıkla {h1}. ev ({HOUSE_TOPICS.get(h1)}) temalarını çalıştırır.")
        else:
            house_themes.append(f"{tname} {h1}. ev → {h3}. ev: {HOUSE_TOPICS.get(h1)} temaslarından {HOUSE_TOPICS.get(h3)} temalarına kayış.")

        checks = [(d1,"başlangıç"),(d2,"orta"),(d3,"bitiş")]
        for np_name, np in natal_map.items():
            nd = np["deg"]
            nh = np["house"]
            topic = HOUSE_TOPICS.get(nh,"Genel")

            for dcheck, when in checks:
                delta = angle_diff(dcheck, nd)
                for asp, ang in ASPECT_ANGLES.items():
                    orb = 3 if asp in ("Kavuşum","Kare","Karşıt") else 2
                    if abs(delta - ang) <= orb:
                        score = 0
                        if tname in ("Satürn","Plüton"): score += 5
                        elif tname in ("Uranüs","Neptün"): score += 4
                        else: score += 3
                        if asp in ("Kavuşum","Karşıt"): score += 3
                        elif asp == "Kare": score += 2
                        else: score += 1

                        hits.append((score, f"⚠️ {when}: Transit {tname} {asp} natal {np_name} → {topic} (güç:{score})"))

    uniq = {}
    for s,t in hits:
        if t not in uniq or s > uniq[t]:
            uniq[t] = s
    hits_sorted = sorted([(s,t) for t,s in uniq.items()], reverse=True)

    return movement, house_themes, hits_sorted

# =========================
# CHART VISUAL (smaller)
# =========================
def draw_chart_visual(bodies_data, cusps):
    # daha küçük ve dengeli görünüm
    fig = plt.figure(figsize=(7.2, 7.2), facecolor='#0e1117')
    ax = fig.add_subplot(111, projection='polar')
    ax.set_facecolor('#1a1c24')

    asc_deg = cusps[1]
    ax.set_theta_offset(np.pi - math.radians(asc_deg))
    ax.set_theta_direction(1)
    ax.set_yticklabels([]); ax.set_xticklabels([])
    ax.grid(False); ax.spines['polar'].set_visible(False)

    # house lines
    for i in range(1, 13):
        angle = math.radians(cusps[i])
        ax.plot([angle, angle], [0, 1.05], color='#444', linewidth=1, linestyle='--')
        nxt = cusps[i+1] if i < 12 else cusps[1]
        d = (nxt - cusps[i]) % 360
        mid = math.radians(cusps[i] + d/2)
        ax.text(mid, 0.40, str(i), color='#9aa0aa', ha='center', fontsize=10, fontweight='bold')

    # zodiac ring
    circles = np.linspace(0, 2*np.pi, 120)
    ax.plot(circles, [1.08]*120, color='#FFD700', linewidth=2)
    for i in range(12):
        deg = i*30 + 15
        rad = math.radians(deg)
        ax.text(rad, 1.18, ZODIAC_SYMBOLS[i], ha='center', color='#FFD700', fontsize=14, rotation=deg-180)
        sep = math.radians(i*30)
        ax.plot([sep, sep], [1.04, 1.12], color='#FFD700')

    # bodies
    for name, sign, deg, sym in bodies_data:
        rad = math.radians(deg)
        c = '#FF4B4B' if name in ("ASC","MC") else 'white'
        s = 12 if name in ("ASC","MC") else 9
        ax.plot(rad, 0.97, 'o', color=c, markersize=s, markeredgecolor='#FFD700')
        ax.text(rad, 1.06, sym, color=c, fontsize=10, ha='center')

    return fig

# =========================
# RULE-BASED (hybrid)
# =========================
def rule_based_summary(
    placements,
    aspects_raw,
    elem_scores, qual_scores,
    dom_elem, dom_qual,
    transit_hits_sorted=None, transit_house_themes=None,
    question=""
):
    asc = next((p for p in placements if p["planet"]=="ASC"), None)
    mc  = next((p for p in placements if p["planet"]=="MC"), None)
    sun = next((p for p in placements if p["planet"]=="Güneş"), None)
    moon= next((p for p in placements if p["planet"]=="Ay"), None)

    hard = [a for a in aspects_raw if a[1] in ("Kare","Karşıt")]
    soft = [a for a in aspects_raw if a[1] in ("Sekstil","Üçgen")]
    conj = [a for a in aspects_raw if a[1] == "Kavuşum"]

    lines = []
    lines.append("## Kural Tabanlı Özet (AI yoksa da çalışır)")
    if asc: lines.append(f"- **Yükselen {asc['sign']}**: dışa yansıyan stil ve yaklaşım.")
    if sun: lines.append(f"- **Güneş {sun['sign']} ({sun['house']}. ev)**: {HOUSE_TOPICS.get(sun['house'])} alanında kimlik vurgusu.")
    if moon: lines.append(f"- **Ay {moon['sign']} ({moon['house']}. ev)**: {HOUSE_TOPICS.get(moon['house'])} alanında duygusal hassasiyet.")
    if mc:  lines.append(f"- **MC {mc['sign']}**: kariyer/itibar yönelimi.")

    # ✅ ARTIK PUANLI baskınlık (tablo ile aynı!)
    lines.append(f"- **Baskın element (puan):** {dom_elem} | **Baskın nitelik (puan):** {dom_qual}")
    lines.append(f"  <span class='kpi'>(Element puanları: {', '.join([f'{k}:{v}' for k,v in elem_scores.items()])} | "
                 f"Nitelik puanları: {', '.join([f'{k}:{v}' for k,v in qual_scores.items()])})</span>")

    lines.append("")
    lines.append("## Açılar (Öne çıkanlar)")
    def fmt(a):
        p1, asp, p2, ang = a
        return f"- **{p1} {asp} {p2}** ({round(ang,1)}°): {ASPECT_MEANING.get(asp,'')}"
    if conj[:3]:
        lines.append("**Kavuşumlar:**")
        for a in conj[:3]: lines.append(fmt(a))
    if hard[:4]:
        lines.append("\n**Zorlayıcı (gelişim) açıları:**")
        for a in hard[:4]: lines.append(fmt(a))
    if soft[:4]:
        lines.append("\n**Destekleyici açıları:**")
        for a in soft[:4]: lines.append(fmt(a))

    if question:
        lines.append("")
        lines.append("## Soru Mantığı")
        lines.append(f"- Soru: **{question}**")
        lines.append("- Yorum akışı: ilgili ev → o evdeki gezegenler → yöneticiler → natal açılar → transit temaslar.")

    if transit_house_themes or transit_hits_sorted:
        lines.append("")
        lines.append("## Transit (kural tabanlı)")
        if transit_house_themes:
            for t in transit_house_themes[:6]:
                lines.append(f"- {t}")
        if transit_hits_sorted:
            lines.append("\n**Öncelikli temaslar:**")
            for s,t in transit_hits_sorted[:10]:
                lines.append(f"- {t}")

    return "\n".join(lines)

# =========================
# PDF
# =========================
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

# =========================
# APP UI
# =========================
st.title("🌌 Doğum Haritası + Transit (Soru Sorabilir)")

models, models_err = list_gemini_models()
default_model = pick_default_model(models) if not models_err else "models/gemini-2.5-flash"

with st.sidebar:
    st.header("Giriş Paneli")

    with st.form("astro_form"):
        name = st.text_input("İsim", value="Misafir")
        city = st.text_input("Doğum Yeri (Şehir)", value="İstanbul")
        use_city = st.checkbox("Şehirden otomatik koordinat al", value=True)

        d_date = st.date_input("Doğum Tarihi", value=date(1980,11,26))
        d_time = st.time_input("Doğum Saati", value=time(16,0), step=60)

        st.write("---")
        st.subheader("Zaman yöntemi")
        tz_mode = st.radio(
            "Seçim",
            options=["manual_gmt","istanbul_tz"],
            format_func=lambda x: "Manuel GMT (önerilir)" if x=="manual_gmt" else "Europe/Istanbul (pytz)",
            index=0
        )
        utc_offset = st.number_input("GMT farkı (Manuel)", value=3, min_value=-12, max_value=12, step=1)
        st.caption("Not: Eski yıllarda DST/offset için Manuel GMT daha tutarlı olabilir.")

        st.write("---")
        st.subheader("Koordinat")
        c1, c2 = st.columns(2)
        lat = c1.number_input("Enlem", value=41.000000, format="%.6f")
        lon = c2.number_input("Boylam", value=29.000000, format="%.6f")

        st.write("---")
        st.subheader("Element/Nitelik puanlama")
        include_outer = st.checkbox("Uranüs/Neptün/Plüton'u +1 puana dahil et", value=False)
        st.caption("Varsayılan: dış gezegenler 0 puan (paylaştığın kurala en yakın).")

        st.write("---")
        st.subheader("Transit (Öngörü)")
        transit_mode = st.checkbox("Transit modu aç", value=False)
        start_date = date.today()
        end_date = (datetime.now() + timedelta(days=180)).date()
        if transit_mode:
            t1, t2 = st.columns(2)
            start_date = t1.date_input("Başlangıç", value=start_date)
            end_date = t2.date_input("Bitiş", value=end_date)

        st.write("---")
        st.subheader("AI (Gemini)")
        if models_err:
            st.warning(models_err)
            model_fullname = "models/gemini-2.5-flash"
        else:
            model_fullname = st.selectbox("Model", models, index=models.index(default_model) if default_model in models else 0)

        question = st.text_area("Sorunuz", value="Genel yorum")
        submitted = st.form_submit_button("Analiz Et ✨")

if submitted:
    # Geocode
    if use_city:
        lt, ln = city_to_latlon(city)
        if lt is not None and ln is not None:
            lat, lon = lt, ln
        else:
            st.warning("Şehirden koordinat bulunamadı; manuel koordinatlar kullanılacak.")

    # Build UTC dt
    local_dt = datetime.combine(d_date, d_time)
    if tz_mode == "manual_gmt":
        utc_dt = local_dt - timedelta(hours=int(utc_offset))
        tz_label = f"Manuel GMT{int(utc_offset):+d}"
    else:
        tz = pytz.timezone("Europe/Istanbul")
        utc_dt = tz.localize(local_dt).astimezone(pytz.utc).replace(tzinfo=None)
        tz_label = "Europe/Istanbul"

    # Natal
    cusps, visual_data, placements, aspects_str, aspects_raw, elem_count, qual_count = compute_natal(utc_dt, lat, lon)

    # ✅ Puanlı element/nitelik
    points_cfg = build_points_config(include_outer_as_1=include_outer)
    elem_scores, qual_scores, score_matrix, total_points, dom_elem, dom_qual = compute_element_quality_scored(placements, points_cfg)
    score_table_html, col_tot, row_tot, grand = render_score_table_html(score_matrix)

    # Transit
    transit_movement = []
    transit_house_themes = []
    transit_hits_sorted = []
    transit_html = ""
    if transit_mode:
        tr_start_local = datetime.combine(start_date, d_time)
        tr_end_local   = datetime.combine(end_date, d_time)
        if tz_mode == "manual_gmt":
            tr_start_utc = tr_start_local - timedelta(hours=int(utc_offset))
            tr_end_utc   = tr_end_local   - timedelta(hours=int(utc_offset))
        else:
            tz = pytz.timezone("Europe/Istanbul")
            tr_start_utc = tz.localize(tr_start_local).astimezone(pytz.utc).replace(tzinfo=None)
            tr_end_utc   = tz.localize(tr_end_local).astimezone(pytz.utc).replace(tzinfo=None)

        transit_movement, transit_house_themes, transit_hits_sorted = compute_transits(
            placements, cusps, lat, lon, tr_start_utc, tr_end_utc
        )

        transit_html = "<h4>⏳ Transit Hareketleri</h4>"
        for line in transit_movement:
            transit_html += f"<div class='transit-box'>{line}</div>"
        transit_html += "<h4>🪐 Ev Bazlı Transit Temaları</h4>"
        for line in transit_house_themes:
            transit_html += f"<div class='transit-box'>{line}</div>"
        if transit_hits_sorted:
            transit_html += "<h4>⚡ Transit–Natal Temaslar</h4>"
            for s,t in transit_hits_sorted[:15]:
                transit_html += f"<div class='transit-box'>{t}</div>"

    # Build technical text for AI
    asc_sign = sign_name(cusps[1])
    mc_sign  = sign_name(cusps[10])

    info_html = f"<div class='metric-box'>🌍 <b>UTC:</b> {utc_dt.strftime('%Y-%m-%d %H:%M')} <span class='small-note'>({tz_label})</span></div>"
    info_html += f"<div class='metric-box'>📍 <b>Koordinat:</b> {lat:.6f}, {lon:.6f} | <b>Ev Sistemi:</b> Placidus</div>"
    info_html += f"<div class='metric-box'>🚀 <b>ASC:</b> {asc_sign} {dec_to_dms(cusps[1]%30)} | <b>MC:</b> {mc_sign} {dec_to_dms(cusps[10]%30)}</div>"

    ai_data = f"Kişi: {name}\nŞehir: {city}\nUTC: {utc_dt.strftime('%Y-%m-%d %H:%M')} ({tz_label})\n"
    ai_data += f"Koordinat: {lat:.6f}, {lon:.6f}\nEv Sistemi: Placidus\n"
    ai_data += f"ASC: {asc_sign} {dec_to_dms(cusps[1]%30)}\nMC: {mc_sign} {dec_to_dms(cusps[10]%30)}\n\n"

    for p in placements:
        if p["planet"] in ("ASC","MC"):
            continue
        ai_data += f"{p['planet']}: {p['sign']} {dec_to_dms(p['deg']%30)} ({p['house']}. Ev) | Tema: {HOUSE_TOPICS.get(p['house'])} | Anlam: {PLANET_MEANING.get(p['planet'],'')}\n"

    ai_data += "\nAçılar:\n" + (", ".join(aspects_str) if aspects_str else "Zayıf/Yok") + "\n"

    # ✅ PUANLI element/nitelik AI verisine de ekleniyor
    ai_data += "\nElement (puan):\n" + ", ".join([f"{k}:{v}" for k,v in elem_scores.items()]) + "\n"
    ai_data += "Nitelik (puan):\n" + ", ".join([f"{k}:{v}" for k,v in qual_scores.items()]) + "\n"
    ai_data += f"Baskın (puan): Element={dom_elem}, Nitelik={dom_qual} | Toplam Puan={total_points}\n"

    if transit_mode:
        ai_data += f"\nTRANSIT DÖNEMİ: {start_date} - {end_date}\n"
        ai_data += "Hareket:\n" + "\n".join(transit_movement) + "\n"
        ai_data += "Ev bazlı:\n" + "\n".join(transit_house_themes) + "\n"
        if transit_hits_sorted:
            ai_data += "Temaslar:\n" + "\n".join([t for s,t in transit_hits_sorted[:20]]) + "\n"

    # Rule based appendix / fallback (✅ puanlı)
    rule_text = rule_based_summary(
        placements, aspects_raw,
        elem_scores, qual_scores,
        dom_elem, dom_qual,
        transit_hits_sorted=transit_hits_sorted if transit_mode else None,
        transit_house_themes=transit_house_themes if transit_mode else None,
        question=question
    )

    # AI prompt
    prompt = f"""
Sen uzman bir astrologsun. Profesyonel danışman üslubuyla yaz.
Kişi: {name} | Şehir: {city}
Soru: {question}

Kurallar:
- Teknik veriye sadık kal; uydurma yapma.
- 1) Genel özet: ASC/MC, Güneş, Ay, element/nitelik (PUANLI dağılımı kullan).
- 2) Natal yorum: evlere göre (özellikle 1/4/7/10 ve soru ile ilgili evler).
- 3) Açılar: en etkili 5 açıyı yorumla (kare/karşıt/kavuşum öncelik).
- 4) Transit modu açıksa: {start_date} - {end_date} dönemi için öngörü yap; ev bazlı temaları ve güçlü temasları önce anlat.
- 5) En sonda "Özet & Tavsiye" maddeleri.

TEKNİK VERİ:
{ai_data}

KURAL TABANLI EK (kontrol amaçlı):
{rule_text}
""".strip()

    with st.spinner("Yorum hazırlanıyor..."):
        ai_reply = gemini_generate(prompt, model_fullname)

    ai_failed = ai_reply.startswith("AI Servis Hatası")

    if ai_failed:
        final_text = f"⚠️ AI erişim sorunu nedeniyle kural tabanlı rapor gösteriliyor.\n\n{rule_text}"
    else:
        final_text = ai_reply.strip() + "\n\n---\n\n" + rule_text

    # PDF
    meta_lines = [
        f"Tarih/Saat: {d_date} {d_time}",
        f"Doğum yeri: {city} | Koordinat: {lat:.6f}, {lon:.6f}",
        f"Zaman: UTC ({tz_label}) | Ev: Placidus",
        f"Soru: {question}"
    ]
    tech_lines = [
        f"ASC: {asc_sign} {dec_to_dms(cusps[1]%30)} | MC: {mc_sign} {dec_to_dms(cusps[10]%30)}",
        "Element (puan): " + ", ".join([f"{k}:{v}" for k,v in elem_scores.items()]),
        "Nitelik (puan): " + ", ".join([f"{k}:{v}" for k,v in qual_scores.items()]),
        f"Baskın (puan): Element={dom_elem}, Nitelik={dom_qual} | Toplam={total_points}",
        "Açılar: " + (", ".join(aspects_str[:12]) if aspects_str else "Zayıf/Yok"),
    ]
    if transit_mode:
        tech_lines.append(f"Transit dönemi: {start_date} - {end_date}")
        if transit_hits_sorted:
            tech_lines.append("Öncelikli temaslar: " + " | ".join([t for s,t in transit_hits_sorted[:6]]))

    pdf_bytes = create_pdf_report(f"ASTRO RAPOR - {name}", meta_lines, final_text, tech_lines)

    # =========================
    # OUTPUT TABS
    # =========================
    tab1, tab2, tab3, tab4 = st.tabs(["📝 Yorum & Öngörü", "🗺️ Harita", "📊 Teknik Veriler", "📈 Element/Nitelik (Puanlı)"])

    with tab1:
        if ai_failed:
            st.markdown(f"<div class='bad'>{ai_reply}</div>", unsafe_allow_html=True)
        st.markdown(final_text)
        if pdf_bytes:
            st.download_button("📄 PDF İndir", pdf_bytes, "astro_rapor.pdf", "application/pdf")
        else:
            st.warning("PDF üretilemedi.")

    with tab2:
        st.pyplot(draw_chart_visual(visual_data, cusps))

    with tab3:
        c1, c2 = st.columns(2)
        with c1:
            st.markdown("### 🪐 Natal Konumlar")
            st.markdown(info_html, unsafe_allow_html=True)
            for p in placements:
                if p["planet"] in ("ASC","MC"):
                    continue
                idx = ZODIAC.index(p["sign"])
                st.markdown(
                    f"<div class='metric-box'><b>{p['planet']}</b>: {ZODIAC_SYMBOLS[idx]} {p['sign']} {dec_to_dms(p['deg']%30)} | <b>{p['house']}. Ev</b> <span class='small-note'>({HOUSE_TOPICS.get(p['house'])})</span></div>",
                    unsafe_allow_html=True
                )
        with c2:
            st.markdown("### 📐 Açılar")
            if aspects_str:
                for a in aspects_str:
                    st.markdown(f"<div class='aspect-box'>{a}</div>", unsafe_allow_html=True)
            else:
                st.info("Belirgin ana açı bulunamadı (orb dışında).")

            if transit_mode:
                st.markdown("### ⏳ Transit")
                st.markdown(transit_html, unsafe_allow_html=True)

    with tab4:
        st.markdown("### 📊 Element & Nitelik (Puanlı)")
        st.markdown(
            f"<div class='metric-box'><b>Toplam Puan:</b> {total_points} "
            f"<span class='small-note'>(Güneş/Ay/ASC=3, MC+Kişisel+Sosyal=1, dış gezegenler {'1' if include_outer else '0'})</span></div>",
            unsafe_allow_html=True
        )
        st.markdown(score_table_html, unsafe_allow_html=True)
        st.markdown(
            f"<div class='metric-box'><b>Baskın:</b> Element = {dom_elem} | Nitelik = {dom_qual}</div>",
            unsafe_allow_html=True
        )

        cc1, cc2 = st.columns(2)
        with cc1:
            fig = plt.figure()
            ax = fig.add_subplot(111)
            ax.bar(list(elem_scores.keys()), list(elem_scores.values()))
            ax.set_title("Element (Puan)")
            st.pyplot(fig)
        with cc2:
            fig2 = plt.figure()
            ax2 = fig2.add_subplot(111)
            ax2.bar(list(qual_scores.keys()), list(qual_scores.values()))
            ax2.set_title("Nitelik (Puan)")
            st.pyplot(fig2)
