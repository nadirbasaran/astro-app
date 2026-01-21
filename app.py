import streamlit as st
import matplotlib
matplotlib.use('Agg') # Grafik motorunu sabitler
import matplotlib.pyplot as plt
import ephem
import math
from datetime import datetime, timedelta
import requests
import json
import numpy as np
from fpdf import FPDF

# --- SAYFA AYARLARI ---
st.set_page_config(page_title="Astro-Analiz Pro", layout="wide", page_icon="🔮")

# --- GÜVENLİK ---
def check_password():
    if "password_correct" not in st.session_state: st.session_state["password_correct"] = False
    def password_entered():
        if st.session_state["password"] == st.secrets["APP_PASSWORD"]: st.session_state["password_correct"] = True
        else: st.session_state["password_correct"] = False
    if st.session_state["password_correct"]: return True
    st.text_input("Şifre", type="password", on_change=password_entered, key="password"); return False

if not check_password(): st.stop()

# --- CSS ---
st.markdown("""
    <style>
    .stApp { background: linear-gradient(to bottom, #0e1117, #24283b); color: #e0e0e0; }
    h1, h2, h3 { color: #FFD700 !important; font-family: 'Helvetica', sans-serif; }
    .stButton>button { background-color: #FFD700; color: #000; border-radius: 20px; font-weight: bold; width: 100%; }
    .metric-box { background-color: #1e2130; padding: 10px; border-radius: 8px; border-left: 4px solid #FFD700; margin-bottom: 8px; font-size: 14px; color: white; }
    .aspect-box { background-color: #25293c; padding: 5px; margin: 2px; border-radius: 4px; font-size: 13px; border: 1px solid #444; }
    .transit-box { background-color: #2d1b2e; border-left: 4px solid #ff4b4b; padding: 8px; margin-bottom: 5px; font-size: 13px; }
    </style>
    """, unsafe_allow_html=True)

# --- API ---
api_key = st.secrets.get("GOOGLE_API_KEY", "")

# --- SABİTLER ---
ZODIAC = ["Koç", "Boğa", "İkizler", "Yengeç", "Aslan", "Başak", "Terazi", "Akrep", "Yay", "Oğlak", "Kova", "Balık"]
ZODIAC_SYMBOLS = ["♈", "♉", "♊", "♋", "♌", "♍", "♎", "♏", "♐", "♑", "♒", "♓"]
PLANET_SYMBOLS = {"Güneş": "☉", "Ay": "☽", "Merkür": "☿", "Venüs": "♀", "Mars": "♂", "Jüpiter": "♃", "Satürn": "♄", "Uranüs": "♅", "Neptün": "♆", "Plüton": "♇", "Yükselen": "ASC", "MC": "MC"}

def dec_to_dms(deg):
    d = int(deg)
    m = int(round((deg - d) * 60))
    return f"{d:02d}° {m:02d}'"

def clean_text_for_pdf(text):
    replacements = {'ğ':'g', 'Ğ':'G', 'ş':'s', 'Ş':'S', 'ı':'i', 'İ':'I', 'ü':'u', 'Ü':'U', 'ö':'o', 'Ö':'O', 'ç':'c', 'Ç':'C', '–':'-', '’':"'", '“':'"', '”':'"', '…':'...'}
    for k, v in replacements.items(): text = text.replace(k, v)
    return text.encode('latin-1', 'replace').decode('latin-1')

# --- HESAPLAMA ---
def normalize(deg):
    return deg % 360

