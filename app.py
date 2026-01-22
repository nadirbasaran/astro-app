import streamlit as st
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import ephem
import math
from datetime import datetime, timedelta
import requests
import json
import pytz
import numpy as np
from fpdf import FPDF

# =========================================================
# AYARLAR & CSS
# =========================================================
st.set_page_config(page_title="Astro-Analiz Pro", layout="wide", page_icon="🔮")

st.markdown("""
<style>
.stApp { background: linear-gradient(to bottom, #0e1117, #24283b); color: #e0e0e0; }
h1, h2, h3 { color: #FFD700 !important; font-family: 'Helvetica', sans-serif; }
/* Form Butonu */
[data-testid="stFormSubmitButton"] > button { 
    background-color: #FFD700 !important; color: #000 !important; border-radius: 20px; border: none; font-weight: bold; width: 100%; height: 50px; font-size: 18px; margin-top: 10px;
}
[data-testid="stSidebar"] { background-color: #161a25; border-right: 1px solid #FFD700; }
.metric-box { background-color: #1e2130; padding: 10px; border-radius: 8px; border-left: 4px solid #FFD700; margin-bottom: 8px; font-size: 14px; color: white; }
.aspect-box { background-color: #25293c; padding: 5px 10px; margin: 2px; border-radius: 4px; font-size: 13px; border: 1px solid #444; }
.transit-box { background-color: #2d1b2e; border-left: 4px solid #ff4b4b; padding: 8px; margin-bottom: 6px; font-size: 13px; }
.error-box { background-color: #ff4b4b30; border-left: 4px solid #ff4b4b; padding: 10px; border-radius: 5px; color: white; }
</style>
""", unsafe_allow_html=True)

# API KONTROL
if "GOOGLE_API_KEY" not in st.secrets:
    st.error("🚨 Lütfen 'secrets' ayarlarından GOOGLE_API_KEY ekleyin.")
    st.stop()
API_KEY = st.secrets["GOOGLE_API_KEY"]

# =========================================================
# SABİTLER
# =========================================================
ZODIAC = ["Koç","Boğa","İkizler","Yengeç","Aslan","Başak","Terazi","Akrep","Yay","Oğlak","Kova","Balık"]
ZODIAC_SYMBOLS = ["♈","♉","♊","♋","♌","♍","♎","♏","♐","♑","♒","♓"]
PLANET_SYMBOLS = {"Güneş":"☉","Ay":"☽","Merkür":"☿","Venüs":"♀","Mars":"♂","Jüpiter":"♃","Satürn":"♄","Uranüs":"♅","Neptün":"♆","Plüton":"♇","ASC":"ASC","MC":"MC"}
ASPECT_ANGLES = {"Kavuşum":0,"Sekstil":60,"Kare":90,"Üçgen":120,"Karşıt":180}
ASPECT_ORBS = {"Kavuşum":8,"Sekstil":6,"Kare":8,"Üçgen":8,"Karşıt":8}

# =========================================================
# YARDIMCI FONKSİYONLAR
# =========================================================
def normalize(deg): return deg % 360
def angle_diff(a,b): d = abs(a-b); return min(d, 360-d)
def dec_to_dms(deg): d = int(deg); m = int(round((deg - d) * 60)); return f"{d:02d}° {m:02d}'" if m!=60 else f"{d+1:02d}° 00'"
def sign_name(deg): return ZODIAC[int(deg/30) % 12]
def clean_text_for_pdf(text):
    replacements = {'ğ':'g','Ğ':'G','ş':'s','Ş':'S','ı':'i','İ':'I','ü':'u','Ü':'U','ö':'o','Ö':'O','ç':'c','Ç':'C'}
    for k,v in replacements.items(): text = text.replace(k,v)
    return text.encode('latin-1','ignore').decode('latin-1')

def get_ephem_body(name):
    bodies = {"Güneş": ephem.Sun(), "Ay": ephem.Moon(), "Merkür": ephem.Mercury(), "Venüs": ephem.Venus(), "Mars": ephem.Mars(), "Jüpiter": ephem.Jupiter(), "Satürn": ephem.Saturn(), "Uranüs": ephem.Uranus(), "Neptün": ephem.Neptune(), "Plüton": ephem.Pluto()}
    return bodies.get(name)

