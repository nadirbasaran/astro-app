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
# UI / CSS
# =========================================================
st.set_page_config(page_title="Astro-Analiz Pro", layout="wide", page_icon="🔮")

st.markdown("""
<style>
.stApp { background: linear-gradient(to bottom, #0e1117, #24283b); color: #e0e0e0; }
h1, h2, h3 { color: #FFD700 !important; font-family: 'Helvetica', sans-serif; text-shadow: 2px 2px 4px #000000; }
.stButton>button { background-color: #FFD700; color: #000; border-radius: 20px; border: none; font-weight: bold; width: 100%; }
[data-testid="stSidebar"] { background-color: #161a25; border-right: 1px solid #FFD700; }
.metric-box { background-color: #1e2130; padding: 10px; border-radius: 8px; border-left: 4px solid #FFD700; margin-bottom: 8px; font-size: 14px; color: white; }
.metric-box b { color: #FFD700; }
.aspect-box { background-color: #25293c; padding: 5px 10px; margin: 2px; border-radius: 4px; font-size: 13px; border: 1px solid #444; }
.transit-box { background-color: #2d1b2e; border-left: 4px solid #ff4b4b; padding: 8px; margin-bottom: 6px; font-size: 13px; }
.small-note { color: #9aa0aa; font-size: 12px; }
</style>
""", unsafe_allow_html=True)

# =========================================================
# API (Gemini)
# =========================================================
if "GOOGLE_API_KEY" not in st.secrets:
    st.error("🚨 st.secrets['GOOGLE_API_KEY'] bulunamadı! Lütfen API anahtarınızı Secrets ayarlarından ekleyin.")
    st.stop()
API_KEY = st.secrets["GOOGLE_API_KEY"]

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

def get_planet_objects():
    return {
        "Güneş": ephem.Sun(), "Ay": ephem.Moon(), "Merkür": ephem.Mercury(),
        "Venüs": ephem.Venus(), "Mars": ephem.Mars(), "Jüpiter": ephem.Jupiter(),
        "Satürn": ephem.Saturn(), "Uranüs": ephem.Uranus(), "Neptün": ephem.Neptune(),
        "Plüton": ephem.Pluto()
    }

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

ASPECT_ANGLES = {"Kavuşum":0,"Sekstil":60,"Kare":90,"Üçgen":120,"Karşıt":180}
ASPECT_ORBS   = {"Kavuşum":8,"Sekstil":6,"Kare":8,"Üçgen":8,"Karşıt":8}

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

def clean_text_for_pdf(text):
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

def city_to_latlon(city):
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
    except:
        pass
    return None, None

# =========================================================
# PLACIDUS (DÜZELTİLDİ: TARİH FORMATI STRING)
# =========================================================
def calculate_placidus_cusps(utc_dt, lat, lon):
    obs = ephem.Observer()
    
    # --- KRİTİK DÜZELTME: Datetime objesi yerine STRING veriyoruz ---
    # Bu, "format string" hatasını çözer.
    obs.date = utc_dt.strftime('%Y/%m/%d %H:%M:%S')
    
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

def get_house_of_planet(deg, cusps):
    deg = normalize(deg)
    for i in range(1, 13):
        start = cusps[i]
        end = cusps[i+1] if i < 12 else cusps[1]
        if start < end:
            if start <= deg < end: return i
        else:
            if start <= deg or deg < end: return i
    return 1