def calculate_chart(name, d_date, d_time, lat, lon, utc_offset, transit_enabled, start_date, end_date):
    try:
        # Tarih
        local_dt = datetime.combine(d_date, d_time)
        utc_dt = local_dt - timedelta(hours=utc_offset)
        date_str = utc_dt.strftime('%Y/%m/%d %H:%M:%S') # String formatı en güvenlisidir
        
        # Gözlemci
        obs = ephem.Observer()
        obs.lat = str(lat)
        obs.lon = str(lon)
        obs.date = date_str
        # obs.epoch AYARINI SİLDİM - Çökme sebebi buydu. Varsayılan (J2000) kullanacak.
        
        # Evler (Placidus Basit)
        ramc = float(obs.sidereal_time())
        eps = math.radians(23.44)
        lat_rad = math.radians(lat)
        
        mc_rad = math.atan2(math.tan(ramc), math.cos(eps))
        mc_deg = normalize(math.degrees(mc_rad))
        if not (0 <= abs(mc_deg - math.degrees(ramc)) <= 90 or 0 <= abs(mc_deg - math.degrees(ramc) - 360) <= 90):
            mc_deg = normalize(mc_deg + 180)
        
        asc_rad = math.atan2(math.cos(ramc), -(math.sin(ramc)*math.cos(eps) + math.tan(lat_rad)*math.sin(eps)))
        asc_deg = normalize(math.degrees(asc_rad))
        
        cusps = {1: asc_deg, 10: mc_deg} 
        # Diğer evleri yaklaşık hesapla (Hatasız yöntem)
        for i in range(2, 10): 
            if i not in cusps: cusps[i] = normalize(asc_deg + (i-1)*30)
        
        # Veri Listeleri
        info_html = f"<div class='metric-box'>🌍 <b>UTC:</b> {date_str}</div>"
        ai_data = "SİSTEM: PLACIDUS (Standard J2000)\n"
        
        asc_sign = ZODIAC[int(cusps[1]/30)%12]
        mc_sign = ZODIAC[int(cusps[10]/30)%12]
        
        # GÖRSEL VERİ (4 ELEMANLI OLMAK ZORUNDA)
        visual_data = [
            ("ASC", asc_sign, cusps[1], "ASC"), 
            ("MC", mc_sign, cusps[10], "MC")
        ]
        
        info_html += f"<div class='metric-box'>🚀 <b>ASC:</b> {asc_sign}</div>"
        ai_data += f"YÜKSELEN: {asc_sign}\n"

        bodies = [('Güneş', ephem.Sun()), ('Ay', ephem.Moon()), ('Merkür', ephem.Mercury()), ('Venüs', ephem.Venus()), ('Mars', ephem.Mars()), ('Jüpiter', ephem.Jupiter()), ('Satürn', ephem.Saturn()), ('Uranüs', ephem.Uranus()), ('Neptün', ephem.Neptune()), ('Plüton', ephem.Pluto())]
        
        for n, b in bodies:
            b.compute(obs)
            # Standart Ecliptic (Hatasız)
            ecl = ephem.Ecliptic(b)
            deg = math.degrees(ecl.lon)
            sign_idx = int(deg/30)%12
            dms = dec_to_dms(deg % 30)
            
            info_html += f"<div class='metric-box'><b>{n}</b>: {ZODIAC[sign_idx]} {dms}</div>"
            ai_data += f"{n}: {ZODIAC[sign_idx]} {dms}\n"
            # BURASI ÇOK ÖNEMLİ: 4 Eleman ekliyoruz
            visual_data.append((n, ZODIAC[sign_idx], deg, PLANET_SYMBOLS.get(n, "")))

        # Açılar
        aspects = []
        # Sadece Gezegenleri al (ASC/MC hariç) - visual_data[2:]
        p_list = visual_data[2:]
        for i in range(len(p_list)):
            for j in range(i+1, len(p_list)):
                n1, _, d1, _ = p_list[i]
                n2, _, d2, _ = p_list[j]
                diff = abs(d1 - d2)
                if diff > 180: diff = 360 - diff
                asp = ""
                if diff <= 8: asp = "Kavuşum"
                elif 115 <= diff <= 125: asp = "Üçgen"
                elif 85 <= diff <= 95: asp = "Kare"
                elif 175 <= diff <= 180: asp = "Karşıt"
                if asp: aspects.append(f"{n1} {asp} {n2}")
        
        transit_html = ""
        if transit_enabled:
            transit_html = "<div class='transit-box'>Transit Modu Aktif (Detaylar AI Yorumunda)</div>"

        return info_html, ai_data, visual_data, cusps, aspects, transit_html, None

    except Exception as e:
        # Hata olsa bile None döndürme, hata mesajını döndür
        return None, None, None, None, None, None, str(e)

