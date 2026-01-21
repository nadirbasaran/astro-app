import streamlit as st
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import ephem
import math
from datetime import datetime, timedelta
import requests
import json
import pytz
import numpy as np
from fpdf import FPDF

# --- SAYFA AYARLARI ---
st.set_page_config(page_title="Astro-Analiz Pro", layout="wide", page_icon="🔮")

# --------------------------------------------------------------------------
# 🔒 GÜVENLİK DUVARI
# --------------------------------------------------------------------------
def check_password():
    if "password_correct" not in st.session_state:
        st.session_state["password_correct"] = False

    def password_entered():
        if st.session_state["password"] == st.secrets["APP_PASSWORD"]:
            st.session_state["password_correct"] = True
            del st.session_state["password"]
        else:
            st.session_state["password_correct"] = False

    if st.session_state["password_correct"]:
        return True

    st.markdown("""<style>.stTextInput > label { display:none; }</style>""", unsafe_allow_html=True)
    col1, col2, col3 = st.columns([1,2,1])
    with col2:
        st.warning("🔒 Erişim İzni Gerekiyor")
        st.text_input("Şifre", type="password", on_change=password_entered, key="password")
    return False

if not check_password():
    st.stop()

# --- CSS ---
st.markdown("""
    <style>
    .stApp { background: linear-gradient(to bottom, #0e1117, #24283b); color: #e0e0e0; }
    h1, h2, h3 { color: #FFD700 !important; font-family: 'Helvetica', sans-serif; }
    .stButton>button { background-color: #FFD700; color: #000; border-radius: 20px; font-weight: bold; width: 100%; }
    [data-testid="stSidebar"] { background-color: #161a25; border-right: 1px solid #FFD700; }
    .metric-box { background-color: #1e2130; padding: 10px; border-radius: 8px; border-left: 4px solid #FFD700; margin-bottom: 8px; font-size: 14px; color: white; }
    .metric-box b { color: #FFD700; }
    .aspect-box { background-color: #25293c; padding: 5px; margin: 2px; border-radius: 4px; font-size: 13px; border: 1px solid #444; }
    .transit-box { background-color: #2d1b2e; border-left: 4px solid #ff4b4b; padding: 8px; margin-bottom: 5px; font-size: 13px; }
    </style>
    """, unsafe_allow_html=True)

# --- API ---
if "GOOGLE_API_KEY" in st.secrets:
    api_key = st.secrets["GOOGLE_API_KEY"]
else:
    st.error("🚨 API Anahtarı bulunamadı!")
    st.stop()

# --- SABİTLER ---
ZODIAC = ["Koç", "Boğa", "İkizler", "Yengeç", "Aslan", "Başak", "Terazi", "Akrep", "Yay", "Oğlak", "Kova", "Balık"]
ZODIAC_SYMBOLS = ["♈", "♉", "♊", "♋", "♌", "♍", "♎", "♏", "♐", "♑", "♒", "♓"]
PLANET_SYMBOLS = {"Güneş": "☉", "Ay": "☽", "Merkür": "☿", "Venüs": "♀", "Mars": "♂", "Jüpiter": "♃", "Satürn": "♄", "Uranüs": "♅", "Neptün": "♆", "Plüton": "♇", "Yükselen": "ASC", "MC": "MC"}

def dec_to_dms(deg):
    d = int(deg)
    m = int(round((deg - d) * 60))
    return f"{d:02d}° {m:02d}'"

def clean_text_for_pdf(text):
    replacements = {'ğ':'g', 'Ğ':'G', 'ş':'s', 'Ş':'S', 'ı':'i', 'İ':'I', 'ü':'u', 'Ü':'U', 'ö':'o', 'Ö':'O', 'ç':'c', 'Ç':'C', '–':'-', '’':"'", '“':'"', '”':'"'}
    for k, v in replacements.items(): text = text.replace(k, v)
    return text.encode('latin-1', 'ignore').decode('latin-1')

# --- HESAPLAMA MOTORU (STABİL PORPHYRY/PLACIDUS APPROX) ---
def normalize(deg):
    return deg % 360

