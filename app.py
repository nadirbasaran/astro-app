# ==========================================================
# ASTRO ANALIZ PRO — FINAL (PLACIDUS / TRANSIT / AI)
# ==========================================================

import streamlit as st
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import ephem, math, pytz, json, requests, numpy as np
from datetime import datetime, timedelta
from fpdf import FPDF

# ---------------- PAGE ----------------
st.set_page_config("Astro-Analiz Pro", "🔮", layout="wide")

# ---------------- API ----------------
if "GOOGLE_API_KEY" not in st.secrets:
    st.error("GOOGLE_API_KEY tanımlı değil")
    st.stop()
API_KEY = st.secrets["GOOGLE_API_KEY"]

# ---------------- CONSTANTS ----------------
ZODIAC = ["Koç","Boğa","İkizler","Yengeç","Aslan","Başak",
          "Terazi","Akrep","Yay","Oğlak","Kova","Balık"]

ELEMENT = {
    "Koç":"Ateş","Aslan":"Ateş","Yay":"Ateş",
    "Boğa":"Toprak","Başak":"Toprak","Oğlak":"Toprak",
    "İkizler":"Hava","Terazi":"Hava","Kova":"Hava",
    "Yengeç":"Su","Akrep":"Su","Balık":"Su"
}

QUALITY = {
    "Koç":"Öncü","Yengeç":"Öncü","Terazi":"Öncü","Oğlak":"Öncü",
    "Boğa":"Sabit","Aslan":"Sabit","Akrep":"Sabit","Kova":"Sabit",
    "İkizler":"Değişken","Başak":"Değişken","Yay":"Değişken","Balık":"Değişken"
}

PLANETS = {
    "Güneş":ephem.Sun(),"Ay":ephem.Moon(),"Merkür":ephem.Mercury(),
    "Venüs":ephem.Venus(),"Mars":ephem.Mars(),"Jüpiter":ephem.Jupiter(),
    "Satürn":ephem.Saturn(),"Uranüs":ephem.Uranus(),
    "Neptün":ephem.Neptune(),"Plüton":ephem.Pluto()
}

ASPECTS = {
    "Kavuşum":0,"Sekstil":60,"Kare":90,"Üçgen":120,"Karşıt":180
}

HOUSE_TOPICS = {
    1:"Kimlik","2":"Gelir","3":"Yakın çevre","4":"Ev / Aile",
    5:"Aşk / Çocuk","6":"İş / Sağlık","7":"Evlilik",
    8:"Kriz / Dönüşüm","9":"Yurt dışı","10":"Kariyer",
    11:"Sosyal çevre","12":"Bilinçaltı"
}

# ---------------- HELPERS ----------------
def normalize(x): return x % 360
def diff(a,b): return min(abs(a-b),360-abs(a-b))
def sign_of(d): return ZODIAC[int(d//30)]
def house_of(d,c):
    for i in range(1,13):
        s=c[i]; e=c[i+1] if i<12 else c[1]
        if s<e and s<=d<e: return i
        if s>e and (d>=s or d<e): return i
    return 1

# ---------------- PLACIDUS ----------------
def placidus_cusps(dt,lat,lon):
    obs=ephem.Observer()
    obs.date=dt; obs.lat=str(lat); obs.lon=str(lon)
    ramc=float(obs.sidereal_time())
    eps=math.radians(23.44)
    latr=math.radians(lat)

    mc=math.degrees(math.atan2(math.tan(ramc),math.cos(eps)))%360
    asc=math.degrees(math.atan2(math.cos(ramc),
        -(math.sin(ramc)*math.cos(eps)+math.tan(latr)*math.sin(eps))))%360

    cusps={1:asc,10:mc,4:(mc+180)%360,7:(asc+180)%360}
    d=(asc-mc)%360
    cusps[11]=(mc+d/3)%360; cusps[12]=(mc+2*d/3)%360
    d=(cusps[4]-asc)%360
    cusps[2]=(asc+d/3)%360; cusps[3]=(asc+2*d/3)%360
    cusps[5]=(cusps[11]+180)%360; cusps[6]=(cusps[12]+180)%360
    cusps[8]=(cusps[2]+180)%360; cusps[9]=(cusps[3]+180)%360
    return cusps

# ---------------- POSITIONS ----------------
def positions(dt,lat,lon,cusps):
    obs=ephem.Observer()
    obs.date=dt; obs.lat=str(lat); obs.lon=str(lon)
    out={}
    for n,b in PLANETS.items():
        b.compute(obs)
        d=normalize(math.degrees(ephem.Ecliptic(b).lon))
        out[n]=(d,sign_of(d),house_of(d,cusps))
    return out

# ---------------- TRANSITS ----------------
def transit_hits(natal,transit):
    hits=[]
    for tp,(td,_,_) in transit.items():
        for np,(nd,_,h) in natal.items():
            for a,ang in ASPECTS.items():
                if abs(diff(td,nd)-ang)<=2:
                    hits.append(
                        f"{tp} – {np} {a} | {HOUSE_TOPICS[h]}"
                    )
    return hits

# ---------------- AI ----------------
def ai_text(prompt):
    url=f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={API_KEY}"
    data={"contents":[{"parts":[{"text":prompt}]}]}
    r=requests.post(url,json=data)
    return r.json()["candidates"][0]["content"]["parts"][0]["text"]

# ---------------- PDF ----------------
class PDF(FPDF):
    def header(self):
        self.set_font("Arial","B",16)
        self.cell(0,10,"ASTROLOJIK ANALIZ RAPORU",ln=1,align="C")

def clean(t):
    repl={"ğ":"g","Ğ":"G","ş":"s","Ş":"S","ı":"i","İ":"I",
          "ü":"u","Ü":"U","ö":"o","Ö":"O","ç":"c","Ç":"C"}
    for k,v in repl.items(): t=t.replace(k,v)
    return t.encode("latin-1","ignore").decode("latin-1")

def make_pdf(name,text):
    p=PDF(); p.add_page()
    p.set_font("Arial","",11)
    p.multi_cell(0,8,clean(text))
    return p.output(dest="S").encode("latin-1","ignore")

# ---------------- UI ----------------
st.title("🌌 Astro-Analiz Pro — FINAL")

name=st.text_input("İsim","Ziyaretçi")
city=st.text_input("Şehir","İstanbul")
date=st.date_input("Doğum Tarihi")
time=st.time_input("Saat",step=60)
lat=st.number_input("Enlem",41.0)
lon=st.number_input("Boylam",29.0)
question=st.text_area("Sorunuz")

if st.button("Analiz Et"):
    tz=pytz.timezone("Europe/Istanbul")
    birth=tz.localize(datetime.combine(date,time)).astimezone(pytz.utc)
    cusps=placidus_cusps(birth,lat,lon)
    natal=positions(birth,lat,lon,cusps)

    now=datetime.utcnow()
    transit=positions(now,lat,lon,cusps)
    hits=transit_hits(natal,transit)

    ai_prompt=f"""
Sen profesyonel astrologsun.
SORU: {question}

NATAL:
{natal}

TRANSIT:
{hits}

Danisman gibi detayli yorumla.
"""
    result=ai_text(ai_prompt)
    st.markdown(result)

    pdf=make_pdf(name,result)
    st.download_button("PDF indir",pdf,"astro_rapor.pdf","application/pdf")