# =========================================================
# TEMEL HESAPLAMA (GARANTİLİ YÖNTEM)
# =========================================================
def calculate_chart_data(name, city, d_date, d_time, lat, lon, utc_offset, transit_enabled, s_date, e_date):
    # 1. Tarih Hazırlığı (Hata vermeyen yöntem)
    local_dt = datetime.combine(d_date, d_time)
    utc_dt = local_dt - timedelta(hours=int(utc_offset))
    date_str = utc_dt.strftime('%Y/%m/%d %H:%M:%S') # KESİN ÇÖZÜM: String Format

    # 2. Gözlemci
    obs = ephem.Observer()
    obs.date = date_str
    obs.lat, obs.lon = str(lat), str(lon)
    # obs.epoch = date_str # Astro-Seek uyumu için bunu pasif yapıyoruz veya J2000 kullanıyoruz.

    # 3. ASC & MC (Trigonometrik)
    ra_mc = float(obs.sidereal_time())
    obl = math.radians(23.44)
    lat_rad = math.radians(lat)

    mc_rad = math.atan2(math.tan(ra_mc), math.cos(obl))
    mc_deg = normalize(math.degrees(mc_rad))
    if not (0 <= abs(mc_deg - math.degrees(ra_mc)) <= 90 or 0 <= abs(mc_deg - math.degrees(ra_mc) - 360) <= 90):
        mc_deg = normalize(mc_deg + 180)

    asc_rad = math.atan2(math.cos(ra_mc), -(math.sin(ra_mc)*math.cos(obl) + math.tan(lat_rad)*math.sin(obl)))
    asc_deg = normalize(math.degrees(asc_rad))

    # 4. EV SİSTEMİ (Equal House - Görsel Hata Vermez)
    # Placidus matematiksel olarak karmaşıktır ve kodda hata yaptırır. 
    # Equal sistemde 1. Ev ASC'dir, diğerleri +30 eklenerek gider. Görseli kusursuzdur.
    cusps = {}
    for i in range(1, 13):
        cusps[i] = normalize(asc_deg + (i-1)*30)
    
    # MC'yi 10. Ev girişi olarak kaydetmiyoruz (Equal sistemde MC haritada serbest dolaşır), 
    # ama görselde MC noktasını ayrıca çizeceğiz.

    asc_sign = sign_name(asc_deg)
    mc_sign = sign_name(mc_deg)

    info_html = f"<div class='metric-box'>🌍 <b>Doğum:</b> {local_dt.strftime('%d.%m.%Y %H:%M')}</div>"
    info_html += f"<div class='metric-box'>🚀 <b>Yükselen:</b> {asc_sign} {dec_to_dms(asc_deg%30)}</div>"
    info_html += f"<div class='metric-box'>👑 <b>MC:</b> {mc_sign} {dec_to_dms(mc_deg%30)}</div>"
    
    ai_data = f"İsim: {name}\nŞehir: {city}\nASC: {asc_sign} {dec_to_dms(asc_deg)}\nMC: {mc_sign}\n"

    # 5. Gezegenler (Unpack Hatası Önlemi: 4'lü tuple)
    visual_data = [
        ("ASC", asc_sign, asc_deg, "ASC"),
        ("MC", mc_sign, mc_deg, "MC")
    ]

    planet_list = ["Güneş", "Ay", "Merkür", "Venüs", "Mars", "Jüpiter", "Satürn", "Uranüs", "Neptün", "Plüton"]
    
    for pname in planet_list:
        body = get_ephem_body(pname)
        body.compute(obs)
        deg = normalize(math.degrees(ephem.Ecliptic(body).lon))
        sign = sign_name(deg)
        
        # Ev Bulucu (Equal House)
        # Gezegenin derecesi - ASC derecesi bize evini verir
        diff = normalize(deg - asc_deg)
        house_num = int(diff / 30) + 1
        
        info_html += f"<div class='metric-box'><b>{pname}</b>: {sign} {dec_to_dms(deg%30)} ({house_num}. Ev)</div>"
        ai_data += f"{pname}: {sign} ({house_num}. Ev)\n"
        
        visual_data.append((pname, sign, deg, PLANET_SYMBOLS.get(pname,"")))

    # 6. Açılar
    aspects_str = []
    # Sadece gezegenleri al (ASC/MC visual_data'nın ilk 2 elemanı, onları atla)
    p_objs = visual_data[2:] 
    for i in range(len(p_objs)):
        for j in range(i+1, len(p_objs)):
            n1, _, d1, _ = p_objs[i]
            n2, _, d2, _ = p_objs[j]
            diff = angle_diff(d1, d2)
            for asp, ang in ASPECT_ANGLES.items():
                if abs(diff - ang) <= ASPECT_ORBS.get(asp, 8):
                    aspects_str.append(f"{n1} {asp} {n2} ({int(diff)}°)")
                    break
    
    ai_data += "Açılar: " + ", ".join(aspects_str) + "\n"

    # 7. Transitler
    transit_html = ""
    if transit_enabled:
        t_start = datetime.combine(s_date, d_time) - timedelta(hours=int(utc_offset))
        t_end = datetime.combine(e_date, d_time) - timedelta(hours=int(utc_offset))
        
        obs_tr = ephem.Observer()
        obs_tr.lat, obs_tr.lon = str(lat), str(lon)
        
        tr_lines = []
        for pname in ["Jüpiter", "Satürn", "Plüton"]:
            body = get_ephem_body(pname)
            
            # Başlangıç
            obs_tr.date = t_start.strftime('%Y/%m/%d %H:%M:%S')
            body.compute(obs_tr)
            s1 = sign_name(math.degrees(ephem.Ecliptic(body).lon))
            
            # Bitiş
            obs_tr.date = t_end.strftime('%Y/%m/%d %H:%M:%S')
            body.compute(obs_tr)
            s2 = sign_name(math.degrees(ephem.Ecliptic(body).lon))
            
            tr_lines.append(f"<div class='transit-box'><b>{pname}:</b> {s1} ➔ {s2}</div>")
            if s1 != s2: ai_data += f"TRANSIT: {pname} {s1} burcundan {s2} burcuna geçiyor.\n"
        
        transit_html = "".join(tr_lines)

    return {
        "info": info_html, "ai": ai_data, "vis": visual_data, "cusps": cusps,
        "asps": aspects_str, "tr_html": transit_html
    }

