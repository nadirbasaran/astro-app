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
# UI / CSS
# =========================================================
st.set_page_config(page_title="Astro-Analiz Pro", layout="wide", page_icon="🔮")

st.markdown("""
<style>
.stApp { background: linear-gradient(to bottom, #0e1117, #24283b); color: #e0e0e0; }
h1, h2, h3 { color: #FFD700 !important; font-family: 'Helvetica', sans-serif; text-shadow: 2px 2px 4px #000000; }

/* FORM BUTONU İÇİN ÖZEL STİL - MOBİL VE WEB UYUMLU */
[data-testid="stFormSubmitButton"] > button { 
    background-color: #FFD700 !important; 
    color: #000 !important; 
    border-radius: 20px; 
    border: none; 
    font-weight: bold; 
    width: 100%; 
    height: 50px;
    font-size: 18px;
    margin-top: 10px;
}
[data-testid="stFormSubmitButton"] > button:hover {
    background-color: #FFC107 !important;
    color: #000 !important;
}

[data-testid="stSidebar"] { background-color: #161a25; border-right: 1px solid #FFD700; }
.metric-box { background-color: #1e2130; padding: 10px; border-radius: 8px; border-left: 4px solid #FFD700; margin-bottom: 8px; font-size: 14px; color: white; }
.metric-box b { color: #FFD700; }
.aspect-box { background-color: #25293c; padding: 5px 10px; margin: 2px; border-radius: 4px; font-size: 13px; border: 1px solid #444; }
.transit-box { background-color: #2d1b2e; border-left: 4px solid #ff4b4b; padding: 8px; margin-bottom: 6px; font-size: 13px; }
.small-note { color: #9aa0aa; font-size: 12px; }
.error-box { background-color: #ff4b4b20; border-left: 4px solid #ff4b4b; padding: 10px; margin: 10px 0; border-radius: 5px; }
</style>
""", unsafe_allow_html=True)

# =========================================================
# API (Gemini) KONTROLÜ
# =========================================================
if "GOOGLE_API_KEY" not in st.secrets:
    st.error("🚨 Lütfen 'secrets' ayarlarından GOOGLE_API_KEY ekleyin.")
    st.stop()
API_KEY = st.secrets["GOOGLE_API_KEY"]

# =========================================================
# SABİTLER
# =========================================================
ZODIAC = ["Koç","Boğa","İkizler","Yengeç","Aslan","Başak","Terazi","Akrep","Yay","Oğlak","Kova","Balık"]
ZODIAC_SYMBOLS = ["♈","♉","♊","♋","♌","♍","♎","♏","♐","♑","♒","♓"]
PLANET_SYMBOLS = {
    "Güneş":"☉","Ay":"☽","Merkür":"☿","Venüs":"♀","Mars":"♂",
    "Jüpiter":"♃","Satürn":"♄","Uranüs":"♅","Neptün":"♆","Plüton":"♇",
    "ASC":"ASC","MC":"MC"
}

def get_planet_objects():
    return {
        "Güneş": ephem.Sun(), "Ay": ephem.Moon(), "Merkür": ephem.Mercury(),
        "Venüs": ephem.Venus(), "Mars": ephem.Mars(), "Jüpiter": ephem.Jupiter(),
        "Satürn": ephem.Saturn(), "Uranüs": ephem.Uranus(), "Neptün": ephem.Neptune(),
        "Plüton": ephem.Pluto()
    }

ELEMENT = {"Koç":"Ateş","Aslan":"Ateş","Yay":"Ateş","Boğa":"Toprak","Başak":"Toprak","Oğlak":"Toprak","İkizler":"Hava","Terazi":"Hava","Kova":"Hava","Yengeç":"Su","Akrep":"Su","Balık":"Su"}
QUALITY = {"Koç":"Öncü","Yengeç":"Öncü","Terazi":"Öncü","Oğlak":"Öncü","Boğa":"Sabit","Aslan":"Sabit","Akrep":"Sabit","Kova":"Sabit","İkizler":"Değişken","Başak":"Değişken","Yay":"Değişken","Balık":"Değişken"}
HOUSE_TOPICS = {1:"Kimlik", 2:"Para", 3:"İletişim", 4:"Aile", 5:"Aşk", 6:"İş/Sağlık", 7:"İlişkiler", 8:"Dönüşüm", 9:"İnanç", 10:"Kariyer", 11:"Sosyal", 12:"Bilinçaltı"}
ASPECT_ANGLES = {"Kavuşum":0,"Sekstil":60,"Kare":90,"Üçgen":120,"Karşıt":180}
ASPECT_ORBS = {"Kavuşum":8,"Sekstil":6,"Kare":8,"Üçgen":8,"Karşıt":8}