# =========================================================
# NATAL POSITIONS
# =========================================================
def calculate_natal(utc_dt_str, lat, lon):
    obs = ephem.Observer()
    obs.date = utc_dt_str # Zaten string geliyor
    obs.lat, obs.lon = str(lat), str(lon)
    # Güneş konumu (epoch) düzeltmesi:
    obs.epoch = utc_dt_str

    planets = []
    planet_objs = get_planet_objects()
    for n, body in planet_objs.items():
        body.compute(obs)
        deg = normalize(math.degrees(ephem.Ecliptic(body).lon))
        planets.append((n, deg))
    return planets

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
# TRANSITS
# =========================================================
def calculate_transit_range(natal_visual, natal_cusps, start_dt_str, end_dt_str, lat, lon):
    obs = ephem.Observer()
    obs.lat, obs.lon = str(lat), str(lon)

    heavy_planets = [
        ("Jüpiter", ephem.Jupiter()),
        ("Satürn", ephem.Saturn()),
        ("Uranüs", ephem.Uranus()),
        ("Neptün", ephem.Neptune()),
        ("Plüton", ephem.Pluto())
    ]

    natal_map = {}
    for n, sign, nd, sym in natal_visual:
        if n in ("ASC","MC"):
            continue
        natal_map[n] = {
            "deg": nd,
            "house": get_house_of_planet(nd, natal_cusps),
            "sign": sign_name(nd)
        }

    move_lines = []
    display_lines = []
    hits_ranked = [] 

    for pname, body in heavy_planets:
        # Start
        obs.date = start_dt_str
        body.compute(obs)
        d_start = normalize(math.degrees(ephem.Ecliptic(body).lon))
        s_start = sign_name(d_start)

        # End
        obs.date = end_dt_str
        body.compute(obs)
        d_end = normalize(math.degrees(ephem.Ecliptic(body).lon))
        s_end = sign_name(d_end)

        move_lines.append(f"Transit {pname}: {s_start} -> {s_end}")
        display_lines.append(f"<b>{pname}:</b> {s_start} {dec_to_dms(d_start%30)} ➔ {s_end} {dec_to_dms(d_end%30)}")

        # Check midpoint/start/end
        checks = [d_start, normalize((d_start+d_end)/2), d_end]

        for natal_p, info in natal_map.items():
            nd = info["deg"]
            nh = info["house"]
            topic = HOUSE_TOPICS.get(nh, "Genel Temalar")

            for dcheck in checks:
                delta = angle_diff(dcheck, nd)
                for asp, ang in ASPECT_ANGLES.items():
                    orb = 3 if asp in ("Kavuşum","Kare","Karşıt") else 2
                    if abs(delta - ang) <= orb:
                        score = 0
                        if pname in ("Satürn","Plüton"): score += 4
                        elif pname in ("Uranüs","Neptün"): score += 3
                        elif pname == "Jüpiter": score += 2

                        if asp in ("Kavuşum","Karşıt"): score += 3
                        elif asp == "Kare": score += 2
                        else: score += 1

                        txt = f"⚠️ Transit {pname} {asp} natal {natal_p} → {topic} (güç:{score})"
                        hits_ranked.append((score, txt))

    # uniq + sort
    uniq = {}
    for s,t in hits_ranked:
        if t not in uniq or s > uniq[t]:
            uniq[t] = s
    hits_sorted = sorted([(s,t) for t,s in uniq.items()], reverse=True)

    hits_text = "\n".join([f"- {t}" for s,t in hits_sorted[:20]]) if hits_sorted else "Belirgin güçlü transit temas bulunamadı."

    html = "<br><h4>⏳ Transit Hareketleri</h4>"
    for line in display_lines:
        html += f"<div class='transit-box'>{line}</div>"

    if hits_sorted:
        html += "<h4>⚡ Transit–Natal Temaslar (Öncelikli)</h4>"
        for s,t in hits_sorted[:15]:
            html += f"<div class='transit-box'>{t}</div>"

    return "\n".join(move_lines), hits_text, html

# =========================================================
# ELEMENT / QUALITY
# =========================================================
def element_quality_summary(visual_data):
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

def element_quality_charts(elem, qual):
    c1, c2 = st.columns(2)
    with c1:
        fig = plt.figure()
        ax = fig.add_subplot(111)
        ax.bar(list(elem.keys()), list(elem.values()), color='#FFD700')
        ax.set_title("Element Dağılımı", color='white')
        ax.tick_params(axis='x', colors='white')
        ax.tick_params(axis='y', colors='white')
        fig.patch.set_alpha(0) 
        st.pyplot(fig)
    with c2:
        fig2 = plt.figure()
        ax2 = fig2.add_subplot(111)
        ax2.bar(list(qual.keys()), list(qual.values()), color='#FF4B4B')
        ax2.set_title("Nitelik Dağılımı", color='white')
        ax2.tick_params(axis='x', colors='white')
        ax2.tick_params(axis='y', colors='white')
        fig2.patch.set_alpha(0)
        st.pyplot(fig2)

# =========================================================
# CHART VISUAL
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

    for i in range(1, 13):
        angle = math.radians(cusps[i])
        ax.plot([angle, angle], [0, 1.2], color='#444', linewidth=1, linestyle='--')
        nxt = cusps[i+1] if i < 12 else cusps[1]
        d = (nxt - cusps[i]) % 360
        mid = math.radians(cusps[i] + d/2)
        ax.text(mid, 0.4, str(i), color='#888', ha='center', fontsize=11, fontweight='bold')

    circles = np.linspace(0, 2*np.pi, 100)
    ax.plot(circles, [1.2]*100, color='#FFD700', linewidth=2)

    for i in range(12):
        deg = i * 30 + 15
        rad = math.radians(deg)
        ax.text(rad, 1.3, ZODIAC_SYMBOLS[i], ha='center', color='#FFD700', fontsize=16, rotation=deg-180)
        sep = math.radians(i*30)
        ax.plot([sep, sep], [1.15, 1.25], color='#FFD700')

    for name, sign, deg, sym in bodies_data:
        rad = math.radians(deg)
        color = '#FF4B4B' if name in ('ASC','MC') else 'white'
        size = 14 if name in ('ASC','MC') else 11
        ax.plot(rad, 1.05, 'o', color=color, markersize=size, markeredgecolor='#FFD700')
        ax.text(rad, 1.17, sym, color=color, fontsize=12, ha='center')

    return fig

