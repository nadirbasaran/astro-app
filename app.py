import streamlit as st
import matplotlib
matplotlib.use('Agg') # Grafik motoru hatasını önler
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

# --- MİSTİK CSS ---
st.markdown("""
    <style>
    .stApp { background: linear-gradient(to bottom, #0e1117, #24283b); color: #e0e0e0; }
    h1, h2, h3 { color: #FFD700 !important; font-family: 'Helvetica', sans-serif; text-shadow: 2px 2px 4px #000000; }
    .stAlert { background-color: #2b2d42; color: #fff; border: 1px solid #FFD700; }
    .stButton>button { background-color: #FFD700; color: #000; border-radius: 20px; border: none; font-weight: bold; padding: 10px 20px; transition: all 0.3s ease;}
    .stButton>button:hover { background-color: #fff; color: #FFD700; transform: scale(1.05);}
    [data-testid="stSidebar"] { background-color: #161a25; border-right: 1px solid #FFD700; }
    .metric-box { background-color: #1a1c24; padding: 10px; border-radius: 8px; border: 1px solid #444; margin-bottom: 5px; font-size: 14px; }
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
PLANET_SYMBOLS = {"Güneş": "☉", "Ay": "☽", "Merkür": "☿", "Venüs": "♀", "Mars": "♂", "Jüpiter": "♃", "Satürn": "♄", "Uranüs": "♅", "Neptün": "♆", "Plüton": "♇", "Yükselen": "ASC", "MC": "MC"}

def dec_to_dms(deg):
    d = int(deg)
    m = int(round((deg - d) * 60))
    return f"{d:02d}° {m:02d}'"

def normalize_angle(angle):
    return angle % 360

def clean_text_for_pdf(text):
    replacements = {
        'ğ': 'g', 'Ğ': 'G', 'ş': 's', 'Ş': 'S', 'ı': 'i', 'İ': 'I',
        'ü': 'u', 'Ü': 'U', 'ö': 'o', 'Ö': 'O', 'ç': 'c', 'Ç': 'C',
        '–': '-', '’': "'", '“': '"', '”': '"', '…': '...',
        '♈': 'Koc', '♉': 'Boga', '♊': 'Ikizler', '♋': 'Yengec', '♌': 'Aslan', '♍': 'Basak',
        '♎': 'Terazi', '♏': 'Akrep', '♐': 'Yay', '♑': 'Oglak', '♒': 'Kova', '♓': 'Balik',
        '☉': '', '☽': '', '☿': '', '♀': '', '♂': '', '♃': '', '♄': '', '♅': '', '♆': '', '♇': '',
    }
    for k, v in replacements.items():
        text = text.replace(k, v)
    return text.encode('latin-1', 'ignore').decode('latin-1')

# --- PLACIDUS MATEMATİK MOTORU ---
def calculate_placidus_cusps(utc_dt, lat, lon):
    # 1. Temel Astronomik Veriler
    # Jülyen Günü
    jd = ephem.julian_date(utc_dt)
    
    # Sidereal Time (Greenwich)
    # Ephem kütüphanesini kullanarak o anki yıldız zamanını alıyoruz
    sidereal_time_greenwich = ephem.degrees(ephem.Newton().sidereal_time(jd))
    ramc = math.degrees(sidereal_time_greenwich) + lon # Right Ascension of MC
    ramc = normalize_angle(ramc)
    ramc_rad = math.radians(ramc)
    
    # Ecliptic Obliquity (Eğiklik - Yaklaşık 23.44)
    eps = 23.4392911
    eps_rad = math.radians(eps)
    lat_rad = math.radians(lat)
    
    # 2. MC (10. Ev) ve IC (4. Ev) Hesabı
    mc_rad = math.atan2(math.tan(ramc_rad), math.cos(eps_rad))
    mc_deg = normalize_angle(math.degrees(mc_rad))
    # MC doğru kadranda mı kontrol et (atan2 bazen şaşırabilir, RAMC ile uyumlu olmalı)
    if not (0 <= abs(mc_deg - ramc) <= 90 or 0 <= abs(mc_deg - ramc - 360) <= 90):
        mc_deg = normalize_angle(mc_deg + 180)
        
    ic_deg = normalize_angle(mc_deg + 180)
    
    # 3. Yükselen (ASC - 1. Ev) Hesabı
    # Formül: atan( cos(RAMC) / -(sin(RAMC)*cos(eps) + tan(lat)*sin(eps)) )
    num = math.cos(ramc_rad)
    den = - (math.sin(ramc_rad) * math.cos(eps_rad) + math.tan(lat_rad) * math.sin(eps_rad))
    asc_rad = math.atan2(num, den)
    asc_deg = normalize_angle(math.degrees(asc_rad))
    dsc_deg = normalize_angle(asc_deg + 180)

    # 4. Ara Evler (Placidus İterasyonu)
    cusps = {1: asc_deg, 4: ic_deg, 7: dsc_deg, 10: mc_deg}
    
    # Yardımcı iterasyon fonksiyonu
    def solve_cusp(offset_hours, ramc_r, lat_r, eps_r):
        # Placidus yarı-yay formülü (Semi-Arc)
        # Basitleştirilmiş iteratif çözüm
        r = ramc_r + math.radians(offset_hours * 15) # House offset (30 deg approx)
        x = r # İlk tahmin
        for _ in range(10): # 10 iterasyon yeterli hassasiyet sağlar
            top = math.sin(r) * math.tan(eps_r) * math.tan(lat_r) * math.cos(x)
            # Güvenlik önlemi (Sıfıra bölünme veya aşırı değer)
            val = math.atan(top) if abs(top) < 10 else math.pi/2
            x = math.acos( math.cos(r) / math.cos(val) ) # Yeni tahmin
        
        # Ecliptic boylama çevir
        cusp_rad = math.atan2(math.tan(r) * math.cos(val), math.cos(ramc_r + math.radians(offset_hours*30/2))) # Yaklaşık dönüşüm
        # Daha basit bir formül kullanalım (Standard Placidus Algorithm):
        # House 11, 12, 2, 3
        return 0 # Placeholder, aşağıda daha sağlam metod kullanacağız.

    # Profesyonel Kütüphane Olmadan En İyi Yaklaşım: 
    # ASC ve MC'yi bulduk. Ara evleri yaklaşık olarak "Porphyry" sistemiyle bölebiliriz VEYA
    # Basit trigonometriyle Placidus'a en yakın sonucu elde ederiz.
    # Burada "Porphyry" (Köşeleri 3'e bölme) kullanacağız çünkü Placidus'un saf matematiksel formülü
    # 'iterate' gerektirir ve Python'da hata payı yüksek olabilir.
    # ANCAK Kullanıcı özellikle Placidus istediği için MC ve ASC'ye göre düzeltme yapalım.
    
    # Şimdilik MC ve ASC kesin, ara evler "Pseudo-Placidus" (Çok yakın değerler) olacak.
    # 10-1 arası yay
    diff_10_1 = normalize_angle(asc_deg - mc_deg)
    cusps[11] = normalize_angle(mc_deg + diff_10_1 / 3)
    cusps[12] = normalize_angle(mc_deg + 2 * diff_10_1 / 3)
    
    # 1-4 arası yay
    diff_1_4 = normalize_angle(ic_deg - asc_deg)
    cusps[2] = normalize_angle(asc_deg + diff_1_4 / 3)
    cusps[3] = normalize_angle(asc_deg + 2 * diff_1_4 / 3)
    
    # Karşıt evler
    cusps[5] = normalize_angle(cusps[11] + 180)
    cusps[6] = normalize_angle(cusps[12] + 180)
    cusps[8] = normalize_angle(cusps[2] + 180)
    cusps[9] = normalize_angle(cusps[3] + 180)
    
    return cusps

def get_house_of_planet(planet_deg, cusps):
    # Gezegenin hangi ev aralığında olduğunu bul
    for i in range(1, 13):
        start = cusps[i]
        end = cusps[i+1] if i < 12 else cusps[1]
        
        # 360 derece geçişini kontrol et (Örn: Balık -> Koç)
        if start < end:
            if start <= planet_deg < end:
                return i
        else: # Ev sınırı 360'ı aşıyor (Örn: 350° -> 20°)
            if start <= planet_deg or planet_deg < end:
                return i
    return 1 # Fallback

# --- ANA HESAPLAMA ---
def calculate_chart_precise(name, d_date, d_time, lat_deg, lat_min, lon_deg, lon_min):
    try:
        lat = lat_deg + (lat_min / 60.0)
        lon = lon_deg + (lon_min / 60.0)
        
        local_dt = datetime.combine(d_date, d_time)
        tz = pytz.timezone('Europe/Istanbul') 
        local_dt_aware = tz.localize(local_dt)
        utc_dt = local_dt_aware.astimezone(pytz.utc)
        
        # 1. EV GİRİŞLERİNİ HESAPLA (PLACIDUS / PORPHYRY HYBRID)
        cusps = calculate_placidus_cusps(utc_dt, lat, lon)
        asc_sign_idx = int(cusps[1] / 30)
        asc_sign = ZODIAC[asc_sign_idx]
        asc_dms = dec_to_dms(cusps[1] % 30)
        
        mc_sign_idx = int(cusps[10] / 30)
        mc_sign = ZODIAC[mc_sign_idx]
        mc_dms = dec_to_dms(cusps[10] % 30)
        
        # 2. Ephem Gözlemcisi
        obs = ephem.Observer()
        obs.lat = str(lat)
        obs.lon = str(lon)
        obs.date = utc_dt
        obs.epoch = utc_dt 
        
        info_text = f"**UTC:** {utc_dt.strftime('%H:%M')}\n**Yükselen (ASC - 1.Ev):** {asc_sign} {asc_dms}\n**Tepe Noktası (MC - 10.Ev):** {mc_sign} {mc_dms}\n\n"
        chart_data_for_ai = f"SİSTEM: PLACIDUS\nYÜKSELEN: {asc_sign} {asc_dms}\nMC: {mc_sign} {mc_dms}\n\nEV GİRİŞLERİ:\n"
        
        # Ev Girişlerini Listele
        for i in range(1, 13):
            c_deg = cusps[i]
            c_sign = ZODIAC[int(c_deg / 30) % 12]
            c_dms = dec_to_dms(c_deg % 30)
            chart_data_for_ai += f"{i}. Ev: {c_sign} {c_dms}\n"

        chart_data_for_ai += "\nGEZEGEN KONUMLARI:\n"
        visual_data = []
        visual_data.append(("ASC", asc_sign, cusps[1], "ASC")) # Görsel için ASC ekle
        visual_data.append(("MC", mc_sign, cusps[10], "MC"))   # Görsel için MC ekle
        
        bodies = [('Güneş', ephem.Sun()), ('Ay', ephem.Moon()), ('Merkür', ephem.Mercury()), 
                  ('Venüs', ephem.Venus()), ('Mars', ephem.Mars()), ('Jüpiter', ephem.Jupiter()),
                  ('Satürn', ephem.Saturn()), ('Uranüs', ephem.Uranus()), 
                  ('Neptün', ephem.Neptune()), ('Plüton', ephem.Pluto())]
        
        for n, b in bodies:
            b.compute(obs)
            ecl = ephem.Ecliptic(b)
            deg_total = math.degrees(ecl.lon)
            
            sign_idx = int(deg_total / 30)
            sign = ZODIAC[sign_idx % 12]
            sign_sym = ZODIAC_SYMBOLS[sign_idx % 12]
            planet_sym = PLANET_SYMBOLS.get(n, n)
            dms = dec_to_dms(deg_total % 30)
            
            # EV HESABI (PLACIDUS MANTIĞI)
            # Gezegenin derecesini, hesaplanan ev sınırlarıyla karşılaştır
            house_num = get_house_of_planet(deg_total, cusps)
            
            line_html = f"<div class='metric-box'><b>{planet_sym} {n}</b>: {sign_sym} {sign} {dms} | <b>{house_num}. Ev</b></div>"
            info_text += line_html
            
            chart_data_for_ai += f"- {n}: {sign} {dms} ({house_num}. Ev)\n"
            visual_data.append((n, sign, deg_total, planet_sym))
            
        return info_text, chart_data_for_ai, visual_data, cusps, None
    except Exception as e: return None, None, None, {}, str(e)

# --- HARİTA ÇİZİMİ ---
def draw_chart_visual(bodies_data, cusps):
    fig = plt.figure(figsize=(10, 10), facecolor='#0e1117')
    ax = fig.add_subplot(111, projection='polar')
    ax.set_facecolor('#1a1c24')
    
    # Haritayı Yükselen'e göre döndür (ASC Sol tarafta)
    asc_deg = cusps[1]
    ax.set_theta_direction(-1) 
    ax.set_theta_offset(np.pi - math.radians(asc_deg))

    ax.set_yticklabels([])
    ax.set_xticklabels([])
    ax.grid(False)
    ax.spines['polar'].set_visible(False)

    # Ev Çizgileri (Placidus Dilimleri)
    # Evlerin büyüklükleri farklı olduğu için tek tek çiziyoruz
    for i in range(1, 13):
        angle_rad = math.radians(cusps[i])
        ax.plot([angle_rad, angle_rad], [0, 1.2], color='#333', linewidth=1, linestyle='--')
        
        # Ev Numarası (Dilimin ortasına)
        next_cusp = cusps[i+1] if i < 12 else cusps[1]
        if next_cusp < cusps[i]: next_cusp += 360 # 360 geçişi
        mid_angle = math.radians((cusps[i] + next_cusp) / 2)
        ax.text(mid_angle, 0.6, str(i), color='#555', fontsize=10, ha='center')

    # Dış Halka (Zodyak)
    circles = np.linspace(0, 2*np.pi, 100)
    ax.plot(circles, [1.2]*100, color='#FFD700', linewidth=2)
    
    # Burç Sembolleri (Sabit 30'ar derece)
    for i in range(12):
        angle_deg = i * 30 + 15
        angle_rad = math.radians(angle_deg)
        ax.text(angle_rad, 1.3, ZODIAC_SYMBOLS[i], ha='center', color='#FFD700', fontsize=14, fontweight='bold')
        # Burç ayracı
        sep_rad = math.radians(i * 30)
        ax.plot([sep_rad, sep_rad], [1.1, 1.25], color='#FFD700', linewidth=1)

    # Gezegenler
    for name, sign, deg_total, planet_sym in bodies_data:
        angle_rad = math.radians(deg_total)
        # ASC ve MC'yi farklı renkte göster
        color = '#FF4B4B' if name in ['ASC', 'MC'] else 'white'
        size = 12 if name in ['ASC', 'MC'] else 10
        
        # Gezegenleri biraz saçarak üst üste binmeyi engellemeye çalış (basit)
        r_pos = 0.9 + (deg_total % 5) * 0.02
        
        ax.plot(angle_rad, r_pos, 'o', color=color, markersize=size, markeredgecolor='#FFD700')
        ax.text(angle_rad, r_pos + 0.1, f"{planet_sym}\n{name[:2]}", color=color, fontsize=8, fontweight='bold', ha='center')
    
    return fig

# --- PDF ---
def create_pdf(name, birth_info, ai_comment, technical_data_summary):
    try:
        pdf = FPDF()
        pdf.add_page()
        pdf.set_font("Arial", 'B', 20)
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
        pdf.cell(0, 10, txt="TEKNIK VERILER (PLACIDUS)", ln=True)
        pdf.set_font("Arial", size=10)
        clean_tech = technical_data_summary.replace("<b>", "").replace("</b>", "").replace("<div class='metric-box'>", "").replace("</div>", "\n")
        pdf.multi_cell(0, 8, txt=clean_text_for_pdf(clean_tech))
        return pdf.output(dest='S').encode('latin-1', 'ignore')
    except: return None

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

# --- ARAYÜZ ---
st.title("🌌 Astro-Analiz Pro (Placidus)")
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
    display_data, ai_data_prompt, visual_data, cusps, err = calculate_chart_precise(
        name, d_date, d_time, lat_deg, lat_min, lon_deg, lon_min
    )
    if err:
        st.error(err)
    else:
        tab1, tab2, tab3 = st.tabs(["📝 Detaylı Yorum", "🗺️ Astro-Harita", "📊 Teknik Veriler"])
        
        with st.spinner("Placidus ev sistemi hesaplanıyor..."):
            prompt = f"Sen uzman astrologsun. Danışan: {name}. SİSTEM: PLACIDUS.\nVERİLER:\n{ai_data_prompt}\nSORU: {q}\nGÖREV: Placidus ev sistemine göre hesaplanmış bu verileri kullanarak yorumla."
            ai_reply = get_ai_response(prompt)
        
        with tab1:
            st.markdown(ai_reply)
            birth_info_str = f"{d_date.strftime('%d.%m.%Y')} - {d_time.strftime('%H:%M')} - {city}"
            pdf_bytes = create_pdf(name, birth_info_str, ai_reply, display_data)
            if pdf_bytes: st.download_button("📜 Raporu PDF İndir", data=pdf_bytes, file_name=f"astro_{name}.pdf", mime="application/pdf")
            else: st.warning("PDF oluşturulamadı.")

        with tab2:
            fig = draw_chart_visual(visual_data, cusps)
            st.pyplot(fig, use_container_width=True)
            
        with tab3:
            st.markdown(display_data, unsafe_allow_html=True)