# =========================================================
# YARDIMCI FONKSİYONLAR
# =========================================================
def normalize(deg): return deg % 360
def angle_diff(a,b): d = abs(a-b); return min(d, 360-d)
def dec_to_dms(deg): d = int(deg); m = int(round((deg - d) * 60)); return f"{d:02d}° {m:02d}'" if m!=60 else f"{d+1:02d}° 00'"
def sign_name(deg): return ZODIAC[int(deg/30) % 12]
def get_element(sign): return ELEMENT.get(sign, "-")
def get_quality(sign): return QUALITY.get(sign, "-")

def clean_text_for_pdf(text):
    replacements = {'ğ':'g','Ğ':'G','ş':'s','Ş':'S','ı':'i','İ':'I','ü':'u','Ü':'U','ö':'o','Ö':'O','ç':'c','Ç':'C','–':'-'}
    for k,v in replacements.items(): text = text.replace(k,v)
    return text.encode('latin-1','ignore').decode('latin-1')

def city_to_latlon(city):
    try:
        r = requests.get("https://nominatim.openstreetmap.org/search", params={"q": city, "format":"json", "limit": 1}, headers={"User-Agent":"astro-analiz-pro"}, timeout=10)
        js = r.json()
        if js: return float(js[0]["lat"]), float(js[0]["lon"])
    except: pass
    return None, None

# =========================================================
# HESAPLAMA MOTORU (Hata Korumalı)
# =========================================================
def calculate_placidus_cusps(utc_dt, lat, lon):
    obs = ephem.Observer()
    # HATA ÖNLEYİCİ: Tarihi string yapıyoruz
    obs.date = utc_dt.strftime('%Y/%m/%d %H:%M:%S')
    obs.lat, obs.lon = str(lat), str(lon)
    
    ramc = float(obs.sidereal_time())
    eps = math.radians(23.44)
    lat_rad = math.radians(lat)
    
    mc_deg = normalize(math.degrees(math.atan2(math.tan(ramc), math.cos(eps))))
    if not (0 <= abs(mc_deg - math.degrees(ramc)) <= 90 or 0 <= abs(mc_deg - math.degrees(ramc) - 360) <= 90):
        mc_deg = normalize(mc_deg + 180)
    
    asc_deg = normalize(math.degrees(math.atan2(math.cos(ramc), -(math.sin(ramc)*math.cos(eps) + math.tan(lat_rad)*math.sin(eps)))))
    
    cusps = {1: asc_deg, 4: normalize(mc_deg+180), 7: normalize(asc_deg+180), 10: mc_deg}
    for i in range(2, 10):
        if i not in cusps: cusps[i] = normalize(asc_deg + (i-1)*30) # Basit yedekleme
    return cusps

def get_house_of_planet(deg, cusps):
    return int(deg / 30) + 1

