import streamlit as st
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import ephem
import math
from datetime import datetime, timedelta
import requests
import json
import numpy as np
from fpdf import FPDF

# =========================================================
# AYARLAR
# =========================================================
st.set_page_config(page_title="Astro-Analiz Pro", layout="wide", page_icon="🔮")

st.markdown("""
<style>
.stApp { background: linear-gradient(to bottom, #0e1117, #1a1c24); color: #e0e0e0; }
h1, h2 { color: #FFD700 !important; font-family: sans-serif; }
.metric-box { background-color: #262730; padding: 10px; border-radius: 5px; border-left: 3px solid #FFD700; margin-bottom: 5px; }
.aspect-box { background-color: #2d2f3d; padding: 5px; margin: 2px; border-radius: 3px; font-size: 13px; border: 1px solid #444; }
/* Form Butonu */
[data-testid="stFormSubmitButton"] > button {
    background-color: #FFD700 !important; color: black !important; border: none; font-weight: bold; width: 100%; padding: 10px;
}
</style>
""", unsafe_allow_html=True)

# API KONTROL
if "GOOGLE_API_KEY" not in st.secrets:
    st.error("Lütfen Secrets ayarlarından GOOGLE_API_KEY ekleyin.")
    st.stop()
API_KEY = st.secrets["GOOGLE_API_KEY"]

# =========================================================
# SABİTLER & VERİ YAPILARI
# =========================================================
ZODIAC = ["Koç", "Boğa", "İkizler", "Yengeç", "Aslan", "Başak", "Terazi", "Akrep", "Yay", "Oğlak", "Kova", "Balık"]
ZODIAC_SYMBOLS = ["♈", "♉", "♊", "♋", "♌", "♍", "♎", "♏", "♐", "♑", "♒", "♓"]
PLANET_SYMBOLS = {
    "Güneş": "☉", "Ay": "☽", "Merkür": "☿", "Venüs": "♀", "Mars": "♂",
    "Jüpiter": "♃", "Satürn": "♄", "Uranüs": "♅", "Neptün": "♆", "Plüton": "♇",
    "ASC": "ASC", "MC": "MC"
}

# =========================================================
# MATEMATİK MOTORU (Astro-Seek Hassasiyeti)
# =========================================================
def normalize(deg):
    """Açıyı 0-360 derece arasına sabitler"""
    return deg % 360

def dec_to_dms(deg):
    """Dereceyi Derece dk' formata çevirir"""
    d = int(deg)
    m = int(round((deg - d) * 60))
    if m == 60:
        d += 1
        m = 0
    return f"{d:02d}° {m:02d}'"

def get_zodiac_sign(deg):
    """Derecenin hangi burca düştüğünü bulur"""
    return ZODIAC[int(deg / 30) % 12]

def get_house_placidus(deg, cusps):
    """Gezegenin hangi evde olduğunu bulur"""
    deg = normalize(deg)
    for i in range(1, 13):
        start = cusps[i]
        end = cusps[i+1] if i < 12 else cusps[1]
        if start < end:
            if start <= deg < end: return i
        else: # Balık-Koç geçişi (359->0)
            if start <= deg or deg < end: return i
    return 1