# =========================================================
# ÇİZİM MOTORU (Düzeltildi)
# =========================================================
def draw_chart(visual_data, cusps):
    fig = plt.figure(figsize=(10,10), facecolor='#0e1117')
    ax = fig.add_subplot(111, projection='polar')
    ax.set_facecolor('#1a1c24')
    ax.grid(False)
    ax.set_yticklabels([])
    
    # Haritayı ASC'ye göre döndür (ASC solda = 180 derece)
    asc_deg = cusps[1]
    ax.set_theta_offset(np.pi - math.radians(asc_deg))
    ax.set_theta_direction(1) # Saat yönünün tersi

    # 1. Ev Çizgileri (Kusursuz 12 Dilim)
    for i in range(1, 13):
        angle = math.radians(cusps[i])
        ax.plot([angle, angle], [0, 1.2], color='#444', linewidth=1, linestyle='--')
        # Ev Numarası
        mid_angle = math.radians(cusps[i] + 15)
        ax.text(mid_angle, 0.4, str(i), color='#555', ha='center', fontweight='bold')

    # 2. Zodyak Çemberi
    circles = np.linspace(0, 2*np.pi, 100)
    ax.plot(circles, [1.2]*100, color='#FFD700', linewidth=2)
    
    for i in range(12):
        deg = i * 30 + 15
        rad = math.radians(deg)
        # Burç Sembolleri (Dönme açısını düzelterek)
        rot = deg - asc_deg - 90 # Metni merkeze hizala
        ax.text(rad, 1.25, ZODIAC_SYMBOLS[i], color='#FFD700', fontsize=14, ha='center')
        # Burç Ayrım Çizgileri
        sep = math.radians(i*30)
        ax.plot([sep, sep], [1.15, 1.25], color='#FFD700', linewidth=1)

    # 3. Gezegenler
    for name, sign, deg, sym in visual_data:
        rad = math.radians(deg)
        color = '#FF4B4B' if name in ["ASC", "MC"] else 'white'
        
        # MC ve ASC'yi çizgi olarak uzat
        if name in ["ASC", "MC"]:
            ax.plot([rad, rad], [0, 1.2], color=color, linewidth=2)
        
        ax.plot(rad, 1.05, 'o', color=color, markersize=8)
        ax.text(rad, 1.12, sym, color=color, fontsize=12, ha='center', fontweight='bold')

    return fig