# =========================================================
# ANA HESAPLAMA (Veri Bütünlüğü Garantili)
# =========================================================
def calculate_all(name, city, d_date, d_time, lat, lon, tz_mode, utc_offset, transit_enabled, start_date, end_date):
    local_dt = datetime.combine(d_date, d_time)
    if tz_mode == "manual_gmt":
        utc_dt = local_dt - timedelta(hours=int(utc_offset))
        tz_label = f"GMT{int(utc_offset):+d}"
    else:
        tz = pytz.timezone("Europe/Istanbul")
        utc_dt = tz.localize(local_dt).astimezone(pytz.utc).replace(tzinfo=None)
        tz_label = "Istanbul"

    # 1. Evler
    cusps = calculate_placidus_cusps(utc_dt, lat, lon)
    asc_sign = sign_name(cusps[1])
    mc_sign = sign_name(cusps[10])

    # 2. Gezegenler & Görsel Veri (4'lü Paket)
    obs = ephem.Observer()
    obs.date = utc_dt.strftime('%Y/%m/%d %H:%M:%S')
    obs.lat, obs.lon = str(lat), str(lon)
    obs.epoch = utc_dt.strftime('%Y/%m/%d %H:%M:%S')

    info_html = f"<div class='metric-box'>🌍 <b>Doğum:</b> {utc_dt.strftime('%d.%m.%Y %H:%M')} <span class='small-note'>({tz_label})</span></div>"
    info_html += f"<div class='metric-box'>🚀 <b>Yükselen:</b> {asc_sign} | <b>MC:</b> {mc_sign}</div>"
    ai_data = f"İsim: {name}\nŞehir: {city}\nASC: {asc_sign}\n"

    # UNPACK HATASINI ÖNLEMEK İÇİN SABİT YAPI: (İsim, Burç, Derece, Sembol)
    visual_data = [
        ("ASC", asc_sign, cusps[1], "ASC"),
        ("MC", mc_sign, cusps[10], "MC")
    ]

    planet_objs = get_planet_objects()
    for pname, body in planet_objs.items():
        body.compute(obs)
        deg = normalize(math.degrees(ephem.Ecliptic(body).lon))
        sign = sign_name(deg)
        h = get_house_of_planet(deg, cusps)
        
        info_html += f"<div class='metric-box'><b>{pname}</b>: {sign} {dec_to_dms(deg%30)} ({h}. Ev)</div>"
        ai_data += f"{pname}: {sign} ({h}. Ev)\n"
        
        # LİSTEYE EKLERKEN 4 PARÇA OLDUĞUNDAN EMINIZ
        visual_data.append((pname, sign, deg, PLANET_SYMBOLS.get(pname,"")))

    # 3. Açılar
    aspects_str = []
    # Sadece gezegenleri al (ilk 2 eleman ASC/MC, onları atla)
    p_list = visual_data[2:] 
    for i in range(len(p_list)):
        for j in range(i+1, len(p_list)):
            n1, _, d1, _ = p_list[i] # 4 parça var, hata vermez
            n2, _, d2, _ = p_list[j] # 4 parça var, hata vermez
            dd = angle_diff(d1, d2)
            for asp, ang in ASPECT_ANGLES.items():
                if abs(dd - ang) <= ASPECT_ORBS.get(asp, 8):
                    aspects_str.append(f"{n1} {asp} {n2} ({int(dd)}°)")
                    break
    
    ai_data += "Açılar: " + ", ".join(aspects_str) + "\n"

    # 4. Element/Nitelik
    elem_c = {"Ateş":0,"Toprak":0,"Hava":0,"Su":0}
    qual_c = {"Öncü":0,"Sabit":0,"Değişken":0}
    for n, s, d, sym in visual_data[2:]: # Sadece gezegenler
        e = get_element(s); q = get_quality(s)
        if e in elem_c: elem_c[e]+=1
        if q in qual_c: qual_c[q]+=1

    # 5. Transit (Hata Korumalı)
    transit_html = ""
    transit_hits = ""
    if transit_enabled:
        t_start = datetime.combine(start_date, d_time)
        t_end = datetime.combine(end_date, d_time)
        obs_tr = ephem.Observer()
        obs_tr.lat, obs_tr.lon = str(lat), str(lon)
        
        tr_lines = []
        for pname in ["Jüpiter", "Satürn", "Plüton"]:
            body = get_planet_objects()[pname]
            obs_tr.date = t_start.strftime('%Y/%m/%d %H:%M:%S')
            body.compute(obs_tr)
            s1 = sign_name(math.degrees(ephem.Ecliptic(body).lon))
            
            obs_tr.date = t_end.strftime('%Y/%m/%d %H:%M:%S')
            body.compute(obs_tr)
            s2 = sign_name(math.degrees(ephem.Ecliptic(body).lon))
            
            tr_lines.append(f"<div class='transit-box'><b>{pname}</b>: {s1} ➔ {s2}</div>")
            if s1 != s2: transit_hits += f"{pname} burç değiştiriyor: {s1}->{s2}. "
        
        transit_html = "".join(tr_lines)
        ai_data += f"\nTRANSIT: {transit_hits}"

    return {
        "info": info_html, "ai": ai_data, "vis": visual_data, "cusps": cusps,
        "asps": aspects_str, "tr_html": transit_html, "elem": elem_c, "qual": qual_c, "tr_hits": transit_hits
    }