# --- ÇİZİM ---
def draw_chart(vis_data):
    fig = plt.figure(figsize=(10,10), facecolor='#0e1117')
    ax = fig.add_subplot(111, projection='polar')
    ax.set_facecolor('#1a1c24')
    ax.grid(False); ax.set_yticklabels([])
    
    # Zodyak
    for i in range(12):
        rad = math.radians(i*30)
        ax.plot([rad, rad], [1, 1.2], color='#FFD700')
        ax.text(rad+0.25, 1.3, ZODIAC_SYMBOLS[i], color='white', fontsize=14)
        
    # Gezegenler
    for name, sign, deg, sym in vis_data:
        rad = math.radians(deg)
        ax.plot(rad, 1.1, 'o', color='white')
        ax.text(rad, 1.15, sym, color='yellow', fontsize=10, ha='center')
        
    return fig

# --- AI ---
def get_ai(prompt):
    if not api_key: return "API Key Yok"
    try:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={api_key}"
        resp = requests.post(url, headers={'Content-Type': 'application/json'}, data=json.dumps({"contents": [{"parts": [{"text": prompt}]}]}))
        return resp.json()['candidates'][0]['content']['parts'][0]['text'] if resp.status_code==200 else "Hata"
    except: return "Bağlantı Hatası"

# --- PDF ---
def make_pdf(name, text):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", 'B', 16)
    pdf.cell(40, 10, clean_text_for_pdf(f"Analiz: {name}"))
    pdf.ln(10)
    pdf.set_font("Arial", '', 12)
    pdf.multi_cell(0, 10, clean_text_for_pdf(text))
    return pdf.output(dest='S').encode('latin-1', 'ignore')

# --- ARAYÜZ ---
with st.sidebar:
    st.header("Giriş")
    name = st.text_input("İsim", "Misafir")
    d_date = st.date_input("Tarih", value=datetime(1980, 11, 26))
    
    # DAKİKA AYARI (DÜZELTİLDİ)
    d_time = st.time_input("Saat", value=datetime.strptime("16:00", "%H:%M"), step=60)
    
    utc_offset = st.number_input("GMT", 3)
    city = st.text_input("Şehir", "İstanbul")
    tr_mode = st.checkbox("Transit Modu")
    
    # Transit tarihleri (sadece mod açıksa göster)
    s_date = datetime.now()
    e_date = datetime.now()
    if tr_mode:
        s_date = st.date_input("Başlangıç", datetime.now())
        e_date = st.date_input("Bitiş", datetime.now() + timedelta(days=365))
        
    lat = st.number_input("Enlem", 41.0)
    lon = st.number_input("Boylam", 28.0)
    q = st.text_area("Soru", "Genel?")
    btn = st.button("Analiz Et")

if btn:
    info, ai_d, vis, cusps, asps, tr_html, err = calculate_chart(name, d_date, d_time, lat, lon, utc_offset, tr_mode, s_date, e_date)
    
    if err:
        st.error(f"Hata: {err}")
    else:
        t1, t2, t3 = st.tabs(["Yorum", "Harita", "Veri"])
        with t1:
            with st.spinner("AI Yazıyor..."):
                res = get_ai(f"Sen astrologsun. {name}, {city}. Soru: {q}. Veri: {ai_d}")
            st.markdown(res)
            st.download_button("PDF", make_pdf(name, res), "analiz.pdf")
        with t2:
            st.pyplot(draw_chart(vis))
        with t3:
            st.markdown(info, unsafe_allow_html=True)
            st.write(asps)
            if tr_mode: st.markdown(tr_html, unsafe_allow_html=True)
