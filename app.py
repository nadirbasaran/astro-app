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
# AYARLAR
# =========================================================
st.set_page_config(page_title="Astro-Analiz Pro", layout="wide", page_icon="🔮")

st.markdown("""
<style>
.stApp { background: linear-gradient(to bottom, #0e1117, #1a1c24); color: #e0e0e0; }
h1, h2 { color: #FFD700 !important; }
.metric-box { background-color: #262730; padding: 10px; border-radius: 5px; border-left: 3px solid #FFD700; margin-bottom: 5px; }
.aspect-box { background-color: #2d2f3d; padding: 5px; margin: 2px; border-radius: 3px; font-size: 13px; border: 1px solid #444; }
.transit-box { background-color: #3b2c30; padding: 8px; border-radius: 5px; margin-bottom: 5px; border-left: 3px solid #ff4b4b; }
/* Form Butonu */
[data-testid="stFormSubmitButton"] > button {
    background-color: #FFD700 !important; color: black !important; border: none; font-weight: bold; width: 100%; padding: 12px; font-size: 16px; margin-top: 15px;
}
</style>
""", unsafe_allow_html=True)

# API KONTROL (Hata vermez, uyarı verir)
API_KEY = st.secrets.get("GOOGLE_API_KEY", "")

# =========================================================
# SABİTLER
# =========================================================
ZODIAC = ["Koç", "Boğa", "İkizler", "Yengeç", "Aslan", "Başak", "Terazi", "Akrep", "Yay", "Oğlak", "Kova", "Balık"]
ZODIAC_SYMBOLS = ["♈", "♉", "♊", "♋", "♌", "♍", "♎", "♏", "♐", "♑", "♒", "♓"]
PLANET_SYMBOLS = {
    "Güneş": "☉", "Ay": "☽", "Merkür": "☿", "Venüs": "♀", "Mars": "♂",
    "Jüpiter": "♃", "Satürn": "♄", "Uranüs": "♅", "Neptün": "♆", "Plüton": "♇",
    "ASC": "ASC", "MC": "MC"
}

# =========================================================
# EKSİK OLAN FONKSİYON (GERİ EKLENDİ) [Image 24'teki Hata İçin]
# =========================================================
def city_to_latlon(city):
    try:
        headers = {"User-Agent": "AstroApp/1.0"}
        r = requests.get("https://nominatim.openstreetmap.org/search", 
                         params={"q": city, "format": "json", "limit": 1}, 
                         headers=headers, timeout=5)
        if r.status_code == 200 and len(r.json()) > 0:
            data = r.json()[0]
            return float(data["lat"]), float(data["lon"])
    except:
        return None, None
    return None, None

# =========================================================
# MATEMATİK MOTORU (Astro-Seek Hassasiyeti)
# =========================================================
def normalize(deg):
    return deg % 360

def dec_to_dms(deg):
    d = int(deg)
    m = int(round((deg - d) * 60))
    if m == 60: d += 1; m = 0
    return f"{d:02d}° {m:02d}'"

def sign_name(deg):
    return ZODIAC[int(deg / 30) % 12]

def get_house_equal(deg, asc_deg):
    # Equal House System (En garantisi, hata vermez, kayma yapmaz)
    return int(normalize(deg - asc_deg) / 30) + 1