# =========================================================
# AI & PDF
# =========================================================
def get_ai_response(prompt):
    # Kota hatasını (429) yakalayıp kullanıcıya göstermek için try-except
    try:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={API_KEY}"
        resp = requests.post(url, headers={'Content-Type':'application/json'}, data=json.dumps({"contents":[{"parts":[{"text":prompt}]}]}), timeout=10)
        
        if resp.status_code == 200:
            return resp.json()['candidates'][0]['content']['parts'][0]['text']
        elif resp.status_code == 429:
            return "⚠️ **AI Kotası Doldu:** Google API kullanım limitiniz dolmuş. Lütfen yeni bir API anahtarı alın. Analiziniz aşağıda harita verileriyle devam ediyor."
        else:
            return f"⚠️ AI Servis Hatası: {resp.status_code} ({resp.text[:100]}...)"
    except Exception as e:
        return f"Bağlantı Hatası: {str(e)}"

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
st.title("🌌 Astro-Analiz Pro (Final)")

with st.sidebar:
    st.header("Giriş Paneli")
    # FORM: Enter tuşu çalışır, buton sabittir
    with st.form("astro_form"):
        name = st.text_input("İsim", "Misafir")
        city = st.text_input("Şehir", "İstanbul")
        d_date = st.date_input("Doğum Tarihi", value=datetime(1980, 11, 26))
        d_time = st.time_input("Saat", value=datetime.strptime("16:00", "%H:%M"))
        
        st.write("---")
        tz_mode = st.radio("Zaman", ["Manuel GMT", "Otomatik (İstanbul)"], index=0)
        utc_offset = st.number_input("GMT Farkı", value=3)
        
        st.write("---")
        c1, c2 = st.columns(2)
        lat = c1.number_input("Enlem", 41.00)
        lon = c2.number_input("Boylam", 29.00)
        
        tr_mode = st.checkbox("Transit Modu")
        s_date = datetime.now().date(); e_date = s_date + timedelta(days=180)
        
        st.write("---")
        q = st.text_area("Sorunuz (Enter ile gönder)", "Genel yorum")
        
        # BUTON
        submitted = st.form_submit_button("ANALİZİ BAŞLAT ✨")

if submitted:
    try:
        data = calculate_all(name, city, d_date, d_time, lat, lon, "manual_gmt" if "Manuel" in tz_mode else "auto", utc_offset, tr_mode, s_date, e_date)
        
        t1, t2, t3 = st.tabs(["📝 Yorum", "🗺️ Harita", "📊 Veriler"])
        
        with t1:
            with st.spinner("Yıldızlar inceleniyor..."):
                ai_reply = get_ai_response(f"Sen astrologsun. {name}, {city}. Soru: {q}.\nVeri: {data['ai']}")
            
            # Eğer AI hata verdiyse (429 vs) bunu kutu içinde göster
            if "⚠️" in ai_reply:
                st.markdown(f"<div class='error-box'>{ai_reply}</div>", unsafe_allow_html=True)
            else:
                st.markdown(ai_reply)
                
            pdf = create_pdf(name, ai_reply)
            if pdf: st.download_button("PDF İndir", pdf, "analiz.pdf")

        with t2:
            fig = plt.figure(figsize=(8,8), facecolor='#0e1117')
            ax = fig.add_subplot(111, projection='polar'); ax.set_facecolor('#1a1c24')
            ax.set_theta_offset(np.pi - math.radians(data['cusps'][1])); ax.set_theta_direction(1)
            ax.set_yticklabels([])
            
            for i in range(12): 
                r=math.radians(i*30); ax.plot([r,r],[1,1.2], color='#FFD700', alpha=0.3)
                ax.text(r+0.25, 1.3, ZODIAC_SYMBOLS[i], color='white', fontsize=12)
            
            for n,s,d,sym in data['vis']:
                r=math.radians(d); c='#FF4B4B' if n in ("ASC","MC") else 'white'
                ax.plot(r, 1.05, 'o', color=c)
                ax.text(r, 1.15, sym, color=c, fontsize=10, ha='center')
            
            st.pyplot(fig)

        with t3:
            c1, c2 = st.columns(2)
            with c1: st.markdown(data['info'], unsafe_allow_html=True)
            with c2:
                st.markdown("### Açılar")
                for a in data['asps']: st.markdown(f"<div class='aspect-box'>{a}</div>", unsafe_allow_html=True)
                if tr_mode: st.markdown(data['tr_html'], unsafe_allow_html=True)
            
            st.markdown("### Element/Nitelik")
            c3, c4 = st.columns(2)
            c3.bar_chart(data['elem'])
            c4.bar_chart(data['qual'])

    except Exception as e:
        st.error(f"Beklenmedik Hata: {str(e)}")