# =========================================================
# PDF
# =========================================================
def create_pdf(name, info, ai_text, tech_block=""):
    try:
        pdf = FPDF()
        pdf.add_page()
        pdf.set_auto_page_break(auto=True, margin=15)

        pdf.set_font("Arial", 'B', 16)
        pdf.cell(0, 10, clean_text_for_pdf(f"ANALIZ: {name}"), ln=True, align='C')

        pdf.set_font("Arial", '', 12)
        pdf.multi_cell(0, 8, clean_text_for_pdf(info))
        pdf.ln(2)

        if tech_block:
            pdf.set_font("Arial", 'B', 12)
            pdf.cell(0, 8, "TEKNIK OZET", ln=True)
            pdf.set_font("Arial", '', 10)
            pdf.multi_cell(0, 6, clean_text_for_pdf(tech_block))
            pdf.ln(2)

        pdf.set_font("Arial", 'B', 14)
        pdf.cell(0, 10, "YORUM & ONGORU", ln=True)

        pdf.set_font("Arial", '', 11)
        pdf.multi_cell(0, 7, clean_text_for_pdf(ai_text))

        return pdf.output(dest='S').encode('latin-1', 'ignore')
    except Exception:
        return None

# =========================================================
# AI (Gemini) - DÜZELTİLDİ: gemini-1.5-flash
# =========================================================
def get_ai_response(prompt, model="gemini-1.5-flash"):
    try:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={API_KEY}"
        resp = requests.post(
            url,
            headers={'Content-Type': 'application/json'},
            data=json.dumps({"contents": [{"parts": [{"text": prompt}]}]}),
            timeout=60
        )
        if resp.status_code == 200:
            data = resp.json()
            if data.get("candidates"):
                return data["candidates"][0]["content"]["parts"][0]["text"]
            return "AI yanıtı boş döndü."
        
        # Hata durumunda detaylı bilgi verelim
        error_msg = f"AI Servis Hatası: HTTP {resp.status_code}"
        try:
            error_details = resp.json()
            if "error" in error_details:
                error_msg += f" - {error_details['error'].get('message', '')}"
        except:
            pass
        return error_msg

    except Exception as e:
        return str(e)

