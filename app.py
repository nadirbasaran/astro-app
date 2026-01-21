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
    st.error("🚨 HATA: API Anahtarı bulunamadı!")
    st.stop()

# --- OTOMATİK MODEL SEÇİCİ VE İSTEK GÖNDERİCİ ---
def get_ai_response(prompt):
    try:
        # ADIM 1: Önce elimizdeki modelleri listele (Menüye Bak)
        list_url = f"https://generativelanguage.googleapis.com/v1beta/models?key={api_key}"
        list_resp = requests.get(list_url)
        
        if list_resp.status_code != 200:
            return f"⚠️ Model Listesi Alınamadı. Hata Kodu: {list_resp.status_code}"
            
        models = list_resp.json().get('models', [])
        
        # ADIM 2: 'generateContent' özelliğini destekleyen ilk modeli bul
        target_model_name = ""
        for m in models:
            if 'generateContent' in m.get('supportedGenerationMethods', []):
                target_model_name = m['name'] # Örn: models/gemini-1.0-pro
                break
        
        if not target_model_name:
            return "⚠️ Hesabınızda uygun bir AI modeli bulunamadı."

        # ADIM 3: Bulunan modele soruyu gönder
        generate_url = f"https://generativelanguage.googleapis.com/v1beta/{target_model_name}:generateContent?key={api_key}"
        
        headers = {'Content-Type': 'application/json'}
        data = {"contents": [{"parts": [{"text": prompt}]}]}
        
        response = requests.post(generate_url, headers=headers, data=json.dumps(data))
        
        if response.status_code == 200:
            # Başarılı! Cevabı al ve model ismini de ekle ki görelim
            ai_text = response.json()['candidates'][0]['content']['parts'][0]['text']
            return f"Thinking Process: **{target_model_name.replace('models/', '')}** kullanıldı.\n\n" + ai_text
        else:
            return f"⚠️ Hata ({target_model_name}): {response.text}"
            
    except Exception as e:
        return f"⚠️ Bağlantı Hatası: {str(e)}"

# --- HESAPLAMA (NASA) ---
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
st.title("🔮 Astro-Analiz (Akıllı Model)")

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
            with st.spinner("Uygun AI Modeli Aranıyor ve Yorumlanıyor..."):
                prompt = f"Sen astrologsun. Kişi: {name}, {city}. Soru: {q}. Veriler: {data}"
                res = get_ai_response(prompt)
                st.markdown(res)
