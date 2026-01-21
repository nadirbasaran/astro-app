import streamlit as st
import matplotlib
matplotlib.use('Agg') # Grafik hatasını önler
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
    # Türkçe karakterleri İngilizce karşılıklarına çevir (PDF çökmemesi için)
    replacements = {'ğ':'g', 'Ğ':'G', 'ş':'s', 'Ş':'S', 'ı':'i', 'İ':'I', 'ü':'u', 'Ü':'U', 'ö':'o', 'Ö':'O', 'ç':'c', 'Ç':'C', '–':'-', '’':"'", '“':'"', '”':'"', '…':'...'}
    for k, v in replacements.items(): text = text.replace(k, v)
    return text.encode('latin-1', 'replace').decode('latin-1')

# --- ASTROLOJİ HESAPLAMALARI ---
def normalize(deg):
    return deg % 360

def calculate_chart(name, d_date, d_time, lat, lon, utc_offset, transit_enabled, start_date, end_date):
    try:
        # 1. Tarih Ayarı
        local_dt = datetime.combine(d_date, d_time)
        utc_dt = local_dt - timedelta(hours=utc_offset)
        
        # --- KESİN ÇÖZÜM: TARİHİ STRING (METİN) OLARAK VERİYORUZ ---
        # Bu sayede "format string" hatası oluşamaz.
        # Format: 'YYYY/MM/DD HH:MM:SS'
        date_str = utc_dt.strftime('%Y/%m/%d %H:%M:%S')
        
        # 2. Gözlemci (Observer)
        obs = ephem.Observer()
        obs.lat = str(lat)
        obs.lon = str(lon)
        obs.date = date_str
        
        # KRİTİK: Güneş'i 7. Eve oturtan ayar (Epoch = Doğum Anı)
        # Bunu da string olarak veriyoruz.
        obs.epoch = date_str
        
        # 3. Ev Sistemi (Placidus & Eğim)
        ramc = float(obs.sidereal_time())
        ecl = ephem.Ecliptic(obs)
        eps = float(ecl.obliquity)
        lat_rad = math.radians(lat)
        
        # Köşe Evler
        mc_rad = math.atan2(math.tan(ramc), math.cos(eps))
        mc_deg = normalize(math.degrees(mc_rad))
        if not (0 <= abs(mc_deg - math.degrees(ramc)) <= 90 or 0 <= abs(mc_deg - math.degrees(ramc) - 360) <= 90):
            mc_deg = normalize(mc_deg + 180)
        ic_deg = normalize(mc_deg + 180)
        
        asc_rad = math.atan2(math.cos(ramc), -(math.sin(ramc)*math.cos(eps) + math.tan(lat_rad)*math.sin(eps)))
        asc_deg = normalize(math.degrees(asc_rad))
        dsc_deg = normalize(asc_deg + 180)

        # Ara Evler (Placidus Yaklaşımı - Unequal)
        def cusp_pole(offset_deg, factor):
            pole_rad = math.atan(math.tan(lat_rad) * factor)
            ramc_off = ramc + math.radians(offset_deg)
            top = math.cos(ramc_off)
            bot = -(math.sin(ramc_off)*math.cos(eps) + math.tan(pole_rad)*math.sin(eps))
            res = math.atan2(top, bot)
            return normalize(math.degrees(res))

        cusps = {1: asc_deg, 4: ic_deg, 7: dsc_deg, 10: mc_deg}
        cusps[11] = cusp_pole(30, 1/3); cusps[12] = cusp_pole(60, 2/3)
        cusps[2] = cusp_pole(120, 2/3); cusps[3] = cusp_pole(150, 1/3)
        cusps[5] = normalize(cusps[11] + 180); cusps[6] = normalize(cusps[12] + 180)
        cusps[8] = normalize(cusps[2] + 180); cusps[9] = normalize(cusps[3] + 180)

        # 4. Gezegenler
        bodies = [('Güneş', ephem.Sun()), ('Ay', ephem.Moon()), ('Merkür', ephem.Mercury()), ('Venüs', ephem.Venus()), ('Mars', ephem.Mars()), ('Jüpiter', ephem.Jupiter()), ('Satürn', ephem.Saturn()), ('Uranüs', ephem.Uranus()), ('Neptün', ephem.Neptune()), ('Plüton', ephem.Pluto())]
        
        info_html = f"<div class='metric-box'>🌍 <b>Doğum (UTC):</b> {utc_dt.strftime('%H:%M')} (GMT+{utc_offset})</div>"
        ai_data = "SİSTEM: PLACIDUS (Fixed Epoch)\n"
        
        asc_sign = ZODIAC[int(cusps[1]/30)%12]
        mc_sign = ZODIAC[int(cusps[10]/30)%12]
        visual_data = [("ASC", asc_sign, cusps[1], "ASC"), ("MC", mc_sign, cusps[10], "MC")]
        
        info_html += f"<div class='metric-box'>🚀 <b>Yükselen:</b> {asc_sign} {dec_to_dms(cusps[1]%30)}</div>"
        info_html += f"<div class='metric-box'>👑 <b>MC:</b> {mc_sign} {dec_to_dms(cusps[10]%30)}</div><br>"
        ai_data += f"YÜKSELEN: {asc_sign} {dec_to_dms(cusps[1]%30)}\nMC: {mc_sign}\n"

        # Ev Bulucu
        def get_house(deg, cusps_dict):
            for i in range(1, 13):
                start = cusps_dict[i]
                end = cusps_dict[i+1] if i < 12 else cusps_dict[1]
                if start < end:
                    if start <= deg < end: return i
                else:
                    if start <= deg or deg < end: return i
            return 1

        for n, b in bodies:
            b.compute(obs)
            # Standart Ecliptic Longitude Hesabı
            ecl_obj = ephem.Ecliptic(b)
            deg = math.degrees(ecl_obj.lon)
            
            sign_idx = int(deg/30)%12
            h = get_house(deg, cusps)
            dms = dec_to_dms(deg % 30)
            
            info_html += f"<div class='metric-box'><b>{n}</b>: {ZODIAC_SYMBOLS[sign_idx]} {ZODIAC[sign_idx]} {dms} | <b>{h}. Ev</b></div>"
            ai_data += f"{n}: {ZODIAC[sign_idx]} {dms} ({h}. Ev)\n"
            visual_data.append((n, ZODIAC[sign_idx], deg, PLANET_SYMBOLS.get(n, "")))

        # Açılar
        aspects = []
        planet_list = [(n, d) for n, _, d, _ in bodies]
        for i in range(len(planet_list)):
            for j in range(i+1, len(planet_list)):
                p1, d1 = planet_list[i]
                p2, d2 = planet_list[j]
                diff = abs(d1 - d2)
                if diff > 180: diff = 360 - diff
                asp = ""
                if diff <= 8: asp = "Kavuşum"
                elif 54 <= diff <= 66: asp = "Sekstil"
                elif 82 <= diff <= 98: asp = "Kare"
                elif 112 <= diff <= 128: asp = "Üçgen"
                elif 172 <= diff <= 180: asp = "Karşıt"
                if asp: aspects.append(f"{p1} {asp} {p2}")
        ai_data += "\nAÇILAR:\n" + ", ".join(aspects)

        # Transitler
        transit_html = ""
        if transit_enabled:
            tr_start = datetime.combine(start_date, d_time) - timedelta(hours=utc_offset)
            tr_end = datetime.combine(end_date, d_time) - timedelta(hours=utc_offset)
            
            obs_tr = ephem.Observer()
            obs_tr.lat, obs_tr.lon = str(lat), str(lon)
            tr_report, tr_display = [], []
            
            tr_planets = [('Jüpiter', ephem.Jupiter()), ('Satürn', ephem.Saturn()), ('Uranüs', ephem.Uranus()), ('Neptün', ephem.Neptune()), ('Plüton', ephem.Pluto())]
            
            for n, b in tr_planets:
                # String Formatı ile Hata Önleme
                obs_tr.date = tr_start.strftime('%Y/%m/%d %H:%M:%S')
                obs_tr.epoch = obs_tr.date 
                b.compute(obs_tr)
                ecl_start = ephem.Ecliptic(b)
                d1 = math.degrees(ecl_start.lon)
                
                obs_tr.date = tr_end.strftime('%Y/%m/%d %H:%M:%S')
                obs_tr.epoch = obs_tr.date
                b.compute(obs_tr)
                ecl_end = ephem.Ecliptic(b)
                d2 = math.degrees(ecl_end.lon)
                
                s1 = ZODIAC[int(d1/30)%12]
                s2 = ZODIAC[int(d2/30)%12]
                tr_display.append(f"<b>{n}:</b> {s1} -> {s2}")
                tr_report.append(f"Transit {n}: {s1} -> {s2}")
                
                for natal_n, _, natal_deg, _ in visual_data[2:]:
                    if abs(d1 - natal_deg) < 4 or abs(d2 - natal_deg) < 4:
                        tr_display.append(f"⚠️ {n} -> {natal_n}")
                        tr_report.append(f"{n} transit, {natal_n} ile temas.")
            
            ai_data += f"\n\nTRANSIT ({start_date}-{end_date}):\n" + "\n".join(set(tr_report))
            transit_html = "<br><h4>⏳ Transitler</h4>" + "".join([f"<div class='transit-box'>{l}</div>" for l in tr_display])

        return info_html, ai_data, visual_data, cusps, aspects, transit_html, None

    except Exception as e: return None, None, None, None, None, None, str(e)