# =========================================================
# MAIN CALC
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

    # --- HATA ÖNLEME BURADA: `utc_dt` ARTIK GÜVENLİ ---
    cusps = calculate_placidus_cusps(utc_dt, lat, lon)

    asc_sign = sign_name(cusps[1])
    mc_sign = sign_name(cusps[10])

    info_html = f"<div class='metric-box'>🌍 <b>Doğum (UTC):</b> {utc_dt.strftime('%Y-%m-%d %H:%M')} <span class='small-note'>({tz_label})</span></div>"
    info_html += f"<div class='metric-box'>🚀 <b>Yükselen:</b> {asc_sign} {dec_to_dms(cusps[1]%30)} | <b>MC:</b> {mc_sign} {dec_to_dms(cusps[10]%30)}</div>"

    # Observer date string
    utc_dt_str = utc_dt.strftime("%Y/%m/%d %H:%M:%S")

    # Natal planet longitudes
    planet_lons = calculate_natal(utc_dt_str, lat, lon)

    visual_data = [("ASC", asc_sign, cusps[1], "ASC"), ("MC", mc_sign, cusps[10], "MC")]

    ai_data = "SİSTEM: PLACIDUS\n"
    ai_data += f"Şehir: {city}\n"
    ai_data += f"Doğum UTC: {utc_dt.strftime('%Y-%m-%d %H:%M')}\n"
    ai_data += f"ASC: {asc_sign} {dec_to_dms(cusps[1]%30)}\n"
    ai_data += f"MC: {mc_sign} {dec_to_dms(cusps[10]%30)}\n\n"

    # Build natal details
    for (pname, deg) in planet_lons:
        sign = sign_name(deg)
        idx = int(deg/30) % 12
        house = get_house_of_planet(deg, cusps)
        info_html += f"<div class='metric-box'><b>{pname}</b>: {ZODIAC_SYMBOLS[idx]} {ZODIAC[idx]} {dec_to_dms(deg%30)} | <b>{house}. Ev</b></div>"
        ai_data += f"{pname}: {sign} {dec_to_dms(deg%30)} ({house}. Ev) | Tema: {HOUSE_TOPICS.get(house,'Genel')}\n"
        visual_data.append((pname, sign, deg, PLANET_SYMBOLS.get(pname,"")))

    # Aspects
    aspect_strings, aspect_raw = calculate_aspects(visual_data)
    ai_data += "\nNATAL AÇILAR:\n" + (", ".join(aspect_strings) if aspect_strings else "Yok / Zayıf") + "\n"

    # Element & Quality
    elem_counts, qual_counts = element_quality_summary(visual_data)
    ai_data += "\nELEMENT DAĞILIMI:\n" + "\n".join([f"{k}: {v}" for k,v in elem_counts.items()]) + "\n"
    ai_data += "\nNİTELİK DAĞILIMI:\n" + "\n".join([f"{k}: {v}" for k,v in qual_counts.items()]) + "\n"

    # Transit
    transit_html = ""
    transit_hits_text = ""

    if transit_enabled:
        if tz_mode == "manual_gmt":
            tr_start_utc = datetime.combine(start_date, d_time) - timedelta(hours=int(utc_offset))
            tr_end_utc = datetime.combine(end_date, d_time) - timedelta(hours=int(utc_offset))
        else:
            tz = pytz.timezone("Europe/Istanbul")
            tr_start_utc = tz.localize(datetime.combine(start_date, d_time)).astimezone(pytz.utc).replace(tzinfo=None)
            tr_end_utc = tz.localize(datetime.combine(end_date, d_time)).astimezone(pytz.utc).replace(tzinfo=None)

        tr_report, tr_hits_text, tr_html = calculate_transit_range(
            natal_visual=visual_data,
            natal_cusps=cusps,
            start_dt_str=tr_start_utc.strftime("%Y/%m/%d %H:%M:%S"),
            end_dt_str=tr_end_utc.strftime("%Y/%m/%d %H:%M:%S"),
            lat=lat, lon=lon
        )
        transit_html = tr_html
        transit_hits_text = tr_hits_text

        transit_ai_block = f"""
TRANSIT DÖNEMİ: {start_date} - {end_date}
GEZEGEN HAREKETLERİ:
{tr_report}

ÖNCELİKLİ TEMASLAR:
{tr_hits_text}
"""
        ai_data += "\n\n" + transit_ai_block

    rule_summary = "KISA TEKNİK ÖZET:\n"
    rule_summary += f"- ASC {asc_sign}, MC {mc_sign} ekseni temel yaşam yönünü verir.\n"
    rule_summary += "- Element/Nitelik baskınlıkları karakter stilini gösterir.\n"
    if transit_enabled:
        rule_summary += "- Transitlerde 'güç' puanı yüksek olan temasları önce yorumla.\n"

    return {
        "utc_dt": utc_dt,
        "cusps": cusps,
        "info_html": info_html,
        "ai_data": ai_data,
        "visual_data": visual_data,
        "aspects": aspect_strings,
        "transit_html": transit_html,
        "elem_counts": elem_counts,
        "qual_counts": qual_counts,
        "rule_summary": rule_summary,
        "transit_hits_text": transit_hits_text
    }

# =========================================================
# UI
# =========================================================
st.title("🌌 Astro-Analiz Pro (Full – Hibrit)")

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
    st.caption("Not: 2016 ve benzeri yıllarda DST/offset değişimleri için 'Manuel GMT' daha tutarlı sonuç verir.")

    st.write("---")
    st.subheader("Koordinat")
    use_city = st.checkbox("Şehirden otomatik koordinat al", value=False)
    if use_city:
        st.caption("Şehirden alınan koordinat internet gerektirir (OSM Nominatim).")

    c1, c2 = st.columns(2)
    lat = c1.number_input("Enlem", 41.00)
    lon = c2.number_input("Boylam", 29.00)

    st.write("---")
    transit_mode = st.checkbox("Transit (Öngörü) Modu Aç ⏳", value=False)
    start_date = datetime.now().date()
    end_date = (datetime.now() + timedelta(days=180)).date()
    if transit_mode:
        t1, t2 = st.columns(2)
        start_date = t1.date_input("Başlangıç", value=start_date)
        end_date = t2.date_input("Bitiş", value=end_date)

    st.write("---")
    q = st.text_area("Sorunuz", "Genel yorum")
    btn = st.button
