# ================== ASTRO ANALIZ PRO — FIXED FULL ==================

import streamlit as st
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import ephem, math, pytz, json, requests
import numpy as np
from datetime import datetime, timedelta
from fpdf import FPDF

# ---------------- PAGE ----------------
st.set_page_config("Astro-Analiz Pro", "🔮", layout="wide")

# ---------------- ZODIAC ----------------
ZODIAC = ["Koç","Boğa","İkizler","Yengeç","Aslan","Başak",
          "Terazi","Akrep","Yay","Oğlak","Kova","Balık"]

ASPECT_MEANING = {
    "Kavuşum": "hayatınızda güçlü ve kaçınılmaz bir etki yaratır.",
    "Kare": "zorlayıcı ama büyüme sağlayan bir süreçtir.",
    "Üçgen": "destekleyici ve akışkan bir enerji sunar.",
    "Karşıt": "denge kurmanız gereken bir alanı vurgular.",
    "Sekstil": "fırsatları değerlendirme şansı verir."
}

# ---------------- UTILS ----------------
def normalize(d): return d % 360
def diff(a,b): return min(abs(a-b), 360-abs(a-b))

def sign_of(d): return ZODIAC[int(d//30)%12]

# ---------------- PLACIDUS ----------------
def calculate_placidus_cusps(utc_dt, lat, lon):
    obs = ephem.Observer()
    obs.date = utc_dt
    obs.lat, obs.lon = str(lat), str(lon)

    ramc = float(obs.sidereal_time())
    eps = math.radians(23.44)
    lat_r = math.radians(lat)

    mc = math.degrees(math.atan2(math.tan(ramc), math.cos(eps))) % 360
    asc = math.degrees(
        math.atan2(
            math.cos(ramc),
            -(math.sin(ramc)*math.cos(eps)+math.tan(lat_r)*math.sin(eps))
        )
    ) % 360

    cusps = {1:asc, 10:mc, 4:(mc+180)%360, 7:(asc+180)%360}
    cusps[11]=(mc+(asc-mc)/3)%360
    cusps[12]=(mc+2*(asc-mc)/3)%360
    cusps[2]=(asc+(cusps[4]-asc)/3)%360
    cusps[3]=(asc+2*(cusps[4]-asc)/3)%360
    cusps[5]=(cusps[11]+180)%360
    cusps[6]=(cusps[12]+180)%360
    cusps[8]=(cusps[2]+180)%360
    cusps[9]=(cusps[3]+180)%360
    return cusps

def house_of(deg, cusps):
    for i in range(1,13):
        a = cusps[i]
        b = cusps[i+1] if i<12 else cusps[1]
        if a<b and a<=deg<b: return i
        if a>b and (deg>=a or deg<b): return i
    return 1

# ---------------- PLANETS ----------------
PLANETS = {
    "Güneş":ephem.Sun(), "Ay":ephem.Moon(),
    "Merkür":ephem.Mercury(), "Venüs":ephem.Venus(),
    "Mars":ephem.Mars(), "Jüpiter":ephem.Jupiter(),
    "Satürn":ephem.Saturn(), "Uranüs":ephem.Uranus(),
    "Neptün":ephem.Neptune(), "Plüton":ephem.Pluto()
}

# ---------------- CORE ----------------
def calculate_natal(dt_utc, lat, lon):
    obs = ephem.Observer()
    obs.date = dt_utc
    obs.lat, obs.lon = str(lat), str(lon)
    cusps = calculate_placidus_cusps(dt_utc, lat, lon)

    data=[]
    for n,b in PLANETS.items():
        b.compute(obs)
        deg = normalize(math.degrees(ephem.Ecliptic(b).lon))
        data.append({
            "name":n,
            "deg":deg,
            "sign":sign_of(deg),
            "house":house_of(deg,cusps)
        })
    return data, cusps

# ---------------- ASPECTS ----------------
def aspects(natal):
    res=[]
    for i in range(len(natal)):
        for j in range(i+1,len(natal)):
            d = diff(natal[i]["deg"], natal[j]["deg"])
            for a,ang in {"Kavuşum":0,"Sekstil":60,"Kare":90,"Üçgen":120,"Karşıt":180}.items():
                if abs(d-ang)<=6:
                    res.append(f'{natal[i]["name"]} {a} {natal[j]["name"]}')
    return res

# ---------------- TRANSIT ----------------
def transit_analysis(natal, cusps, start, end, lat, lon):
    obs = ephem.Observer()
    obs.lat, obs.lon = str(lat), str(lon)
    heavy = ["Jüpiter","Satürn","Uranüs","Neptün","Plüton"]

    result=[]
    for p in heavy:
        b = PLANETS[p]
        obs.date = end
        b.compute(obs)
        tdeg = normalize(math.degrees(ephem.Ecliptic(b).lon))
        tsign = sign_of(tdeg)
        thouse = house_of(tdeg,cusps)

        for n in natal:
            d = diff(tdeg,n["deg"])
            if d<=4:
                meaning = f"Transit {p}, natal {n['name']} ile kavuşumda. {thouse}. ev konuları aktif."
                result.append(meaning)
    return result

# ---------------- PDF ----------------
def clean_pdf(t):
    for a,b in {"ğ":"g","ş":"s","ı":"i","İ":"I","ç":"c","ö":"o","ü":"u"}.items():
        t=t.replace(a,b)
    return t.encode("latin-1","ignore").decode("latin-1")

def make_pdf(name, text):
    pdf=FPDF()
    pdf.add_page()
    pdf.set_font("Arial","B",14)
    pdf.cell(0,10,clean_pdf(f"ASTRO ANALIZ – {name}"),ln=1)
    pdf.set_font("Arial","",11)
    pdf.multi_cell(0,8,clean_pdf(text))
    return pdf.output(dest="S").encode("latin-1","ignore")

# ---------------- UI ----------------
st.title("🌌 Astro-Analiz Pro (Gerçek Final)")

name = st.text_input("İsim","Ziyaretçi")
date = st.date_input("Doğum Tarihi")
time = st.time_input("Saat", step=60)
lat = st.number_input("Enlem",41.0)
lon = st.number_input("Boylam",29.0)
gmt = st.number_input("GMT",3)

if st.button("Analiz Et"):
    local = datetime.combine(date,time)
    utc = local - timedelta(hours=gmt)

    natal,cusps = calculate_natal(utc,lat,lon)
    asp = aspects(natal)
    trans = transit_analysis(natal,cusps,utc,datetime.utcnow(),lat,lon)

    text="DOĞUM HARITASI:\n"
    for n in natal:
        text+=f"{n['name']} {n['sign']} {n['house']}. ev\n"

    text+="\nAÇILAR:\n"+"\n".join(asp)
    text+="\n\nTRANSITLER:\n"+"\n".join(trans)

    st.text(text)
    st.download_button("PDF", make_pdf(name,text),"astro.pdf")
