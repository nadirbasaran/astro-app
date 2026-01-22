import streamlit as st
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import ephem
import math
from datetime import datetime, timedelta
import requests
import json
import numpy as np
from fpdf import FPDF

# ------------------ SAYFA ------------------
st.set_page_config(page_title="Astro-Analiz Pro", layout="wide", page_icon="🔮")

# ------------------ CSS ------------------
st.markdown("""
<style>
.stApp { background: linear-gradient(to bottom, #0e1117, #24283b); color: #e0e0e0; }
h1,h2,h3 { color: #FFD700 !important; }
.metric-box { background:#1e2130; padding:8px; border-left:4px solid #FFD700; margin-bottom:6px; }
.aspect-box { background:#25293c; padding:4px; margin:2px; border-radius:4px; font-size:13px; }
.transit-box { background:#2d1b2e; border-left:4px solid #ff4b4b; padding:6px; margin-bottom:4px; }
</style>
""", unsafe_allow_html=True)

# ------------------ API ------------------
if "GOOGLE_API_KEY" not in st.secrets:
    st.error("API anahtarı yok")
    st.stop()
API_KEY = st.secrets["GOOGLE_API_KEY"]

# ------------------ SABİTLER ------------------
ZODIAC = ["Koç","Boğa","İkizler","Yengeç","Aslan","Başak","Terazi","Akrep","Yay","Oğlak","Kova","Balık"]
ZSYM = ["♈","♉","♊","♋","♌","♍","♎","♏","♐","♑","♒","♓"]
PSYM = {"Güneş":"☉","Ay":"☽","Merkür":"☿","Venüs":"♀","Mars":"♂",
        "Jüpiter":"♃","Satürn":"♄","Uranüs":"♅","Neptün":"♆","Plüton":"♇",
        "ASC":"ASC","MC":"MC"}

# ------------------ YARDIMCILAR ------------------
def normalize(x): return x % 360

def dms(x):
    d = int(x)
    m = int((x-d)*60)
    return f"{d:02d}°{m:02d}'"

def angle_diff(a,b):
    d = abs(a-b)
    return min(d,360-d)

def clean_pdf(t):
    repl = {'ğ':'g','ş':'s','ı':'i','ü':'u','ö':'o','ç':'c',
            'Ğ':'G','Ş':'S','İ':'I','Ü':'U','Ö':'O','Ç':'C'}
    for k,v in repl.items(): t=t.replace(k,v)
    return t.encode("latin-1","replace").decode("latin-1")

# ------------------ HARİTA HESABI ------------------
def calculate_chart(name, d_date, d_time, lat, lon, utc, transit, sd, ed):

    local_dt = datetime.combine(d_date, d_time)
    utc_dt = local_dt - timedelta(hours=utc)
    date_str = utc_dt.strftime("%Y/%m/%d %H:%M:%S")

    obs = ephem.Observer()
    obs.lat, obs.lon, obs.date = str(lat), str(lon), date_str

    ramc = float(obs.sidereal_time())
    eps = math.radians(23.4392911)
    lat_r = math.radians(lat)

    mc = normalize(math.degrees(math.atan2(math.tan(ramc), math.cos(eps))))
    asc = normalize(math.degrees(math.atan2(
        math.cos(ramc),
        -(math.sin(ramc)*math.cos(eps)+math.tan(lat_r)*math.sin(eps))
    )))

    cusps = {1:asc, 4:normalize(mc+180), 7:normalize(asc+180), 10:mc}
    cusps[2]=normalize(cusps[1]+30); cusps[3]=normalize(cusps[2]+30)
    cusps[5]=normalize(cusps[4]+30); cusps[6]=normalize(cusps[5]+30)
    cusps[8]=normalize(cusps[7]+30); cusps[9]=normalize(cusps[8]+30)
    c
