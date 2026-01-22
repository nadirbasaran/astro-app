# ============================================================
# ASTRO-ANALIZ PRO – FINAL / STABLE
# ============================================================

import streamlit as st
import matplotlib
matplotlib.use("Agg")
import ephem
import math
import requests
from datetime import datetime, timedelta
from fpdf import FPDF

# -------------------- SAYFA --------------------
st.set_page_config(
    page_title="Astro-Analiz Pro",
    page_icon="🔮",
    layout="wide"
)

# -------------------- SABİTLER --------------------
ZODIAC = [
    "Koç","Boğa","İkizler","Yengeç","Aslan","Başak",
    "Terazi","Akrep","Yay","Oğlak","Kova","Balık"
]

PLANET_MEANING = {
    "Güneş":"kişilik ve yaşam amacı",
    "Ay":"duygusal yapı",
    "Merkür":"zihinsel süreçler",
    "Venüs":"ilişkiler ve değerler",
    "Mars":"motivasyon ve mücadele",
    "Jüpiter":"büyüme ve fırsatlar",
    "Satürn":"sorumluluk ve sınavlar",
    "Uranüs":"özgürlük ve değişim",
    "Neptün":"hayaller ve sezgi",
    "Plüton":"dönüşüm ve güç"
}

ASPECT_MEANING = {
    "Kavuşum": "hayatınızda güçlü bir etki yaratır",
    "Kare": "zorlayıcı ama geliştirici bir süreçtir",
    "Karşıt": "denge kurmanız gereken bir temayı gösterir",
    "Üçgen": "doğal ve destekleyici bir akış sağlar",
    "Sekstil": "fırsat ve gelişim potansiyeli sunar"
}

# -------------------- YARDIMCILAR --------------------
def normalize(x):
    return x % 360

def angle_diff(a, b):
    return min(abs(a - b), 360 - abs(a - b))

def city_to_latlon(city):
    try:
        r = requests.get(
            "https://nominatim.openstreetmap.org/search",
            params={"q": city, "format": "json", "limit": 1},
            headers={"User-Agent": "astro-analiz-app"},
            timeout=10
        )
        if r.status_code == 200 and r.json():
            return float(r.json()[0]["lat"]), float(r.json()[0]["lon"])
    except:
        pass
    return None, None

# -------------------- GEZEGEN KONUMU --------------------
def calculate_positions(dt_utc, lat, lon):
    obs = ephem.Observer()
    obs.lat = str(lat)
    obs.lon = str(lon)
    obs.date = dt_utc.strftime("%Y/%m/%d %H:%M:%S")

    bodies = {
        "Güneş": ephem.Sun(),
        "Ay": ephem.Moon(),
        "Merkür": ephem.Mercury(),
        "Venüs": ephem.Venus(),
        "Mars": ephem.Mars(),
        "Jüpiter": ephem.Jupiter(),
        "Satürn": ephem.Saturn(),
        "Uranüs": ephem.Uranus(),
        "Neptün": ephem.Neptune(),
        "Plüton": ephem.Pluto()
    }

    data = {}
    for name, body in bodies.items():
        body.compute(obs)
        lon_deg = math.degrees(ephem.Ecliptic(body).lon)
        data[name] = normalize(lon_deg)

    return data

# -------------------- TRANSIT–NATAL YORUM --------------------
def transit_natal_comment(transits, natal):
    text = "TRANSIT–NATAL ETKİLER:\n\n"

    for tp, td in transits.items():
        for np, nd in natal.items():
            d = angle_diff(td, nd)

            aspect = None
            if d <= 2:
                aspect = "Kavuşum"
            elif 88 <= d <= 92:
                aspect = "Kare"
            elif 118 <= d <= 122:
                aspect = "Üçgen"
            elif 178 <= d <= 182:
                aspect = "Karşıt"
            elif 58 <= d <= 62:
                aspect = "Sekstil"

            if aspect:
                text += (
                    f"- Transit {tp}, natal {np} ile {aspect}: "
                    f"{ASPECT_MEANING[aspect]}.\n"
                )

    if text.strip() == "TRANSIT–NATAL ETKİLER:":
        text += "Belirgin güçlü transit açı bulunmamaktadır.\n"

    return text

# -------------------- PDF --------------------
class AstroPDF(FPDF):
    def header(self):
        self.set_font("Arial", "B", 16)
        self.cell(0, 10, "ASTROLOJIK DOGUM & TRANSIT RAPORU", ln=True, align="C")
        self.ln(5)

    def section(self, title):
        self.ln(3)
        self.set_font("Arial", "B", 13)
        self.cell(0, 8, title, ln=True)
        self.set_font("Arial", "", 11)

def create_pdf(name, info, natal_text, transit_text):
    pdf = AstroPDF()
    pdf.add_page()

    pdf.section("KISI BILGILERI")
    pdf.multi_cell(0, 7, info)

    pdf.section("DOGUM HARITASI OZETI")
    pdf.multi_cell(0, 7, natal_text)

    pdf.section("TRANSIT ANALIZI")
    pdf.multi_cell(0, 7, transit_text)

    return pdf.output(dest="S").encode("latin-1", "ignore")

# -------------------- UI --------------------
st.title("🌌 Astro-Analiz Pro")

with st.sidebar:
    name = st.text_input("İsim", "Ziyaretçi")
    city = st.text_input("Şehir", "İstanbul")
    birth_date = st.date_input("Doğum Tarihi", datetime(1990, 1, 1))
    birth_time = st.time_input("Saat", datetime.strptime("12:00", "%H:%M"))
    utc_offset = st.number_input("GMT Farkı", value=3)
    run = st.button("Analiz Et ✨")

if run:
    lat, lon = city_to_latlon(city)
    if lat is None:
        st.error("Şehir bulunamadı.")
        st.stop()

    birth_dt_utc = datetime.combine(birth_date, birth_time) - timedelta(hours=utc_offset)
    natal = calculate_positions(birth_dt_utc, lat, lon)

    now_utc = datetime.utcnow()
    transits = calculate_positions(now_utc, lat, lon)

    natal_text = "DOGUM HARITASI TEMALARI:\n\n"
    for p, d in natal.items():
        sign = ZODIAC[int(d // 30)]
        natal_text += f"- {p} {sign}: {PLANET_MEANING[p]}\n"

    transit_text = transit_natal_comment(transits, natal)

    st.subheader("🧠 Otomatik Yorum")
    st.text(natal_text + "\n" + transit_text)

    pdf_bytes = create_pdf(
        name,
        f"{name}\n{city}\n{birth_date} {birth_time}",
        natal_text,
        transit_text
    )

    st.download_button(
        "📄 Profesyonel PDF İndir",
        pdf_bytes,
        file_name="astro_rapor.pdf",
        mime="application/pdf"
    )
