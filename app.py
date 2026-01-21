import streamlit as st
# --- KRİTİK AYAR: Siyah Ekran Çözümü (Penceresiz Mod) ---
import matplotlib
matplotlib.use('Agg') 
import matplotlib.pyplot as plt
# --------------------------------------------------------
import ephem
import math
from datetime import datetime
import requests
import json
import pytz
import numpy as np
from fpdf import FPDF
import io

# --- SAYFA AYARLARI ---
st.set_page_config(page_title="Astro-Analiz Pro", layout="wide", page_icon="🔮")

# --- MİSTİK CSS ---
st.markdown("""
    <style>
    .stApp { background: linear-gradient(to bottom, #0e1117, #24283b); color: #e0e0e0; }
    h1, h2, h3 { color: #FFD700 !important; font-family: 'Helvetica', sans-serif; }
    .stButton>button { background-color: #FFD700; color: #000; border-radius: 20px; border: none; font-weight: bold; }
    [data-testid="stSidebar"] { background-color: #161a25; border-right: 1px solid #FFD700; }
    </style>
    """, unsafe_allow_html=True)

# --- API KONTROL ---
if "GOOGLE_API_KEY" in st.secrets:
    api_key = st.secrets["GOOGLE_API_KEY"]
else:
    st.error("🚨 API Anahtarı bulunamadı! Lütfen Secrets ayarlarını kontrol et.")
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
    # PDF fontu bozulmasın diye Türkçe karakterleri basitleştiriyoruz
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
            
            line_html = f"**{planet_sym} {n}**: {sign_sym} {sign} {dms}\n"
            info_text += line_html
            chart_data_for_ai += f"- {n}: {deg_total:.2f} derece boylamında ({sign} burcunun {dms} derecesi).\n"
            visual_data.append((n, sign, deg_total, planet_sym))
            
        return info_text, chart_data_for_ai, visual_data, None
    except Exception as e: return None, None, None, str(e)

# --- HARİTA ÇİZİMİ ---
def draw_chart_visual(bodies_data):
    fig = plt.figure(figsize=(10, 10), facecolor='#0e1117')
    ax = fig.add_subplot(111, projection='polar')
    ax.set_facecolor('#1a1c24')
    
    # 0 Dereceyi (Koç) Saat 9 yönüne (Batı) al
    ax.set_theta_zero_location("W")
    ax.set_theta_direction(-1) # Saat yönünün tersi
    ax.set_yticklabels([])
    ax.set_xticklabels([])
    ax.grid(False)
    ax.spines['polar'].set_visible(False)

    circles = np.linspace(0, 2*np.pi, 100)
    ax.plot(circles, [1.2]*100, color='#FFD700', linewidth=2)

    for i in range(12):
        angle_deg = i * 30
        angle_rad = math.radians(angle_deg)
        ax.plot([angle_rad, angle_rad], [0.4, 1.2], color='#555', linewidth=1, linestyle=':')
        
        text_angle = math.radians(angle_deg + 15)
        rotation = angle_deg + 15
        if 90 < rotation < 270: rotation += 180
        ax.text(text_angle, 1.3, f"{ZODIAC_SYMBOLS[i]}\n{ZODIAC[i]}", ha='center', va='center', color='#FFD700', fontsize=9, fontweight='bold', rotation=rotation)
        ax.text(text_angle, 0.5, str(i + 1), ha='center', va='center', color='#888', fontsize=14, fontweight='bold', alpha=0.7)

    for name, sign, deg_total, planet_sym in bodies_data:
        angle_rad = math.radians(deg_total)
        ax.plot(angle_rad, 0.9, 'o', color='white', markersize=10, markeredgecolor='#FFD700', markeredgewidth=2)
        ax.text(angle_rad, 1.05, f"{planet_sym}\n{name[:2]}", color='white', fontsize=8, fontweight='bold', ha='center', va='center')
    
    return fig

