import streamlit as st
import ephem
import math
from datetime import datetime
import requests
import json
import pytz
import matplotlib.pyplot as plt
import numpy as np
from fpdf import FPDF

# --- SAYFA AYARLARI ---
st.set_page_config(page_title="Astro-Analiz Pro", layout="wide", page_icon="🔮")

# --- MİSTİK CSS ---
st.markdown("""
    <style>
    .stApp { background: linear-gradient(to bottom, #0e1117, #24283b); color: #e0e0e0; }
    h1, h2, h3 { color: #FFD700 !important; font-family: 'Helvetica', sans-serif; text-shadow: 2px 2px 4px #000000; }
    .stAlert { background-color: #2b2d42; color: #fff; border: 1px solid #FFD700; }
    .stButton>button { background-color: #FFD700; color: #000; border-radius: 20px; border: none; font-weight: bold; padding: 10px 20px; box-shadow: 0px 0px 10px #FFD700; transition: all 0.3s ease;}
    .stButton>button:hover { background-color: #fff; color: #FFD700; box-shadow: 0px 0px 20px #FFD700; transform: scale(1.05);}
    [data-testid="stSidebar"] { background-color: #161a25; border-right: 1px solid #FFD700; }
    .metric-box { background-color: #1a1c24; padding: 15px; border-radius: 10px; border: 1px solid #444; margin-bottom: 10px; }
    </style>
    """, unsafe_allow_html=True)

# --- API KONTROL ---
if "GOOGLE_API_KEY" in st.secrets:
    api_key = st.secrets["GOOGLE_API_KEY"]
else:
    st.error("🚨 API Anahtarı bulunamadı!")
    st.stop()

# --- YARDIMCI FONKSİYONLAR ---
ZODIAC = ["Koç", "Boğa", "İkizler", "Yengeç", "Aslan", "Başak", "Terazi", "Akrep", "Yay", "Oğlak", "Kova", "Balık"]
ZODIAC_SYMBOLS = ["♈", "♉", "♊", "♋", "♌", "♍", "♎", "♏", "♐", "♑", "♒", "♓"]
PLANET_SYMBOLS = {"Güneş": "☉", "Ay": "☽", "Merkür": "☿", "Venüs": "♀", "Mars": "♂", "Jüpiter": "♃", "Satürn": "♄", "Uranüs": "♅", "Neptün": "♆", "Plüton": "♇"}

def dec_to_dms(deg):
    d = int(deg)
    m = int(round((deg - d) * 60))
    return f"{d:02d}° {m:02d}'"

def clean_text_for_pdf(text):
    replacements = {'ğ': 'g', 'Ğ': 'G', 'ş': 's', 'Ş': 'S', 'ı': 'i', 'İ': 'I', 'ü': 'u', 'Ü': 'U', 'ö': 'o', 'Ö': 'O', 'ç': 'c', 'Ç': 'C', '\n': ' '}
    for search, replace in replacements.items():
        text = text.replace(search, replace)
    return text

# --- HESAPLAMA ---
def calculate_chart_precise(name, d_date, d_time, lat_deg, lat_min, lon_deg, lon_min):
    try:
        lat = lat_deg + (lat_min / 60.0)
        lon = lon_deg + (lon_min / 60.0)
        local_dt = datetime.combine(d_date, d_time)
        tz = pytz.timezone('Europe/Istanbul') 
        local_dt_aware = tz.localize(local_dt)
        utc_dt = local_dt_aware.astimezone(pytz.utc)
        
        obs = ephem.Observer()
        obs.lat = str(lat)
        obs.lon = str(lon)
        obs.date = utc_dt
        obs.epoch = utc_dt 
        
        info_text = f"**UTC Zamanı:** {utc_dt.strftime('%H:%M')} (Hassas Hesaplama)\n\n"
        chart_data_for_ai = "Gezegenlerin Zodyak Konumları (0° Koç başlangıçlı):\n"
        visual_data = []
        
        bodies = [('Güneş', ephem.Sun()), ('Ay', ephem.Moon()), ('Merkür', ephem.Mercury()), 
                  ('Venüs', ephem.Venus()), ('Mars', ephem.Mars()), ('Jüpiter', ephem.Jupiter()),
                  ('Satürn', ephem.Saturn()), ('Uranüs', ephem.Uranus()), 
                  ('Neptün', ephem.Neptune()), ('Plüton', ephem.Pluto())]
        
        for n, b in bodies:
            b.compute(obs)
            ecl = ephem.Ecliptic(b)
            deg_total = math.degrees(ecl.lon)
            idx = int(deg_total / 30)
            sign = ZODIAC[idx % 12]
            sign_sym = ZODIAC_SYMBOLS[idx % 12]
            planet_sym = PLANET_SYMBOLS.get(n, n)
            deg_in_sign = deg_total % 30
            dms = dec_to_dms(deg_in_sign)
            
            # HTML formatında renkli gösterim
            line_html = f"<div class='metric-box'><b>{planet_sym} {n}</b>: {sign_sym} {sign} {dms}</div>"
            info_text += line_html
            
            chart_data_for_ai += f"- {n}: {deg_total:.2f} derece boylamında ({sign} burcunun {dms} derecesi).\n"
            visual_data.append((n, sign, deg_total, planet_sym))
            
        return info_text, chart_data_for_ai, visual_data, None
    except Exception as e: return None, None, None, str(e)

# --- HARİTA ÇİZİMİ (DÜZELTİLMİŞ) ---
def draw_chart_visual(bodies_data):
    fig = plt.figure(figsize=(10, 10), facecolor='#0e1117')
    ax = fig.add_subplot(111, projection='polar')
    ax.set_facecolor('#1a1c24')
    
    # 0 Dereceyi (Koç) Saat 9 yönüne (Batı) al ve saatin tersi yönünde döndür
    ax.set_theta_zero_location("W")
    ax.set_theta_direction(-1)

    ax.set_yticklabels([])
    ax.set_xticklabels([])
    ax.grid(False)
    ax.spines['polar'].set_visible(False)

    # Dış Halka
    circles = np.linspace(0, 2*np.pi, 100)
    ax.plot(circles, [1.2]*100, color='#FFD700', linewidth=2)

    for i in range(12):
        angle_deg = i * 30
        angle_rad = math.radians(angle_deg)
        ax.plot([angle_rad, angle_rad], [0.4, 1.2], color='#555', linewidth=1, linestyle=':')
        
        text_angle = math.radians(angle_deg + 15)
        rotation = angle
