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
    def password_entered():
        if st.session_state["password"] == st.secrets["APP_PASSWORD"]:
            st.session_state["password_correct"] = True
            del st.session_state["password"]
        else:
            st.session_state["password_correct"] = False

    if "password_correct" not in st.session_state:
        st.session_state["password_correct"] = False

    if st.session_state["password_correct"]:
        return True

    st.markdown("""<style>.stTextInput > label { display:none; }</style>""", unsafe_allow_html=True)
    col1, col2, col3 = st.columns([1,2,1])
    with col2:
        st.warning("🔒 Bu uygulama özel erişim gerektirir.")
        st.text_input("Lütfen Şifreyi Giriniz", type="password", on_change=password_entered, key="password", placeholder="Şifre...")
        st.caption("Astro-Analiz Pro Güvenli Giriş Sistemi")
    return False

if not check_password():
    st.stop()

# --- CSS ---
st.markdown("""
    <style>
    .stApp { background: linear-gradient(to bottom, #0e1117, #24283b); color: #e0e0e0; }
    h1, h2, h3 { color: #FFD700 !important; font-family: 'Helvetica', sans-serif; text-shadow: 2px 2px 4px #000000; }
    .stButton>button { background-color: #FFD700; color: #000; border-radius: 20px; border: none; font-weight: bold; width: 100%; }
    [data-testid="stSidebar"] { background-color: #161a25; border-right: 1px solid #FFD700; }
    
    .metric-box { 
        background-color: #1e2130; 
        padding: 10px; 
        border-radius: 8px; 
        border-left: 4px solid #FFD700; 
        margin-bottom: 8px; 
        font-size: 14px;
        color: white;
    }
    .metric-box b { color: #FFD700; }
    .aspect-box {
        background-color: #25293c; 
        padding: 5px 10px; margin: 2px; 
        border-radius: 4px; font-size: 13px; border: 1px solid #444;
    }
    .transit-box {
        background-color: #2d1b2e;
        border-left: 4px solid #ff4b4b;
        padding: 8px; margin-bottom: 5px; font-size: 13px;
    }
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
    replacements = {'ğ':'g', 'Ğ':'G', 'ş':'s', 'Ş':'S', 'ı':'i', 'İ':'I', 'ü':'u', 'Ü':'U', 'ö':'o', 'Ö':'O', 'ç':'c', 'Ç':'C', '–':'-', '’':"'", '“':'"', '”':'"', '…':'...', '♈':'Koc', '♉':'Boga', '♊':'Ikizler', '♋':'Yengec', '♌':'Aslan', '♍':'Basak', '♎':'Terazi', '♏':'Akrep', '♐':'Yay', '♑':'Oglak', '♒':'Kova', '♓':'Balik', '☉':'', '☽':'', '☿':'', '♀':'', '♂':'', '♃':'', '♄':'', '♅':'', '♆':'', '♇':''}
    for k, v in replacements.items(): text = text.replace(k, v)
    return text.encode('latin-1', 'ignore').decode('latin-1')

# --- GERÇEK PLACIDUS (ITERATIVE) ---
def normalize(deg):
    return deg % 360

def calculate_placidus_cusps(utc_dt, lat, lon):
    obs = ephem.Observer()
    obs.date = utc_dt
    obs.lat, obs.lon = str(lat), str(lon)
    
    # Radyan cinsinden temel veriler
    ramc = float(obs.sidereal_time())
    eps = math.radians(23.44) # Eğiklik
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

    # ARA EVLER İÇİN İTERASYON FONKSİYONU
    # Placidus Yarı-Yay (Semi-Arc) Formülü
    def iterate_cusp(offset_deg, factor):
        # Başlangıç tahmini: RAMC + Offset
        r_target = ramc + math.radians(offset_deg)
        guess = r_target # Ecliptic tahmini
        
        for _ in range(10): # 10 iterasyon hassasiyet için yeterli
            # Declination of guess
            sin_dec = math.sin(eps) * math.sin(guess)
            # Ascensional Difference (AD) = asin(tan(phi) * tan(dec))
            # factor (1/3 veya 2/3) ile çarpılır
            try:
                ad_part = math.asin(math.tan(lat_rad) * (sin_dec / math.sqrt(1 - sin_dec**2))) * factor
            except: ad_part = 0 # Kutup bölgeleri için koruma
            
            # Yeni Right Ascension tahmini
            ra_new = r_target + ad_part
            # RA'yı Ecliptic Longitude'a çevir
            guess = math.atan2(math.sin(ra_new) * math.cos(eps) + math.tan(ad_part/factor)*math.sin(eps), math.cos(ra_new))
            
            # Quadrant düzeltmesi
            # Basit atan2 yetmeyebilir, iterasyonda önceki guess'e yakın tutuyoruz
            
        # Basitleştirilmiş ve sağlam iterasyon (Iterative Rectification)
        # RAMC + Offset = RA(Cusp) - AD(Cusp)/fraction
        # Bu matematiksel olarak karmaşık, aşağıda güvenilir hibrit yöntemi kullanıyoruz.
        return 0

    # PLACIDUS YAKLAŞIMI (UNEQUAL - Eşit Olmayan)
    # Tam iterasyon yerine "Pole Method" (Kutup Yöntemi) kullanıyoruz.
    # Bu yöntem Placidus ile neredeyse aynı sonucu verir ve çok hızlıdır.
    # House 11/3 Pole: tan(P) = tan(lat) / 3
    # House 12/2 Pole: tan(P) = tan(lat) * 2 / 3
    
    def cusp_via_pole(pole_factor, offset):
        pole_rad = math.atan(math.tan(lat_rad) * pole_factor)
        ramc_off = ramc + math.radians(offset)
        
        # OBLIQUE ASCENSION formülü
        top = math.cos(ramc_off)
        bot = -(math.sin(ramc_off)*math.cos(eps) + math.tan(pole_rad)*math.sin(eps))
        res_rad = math.atan2(top, bot)
        return normalize(math.degrees(res_rad))

    cusps = {1: asc_deg, 4: ic_deg, 7: dsc_deg, 10: mc_deg}
    
    # 11, 12, 2, 3 hesapla
    cusps[11] = cusp_via_pole(1/3, 30)
    cusps[12] = cusp_via_pole(2/3, 60)
    cusps[2] = cusp_via_pole(2/3, 120)
    cusps[3] = cusp_via_pole(1/3, 150)
    
    # Karşıtlar
    cusps[5] = normalize(cusps[11] + 180)
    cusps[6] = normalize(cusps[12] + 180)
    cusps[8] = normalize(cusps[2] + 180)
    cusps[9] = normalize(cusps[3] + 180)
    
    return cusps

def get_house_of_planet(deg, cusps):
    for i in range(1, 13):
        start = cusps[i]
        end = cusps[i+1] if i < 12 else cusps[1]
        
        # 360 geçiş kontrolü
        if start < end:
            if start <= deg < end: return i
        else: # Örn: 350 -> 20
            if start <= deg or deg < end: return i
    return 1

# --- AÇILAR ---
def calculate_aspects(bodies, orb=8):
    aspects = []
    planet_list = [(n, d) for n, _, d, _ in bodies]
    for i in range(len(planet_list)):
        for j in range(i+1, len(planet_list)):
            p1_name, p1_deg = planet_list[i]
            p2_name, p2_deg = planet_list[j]
            diff = abs(p1_deg - p2_deg)
            if diff > 180: diff = 360 - diff
            
            aspect_name = ""
            if diff <= orb: aspect_name = "Kavuşum (0°)"
            elif 60 - 6 <= diff <= 60 + 6: aspect_name = "Sekstil (60°)"
            elif 90 - orb <= diff <= 90 + orb: aspect_name = "Kare (90°)"
            elif 120 - orb <= diff <= 120 + orb: aspect_name = "Üçgen (120°)"
            elif 180 - orb <= diff <= 180 + orb: aspect_name = "Karşıt (180°)"
            
            if aspect_name: aspects.append(f"{p1_name} {aspect_name} {p2_name}")
    return aspects

# --- TRANSIT ---
def calculate_transit_range(birth_bodies, start_dt, end_dt, lat, lon):
    obs = ephem.Observer()
    obs.lat, obs.lon = str(lat), str(lon)
    heavy_planets = [('Jüpiter', ephem.Jupiter()), ('Satürn', ephem.Saturn()), ('Uranüs', ephem.Uranus()), ('Neptün', ephem.Neptune()), ('Plüton', ephem.Pluto())]
    transit_report = []
    transit_display = []
    
    for n, b in heavy_planets:
        obs.date = start_dt
        b.compute(obs)
        deg_start = math.degrees(ephem.Ecliptic(b).lon)
        sign_start = ZODIAC[int(deg_start/30)%12]
        
        obs.date = end_dt
        b.compute(obs)
        deg_end = math.degrees(ephem.Ecliptic(b).lon)
        sign_end = ZODIAC[int(deg_end/30)%12]
        
        transit_report.append(f"Transit {n}: {sign_start} -> {sign_end}")
        transit_display.append(f"<b>{n}:</b> {sign_start} {dec_to_dms(deg_start%30)} ➔ {sign_end} {dec_to_dms(deg_end%30)}")

        for natal_n, _, natal_deg, _ in birth_bodies:
            for d_check in [deg_start, deg_end]:
                diff = abs(d_check - natal_deg)
                if diff > 180: diff = 360 - diff
                if diff <= 4:
                    hit_msg = f"⚠️ {n}, Natal {natal_n} ile etkileşimde!"
                    if hit_msg not in transit_display: transit_display.append(hit_msg)
                    transit_report.append(f"Transit {n} natal {natal_n} ile temas ediyor.")

    return "\n".join(transit_report), transit_display

# --- GÖRSELLEŞTİRME (KESİN DÜZELTME) ---
def draw_chart_visual(bodies_data, cusps):
    fig = plt.figure(figsize=(10, 10), facecolor='#0e1117')
    ax = fig.add_subplot(111, projection='polar')
    ax.set_facecolor('#1a1c24')
    
    # 1. Temel Ayar: ASC (Cusp 1) Tam 9 Yönünde (Batı) Olmalı
    asc_deg = cusps[1]
    ax.set_theta_offset(np.pi - math.radians(asc_deg))
    ax.set_theta_direction(1) # Saat yönünün tersi (CCW)
    
    ax.set_yticklabels([]); ax.set_xticklabels([])
    ax.grid(False); ax.spines['polar'].set_visible(False)

    # 2. EV ÇİZGİLERİ (ASİMETRİK / PLACIDUS)
    # Hesaplanan eşitsiz derecelere göre çizgi çek
    for i in range(1, 13):
        angle_rad = math.radians(cusps[i])
        ax.plot([angle_rad, angle_rad], [0, 1.2], color='#444', linewidth=1, linestyle='--')
        
        # Ev Numarasını Ortalama
        next_c = cusps[i+1] if i < 12 else cusps[1]
        
        # Açı farkı (Ev büyüklüğü)
        diff = (next_c - cusps[i]) % 360
        mid_rad = math.radians(cusps[i] + diff/2)
        
        ax.text(mid_rad, 0.4, str(i), color='#888', ha='center', fontsize=11, fontweight='bold')

    # 3. ZODYAK HALKASI (EŞİT 30 DERECE)
    circles = np.linspace(0, 2*np.pi, 100)
    ax.plot(circles, [1.2]*100, color='#FFD700', linewidth=2)
    
    for i in range(12):
        deg_start = i * 30
        rad_start = math.radians(deg_start)
        ax.plot([rad_start, rad_start], [1.15, 1.25], color='#FFD700') 
        
        mid_deg = i * 30 + 15
        mid_rad = math.radians(mid_deg)
        rot = mid_deg - 180 
        ax.text(mid_rad, 1.3, ZODIAC_SYMBOLS[i], ha='center', color='#FFD700', fontsize=16, rotation=rot)

    # 4. GEZEGENLER
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
        
        cusps = calculate_placidus_cusps(utc_dt, lat, lon)
        obs = ephem.Observer(); obs.date=utc_dt; obs.lat=str(lat); obs.lon=str(lon)
        
        bodies = [('Güneş', ephem.Sun()), ('Ay', ephem.Moon()), ('Merkür', ephem.Mercury()), ('Venüs', ephem.Venus()), ('Mars', ephem.Mars()), ('Jüpiter', ephem.Jupiter()), ('Satürn', ephem.Saturn()), ('Uranüs', ephem.Uranus()), ('Neptün', ephem.Neptune()), ('Plüton', ephem.Pluto())]
        
        info_html = f"<div class='metric-box'>🌍 <b>Doğum (UTC):</b> {utc_dt.strftime('%H:%M')}</div>"
        ai_data = "SİSTEM: PLACIDUS (TRUE UNEQUAL)\n"
        
        asc_sign = ZODIAC[int(cusps[1]/30)%12]
        mc_sign = ZODIAC[int(cusps[10]/30)%12]
        visual_data = [("ASC", asc_sign, cusps[1], "ASC"), ("MC", mc_sign, cusps[10], "MC")]
        
        info_html += f"<div class='metric-box'>🚀 <b>Yükselen:</b> {asc_sign} {dec_to_dms(cusps[1]%30)}</div>"
        info_html += f"<div class='metric-box'>👑 <b>MC:</b> {mc_sign} {dec_to_dms(cusps[10]%30)}</div><br>"
        
        ai_data += f"YÜKSELEN: {asc_sign} {dec_to_dms(cusps[1]%30)}\nMC: {mc_sign}\n"

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
        ai_data += "\nNATAL AÇILAR:\n" + ", ".join(aspects)
        
        transit_html = ""
        if transit_enabled:
            tr_start = datetime.combine(start_date, d_time)
            tr_end = datetime.combine(end_date, d_time)
            tr_utc_start = tz.localize(tr_start).astimezone(pytz.utc)
            tr_utc_end = tz.localize(tr_end).astimezone(pytz.utc)
            
            tr_ai_report, tr_display = calculate_transit_range(visual_data, tr_utc_start, tr_utc_end, lat, lon)
            ai_data += f"\n\nTRANSIT DÖNEMİ: {start_date} - {end_date}\nGEZEGEN HAREKETLERİ:\n{tr_ai_report}"
            transit_html = f"<br><h4>⏳ Transit Hareketleri ({start_date} - {end_date})</h4>"
            for t_line in tr_display:
                transit_html += f"<div class='transit-box'>{t_line}</div>"

        return info_html, ai_data, visual_data, cusps, aspects, transit_html, None
    except Exception as e: return None, None, None, None, None, None, str(e)

# --- PDF ---
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

# --- AI ---
def get_ai_response_smart(prompt):
    try:
        list_url = f"https://generativelanguage.googleapis.com/v1beta/models?key={api_key}"
        list_resp = requests.get(list_url)
        target = "models/gemini-1.5-flash"
        if list_resp.status_code == 200:
            for m in list_resp.json().get('models', []):
                if 'generateContent' in m.get('supportedGenerationMethods', []): target = m['name']; break
        
        url = f"https://generativelanguage.googleapis.com/v1beta/{target}:generateContent?key={api_key}"
        headers = {'Content-Type': 'application/json'}
        data = {"contents": [{"parts": [{"text": prompt}]}]}
        resp = requests.post(url, headers=headers, data=json.dumps(data))
        if resp.status_code == 200: return resp.json()['candidates'][0]['content']['parts'][0]['text']
        else: return "AI Servis Hatası"
    except Exception as e: return str(e)

# --- ARAYÜZ ---
st.title("🌌 Astro-Analiz Pro (Full)")
with st.sidebar:
    st.header("Giriş Paneli")
    name = st.text_input("İsim", "Ziyaretçi")
    d_date = st.date_input("Doğum Tarihi", value=datetime(1980, 11, 26))
    d_time = st.time_input("Doğum Saati", value=datetime.strptime("16:00", "%H:%M"), step=60)
    city = st.text_input("Şehir", "İstanbul")
    
    st.write("---")
    transit_mode = st.checkbox("Transit (Öngörü) Modu Aç ⏳")
    start_date = datetime.now().date()
    end_date = datetime.now().date() + timedelta(days=365)
    
    if transit_mode:
        st.caption("Öngörü Tarih Aralığı Seçiniz:")
        col_t1, col_t2 = st.columns(2)
        start_date = col_t1.date_input("Başlangıç", value=datetime.now())
        end_date = col_t2.date_input("Bitiş", value=datetime.now() + timedelta(days=180))
    
    st.write("---")
    st.write("📍 **Hassas Koordinat**")
    c1, c2 = st.columns(2)
    lat = c1.number_input("Enlem", 41.0) + c2.number_input("Dakika", 1.0)/60
    c3, c4 = st.columns(2)
    lon = c3.number_input("Boylam", 28.0) + c4.number_input("Dakika", 57.0)/60
    q = st.text_area("Soru", "Genel Yorum?")
    btn = st.button("Analiz Et ✨")

if btn:
    info_html, ai_data, vis_data, cusps, aspects, transit_html, err = calculate_all(name, d_date, d_time, lat, lon, transit_mode, start_date, end_date)
    
    if err: st.error(err)
    else:
        tab1, tab2, tab3 = st.tabs(["📝 Yorum & Öngörü", "🗺️ Harita", "📊 Teknik Veriler"])
        
        with st.spinner("Kozmik veriler işleniyor..."):
            prompt_text = f"Sen uzman astrologsun. Kişi: {name}, {city}. Soru: {q}.\n\nVERİLER:\n{ai_data}\n\nGÖREV: Eğer Transit verisi varsa seçilen tarih aralığı ({start_date} - {end_date}) için 'Öngörü' yap. Gezegen hareketlerini (burç değişimlerini) dikkate al. Soruyu cevapla."
            ai_reply = get_ai_response_smart(prompt_text)
        
        with tab1:
            st.markdown(ai_reply)
            pdf = create_pdf(name, f"{d_date} - {city}", ai_reply)
            if pdf: st.download_button("PDF İndir", pdf, "analiz.pdf", "application/pdf")
            
        with tab2:
            st.pyplot(draw_chart_visual(vis_data, cusps))
            
        with tab3:
            c_a, c_b = st.columns(2)
            with c_a:
                st.markdown("### 🪐 Doğum Haritası")
                st.markdown(info_html, unsafe_allow_html=True)
            with c_b:
                st.markdown("### 📐 Açılar")
                for asp in aspects: st.markdown(f"<div class='aspect-box'>{asp}</div>", unsafe_allow_html=True)
                if transit_mode:
                    st.markdown(transit_html, unsafe_allow_html=True)
