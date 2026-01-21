import streamlit as st
import ephem
import math
from datetime import datetime
import requests
import json
import pytz
import matplotlib.pyplot as plt
import io
from fpdf import FPDF

# --- SAYFA AYARLARI VE MİSTİK TEMA ---
st.set_page_config(page_title="Astro-Analiz Pro", layout="wide", page_icon="🔮")

# CSS ile Mistik Tasarım
st.markdown("""
    <style>
    /* Arka Plan */
    .stApp {
        background: linear-gradient(to bottom, #0e1117, #1a1c24);
        color: #e0e0e0;
    }
    /* Başlıklar */
    h1, h2, h3 {
        color: #FFD700 !important; /* Altın Sarısı */
        font-family: 'Helvetica', sans-serif;
    }
    /* Bilgi Kutuları */
    .stAlert {
        background-color: #2b2d42;
        color: #fff;
        border: 1px solid #FFD700;
    }
    /* Butonlar */
    .stButton>button {
        background-color: #FFD700;
        color: #000;
        border-radius: 10px;
        font-weight: bold;
        border: none;
    }
    .stButton>button:hover {
        background-color: #FFA500;
        color: #fff;
    }
    /* Kenar Çubuğu */
    [data-testid="stSidebar"] {
        background-color: #161a25;
        border-right: 1px solid #333;
    }
    </style>
    """, unsafe_allow_html=True)

# --- API KONTROL ---
if "GOOGLE_API_KEY" in st.secrets:
    api_key = st.secrets["GOOGLE_API_KEY"]
else:
    st.error("🚨 HATA: API Anahtarı bulunamadı!")
    st.stop()

# --- YARDIMCI FONKSİYONLAR ---
ZODIAC = ["Koç", "Boğa", "İkizler", "Yengeç", "Aslan", "Başak", "Terazi", "Akrep", "Yay", "Oğlak", "Kova", "Balık"]

def dec_to_dms(deg):
    d = int(deg)
    m = int((deg - d) * 60)
    return f"{d}° {m:02d}'"

def clean_text_for_pdf(text):
    # FPDF standart fontları Türkçe karakterleri bazen bozar, basit değişim yapıyoruz
    replacements = {
        'ğ': 'g', 'Ğ': 'G', 'ş': 's', 'Ş': 'S', 'ı': 'i', 'İ': 'I',
        'ü': 'u', 'Ü': 'U', 'ö': 'o', 'Ö': 'O', 'ç': 'c', 'Ç': 'C',
        '’': "'", '“': '"', '”': '"'
    }
    for search, replace in replacements.items():
        text = text.replace(search, replace)
    return text

# --- HARİTA ÇİZİMİ (MATPLOTLIB) ---
def draw_chart_visual(bodies_data):
    fig = plt.figure(figsize=(8, 8), facecolor='#0e1117')
    ax = fig.add_subplot(111, projection='polar')
    ax.set_facecolor('#1a1c24')
    
    # Burç Dilimleri
    for i in range(12):
        angle = math.radians(i * 30)
        ax.plot([angle, angle], [0, 1], color='#444', linewidth=1)
        # Burç İsimleri (Dış Halka)
        ax.text(angle + math.radians(15), 1.1, ZODIAC[i], 
                horizontalalignment='center', color='#FFD700', fontsize=10)

    # Gezegenleri Yerleştir
    # Ephem 0 dereceyi Koç (Aries) kabul eder. Polar plotta 0 derece sağdadır.
    # Astrolojik haritada Koç genelde 9'da başlar ama basitlik için standart daire kullanıyoruz.
    
    for name, sign, deg_total in bodies_data:
        # Dereceyi radyana çevir
        angle_rad = math.radians(deg_total)
        
        # Gezegen Noktası
        ax.plot(angle_rad, 0.8, 'o', color='white', markersize=8, markeredgecolor='#FFD700')
        
        # Gezegen İsmi
        ax.text(angle_rad, 0.9, name[:2], color='white', fontsize=9, fontweight='bold', ha='center')

    ax.set_yticklabels([])
    ax.set_xticklabels([])
    ax.grid(False)
    ax.spines['polar'].set_visible(False)
    
    return fig

