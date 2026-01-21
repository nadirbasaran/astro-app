import streamlit as st
import google.generativeai as genai
from datetime import datetime
import math
import ephem
import os

# --- SAYFA AYARLARI ---
st.set_page_config(page_title="Astro-Analiz Pro", layout="wide", page_icon="🔮")

# --- API ANAHTARI (GÜVENLİ YÖNTEM) ---
# Streamlit Cloud'da "Secrets" kısmından çekecek
try:
    api_key = st.secrets["GOOGLE_API_KEY"]
    genai.configure(api_key=api_key)
except:
    st.error("API Anahtarı bulunamadı! Lütfen Streamlit Secrets ayarlarını yapın.")
    st.stop()

# --- MODEL SEÇİCİ ---
def get_ai_response(prompt):
    models = ['models/gemini-1.5-flash', 'models/gemini-1.5-pro', 'models/gemini-1.0-pro']
    for m in models:
        try:
            model = genai.GenerativeModel(m)
            response = model.generate_content(prompt)
            return response.text
        except:
            continue
    return "Üzgünüm, şu an AI servislerine ulaşılamıyor."

# --- HESAPLAMA (NASA/EPHEM) ---
ZODIAC = ["Koç", "Boğa", "İkizler", "Yengeç", "Aslan", "Başak", "Terazi", "Akrep", "Yay", "Oğlak", "Kova", "Balık"]

def calculate_chart(name, d_date, d_time, lat, lon):
    try:
        obs = ephem.Observer()
        obs.lat, obs.lon = str(lat), str(lon)
        obs.date = f"{d_date.strftime('%Y/%m/%d')} {d_time.strftime('%H:%M:%S')}"
        
        info = "**GEZEGEN KONUMLARI (NASA/Ephem):**\n"
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
            deg = deg_total % 30
            info += f"- {n}: {sign} {deg:.2f}°\n"
        return info, None
    except Exception as e: return None, str(e)

# --- ARAYÜZ ---
st.title("🔮 Astro-Analiz (AI Destekli)")
st.markdown("NASA verileriyle hesaplar, Google Gemini AI ile yorumlar.")

with st.sidebar:
    st.header("Giriş Paneli")
    name = st.text_input("İsim", "Ziyaretçi")
    d_date = st.date_input("Tarih", value=datetime(1990, 1, 1))
    d_time = st.time_input("Saat", value=datetime.strptime("12:00", "%H:%M"))
    city = st.text_input("Şehir", "İstanbul")
    lat = st.number_input("Enlem", value=41.00, format="%.2f")
    lon = st.number_input("Boylam", value=28.97, format="%.2f")
    q = st.text_area("Soru", "Kariyerim hakkında yorumlar mısın?")
    btn = st.button("Analiz Et ✨", type="primary")

if btn:
    c1, c2 = st.columns(2)
    with c1:
        st.info("Teknik Veriler")
        data, err = calculate_chart(name, d_date, d_time, lat, lon)
        if data: st.text_area("Veri", data, height=500)
        else: st.error(err)
    with c2:
        st.success("Yorum")
        if data:
            with st.spinner("Yıldızlar okunuyor..."):
                prompt = f"Sen astrologsun. Kişi: {name}, {city}. Soru: {q}. Veriler: {data}"
                res = get_ai_response(prompt)
                st.markdown(res)
