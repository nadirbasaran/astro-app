import streamlit as st
import ephem
import math
from datetime import datetime
import requests
import json
import pytz # Zaman dilimi kütüphanesi

# --- SAYFA AYARLARI ---
st.set_page_config(page_title="Astro-Analiz Pro", layout="wide", page_icon="🔮")

# --- API ANAHTARI KONTROLÜ ---
if "GOOGLE_API_KEY" in st.secrets:
    api_key = st.secrets["GOOGLE_API_KEY"]
else:
    st.error("🚨 HATA: API Anahtarı bulunamadı!")
    st.stop()

# --- YARDIMCI: DERECEYİ DAKİKAYA ÇEVİR (4.5 -> 4° 30') ---
def dec_to_dms(deg):
    d = int(deg)
    m = int((deg - d) * 60)
    return f"{d}° {m:02d}'"

# --- HESAPLAMA (HASSAS ZAMANLI) ---
ZODIAC = ["Koç", "Boğa", "İkizler", "Yengeç", "Aslan", "Başak", "Terazi", "Akrep", "Yay", "Oğlak", "Kova", "Balık"]

def calculate_chart_precise(name, d_date, d_time, city, lat, lon):
    try:
        # 1. Yerel Saati Oluştur
        local_dt = datetime.combine(d_date, d_time)
        
        # 2. Zaman Dilimini Ayarla (İstanbul için)
        # 1980'deki yaz/kış saati uygulamasını otomatik bulur
        tz = pytz.timezone('Europe/Istanbul') 
        local_dt_aware = tz.localize(local_dt)
        
        # 3. NASA İçin UTC'ye Çevir
        utc_dt = local_dt_aware.astimezone(pytz.utc)
        
        # 4. Ephem Gözlemcisini Kur
        obs = ephem.Observer()
        obs.lat, obs.lon = str(lat), str(lon)
        obs.date = utc_dt # Artık UTC zamanını veriyoruz, kayma olmaz!
        
        info_text = f"**GEZEGEN KONUMLARI (Hassas):**\n*Hesaplanan UTC Zamanı: {utc_dt.strftime('%H:%M')}*\n\n"
        chart_data_for_ai = "Gezegen Konumları:\n"
        
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
            
            # Burç içindeki derece (0-30 arası)
            deg_in_sign = deg_total % 30
            dms_str = dec_to_dms(deg_in_sign)
            
            # Retro (Geri Hareket) Kontrolü (İsteğe bağlı, basit hesap)
            # Ephem direk retro vermez ama hızdan anlaşılır, şimdilik detaya girmiyoruz.
            
            line = f"- {n}: {sign} {dms_str}\n"
            info_text += line
            chart_data_for_ai += f"{n} {sign} Burcunda, {dms_str} derecesinde.\n"
            
        return info_text, chart_data_for_ai, None
    except Exception as e: return None, None, str(e)

# --- AI İSTEK ---
def get_ai_response(prompt):
    try:
        list_url = f"https://generativelanguage.googleapis.com/v1beta/models?key={api_key}"
        list_resp = requests.get(list_url)
        if list_resp.status_code != 200: return "Model listesi alınamadı."
        
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
            return f"Thinking Process: **{target_model}**\n\n" + resp.json()['candidates'][0]['content']['parts'][0]['text']
        else:
            return f"Hata: {resp.text}"
    except Exception as e: return str(e)

# --- ARAYÜZ ---
st.title("🔮 Astro-Analiz (Hassas Mod)")

with st.sidebar:
    st.header("Giriş")
    name = st.text_input("İsim", "Ziyaretçi")
    d_date = st.date_input("Tarih", value=datetime(1980, 11, 26))
    d_time = st.time_input("Saat", value=datetime.strptime("16:00", "%H:%M"))
    city = st.text_input("Şehir", "İstanbul")
    
    # Koordinatlar (Varsayılan İstanbul)
    c1, c2 = st.columns(2)
    lat = c1.number_input("Enlem", 41.00)
    lon = c2.number_input("Boylam", 28.97)
    
    q = st.text_area("Soru", "Kariyerim hakkında yorumlar mısın?")
    btn = st.button("Analiz Et ✨", type="primary")

if btn:
    c1, c2 = st.columns(2)
    with c1:
        st.info("Teknik Veriler (DMS Formatı)")
        display_data, ai_data, err = calculate_chart_precise(name, d_date, d_time, city, lat, lon)
        if display_data: st.markdown(display_data)
        else: st.error(err)
        
    with c2:
        st.success("Yorum")
        if ai_data:
            with st.spinner("Yıldızlar okunuyor..."):
                prompt = f"Sen astrologsun. Kişi: {name}, {city}. Soru: {q}.\n\n{ai_data}\n\nLütfen bu hassas derecelere göre yorumla."
                res = get_ai_response(prompt)
                st.markdown(res)
