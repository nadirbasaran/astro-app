import streamlit as st
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import ephem
import math
from datetime import datetime
import requests
import json
import pytz
import numpy as np
from fpdf import FPDF

# --- SAYFA AYARLARI ---
st.set_page_config(page_title="Astro-Analiz Pro", layout="wide", page_icon="🔮")

# --- CSS ---
st.markdown("""
    <style>
    .stApp { background: linear-gradient(to bottom, #0e1117, #24283b); color: #e0e0e0; }
    h1, h2, h3 { color: #FFD700 !important; font-family: 'Helvetica', sans-serif; text-shadow: 2px 2px 4px #000000; }
    .stButton>button { background-color: #FFD700; color: #000; border-radius: 20px; border: none; font-weight: bold; }
    [data-testid="stSidebar"] { background-color: #161a25; border-right: 1px solid #FFD700; }
    .metric-box { background-color: #1a1c24; padding: 10px; border-radius: 8px; border: 1px solid #444; margin-bottom: 5px; font-size: 14px; }
    </style>
    """, unsafe_allow_html=True)

# --- API ---
if "GOOGLE_API_KEY" in st.secrets:
    api_key = st.secrets["GOOGLE_API_KEY"]
else:
    st.error("🚨 API Anahtarı bulunamadı!")
    st.stop()

# --- YARDIMCI FONKSİYONLAR ---
ZODIAC = ["Koç", "Boğa", "İkizler", "Yengeç", "Aslan", "Başak", "Terazi", "Akrep", "Yay", "Oğlak", "Kova", "Balık"]
ZODIAC_SYMBOLS = ["♈", "♉", "♊", "♋", "♌", "♍", "♎", "♏", "♐", "♑", "♒", "♓"]
PLANET_SYMBOLS = {"Güneş": "☉", "Ay": "☽", "Merkür": "☿", "Venüs": "♀", "Mars": "♂", "Jüpiter": "♃", "Satürn": "♄", "Uranüs": "♅", "Neptün": "♆", "Plüton": "♇", "Yükselen": "ASC", "MC": "MC"}

def dec_to_dms(deg):
    d = int(deg)
    m = int(round((deg - d) * 60))
    return f"{d:02d}° {m:02d}'"

def clean_text_for_pdf(text):
    replacements = {'ğ':'g', 'Ğ':'G', 'ş':'s', 'Ş':'S', 'ı':'i', 'İ':'I', 'ü':'u', 'Ü':'U', 'ö':'o', 'Ö':'O', 'ç':'c', 'Ç':'C', '–':'-', '’':"'", '“':'"', '”':'"', '…':'...', '♈':'Koc', '♉':'Boga', '♊':'Ikizler', '♋':'Yengec', '♌':'Aslan', '♍':'Basak', '♎':'Terazi', '♏':'Akrep', '♐':'Yay', '♑':'Oglak', '♒':'Kova', '♓':'Balik', '☉':'', '☽':'', '☿':'', '♀':'', '♂':'', '♃':'', '♄':'', '♅':'', '♆':'', '♇':''}
    for k, v in replacements.items(): text = text.replace(k, v)
    return text.encode('latin-1', 'ignore').decode('latin-1')

# --- PLACIDUS HESAPLAMA ---
def calculate_placidus_cusps(utc_dt, lat, lon):
    obs = ephem.Observer()
    obs.date = utc_dt
    obs.lat, obs.lon = str(lat), str(lon)
    ramc = float(obs.sidereal_time())
    
    eps = math.radians(23.44)
    lat_rad = math.radians(lat)
    
    # MC ve IC
    mc_rad = math.atan2(math.tan(ramc), math.cos(eps))
    mc_deg = (math.degrees(mc_rad)) % 360
    ramc_deg = math.degrees(ramc)
    if not (0 <= abs(mc_deg - ramc_deg) <= 90 or 0 <= abs(mc_deg - ramc_deg - 360) <= 90):
        mc_deg = (mc_deg + 180) % 360
    ic_deg = (mc_deg + 180) % 360
    
    # ASC ve DSC
    asc_rad = math.atan2(math.cos(ramc), -(math.sin(ramc)*math.cos(eps) + math.tan(lat_rad)*math.sin(eps)))
    asc_deg = (math.degrees(asc_rad)) % 360
    dsc_deg = (asc_deg + 180) % 360
    
    # Ara Evler (Basitleştirilmiş Placidus)
    cusps = {1: asc_deg, 4: ic_deg, 7: dsc_deg, 10: mc_deg}
    diff_11_12 = (asc_deg - mc_deg) % 360
    cusps[11] = (mc_deg + diff_11_12/3) % 360
    cusps[12] = (mc_deg + 2*diff_11_12/3) % 360
    diff_2_3 = (ic_deg - asc_deg) % 360
    cusps[2] = (asc_deg + diff_2_3/3) % 360
    cusps[3] = (asc_deg + 2*diff_2_3/3) % 360
    cusps[5] = (cusps[11] + 180) % 360
    cusps[6] = (cusps[12] + 180) % 360
    cusps[8] = (cusps[2] + 180) % 360
    cusps[9] = (cusps[3] + 180) % 360
    
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