# =========================================================
# ANA HESAPLAMA
# =========================================================
def calculate_chart(name, city, d_date, d_time, lat, lon, utc_offset, tr_mode, s_date, e_date):
    # 1. UTC Zamanı
    local_dt = datetime.combine(d_date, d_time)
    utc_dt = local_dt - timedelta(hours=utc_offset)
    date_str = utc_dt.strftime('%Y/%m/%d %H:%M:%S')

    # 2. PyEphem (Epoch AYARLAMADAN - Standart J2000)
    obs = ephem.Observer()
    obs.date = date_str
    obs.lat = str(lat)
    obs.lon = str(lon)
    
    # 3. ASC & MC Hesaplama
    sidereal_time = obs.sidereal_time()
    obl = math.radians(23.44) # Ecliptic eğikliği
    lat_rad = math.radians(lat)
    
    # MC
    mc_rad = math.atan2(math.tan(sidereal_time), math.cos(obl))
    mc_deg = normalize(math.degrees(mc_rad))
    if not (0 <= abs(mc_deg - math.degrees(sidereal_time)) <= 90 or 0 <= abs(mc_deg - math.degrees(sidereal_time) - 360) <= 90):
        mc_deg = normalize(mc_deg + 180)
        
    # ASC
    asc_rad = math.atan2(math.cos(sidereal_time), -(math.sin(sidereal_time)*math.cos(obl) + math.tan(lat_rad)*math.sin(obl)))
    asc_deg = normalize(math.degrees(asc_rad))

    # Ev Girişleri (Equal House - Görsel Hata Vermemesi İçin)
    cusps = {}
    for i in range(1, 13):
        cusps[i] = normalize(asc_deg + (i-1)*30)

    # 4. Gezegenler
    # (Unpack hatası olmaması için her zaman 4'lü tuple kullanacağız)
    visual_data = [
        ("ASC", sign_name(asc_deg), asc_deg, "ASC"),
        ("MC", sign_name(mc_deg), mc_deg, "MC")
    ]
    
    info_html = f"<div class='metric-box'>🌍 <b>Doğum:</b> {local_dt.strftime('%d.%m.%Y %H:%M')} (GMT+{utc_offset})</div>"
    info_html += f"<div class='metric-box'>🚀 <b>Yükselen:</b> {sign_name(asc_deg)} {dec_to_dms(asc_deg%30)}</div>"
    info_html += f"<div class='metric-box'>👑 <b>MC:</b> {sign_name(mc_deg)} {dec_to_dms(mc_deg%30)}</div>"
    
    ai_data = f"İsim: {name}\nŞehir: {city}\nASC: {sign_name(asc_deg)} {dec_to_dms(asc_deg)}\n"

    bodies = [
        ("Güneş", ephem.Sun()), ("Ay", ephem.Moon()), ("Merkür", ephem.Mercury()), 
        ("Venüs", ephem.Venus()), ("Mars", ephem.Mars()), ("Jüpiter", ephem.Jupiter()), 
        ("Satürn", ephem.Saturn()), ("Uranüs", ephem.Uranus()), ("Neptün", ephem.Neptune()), 
        ("Plüton", ephem.Pluto())
    ]

    for pname, body in bodies:
        body.compute(obs)
        deg = normalize(math.degrees(ephem.Ecliptic(body).lon))
        sign = sign_name(deg)
        house = get_house_equal(deg, asc_deg)
        
        # Listeye 4 parça ekle: (İsim, Burç, Derece, Sembol)
        visual_data.append((pname, sign, deg, PLANET_SYMBOLS.get(pname, "")))
        
        info_html += f"<div class='metric-box'><b>{pname}:</b> {sign} {dec_to_dms(deg%30)} ({house}. Ev)</div>"
        ai_data += f"{pname}: {sign} {dec_to_dms(deg%30)} ({house}. Ev)\n"

    # 5. Açılar
    aspects = []
    # visual_data[2:] ile sadece gezegenleri al (ASC/MC hariç)
    planet_objs = visual_data[2:]
    for i in range(len(planet_objs)):
        for j in range(i+1, len(planet_objs)):
            n1, _, d1, _ = planet_objs[i]
            n2, _, d2, _ = planet_objs[j]
            diff = abs(d1 - d2)
            if diff > 180: diff = 360 - diff
            
            asp = ""
            if diff <= 8: asp = "Kavuşum"
            elif 112 <= diff <= 128: asp = "Üçgen"
            elif 82 <= diff <= 98: asp = "Kare"
            elif 172 <= diff <= 180: asp = "Karşıt"
            
            if asp: aspects.append(f"{n1} {asp} {n2} ({int(diff)}°)")
    
    ai_data += "Açılar: " + ", ".join(aspects) + "\n"

    # 6. Transitler
    transit_html = ""
    if tr_mode:
        t_start = datetime.combine(s_date, d_time) - timedelta(hours=utc_offset)
        t_end = datetime.combine(e_date, d_time) - timedelta(hours=utc_offset)
        obs_tr = ephem.Observer()
        obs_tr.lat, obs_tr.lon = str(lat), str(lon)
        
        lines = []
        for pname in ["Jüpiter", "Satürn", "Plüton"]:
            body = {
                "Jüpiter": ephem.Jupiter(), "Satürn": ephem.Saturn(), "Plüton": ephem.Pluto()
            }[pname]
            
            obs_tr.date = t_start.strftime('%Y/%m/%d %H:%M:%S')
            body.compute(obs_tr)
            s1 = sign_name(math.degrees(ephem.Ecliptic(body).lon))
            
            obs_tr.date = t_end.strftime('%Y/%m/%d %H:%M:%S')
            body.compute(obs_tr)
            s2 = sign_name(math.degrees(ephem.Ecliptic(body).lon))
            
            lines.append(f"<div class='transit-box'><b>{pname}:</b> {s1} ➔ {s2}</div>")
            if s1 != s2: ai_data += f"TRANSIT: {pname} {s1}->{s2} burç değişimi.\n"
        
        transit_html = "".join(lines)

    return info_html, ai_data, visual_data, cusps, aspects, transit_html