def calculate_chart_data(name, d_date, d_time, lat, lon, utc_offset):
    # 1. UTC Zamanı Hesapla
    local_dt = datetime.combine(d_date, d_time)
    utc_dt = local_dt - timedelta(hours=utc_offset)
    
    # 2. PyEphem Gözlemci (Epoch AYARLAMAYIN - J2000 Standart Kalsın)
    obs = ephem.Observer()
    obs.date = utc_dt.strftime('%Y/%m/%d %H:%M:%S') # String format şart
    obs.lat = str(lat)
    obs.lon = str(lon)
    # obs.epoch satırı SİLİNDİ (Hatanın kaynağı buydu)

    # 3. ASC ve MC Hesaplama (Trigonometrik)
    # Astro-Seek ile eşleşmesi için hassas sidereal time kullanımı
    st_rad = float(obs.sidereal_time())
    lat_rad = math.radians(lat)
    obl_rad = math.radians(23.4456) # Ekliptik eğikliği (Epsilon)

    # MC (Midheaven)
    mc_rad = math.atan2(math.tan(st_rad), math.cos(obl_rad))
    mc_deg = normalize(math.degrees(mc_rad))
    if not (0 <= abs(mc_deg - math.degrees(st_rad)) <= 90 or 0 <= abs(mc_deg - math.degrees(st_rad) - 360) <= 90):
        mc_deg = normalize(mc_deg + 180)

    # ASC (Ascendant)
    asc_rad = math.atan2(math.cos(st_rad), -(math.sin(st_rad) * math.cos(obl_rad) + math.tan(lat_rad) * math.sin(obl_rad)))
    asc_deg = normalize(math.degrees(asc_rad))

    # Ev Girişleri (Basitleştirilmiş Placidus Yaklaşımı - Hata vermez)
    cusps = {1: asc_deg, 10: mc_deg}
    # Ara evleri yaklaşık hesapla (Tam Placidus algoritması çok uzundur, bu app için yeterli yaklaşım)
    ic_deg = normalize(mc_deg + 180)
    dsc_deg = normalize(asc_deg + 180)
    cusps[4] = ic_deg
    cusps[7] = dsc_deg
    
    # Diğer evler (Eşit aralıklı yaklaşım - Görsel için yeterli)
    for i in [2,3,5,6,8,9,11,12]:
        cusps[i] = normalize(asc_deg + (i-1)*30) # Basit yerleşim

    # 4. Gezegen Konumları
    # (İsim, Obje)
    bodies_def = [
        ("Güneş", ephem.Sun()), ("Ay", ephem.Moon()), 
        ("Merkür", ephem.Mercury()), ("Venüs", ephem.Venus()), ("Mars", ephem.Mars()),
        ("Jüpiter", ephem.Jupiter()), ("Satürn", ephem.Saturn()), 
        ("Uranüs", ephem.Uranus()), ("Neptün", ephem.Neptune()), ("Plüton", ephem.Pluto())
    ]

    # Veri Listesi: (İsim, Burç Adı, Derece, Sembol) -> HEPSİ 4 ELEMANLI OLACAK
    visual_data = []
    
    # Önce ASC ve MC ekle
    visual_data.append(("ASC", get_zodiac_sign(asc_deg), asc_deg, "ASC"))
    visual_data.append(("MC", get_zodiac_sign(mc_deg), mc_deg, "MC"))

    html_info = f"<div class='metric-box'>🌍 <b>UTC:</b> {utc_dt.strftime('%H:%M')}</div>"
    html_info += f"<div class='metric-box'>🚀 <b>Yükselen:</b> {get_zodiac_sign(asc_deg)} {dec_to_dms(asc_deg % 30)}</div>"
    html_info += f"<div class='metric-box'>👑 <b>MC:</b> {get_zodiac_sign(mc_deg)} {dec_to_dms(mc_deg % 30)}</div>"
    
    ai_text_data = f"Doğum: {local_dt}\nYükselen: {get_zodiac_sign(asc_deg)}\n"

    for name, body in bodies_def:
        body.compute(obs)
        # Ecliptic boylamı (Hatasız yöntem)
        lon_deg = normalize(math.degrees(ephem.Ecliptic(body).lon))
        
        sign = get_zodiac_sign(lon_deg)
        dms = dec_to_dms(lon_deg % 30)
        house = get_house_placidus(lon_deg, cusps)
        
        html_info += f"<div class='metric-box'><b>{name}:</b> {sign} {dms} ({house}. Ev)</div>"
        ai_text_data += f"{name}: {sign} {dms} ({house}. Ev)\n"
        
        # LİSTEYE EKLE (4 ELEMANLI - GARANTİ)
        visual_data.append((name, sign, lon_deg, PLANET_SYMBOLS.get(name, "")))

    # 5. Açılar
    aspects = []
    # Sadece gezegenleri al (index 2'den başla, ASC/MC hariç)
    planets_only = visual_data[2:] 
    
    for i in range(len(planets_only)):
        for j in range(i+1, len(planets_only)):
            n1, s1, d1, sym1 = planets_only[i] # 4 eleman unpack edilir, hata vermez
            n2, s2, d2, sym2 = planets_only[j]
            
            diff = abs(d1 - d2)
            if diff > 180: diff = 360 - diff
            
            aspect_name = ""
            if diff <= 8: aspect_name = "Kavuşum"
            elif 112 <= diff <= 128: aspect_name = "Üçgen"
            elif 82 <= diff <= 98: aspect_name = "Kare"
            elif 172 <= diff <= 180: aspect_name = "Karşıt"
            
            if aspect_name:
                aspects.append(f"{n1} {aspect_name} {n2} ({int(diff)}°)")

    ai_text_data += "\nAÇILAR:\n" + ", ".join(aspects)
    
    return html_info, ai_text_data, visual_data, cusps, aspects