def calculate_unequal_houses(utc_dt, lat, lon):
    # Bu yöntem sistemi çökertmeden "Eşit Olmayan" (Unequal) evleri hesaplar.
    # MC ve ASC'yi kesin hesaplar, aralarını orantısal böler.
    obs = ephem.Observer()
    obs.date = utc_dt
    obs.lat, obs.lon = str(lat), str(lon)
    
    ramc = float(obs.sidereal_time())
    eps = math.radians(23.44)
    lat_rad = math.radians(lat)
    
    # MC (10. Ev)
    mc_rad = math.atan2(math.tan(ramc), math.cos(eps))
    mc_deg = normalize(math.degrees(mc_rad))
    if not (0 <= abs(mc_deg - math.degrees(ramc)) <= 90 or 0 <= abs(mc_deg - math.degrees(ramc) - 360) <= 90):
        mc_deg = normalize(mc_deg + 180)
    ic_deg = normalize(mc_deg + 180)
    
    # ASC (1. Ev)
    asc_rad = math.atan2(math.cos(ramc), -(math.sin(ramc)*math.cos(eps) + math.tan(lat_rad)*math.sin(eps)))
    asc_deg = normalize(math.degrees(asc_rad))
    dsc_deg = normalize(asc_deg + 180)

    cusps = {1: asc_deg, 4: ic_deg, 7: dsc_deg, 10: mc_deg}
    
    # Ara Evleri Hesapla (Eşit Olmayan Yay Bölme)
    # MC'den ASC'ye giden yay
    q4_arc = (asc_deg - mc_deg) % 360
    cusps[11] = normalize(mc_deg + q4_arc / 3)
    cusps[12] = normalize(mc_deg + 2 * q4_arc / 3)
    
    # IC'den ASC'ye giden yay (Doğu yarımküre altı) - Hata düzeltme için ASC'den IC'ye ters bakalım
    # ASC(1) -> IC(4)
    q1_arc = (ic_deg - asc_deg) % 360
    cusps[2] = normalize(asc_deg + q1_arc / 3)
    cusps[3] = normalize(asc_deg + 2 * q1_arc / 3)
    
    # Karşıt Evler
    cusps[5] = normalize(cusps[11] + 180)
    cusps[6] = normalize(cusps[12] + 180)
    cusps[8] = normalize(cusps[2] + 180)
    cusps[9] = normalize(cusps[3] + 180)
    
    return cusps

def get_house_of_planet(deg, cusps):
    for i in range(1, 13):
        start = cusps[i]
        end = cusps[i+1] if i < 12 else cusps[1]
        if start < end:
            if start <= deg < end: return i
        else:
            if start <= deg or deg < end: return i
    return 1

def calculate_aspects(bodies, orb=8):
    aspects = []
    planet_list = [(n, d) for n, _, d, _ in bodies]
    for i in range(len(planet_list)):
        for j in range(i+1, len(planet_list)):
            p1, d1 = planet_list[i]
            p2, d2 = planet_list[j]
            diff = abs(d1 - d2)
            if diff > 180: diff = 360 - diff
            
            asp = ""
            if diff <= orb: asp = "Kavuşum"
            elif 60-6 <= diff <= 60+6: asp = "Sekstil"
            elif 90-orb <= diff <= 90+orb: asp = "Kare"
            elif 120-orb <= diff <= 120+orb: asp = "Üçgen"
            elif 180-orb <= diff <= 180+orb: asp = "Karşıt"
            if asp: aspects.append(f"{p1} {asp} {p2}")
    return aspects

def calculate_transits(birth_bodies, start_dt, end_dt, lat, lon):
    obs = ephem.Observer(); obs.lat, obs.lon = str(lat), str(lon)
    planets = [('Jüpiter', ephem.Jupiter()), ('Satürn', ephem.Saturn()), ('Uranüs', ephem.Uranus()), ('Neptün', ephem.Neptune()), ('Plüton', ephem.Pluto())]
    report, display = [], []
    
    for n, b in planets:
        obs.date = start_dt; b.compute(obs); d1 = math.degrees(ephem.Ecliptic(b).lon)
        obs.date = end_dt; b.compute(obs); d2 = math.degrees(ephem.Ecliptic(b).lon)
        s1 = ZODIAC[int(d1/30)%12]
        s2 = ZODIAC[int(d2/30)%12]
        
        display.append(f"<b>{n}:</b> {s1} -> {s2}")
        report.append(f"Transit {n}: {s1} burcundan {s2} burcuna.")
        
        for natal_n, _, natal_deg, _ in birth_bodies:
            for d in [d1, d2]:
                diff = abs(d - natal_deg)
                if diff > 180: diff = 360 - diff
                if diff <= 4:
                    display.append(f"⚠️ {n} -> {natal_n} (Etkileşim)")
                    report.append(f"{n}, {natal_n} ile temas ediyor.")
    return "\n".join(set(report)), list(set(display)) # Tekrarı önle