# --- DOĞRU HARİTA ÇİZİMİ ---
def draw_chart_visual(bodies_data, cusps):
    fig = plt.figure(figsize=(10, 10), facecolor='#0e1117')
    ax = fig.add_subplot(111, projection='polar')
    ax.set_facecolor('#1a1c24')
    
    # AYARLAR (Senin Onayladığın Düzen)
    asc_deg = cusps[1]
    # Yükselen'i Batı'ya (Saat 9) sabitlemek için ofset
    ax.set_theta_offset(np.pi - math.radians(asc_deg))
    # Saat yönünün TERSİNE (1, 2, 3...)
    ax.set_theta_direction(1)
    
    ax.set_yticklabels([])
    ax.set_xticklabels([])
    ax.grid(False)
    ax.spines['polar'].set_visible(False)

    # Ev Çizgileri
    for i in range(1, 13):
        angle = math.radians(cusps[i])
        ax.plot([angle, angle], [0, 1.2], color='#444', linewidth=1, linestyle='--')
        # Ev Numarası
        next_c = cusps[i+1] if i < 12 else cusps[1]
        diff = (next_c - cusps[i]) % 360
        mid = math.radians(cusps[i] + diff/2)
        ax.text(mid, 0.35, str(i), color='#888', ha='center')

    # Zodyak Halkası
    circles = np.linspace(0, 2*np.pi, 100)
    ax.plot(circles, [1.2]*100, color='#FFD700', linewidth=2)
    
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

# --- ANA HESAPLAMA ---
def calculate_all(name, d_date, d_time, lat, lon):
    try:
        local_dt = datetime.combine(d_date, d_time)
        tz = pytz.timezone('Europe/Istanbul')
        utc_dt = tz.localize(local_dt).astimezone(pytz.utc)
        
        cusps = calculate_placidus_cusps(utc_dt, lat, lon)
        obs = ephem.Observer(); obs.date=utc_dt; obs.lat=str(lat); obs.lon=str(lon)
        
        bodies = [('Güneş', ephem.Sun()), ('Ay', ephem.Moon()), ('Merkür', ephem.Mercury()), ('Venüs', ephem.Venus()), ('Mars', ephem.Mars()), ('Jüpiter', ephem.Jupiter()), ('Satürn', ephem.Saturn()), ('Uranüs', ephem.Uranus()), ('Neptün', ephem.Neptune()), ('Plüton', ephem.Pluto())]
        
        info_text = f"**UTC:** {utc_dt.strftime('%H:%M')}\n\n"
        ai_data = "SİSTEM: PLACIDUS\n"
        visual_data = [("ASC", "", cusps[1], "ASC"), ("MC", "", cusps[10], "MC")]
        
        for n, b in bodies:
            b.compute(obs)
            deg = math.degrees(ephem.Ecliptic(b).lon)
            sign = ZODIAC[int(deg/30)%12]
            h = get_house_of_planet(deg, cusps)
            dms = dec_to_dms(deg % 30)
            
            info_text += f"**{n}**: {sign} {dms} | {h}. Ev\n"
            ai_data += f"{n}: {sign} {dms} ({h}. Ev)\n"
            visual_data.append((n, sign, deg, PLANET_SYMBOLS.get(n, n[0])))
            
        return info_text, ai_data, visual_data, cusps, None
    except Exception as e: return None, None, None, None, str(e)