# --- HARİTA GÖRSELİ ---
def draw_chart_visual(bodies_data, cusps):
    fig = plt.figure(figsize=(10, 10), facecolor='#0e1117')
    ax = fig.add_subplot(111, projection='polar')
    ax.set_facecolor('#1a1c24')
    
    asc_rad = math.radians(cusps[1])
    ax.set_theta_offset(np.pi - asc_rad)
    ax.set_theta_direction(1) 
    ax.grid(False); ax.set_yticklabels([]); ax.set_xticklabels([])

    for i in range(1, 13):
        rad = math.radians(cusps[i])
        ax.plot([rad, rad], [0, 1.2], color='#444', linewidth=1, linestyle='--')
        next_c = cusps[i+1] if i < 12 else cusps[1]
        mid = math.radians(cusps[i] + (next_c - cusps[i]) % 360 / 2)
        ax.text(mid, 0.4, str(i), color='#888', ha='center', fontweight='bold')

    ax.plot(np.linspace(0, 2*np.pi, 100), [1.2]*100, color='#FFD700', linewidth=2)
    for i in range(12):
        deg = i * 30 + 15
        rad = math.radians(deg)
        rot = deg - 180
        ax.text(rad, 1.3, ZODIAC_SYMBOLS[i], ha='center', color='#FFD700', fontsize=16, rotation=rot)
        sep = math.radians(i*30)
        ax.plot([sep, sep], [1.15, 1.25], color='#FFD700')

    for name, sign, deg, sym in bodies_data:
        rad = math.radians(deg)
        color = '#FF4B4B' if name in ['ASC', 'MC'] else 'white'
        ax.plot(rad, 1.05, 'o', color=color, markersize=10, markeredgecolor='#FFD700')
        ax.text(rad, 1.17, sym, color=color, fontsize=12, ha='center')
    return fig