# --- GÖRSELLEŞTİRME (SAĞLAM RENDER) ---
def draw_chart_visual(bodies_data, cusps):
    fig = plt.figure(figsize=(10, 10), facecolor='#0e1117')
    ax = fig.add_subplot(111, projection='polar')
    ax.set_facecolor('#1a1c24')
    
    # ASC Sol (9 Yönü)
    asc_rad = math.radians(cusps[1])
    ax.set_theta_offset(np.pi - asc_rad)
    ax.set_theta_direction(1) # CCW
    ax.grid(False); ax.set_yticklabels([]); ax.set_xticklabels([])

    # Ev Çizgileri (Unequal)
    for i in range(1, 13):
        rad = math.radians(cusps[i])
        ax.plot([rad, rad], [0, 1.2], color='#444', linewidth=1, linestyle='--')
        
        # Numara Konumu
        next_c = cusps[i+1] if i < 12 else cusps[1]
        diff = (next_c - cusps[i]) % 360
        mid = math.radians(cusps[i] + diff/2)
        ax.text(mid, 0.4, str(i), color='#888', ha='center', fontweight='bold')

    # Zodyak
    ax.plot(np.linspace(0, 2*np.pi, 100), [1.2]*100, color='#FFD700', linewidth=2)
    for i in range(12):
        deg = i * 30 + 15
        rad = math.radians(deg)
        rot = deg - 180
        ax.text(rad, 1.3, ZODIAC_SYMBOLS[i], ha='center', color='#FFD700', fontsize=16, rotation=rot)
        sep = math.radians(i*30)
        ax.plot([sep, sep], [1.15, 1.25], color='#FFD700')

    # Gezegenler
    for name, sign, deg, sym in bodies_data:
        rad = math.radians(deg)
        color = '#FF4B4B' if name in ['ASC', 'MC'] else 'white'
        size = 14 if name in ['ASC', 'MC'] else 11
        ax.plot(rad, 1.05, 'o', color=color, markersize=size, markeredgecolor='#FFD700')
        ax.text(rad, 1.17, sym, color=color, fontsize=12, ha='center')
    return fig

# --- ANA İŞLEM ---
def calculate_all(name, d_date, d_time, lat, lon, transit_enabled, start_date, end_date):
    try:
        local_dt = datetime.combine(d_date, d_time)
        tz = pytz.timezone('Europe/Istanbul')
        utc_dt = tz.localize(local_dt).astimezone(pytz.utc)
        
        # 1. HESAPLA (PATLAMAYAN YÖNTEM)
        cusps = calculate_unequal_houses(utc_dt, lat, lon)
        obs = ephem.Observer(); obs.date=utc_dt; obs.lat=str(lat); obs.lon=str(lon)
        
        bodies = [('Güneş', ephem.Sun()), ('Ay', ephem.Moon()), ('Merkür', ephem.Mercury()), ('Venüs', ephem.Venus()), ('Mars', ephem.Mars()), ('Jüpiter', ephem.Jupiter()), ('Satürn', ephem.Saturn()), ('Uranüs', ephem.Uranus()), ('Neptün', ephem.Neptune()), ('Plüton', ephem.Pluto())]
        
        info_html = f"<div class='metric-box'>🌍 <b>UTC:</b> {utc_dt.strftime('%H:%M')}</div>"
        ai_data = "SİSTEM: PLACIDUS/UNEQUAL\n"
        
        asc_sign = ZODIAC[int(cusps[1]/30)%12]
        mc_sign = ZODIAC[int(cusps[10]/30)%12]
        visual_data = [("ASC", asc_sign, cusps[1], "ASC"), ("MC", mc_sign, cusps[10], "MC")]
        
        info_html += f"<div class='metric-box'>🚀 <b>ASC:</b> {asc_sign} {dec_to_dms(cusps[1]%30)}</div>"
        info_html += f"<div class='metric-box'>👑 <b>MC:</b> {mc_sign} {dec_to_dms(cusps[10]%30)}</div><br>"
        ai_data += f"YÜKSELEN: {asc_sign}\nMC: {mc_sign}\n"

        for n, b in bodies:
            b.compute(obs)
            deg = math.degrees(ephem.Ecliptic(b).lon)
            sign_idx = int(deg/30)%12
            h = get_house_of_planet(deg, cusps)
            dms = dec_to_dms(deg % 30)
            
            info_html += f"<div class='metric-box'><b>{n}</b>: {ZODIAC_SYMBOLS[sign_idx]} {ZODIAC[sign_idx]} {dms} | <b>{h}. Ev</b></div>"
            ai_data += f"{n}: {ZODIAC[sign_idx]} {dms} ({h}. Ev)\n"
            visual_data.append((n, ZODIAC[sign_idx], deg, PLANET_SYMBOLS.get(n, "")))
            
        aspects = calculate_aspects(visual_data)
        ai_data += "\nAÇILAR:\n" + ", ".join(aspects)
        
        transit_html = ""
        if transit_enabled:
            tr_start = tz.localize(datetime.combine(start_date, d_time)).astimezone(pytz.utc)
            tr_end = tz.localize(datetime.combine(end_date, d_time)).astimezone(pytz.utc)
            rep, disp = calculate_transits(visual_data, tr_start, tr_end, lat, lon)
            ai_data += f"\n\nTRANSIT ({start_date}-{end_date}):\n{rep}"
            transit_html = "<br><h4>⏳ Transitler</h4>" + "".join([f"<div class='transit-box'>{l}</div>" for l in disp])

        return info_html, ai_data, visual_data, cusps, aspects, transit_html, None
    except Exception as e: return None, None, None, None, None, None, str(e)