# =========================================================
# HARİTA ÇİZİMİ
# =========================================================
def draw_chart(vis_data, cusps):
    fig = plt.figure(figsize=(8,8), facecolor='#0e1117')
    ax = fig.add_subplot(111, projection='polar')
    ax.set_facecolor('#1a1c24')
    ax.grid(False)
    ax.set_yticklabels([])
    
    # Haritayı ASC'ye hizala
    asc_deg = cusps[1]
    ax.set_theta_offset(np.pi - math.radians(asc_deg))
    ax.set_theta_direction(1)

    # Ev Çizgileri
    for i in range(1, 13):
        angle = math.radians(cusps[i])
        ax.plot([angle, angle], [0, 1.2], color='#444', linewidth=1, linestyle='--')
        mid = math.radians(cusps[i] + 15)
        ax.text(mid, 0.4, str(i), color='#666', ha='center', fontweight='bold')

    # Zodyak
    for i in range(12):
        angle = math.radians(i*30)
        ax.plot([angle, angle], [1, 1.2], color='#FFD700', alpha=0.5)
        mid = math.radians(i*30 + 15)
        ax.text(mid, 1.3, ZODIAC_SYMBOLS[i], color='white', fontsize=14, ha='center')

    # Gezegenler
    for name, sign, deg, sym in vis_data:
        rad = math.radians(deg)
        color = '#FF4B4B' if name in ["ASC", "MC"] else 'white'
        ax.plot(rad, 1.05, 'o', color=color, markersize=8)
        ax.text(rad, 1.15, sym, color=color, fontsize=11, ha='center', fontweight='bold')

    return fig

# =========================================================
# AI & PDF
# =========================================================
def get_ai_response(prompt):
    if not API_KEY: return "⚠️ API Key girilmedi."
    try:
        # Hata vermeyen model endpoint'i
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={API_KEY}"
        resp = requests.post(url, headers={'Content-Type':'application/json'}, data=json.dumps({"contents":[{"parts":[{"text":prompt}]}]}), timeout=8)
        
        if resp.status_code == 200:
            return resp.json()['candidates'][0]['content']['parts'][0]['text']
        elif resp.status_code == 429:
            return "⚠️ **KOTA DOLDU:** Google API kullanım limitiniz dolmuş. Yeni bir API anahtarı almanız gerekiyor. Ancak harita verileri aşağıdadır."
        else:
            return f"⚠️ AI Hatası: {resp.status_code}. (Veriler aşağıdadır)"
    except Exception as e:
        return f"⚠️ Bağlantı Sorunu: {str(e)}"

def create_pdf(name, text):
    try:
        pdf = FPDF(); pdf.add_page(); pdf.set_font("Arial", 'B', 16)
        pdf.cell(0, 10, clean_text_for_pdf(f"ANALIZ: {name}"), ln=True)
        pdf.set_font("Arial", '', 12); pdf.multi_cell(0, 8, clean_text_for_pdf(text))
        return pdf.output(dest='S').encode('latin-1', 'ignore')
    except: return None

# =========================================================
# ARAYÜZ (FORM İLE)
# =========================================================
st.title("🌌 Astro-Analiz Pro (Final)")

with st.sidebar:
    st.header("Giriş")
    with st.form("astro_form"):
        name = st.text_input("İsim", "Ziyaretçi")
        city = st.text_input("Şehir", "İstanbul")
        
        d_date = st.date_input("Doğum Tarihi", value=datetime(1980, 11, 26))
        d_time = st.time_input("Doğum Saati", value=datetime.strptime("16:00", "%H:%M"))
        
        utc_offset = st.number_input("GMT Farkı (Örn: 3)", value=3)
        
        st.write("---")
        use_city = st.checkbox("Şehir Koordinatlarını Bul", value=True)
        c1, c2 = st.columns(2)
        lat = c1.number_input("Enlem", 41.00)
        lon = c2.number_input("Boylam", 29.00)
        
        tr_mode = st.checkbox("Transit Modu")
        s_val = datetime.now().date(); e_val = s_val + timedelta(days=180)
        if tr_mode:
            s_date = st.date_input("Başlangıç", value=s_val)
            e_date = st.date_input("Bitiş", value=e_val)
        else:
            s_date = s_val; e_date = e_val
            
        q = st.text_area("Sorunuz", "Genel yorum")
        
        submit = st.form_submit_button("ANALİZİ BAŞLAT ✨")

if submit:
    try:
        if use_city and city:
            lt, ln = city_to_latlon(city)
            if lt: lat, lon = lt, ln
            
        info, ai_d, vis, cusps, asps, tr_html = calculate_chart(name, city, d_date, d_time, lat, lon, utc_offset, tr_mode, s_date, e_date)
        
        t1, t2, t3 = st.tabs(["📝 Yorum", "🗺️ Harita", "📊 Veriler"])
        
        with t1:
            with st.spinner("Yıldızlar inceleniyor..."):
                res = get_ai_response(f"Sen astrologsun. {name}, {city}. Soru: {q}.\nVeri: {ai_d}")
            st.markdown(res)
            pdf = create_pdf(name, res)
            if pdf: st.download_button("PDF İndir", pdf, "analiz.pdf")
            
        with t2:
            st.pyplot(draw_chart(vis, cusps))
            
        with t3:
            st.markdown(info, unsafe_allow_html=True)
            st.markdown("### Açılar")
            for a in asps: st.markdown(f"<div class='aspect-box'>{a}</div>", unsafe_allow_html=True)
            if tr_mode: 
                st.markdown("### Transitler")
                st.markdown(tr_html, unsafe_allow_html=True)

    except Exception as e:
        st.error(f"Beklenmeyen Hata: {str(e)}")