# --- PDF OLUŞTURUCU ---
def create_pdf(name, birth_info, ai_comment, technical_data):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", size=12)
    
    # Başlık
    pdf.set_font("Arial", 'B', 16)
    pdf.cell(200, 10, txt=clean_text_for_pdf(f"Astro-Analiz Raporu: {name}"), ln=True, align='C')
    pdf.ln(10)
    
    # Doğum Bilgisi
    pdf.set_font("Arial", size=12)
    pdf.cell(200, 10, txt=clean_text_for_pdf(f"Dogum Bilgileri: {birth_info}"), ln=True)
    pdf.ln(5)
    
    # Teknik Veriler
    pdf.set_font("Arial", 'B', 12)
    pdf.cell(200, 10, txt="Gezegen Konumlari:", ln=True)
    pdf.set_font("Arial", size=10)
    pdf.multi_cell(0, 8, txt=clean_text_for_pdf(technical_data))
    pdf.ln(5)
    
    # Yorum
    pdf.set_font("Arial", 'B', 12)
    pdf.cell(200, 10, txt="Yapay Zeka Yorumu:", ln=True)
    pdf.set_font("Arial", size=11)
    pdf.multi_cell(0, 8, txt=clean_text_for_pdf(ai_comment))
    
    return pdf.output(dest='S').encode('latin-1', 'ignore')

# --- ANA HESAPLAMA ---
def calculate_chart_precise(name, d_date, d_time, city, lat, lon):
    try:
        local_dt = datetime.combine(d_date, d_time)
        tz = pytz.timezone('Europe/Istanbul') 
        local_dt_aware = tz.localize(local_dt)
        utc_dt = local_dt_aware.astimezone(pytz.utc)
        
        obs = ephem.Observer()
        obs.lat, obs.lon = str(lat), str(lon)
        obs.date = utc_dt
        
        info_text = f"**HESAPLANAN UTC:** {utc_dt.strftime('%H:%M')}\n\n"
        chart_data_for_ai = "Gezegen Konumları:\n"
        
        bodies = [('Güneş', ephem.Sun()), ('Ay', ephem.Moon()), ('Merkür', ephem.Mercury()), 
                  ('Venüs', ephem.Venus()), ('Mars', ephem.Mars()), ('Jüpiter', ephem.Jupiter()),
                  ('Satürn', ephem.Saturn()), ('Uranüs', ephem.Uranus()), 
                  ('Neptün', ephem.Neptune()), ('Plüton', ephem.Pluto())]
        
        visual_data = [] # Grafik için veri
        
        for n, b in bodies:
            b.compute(obs)
            ecl = ephem.Ecliptic(b)
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
        else:
            return f"Hata: {resp.text}"
    except Exception as e: return str(e)

# --- ARAYÜZ YAPISI ---
st.title("🌌 Astro-Analiz Pro")
st.markdown("### Yıldızların Rehberliğinde Derinlemesine Analiz")

with st.sidebar:
    st.header("Giriş Paneli")
    name = st.text_input("İsim", "Ziyaretçi")
    d_date = st.date_input("Tarih", value=datetime(1980, 11, 26))
    d_time = st.time_input("Saat", value=datetime.strptime("16:00", "%H:%M"))
    city = st.text_input("Şehir", "İstanbul")
    c1, c2 = st.columns(2)
    lat = c1.number_input("Enlem", 41.00)
    lon = c2.number_input("Boylam", 28.97)
    q = st.text_area("Soru", "Kariyerim hakkında yorumlar mısın?")
    btn = st.button("Analiz Et ✨", type="primary")

if btn:
    # 1. Hesaplama
    display_data, ai_data, visual_data, err = calculate_chart_precise(name, d_date, d_time, city, lat, lon)
    
    if err:
        st.error(err)
    else:
        # Sekmeler Oluştur
        tab1, tab2, tab3 = st.tabs(["📝 Yorum", "🗺️ Harita", "📊 Teknik Veri"])
        
        # AI Yorumu Alma
        with st.spinner("Kozmos ile bağlantı kuruluyor..."):
            prompt = f"Sen mistik bir astrologsun. İsim: {name}, Yer: {city}. Soru: {q}.\n\n{ai_data}\n\nLütfen detaylı yorumla."
            ai_reply = get_ai_response(prompt)
        
        with tab1:
            st.success("Yorum Hazır!")
            st.markdown(ai_reply)
            
            # PDF İndirme Butonu
            birth_info = f"{d_date.strftime('%d.%m.%Y')} - {d_time.strftime('%H:%M')} - {city}"
            pdf_bytes = create_pdf(name, birth_info, ai_reply, display_data)
            st.download_button(
                label="📥 Raporu PDF Olarak İndir",
                data=pdf_bytes,
                file_name=f"astro_analiz_{name}.pdf",
                mime="application/pdf"
            )

        with tab2:
            st.info("Gezegen Konumları Görselleştirmesi")
            fig = draw_chart_visual(visual_data)
            st.pyplot(fig)
            
        with tab3:
            st.code(display_data)