# =========================================================
# HARİTA ÇİZİMİ
# =========================================================
def draw_chart(visual_data, cusps):
    fig = plt.figure(figsize=(8,8), facecolor='#0e1117')
    ax = fig.add_subplot(111, projection='polar')
    ax.set_facecolor('#1a1c24')
    ax.grid(False)
    ax.set_yticklabels([])
    
    # ASC'yi Sola (180 dereceye) sabitle
    asc_angle = math.radians(cusps[1])
    ax.set_theta_offset(np.pi - asc_angle)
    ax.set_theta_direction(1) # Saat yönünün tersi

    # Zodyak Çemberi
    for i in range(12):
        angle = math.radians(i * 30)
        ax.plot([angle, angle], [1, 1.2], color='#FFD700', lw=1, alpha=0.5)
        # Burç Sembolleri
        mid_angle = math.radians(i * 30 + 15)
        ax.text(mid_angle, 1.3, ZODIAC_SYMBOLS[i], color='white', fontsize=14, ha='center')

    # Gezegenler
    for name, sign, deg, sym in visual_data:
        angle = math.radians(deg)
        color = '#FF4B4B' if name in ["ASC", "MC"] else 'white'
        # Marker
        ax.plot(angle, 1.05, 'o', color=color, markersize=8)
        # Sembol
        ax.text(angle, 1.12, sym, color=color, fontsize=12, ha='center', fontweight='bold')

    return fig

# =========================================================
# YARDIMCI SERVİSLER (PDF & AI)
# =========================================================
def create_pdf(name, text):
    try:
        pdf = FPDF()
        pdf.add_page()
        # Türkçe karakterleri temizle (FPDF hatası almamak için)
        tr_map = {'ğ':'g','Ğ':'G','ş':'s','Ş':'S','ı':'i','İ':'I','ü':'u','Ü':'U','ö':'o','Ö':'O','ç':'c','Ç':'C'}
        clean_name = name
        for k,v in tr_map.items(): clean_name = clean_name.replace(k,v)
        
        pdf.set_font("Arial", 'B', 16)
        pdf.cell(0, 10, f"ANALIZ: {clean_name}", ln=True)
        pdf.set_font("Arial", '', 12)
        
        clean_text = text
        for k,v in tr_map.items(): clean_text = clean_text.replace(k,v)
        
        pdf.multi_cell(0, 8, clean_text)
        return pdf.output(dest='S').encode('latin-1', 'ignore')
    except: return None

def get_ai_interpretation(prompt):
    try:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={API_KEY}"
        headers = {'Content-Type': 'application/json'}
        data = {"contents": [{"parts": [{"text": prompt}]}]}
        response = requests.post(url, headers=headers, json=data)
        
        if response.status_code == 200:
            return response.json()['candidates'][0]['content']['parts'][0]['text']
        else:
            return f"AI Servis Hatası: {response.status_code}. (API Kotası dolmuş olabilir)"
    except Exception as e:
        return f"Bağlantı Hatası: {str(e)}"

# =========================================================
# ARAYÜZ (FORM İLE)
# =========================================================
st.title("🌌 Astro-Analiz Pro (Final)")

with st.sidebar:
    st.header("Giriş")
    with st.form("astro_form"):
        name = st.text_input("İsim", "Ziyaretçi")
        
        # Tarih ve Saat
        d_date = st.date_input("Doğum Tarihi", value=datetime(1980, 11, 26))
        d_time = st.time_input("Doğum Saati", value=datetime.strptime("16:00", "%H:%M"))
        
        utc_offset = st.number_input("GMT Farkı (Örn: Türkiye için 3)", value=3)
        
        # Koordinat (Manuel Giriş Daha Güvenli)
        c1, c2 = st.columns(2)
        lat = c1.number_input("Enlem", 41.00)
        lon = c2.number_input("Boylam", 29.00)
        
        q = st.text_area("Sorunuz", "Genel yorum?")
        
        # --- BUTON BURADA ---
        submit = st.form_submit_button("ANALİZ ET ✨")

if submit:
    try:
        html_info, ai_data, vis_data, cusps, asps = calculate_chart_data(name, d_date, d_time, lat, lon, utc_offset)
        
        t1, t2, t3 = st.tabs(["📝 Yorum", "🗺️ Harita", "📊 Veriler"])
        
        with t1:
            with st.spinner("Yıldızlar yorumlanıyor..."):
                ai_reply = get_ai_interpretation(f"Sen bir astrologsun. {name} için yorum yap. Soru: {q}. Veriler: {ai_data}")
            st.markdown(ai_reply)
            
            pdf_bytes = create_pdf(name, ai_reply)
            if pdf_bytes:
                st.download_button("PDF Olarak İndir", pdf_bytes, "analiz.pdf", "application/pdf")
        
        with t2:
            st.pyplot(draw_chart(vis_data, cusps))
            
        with t3:
            st.markdown(html_info, unsafe_allow_html=True)
            st.markdown("### Açılar")
            for a in asps:
                st.markdown(f"<div class='aspect-box'>{a}</div>", unsafe_allow_html=True)

    except Exception as e:
        st.error(f"Beklenmeyen bir hata oluştu: {str(e)}")