# --- PDF ---
def create_pdf(name, info, ai_text):
    try:
        pdf = FPDF()
        pdf.add_page()
        safe_name = clean_text_for_pdf(name)
        safe_info = clean_text_for_pdf(info)
        safe_ai = clean_text_for_pdf(ai_text)
        
        pdf.set_font("Arial", 'B', 16); pdf.cell(0, 10, f"ANALIZ: {safe_name}", ln=True, align='C')
        pdf.set_font("Arial", '', 12); pdf.cell(0, 10, safe_info, ln=True, align='C')
        pdf.ln(5)
        pdf.set_font("Arial", 'B', 14); pdf.cell(0, 10, "YORUM", ln=True)
        pdf.set_font("Arial", '', 11); pdf.multi_cell(0, 8, safe_ai)
        return pdf.output(dest='S').encode('latin-1', 'ignore')
    except: return None

def get_ai(prompt):
    if not api_key: return "API Key Eksik."
    try:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={api_key}"
        resp = requests.post(url, headers={'Content-Type': 'application/json'}, data=json.dumps({"contents": [{"parts": [{"text": prompt}]}]}))
        return resp.json()['candidates'][0]['content']['parts'][0]['text'] if resp.status_code==200 else "AI Hatası"
    except Exception as e: return str(e)