# --- PDF ---
def create_pdf(name, info, ai_text, tech):
    try:
        pdf = FPDF()
        pdf.add_page()
        pdf.set_font("Arial", 'B', 16); pdf.cell(0, 10, clean_text_for_pdf(f"ANALIZ: {name}"), ln=True, align='C')
        pdf.set_font("Arial", '', 12); pdf.cell(0, 10, clean_text_for_pdf(info), ln=True, align='C')
        pdf.ln(5)
        pdf.set_font("Arial", 'B', 14); pdf.cell(0, 10, "YORUM", ln=True)
        pdf.set_font("Arial", '', 11); pdf.multi_cell(0, 8, clean_text_for_pdf(ai_text))
        pdf.ln(5)
        pdf.set_font("Arial", 'B', 14); pdf.cell(0, 10, "VERILER", ln=True)
        pdf.set_font("Arial", '', 10); pdf.multi_cell(0, 8, clean_text_for_pdf(tech.replace('**','')))
        return pdf.output(dest='S').encode('latin-1', 'ignore')
    except: return None

# --- AI BAĞLANTISI (AKILLI MODEL SEÇİCİ) ---
def get_ai_response_smart(prompt):
    try:
        # 1. Modelleri Listele
        list_url = f"https://generativelanguage.googleapis.com/v1beta/models?key={api_key}"
        list_resp = requests.get(list_url)
        
        target_model = ""
        # Listeden 'generateContent' destekleyen ilk modeli bul
        if list_resp.status_code == 200:
            for m in list_resp.json().get('models', []):
                if 'generateContent' in m.get('supportedGenerationMethods', []):
                    target_model = m['name']
                    break
        
        # Eğer liste alamazsak varsayılanı dene
        if not target_model: target_model = "models/gemini-1.5-flash"
        
        # 2. İsteği Gönder
        url = f"https://generativelanguage.googleapis.com/v1beta/{target_model}:generateContent?key={api_key}"
        headers = {'Content-Type': 'application/json'}
        data = {"contents": [{"parts": [{"text": prompt}]}]}
        
        resp = requests.post(url, headers=headers, data=json.dumps(data))
        if resp.status_code == 200:
            return resp.json()['candidates'][0]['content']['parts'][0]['text']
        else:
            return f"⚠️ AI Hatası ({resp.status_code}): {resp.text}"
            
    except Exception as e: return f"Bağlantı Hatası: {str(e)}"

# --- ARAYÜZ ---
st.title("🌌 Astro-Analiz Pro")
with st.sidebar:
    name = st.text_input("İsim", "Ziyaretçi")
    d_date = st.date_input("Tarih", value=datetime(1980, 11, 26))
    d_time = st.time_input("Saat", value=datetime.strptime("16:00", "%H:%M"))
    c1, c2 = st.columns(2)
    lat = c1.number_input("Enlem", 41.0) + c2.number_input("Dakika", 1.0)/60
    c3, c4 = st.columns(2)
    lon = c3.number_input("Boylam", 28.0) + c4.number_input("Dakika", 57.0)/60
    q = st.text_area("Soru", "Genel yorum?")
    btn = st.button("Analiz Et ✨")

if btn:
    info_text, ai_data, vis_data, cusps, err = calculate_all(name, d_date, d_time, lat, lon)
    
    if err: st.error(err)
    else:
        tab1, tab2, tab3 = st.tabs(["📝 Yorum", "🗺️ Harita", "📊 Veri"])
        
        # Verileri Hesapla ve AI'ya Gönder
        with st.spinner("Yıldızlar okunuyor..."):
            ai_reply = get_ai_response_smart(f"Sen astrologsun. Kişi: {name}. Veriler:\n{ai_data}\nSoru: {q}\nYorumla.")
        
        with tab1:
            st.markdown(ai_reply)
            # PDF İndir (AI yanıtı varsa)
            if "Hata" not in ai_reply:
                pdf = create_pdf(name, f"{d_date} {d_time}", ai_reply, info_text)
                if pdf: st.download_button("PDF İndir", pdf, "analiz.pdf", "application/pdf")
        
        with tab2:
            fig = draw_chart_visual(vis_data, cusps)
            st.pyplot(fig)
            
        with tab3:
            st.markdown(info_text)