# --- PDF ---
def create_pdf(name, birth_info, ai_comment, technical_data_summary):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", 'B', 20)
    # HATA VEREN KISIM BURASIYDI, ŞİMDİ DÜZELTİLDİ:
    pdf.cell(0, 15, txt=clean_text_for_pdf(f"ASTRO-ANALIZ: {name.upper()}"), ln=True, align='C')
    pdf.ln(10)
    pdf.set_font("Arial", size=12)
    pdf.cell(0, 10, txt=clean_text_for_pdf(f"Dogum: {birth_info}"), ln=True, align='C')
    pdf.ln(5)
    pdf.set_font("Arial", 'B', 14)
    pdf.cell(0, 10, txt="YAPAY ZEKA YORUMU", ln=True)
    pdf.set_font("Arial", size=11)
    pdf.multi_cell(0, 8, txt=clean_text_for_pdf(ai_comment))
    pdf.ln(10)
    pdf.set_font("Arial", 'B', 14)
    pdf.cell(0, 10, txt="TEKNIK VERILER", ln=True)
    pdf.set_font("Arial", size=10)
    
    clean_tech = technical_data_summary.replace("**", "")
    pdf.multi_cell(0, 8, txt=clean_text_for_pdf(clean_tech))
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
st.title("🌌 Astro-Analiz Pro")
st.markdown("### ✨ Yıldızların Gizemli Rehberliği")

with st.sidebar:
    st.header("Giriş Paneli")
    name = st.text_input("İsim", "Ziyaretçi")
    d_date = st.date_input("Tarih", value=datetime(1980, 11, 26))
    d_time = st.time_input("Saat", value=datetime.strptime("16:00", "%H:%M"))
    city = st.text_input("Şehir", "İstanbul")
    st.write("---")
    st.write("📍 **Hassas Koordinat**")
    c1, c2 = st.columns(2)
    lat_deg = c1.number_input("Enlem (°)", value=41, step=1)
    lat_min = c2.number_input("Enlem (')", value=1, step=1, min_value=0, max_value=59)
    c3, c4 = st.columns(2)
    lon_deg = c3.number_input("Boylam (°)", value=28, step=1)
    lon_min = c4.number_input("Boylam (')", value=57, step=1, min_value=0, max_value=59)
    q = st.text_area("Soru", "Kariyerim hakkında yorumlar mısın?")
    btn = st.button("Analiz Et ✨", type="primary")

if btn:
    display_data, ai_data_prompt, visual_data, err = calculate_chart_precise(
        name, d_date, d_time, lat_deg, lat_min, lon_deg, lon_min
    )
    if err:
        st.error(err)
    else:
        tab1, tab2, tab3 = st.tabs(["📝 Detaylı Yorum", "🗺️ Astro-Harita", "📊 Teknik Veriler"])
        
        with st.spinner("Kozmik veriler işleniyor..."):
            prompt = f"""
            Sen uzman astrologsun. Danışan: {name}. Doğum: {d_date} {d_time}. Yer: {city}.
            Soru: {q}
            KESİN KONUMLAR:
            {ai_data_prompt}
            GÖREV: Yükselen burcu ve evleri bu koordinatlara göre hesapla, evleri yorumla ve soruyu cevapla.
            """
            ai_reply = get_ai_response(prompt)
        
        with tab1:
            st.markdown(ai_reply)
            birth_info_str = f"{d_date.strftime('%d.%m.%Y')} - {d_time.strftime('%H:%M')} - {city}"
            pdf_bytes = create_pdf(name, birth_info_str, ai_reply, display_data)
            st.download_button("📜 Raporu PDF İndir", data=pdf_bytes, file_name=f"astro_{name}.pdf", mime="application/pdf")

        with tab2:
            fig = draw_chart_visual(visual_data)
            st.pyplot(fig, use_container_width=True)
            
        with tab3:
            st.markdown(display_data)