# --- PDF & AI ---
def create_pdf(name, info, ai_text):
    try:
        pdf = FPDF()
        pdf.add_page()
        pdf.set_font("Arial", 'B', 16); pdf.cell(0, 10, clean_text_for_pdf(f"ANALIZ: {name}"), ln=True, align='C')
        pdf.set_font("Arial", '', 12); pdf.cell(0, 10, clean_text_for_pdf(info), ln=True, align='C')
        pdf.ln(5)
        pdf.set_font("Arial", 'B', 14); pdf.cell(0, 10, "YORUM", ln=True)
        pdf.set_font("Arial", '', 11); pdf.multi_cell(0, 8, clean_text_for_pdf(ai_text))
        return pdf.output(dest='S').encode('latin-1', 'ignore')
    except: return None

def get_ai(prompt):
    try:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={api_key}"
        resp = requests.post(url, headers={'Content-Type': 'application/json'}, data=json.dumps({"contents": [{"parts": [{"text": prompt}]}]}))
        return resp.json()['candidates'][0]['content']['parts'][0]['text'] if resp.status_code==200 else "AI Hatası"
    except Exception as e: return str(e)

# --- ARAYÜZ ---
st.title("🌌 Astro-Analiz Pro (Stable)")
with st.sidebar:
    st.header("Giriş")
    name = st.text_input("İsim", "Ziyaretçi")
    d_date = st.date_input("Tarih", value=datetime(1980, 11, 26))
    d_time = st.time_input("Saat", value=datetime.strptime("16:00", "%H:%M"), step=60)
    city = st.text_input("Şehir", "İstanbul")
    
    st.write("---")
    transit_mode = st.checkbox("Transit Modu")
    start_date = datetime.now().date()
    end_date = datetime.now().date() + timedelta(days=365)
    if transit_mode:
        c1, c2 = st.columns(2)
        start_date = c1.date_input("Başlangıç", start_date)
        end_date = c2.date_input("Bitiş", end_date)
        
    st.write("---")
    st.write("📍 **Koordinat**")
    c1, c2 = st.columns(2)
    lat = c1.number_input("Enlem", 41.0) + c2.number_input("Dakika", 1.0)/60
    c3, c4 = st.columns(2)
    lon = c3.number_input("Boylam", 28.0) + c4.number_input("Dakika", 57.0)/60
    q = st.text_area("Soru", "Genel yorum?")
    btn = st.button("Analiz Et ✨")

if btn:
    info_html, ai_data, vis_data, cusps, aspects, transit_html, err = calculate_all(name, d_date, d_time, lat, lon, transit_mode, start_date, end_date)
    
    if err: st.error(err)
    else:
        tab1, tab2, tab3 = st.tabs(["📝 Yorum", "🗺️ Harita", "📊 Veri"])
        with st.spinner("Analiz ediliyor..."):
            ai_reply = get_ai(f"Sen astrologsun. Kişi: {name}, {city}. Soru: {q}.\n\nVERİLER:\n{ai_data}\n\nGÖREV: Transit varsa öngörü yap. Soruyu cevapla.")
        
        with tab1:
            st.markdown(ai_reply)
            pdf = create_pdf(name, f"{d_date} - {city}", ai_reply)
            if pdf: st.download_button("PDF İndir", pdf, "analiz.pdf", "application/pdf")
        with tab2:
            st.pyplot(draw_chart_visual(vis_data, cusps))
        with tab3:
            c1, c2 = st.columns(2)
            with c1: st.markdown(info_html, unsafe_allow_html=True)
            with c2: 
                st.markdown("### AÇILAR")
                for a in aspects: st.markdown(f"<div class='aspect-box'>{a}</div>", unsafe_allow_html=True)
                if transit_mode: st.markdown(transit_html, unsafe_allow_html=True)