# =========================================================
# AI & PDF
# =========================================================
def get_ai_response(prompt):
    try:
        # Hata vermeyen, en güncel model
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={API_KEY}"
        resp = requests.post(url, headers={'Content-Type':'application/json'}, data=json.dumps({"contents":[{"parts":[{"text":prompt}]}]}), timeout=8)
        
        if resp.status_code == 200:
            return resp.json()['candidates'][0]['content']['parts'][0]['text']
        else:
            return f"⚠️ AI Servis Hatası: {resp.status_code}. (Kota dolmuş veya API Key hatalı olabilir). Analiz verileri aşağıdadır."
    except Exception as e:
        return f"⚠️ Bağlantı Hatası: {str(e)}"

def create_pdf(name, text):
    try:
        pdf = FPDF(); pdf.add_page(); pdf.set_font("Arial", 'B', 16)
        pdf.cell(0, 10, clean_text_for_pdf(f"ANALIZ: {name}"), ln=True)
        pdf.set_font("Arial", '', 12); pdf.multi_cell(0, 8, clean_text_for_pdf(text))
        return pdf.output(dest='S').encode('latin-1', 'ignore')
    except: return None

# =========================================================
# ARAYÜZ
# =========================================================
st.title("🌌 Astro-Analiz Pro (Final - Stabil)")

with st.sidebar:
    st.header("Giriş")
    with st.form("astro_form"):
        name = st.text_input("İsim", "Ziyaretçi")
        city = st.text_input("Şehir", "İstanbul")
        d_date = st.date_input("Doğum Tarihi", value=datetime(1980, 11, 26))
        d_time = st.time_input("Saat", value=datetime.strptime("16:00", "%H:%M"))
        
        st.write("---")
        utc_offset = st.number_input("GMT Farkı (Türkiye: +3)", value=3)
        c1, c2 = st.columns(2)
        lat = c1.number_input("Enlem", 41.00)
        lon = c2.number_input("Boylam", 29.00)
        
        tr_mode = st.checkbox("Transit Modu")
        # Varsayılan tarihler
        s_val = datetime.now().date(); e_val = s_val + timedelta(days=180)
        if tr_mode:
            s_date = st.date_input("Başlangıç", value=s_val)
            e_date = st.date_input("Bitiş", value=e_val)
        else:
            s_date = s_val; e_date = e_val

        st.write("---")
        q = st.text_area("Sorunuz", "Genel yorum")
        
        # BUTON
        submitted = st.form_submit_button("ANALİZİ BAŞLAT ✨")

if submitted:
    try:
        # Şehir koordinat (opsiyonel)
        if city and lat==41.0 and lon==29.0:
            lt, ln = city_to_latlon(city)
            if lt: lat, lon = lt, ln

        data = calculate_chart_data(name, city, d_date, d_time, lat, lon, utc_offset, tr_mode, s_date, e_date)
        
        t1, t2, t3 = st.tabs(["📝 Yorum", "🗺️ Harita", "📊 Veriler"])
        
        with t1:
            with st.spinner("Yıldızlar hesaplanıyor..."):
                ai_reply = get_ai_response(f"Sen astrologsun. {name}, {city}. Soru: {q}.\nVeri: {data['ai']}")
            
            if "⚠️" in ai_reply:
                st.markdown(f"<div class='error-box'>{ai_reply}</div>", unsafe_allow_html=True)
            else:
                st.markdown(ai_reply)
            
            pdf = create_pdf(name, ai_reply)
            if pdf: st.download_button("PDF İndir", pdf, "analiz.pdf")

        with t2:
            st.pyplot(draw_chart(data['vis'], data['cusps']))

        with t3:
            st.markdown(data['info'], unsafe_allow_html=True)
            st.markdown("### Açılar")
            for a in data['asps']: st.markdown(f"<div class='aspect-box'>{a}</div>", unsafe_allow_html=True)
            if tr_mode: 
                st.markdown("### Transitler")
                st.markdown(data['tr_html'], unsafe_allow_html=True)

    except Exception as e:
        st.error(f"Kritik Hata: {str(e)}")
