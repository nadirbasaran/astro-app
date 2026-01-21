import streamlit as st
import ephem
import math
from datetime import datetime
import requests
import json

# --- SAYFA AYARLARI ---
st.set_page_config(page_title="Astro-Analiz Pro", layout="wide", page_icon="🔮")

# --- API ANAHTARI KONTROLÜ ---
if "GOOGLE_API_KEY" in st.secrets:
    api_key = st.secrets["GOOGLE_API_KEY"]
else:
    st.error("🚨 HATA: API Anahtarı 'Secrets' kısmında bulunamadı!")
    st.stop()

# --- DİREKT BAĞLANTI FONKSİYONU (KÜTÜPHANESİZ) ---
def get_ai_response(prompt):
    # Google'ın en yeni ve hızlı modeli
    model_name = "gemini-1.5-flash"
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={api_key}"
    
    headers = {'Content-Type': 'application/json'}
    data = {
        "contents": [{
            "parts": [{"text": prompt}]
        }]
    }
    
    try:
        # Direkt internet isteği gönderiyoruz (Requests)
        response = requests.post(url, headers=headers, data=json.dumps(data))
        
        if response.status_code == 200:
            return response.json()['candidates'][0]['content']['parts'][0]['text']
        else:
            return f"⚠️ **HATA:** Google sunucusu {response.status_code} koduyla yanıt verdi.\nDetay: {response.text}"
            
    except Exception as e:
        return f"⚠️ **BAĞLANTI HATASI:** {str(e)}"

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
st.title("🔮 Astro-Analiz (Final Sürüm)")
st.caption("NASA Verisi + Google Gemini (Direkt Bağlantı)")

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
            with st.spinner("AI Yanıtlıyor..."):
                prompt = f"Sen astrologsun. Kişi: {name}, {city}. Soru: {q}. Veriler: {data}"
                res = get_ai_response(prompt)
                st.markdown(res)
