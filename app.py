import streamlit as st
import ephem
import math
from datetime import datetime
import requests
import json
import pytz
import matplotlib.pyplot as plt
from fpdf import FPDF

# --- SAYFA AYARLARI ---
st.set_page_config(page_title="Astro-Analiz Pro", layout="wide", page_icon="🔮")

# --- MİSTİK CSS ---
st.markdown("""
    <style>
    .stApp { background: linear-gradient(to bottom, #0e1117, #1a1c24); color: #e0e0e0; }
    h1, h2, h3 { color: #FFD700 !important; font-family: 'Helvetica', sans-serif; }
    .stAlert { background-color: #2b2d42; color: #fff; border: 1px solid #FFD700; }
    .stButton>button { background-color: #FFD700; color: #000; border-radius: 10px; border: none; font-weight: bold; }
    .stButton>button:hover { background-color: #FFA500; color: #fff; }
    [data-testid="stSidebar"] { background-color: #161a25; border-right: 1px solid #333; }
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

def dec_to_dms(deg):
    d = int(deg)
    m = int(round((deg - d) * 60)) # Dakikayı yuvarla
    return f"{d}° {m:02d}'"

def clean_text_for_pdf(text):
    replacements = {'ğ': 'g', 'Ğ': 'G', 'ş': 's', 'Ş': 'S', 'ı': 'i', 'İ': 'I', 'ü': 'u', 'Ü': 'U', 'ö': 'o', 'Ö': 'O', 'ç': 'c', 'Ç': 'C'}
    for search, replace in replacements.items():
        text = text.replace(search, replace)
    return text

# --- HESAPLAMA (TROPİKAL ZODYAK + HASSAS GİRİŞ) ---
def calculate_chart_precise(name, d_date, d_time, lat_deg, lat_min, lon_deg, lon_min):
    try:
        # 1. Koordinatları Hassas Birleştir
        lat = lat_deg + (lat_min / 60.0)
        lon = lon_deg + (lon_min / 60.0)
        
        # 2. Zaman Dilimi ve UTC
        local_dt = datetime.combine(d_date, d_time)
        tz = pytz.timezone('Europe/Istanbul') 
        local_dt_aware = tz.localize(local_dt)
        utc_dt = local_dt_aware.astimezone(pytz.utc)
        
        # 3. NASA Gözlemcisi (KRİTİK AYARLAR)
        obs = ephem.Observer()
        obs.lat = str(lat)
        obs.lon = str(lon)
        obs.date = utc_dt
        # ÖNEMLİ: Epoch'u o günün tarihine çekiyoruz (Tropical Zodiac için şart!)
        # Bu satır o 16 dakikalık kaymayı düzeltir.
        obs.epoch = utc_dt 
        
        info_text = f"**HESAPLANAN UTC:** {utc_dt.strftime('%H:%M')} (Epoch: Date)\n\n"
        chart_data_for_ai = "Gezegen Konumları:\n"
        visual_data = []
        
        bodies = [('Güneş', ephem.Sun()), ('Ay', ephem.Moon()), ('Merkür', ephem.Mercury()), 
                  ('Venüs', ephem.Venus()), ('Mars', ephem.Mars()), ('Jüpiter', ephem.Jupiter()),
                  ('Satürn', ephem.Saturn()), ('Uranüs', ephem.Uranus()), 
                  ('Neptün', ephem.Neptune()), ('Plüton', ephem.Pluto())]
        
        for n, b in bodies:
            b.compute(obs)
            ecl = ephem.Ecliptic(b) # Ecliptic koordinata çevir
            deg_total = math.degrees(ecl.lon)
            
            idx = int(deg_total / 30)
            sign = ZODIAC[idx % 12]
            deg_in_sign = deg_total % 30
            dms = dec_to_dms(deg_in_sign)
            
            line = f"- {n}: {sign} {dms}\n"
            info_text += line
            chart_data_for_ai += f"{n} {sign} Burcunda, {dms} derecesinde.\n"
            visual_data.append((n, sign, deg_total))
            
        return info_text, chart_data_for_ai, visual_data, None
    except Exception as e: return None, None, None, str(e)

# --- HARİTA ÇİZİMİ ---
def draw_chart_visual(bodies_data):
    fig = plt.figure(figsize=(8, 8), facecolor='#0e1117')
    ax = fig.add_subplot(111, projection='polar')
    ax.set_facecolor('#1a1c24')
    for i in range(12):
        angle = math.radians(i * 30)
        ax.plot([angle, angle], [0, 1], color='#444', linewidth=1)
        ax.text(angle + math.radians(15), 1.1, ZODIAC[i], ha='center', color='#FFD700', fontsize=10)
    for name, sign, deg_total in bodies_data:
        angle_rad = math.radians(deg_total)
        ax.plot(angle_rad, 0.8, 'o', color='white', markersize=8, markeredgecolor='#FFD700')
        ax.text(angle_rad, 0.9, name[:2], color='white', fontsize=9, fontweight='bold', ha='center')
    ax.set_yticklabels([])
    ax.set_xticklabels([])
    ax.grid(False)
    ax.spines['polar'].set_visible(False)
    return fig

# --- PDF ---
def create_pdf(name, birth_info, ai_comment, technical_data):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", 'B', 16)
    pdf.cell(200, 10, txt=clean_text_for_pdf(f"Astro-Analiz: {name}"), ln=True, align='C')
    pdf.ln(10)
    pdf.set_font("Arial", size=12)
    pdf.cell(200, 10, txt=clean_text_for_pdf(f"Dogum: {birth_info}"), ln=True)
    pdf.ln(5)
    pdf.set_font("Arial", 'B', 12)
    pdf.cell(200, 10, txt="Teknik Veriler:", ln=True)
    pdf.set_font("Arial", size=10)
    pdf.multi_cell(0, 8, txt=clean_text_for_pdf(technical_data))
    pdf.ln(5)
    pdf.set_font("Arial", 'B', 12)
    pdf.cell(200, 10, txt="Yorum:", ln=True)
    pdf.set_font("Arial", size=11)
    pdf.multi_cell(0, 8, txt=clean_text_for_pdf(ai_comment))
    return pdf.output(dest='S').encode('latin-1', 'ignore')

# --- AI İSTEK ---
def get_ai_response(prompt):
    try:
        list_url = f"https://generativelanguage.googleapis.com/v1beta/models?key={api_key}"
        list_resp = requests.get(list_url)
        target_model = ""
        for m in list_resp.json().get('models', []):
            if 'generateContent' in m.get('supportedGenerationMethods', []):
                target_model = m['name']
                break
        if not target_model: return "Model bulunamadı."
        url = f"https://generativelanguage.googleapis.com/v1beta/{target_model}:generateContent?key={api_key}"
        headers = {'Content-Type': 'application/json'}
        data = {"contents": [{"parts": [{"text": prompt}]}]}
        resp = requests.post(url, headers=headers, data=json.dumps(data))
        if resp.status_code == 200:
            return resp.json()['candidates'][0]['content']['parts'][0]['text']
        else: return f"Hata: {resp.text}"
    except Exception as e: return str(e)

# --- ARAYÜZ YAPISI ---
st.title("🌌 Astro-Analiz (Hassas Mod)")
st.caption("NASA Verisi + Tropical Zodiac + AI Yorumlama")

with st.sidebar:
    st.header("Giriş Paneli")
    name = st.text_input("İsim", "Ziyaretçi")
    d_date = st.date_input("Tarih", value=datetime(1980, 11, 26))
    d_time = st.time_input("Saat", value=datetime.strptime("16:00", "%H:%M"))
    city = st.text_input("Şehir", "İstanbul")
    
    st.write("---")
    st.write("📍 **Hassas Koordinat Girişi**")
    
    # Koordinatları Ayırdık (Derece / Dakika)
    col_lat1, col_lat2 = st.columns(2)
    lat_deg = col_lat1.number_input("Enlem (°)", value=41, step=1)
    lat_min = col_lat2.number_input("Enlem (')", value=1, step=1) # 41° 1'
    
    col_lon1, col_lon2 = st.columns(2)
    lon_deg = col_lon1.number_input("Boylam (°)", value=28, step=1)
    lon_min = col_lon2.number_input("Boylam (')", value=57, step=1) # 28° 57'
    
    q = st.text_area("Soru", "Kariyerim hakkında yorumlar mısın?")
    btn = st.button("Analiz Et ✨", type="primary")

if btn:
    display_data, ai_data, visual_data, err = calculate_chart_precise(
        name, d_date, d_time, lat_deg, lat_min, lon_deg, lon_min
    )
    
    if err:
        st.error(err)
    else:
        tab1, tab2, tab3 = st.tabs(["📝 Yorum", "🗺️ Harita", "📊 Teknik Veri"])
        
        with st.spinner("Kozmos ile bağlantı kuruluyor..."):
            prompt = f"Sen mistik bir astrologsun. İsim: {name}, Yer: {city}. Soru: {q}.\n\n{ai_data}\n\nLütfen detaylı yorumla."
            ai_reply = get_ai_response(prompt)
        
        with tab1:
            st.markdown(ai_reply)
            birth_info = f"{d_date.strftime('%d.%m.%Y')} - {d_time.strftime('%H:%M')} - {city}"
            pdf_bytes = create_pdf(name, birth_info, ai_reply, display_data)
            st.download_button("📥 Raporu PDF Olarak İndir", data=pdf_bytes, file_name=f"astro_{name}.pdf", mime="application/pdf")

        with tab2:
            fig = draw_chart_visual(visual_data)
            st.pyplot(fig)
            
        with tab3:
            st.info("Referans Hassasiyetinde Veriler:")
            st.code(display_data)