# --- ARAYÜZ ---
st.title("🌌 Astro-Analiz Pro (Final)")
# GÜVENLİK
def check_password():
    if "password_correct" not in st.session_state: st.session_state["password_correct"] = False
    def password_entered():
        if st.session_state["password"] == st.secrets["APP_PASSWORD"]: st.session_state["password_correct"] = True
        else: st.session_state["password_correct"] = False
    if st.session_state["password_correct"]: return True
    st.text_input("Şifre", type="password", on_change=password_entered, key="password"); return False

if not check_password(): st.stop()

with st.sidebar:
    st.header("Giriş")
    name = st.text_input("İsim", "Ziyaretçi")
    d_date = st.date_input("Tarih", value=datetime(1980, 11, 26))
    
    # --- DÜZELTME: STEP=60 EKLENDİ (DAKİKA SEÇİMİ) ---
    d_time = st.time_input("Saat", value=datetime.strptime("16:00", "%H:%M"), step=60)
    
    st.caption("Saat Dilimi (GMT)")
    utc_offset = st.number_input("GMT Farkı", value=3, min_value=-12, max_value=12, step=1)
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
    c1, c2 = st.columns(2)
    lat = c1.number_input("Enlem", 41.0) + c2.number_input("Dakika", 1.0)/60
    c3, c4 = st.columns(2)
    lon = c3.number_input("Boylam", 28.0) + c4.number_input("Dakika", 57.0)/60
    q = st.text_area("Soru", "Genel yorum?")
    btn = st.button("Analiz Et ✨")

if btn:
    info_html, ai_data, vis_data, cusps, aspects, transit_html, err = calculate_chart(name, d_date, d_time, lat, lon, utc_offset, transit_mode, start_date, end_date)
    
    if err: 
        # Hata durumunda bile uygulamanın çökmemesi için mesaj göster
        st.error(f"Hesaplama Hatası: {err}")
    else:
        tab1, tab2, tab3 = st.tabs(["📝 Yorum", "🗺️ Harita", "📊 Veri"])
        with st.spinner("Yıldızlar inceleniyor..."):
            ai_reply = get_ai(f"Sen astrologsun. Kişi: {name}, {city}. Soru: {q}.\n\nVERİLER:\n{ai_data}\n\nGÖREV: Transit varsa öngörü yap. Detaylı yorumla.")
        with tab1:
            st.markdown(ai_reply)
            pdf_bytes = create_pdf(name, f"{d_date} - {city}", ai_reply)
            if pdf_bytes: st.download_button("PDF İndir", pdf_bytes, "analiz.pdf", "application/pdf")
            else: st.warning("PDF oluşturulamadı.")
        with tab2: st.pyplot(draw_chart_visual(vis_data, cusps))
        with tab3:
            c1, c2 = st.columns(2)
            with c1: st.markdown(info_html, unsafe_allow_html=True)
            with c2: 
                st.markdown("### AÇILAR")
                for a in aspects: st.markdown(f"<div class='aspect-box'>{a}</div>", unsafe_allow_html=True)
                if transit_mode: st.markdown(transit_html, unsafe_allow_html=True)
