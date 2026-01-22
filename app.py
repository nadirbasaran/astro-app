# ============================================================
# ASTRO-ANALIZ PRO MAX — SINGLE FILE / STABLE
# ============================================================

import streamlit as st
import ephem, math, requests
from datetime import datetime, timedelta
import matplotlib.pyplot as plt

from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, PageBreak
)
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.pagesizes import A4

# ---------------- PAGE ----------------
st.set_page_config("Astro-Analiz Pro Max", "🪐", layout="wide")

# ---------------- CONSTANTS ----------------
ZODIAC = ["Koç","Boğa","İkizler","Yengeç","Aslan","Başak",
          "Terazi","Akrep","Yay","Oğlak","Kova","Balık"]

ELEMENT = {
    "Koç":"Ateş","Aslan":"Ateş","Yay":"Ateş",
    "Boğa":"Toprak","Başak":"Toprak","Oğlak":"Toprak",
    "İkizler":"Hava","Terazi":"Hava","Kova":"Hava",
    "Yengeç":"Su","Akrep":"Su","Balık":"Su"
}

PLANETS = {
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

ASPECTS = {
    "Kavuşum":0,
    "Sekstil":60,
    "Kare":90,
    "Üçgen":120,
    "Karşıt":180
}

# ---------------- HELPERS ----------------
def normalize(x): return x % 360
def diff(a,b): return min(abs(a-b), 360-abs(a-b))

def city_to_latlon(city):
    r = requests.get(
        "https://nominatim.openstreetmap.org/search",
        params={"q":city,"format":"json","limit":1},
        headers={"User-Agent":"astro-app"}
    )
    if r.json():
        return float(r.json()[0]["lat"]), float(r.json()[0]["lon"])
    return None,None

def planet_positions(dt, lat, lon):
    obs = ephem.Observer()
    obs.lat, obs.lon = str(lat), str(lon)
    obs.date = dt
    data={}
    for n,b in PLANETS.items():
        b.compute(obs)
        data[n]=normalize(math.degrees(ephem.Ecliptic(b).lon))
    return data

def sign_of(deg): return ZODIAC[int(deg//30)]
def house_of(deg): return int(deg//30)+1

# ---------------- ANALYSIS ----------------
def transit_analysis(transit, natal):
    out=[]
    for tp,td in transit.items():
        for np,nd in natal.items():
            for a,ang in ASPECTS.items():
                if diff(td,nd)<=2 and ang==0 or abs(diff(td,nd)-ang)<=2:
                    out.append(
                        f"Transit {tp}, natal {np} ile {a}: "
                        f"{house_of(nd)}. ev konuları tetikleniyor."
                    )
    return out

# ---------------- GRAPH ----------------
def element_chart(natal):
    cnt={"Ateş":0,"Toprak":0,"Hava":0,"Su":0}
    for d in natal.values():
        cnt[ELEMENT[sign_of(d)]]+=1
    fig,ax=plt.subplots()
    ax.bar(cnt.keys(),cnt.values())
    st.pyplot(fig)

# ---------------- PDF ----------------
def create_pdf(name,info,natal,transit):
    styles=getSampleStyleSheet()
    doc=SimpleDocTemplate("/tmp/astro.pdf",pagesize=A4)
    story=[]

    story.append(Paragraph("<b>ASTROLOJİK ANALİZ RAPORU</b>",styles["Title"]))
    story.append(Spacer(1,12))

    story.append(Paragraph("<b>Kişisel Bilgiler</b><br/>"+info,styles["Normal"]))
    story.append(PageBreak())

    story.append(Paragraph("<b>Doğum Haritası</b>",styles["Heading2"]))
    for p,d in natal.items():
        story.append(Paragraph(
            f"{p}: {sign_of(d)} – {house_of(d)}. Ev",styles["Normal"]
        ))

    story.append(PageBreak())
    story.append(Paragraph("<b>Transit Etkileri</b>",styles["Heading2"]))
    for t in transit:
        story.append(Paragraph(t,styles["Normal"]))

    doc.build(story)
    return open("/tmp/astro.pdf","rb").read()

# ---------------- UI ----------------
st.title("🪐 Astro-Analiz Pro Max")

name=st.text_input("İsim","Ziyaretçi")
city=st.text_input("Şehir","İstanbul")
date=st.date_input("Doğum Tarihi")
time=st.time_input("Saat")
gmt=st.number_input("GMT",value=3)

if st.button("Analizi Başlat"):
    lat,lon=city_to_latlon(city)
    birth=datetime.combine(date,time)-timedelta(hours=gmt)
    natal=planet_positions(birth,lat,lon)
    transit=planet_positions(datetime.utcnow(),lat,lon)

    st.subheader("📊 Element Dağılımı")
    element_chart(natal)

    tr=transit_analysis(transit,natal)
    st.subheader("🧠 Transit Yorumları")
    for t in tr: st.write("•",t)

    pdf=create_pdf(
        name,
        f"{name}<br/>{city}<br/>{date} {time}",
        natal,tr
    )

    st.download_button(
        "📄 Profesyonel PDF",
        pdf,
        "astro_rapor.pdf",
        "application/pdf"
    )
