# =========================================================
# ASTRO-ANALİZ PRO – FINAL SÜRÜM
# Transit–Natal Otomatik Yorum + Profesyonel PDF
# =========================================================

import streamlit as st
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import ephem, math, requests, json
from datetime import datetime, timedelta
from fpdf import FPDF
import numpy as np

# ------------------ SAYFA ------------------
st.set_page_config("Astro-Analiz Pro", layout="wide", page_icon="🔮")

# ------------------ SABİTLER ------------------
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

HOUSE_MEANING = {
    1:"kimlik ve yaşam yaklaşımı",2:"maddi güvenlik ve değerler",
    3:"iletişim ve yakın çevre",4:"aile ve iç dünya",
    5:"yaratıcılık ve aşk",6:"iş ve sağlık",
    7:"ilişkiler ve ortaklıklar",8:"krizler ve dönüşüm",
    9:"inançlar ve vizyon",10:"kariyer ve statü",
    11:"sosyal çevre ve idealler",12:"bilinçaltı ve ruhsallık"
}

PLANET_MEANING = {
    "Güneş":"kimlik","Ay":"duygular","Merkür":"zihin",
    "Venüs":"ilişkiler","Mars":"motivasyon","Jüpiter":"büyüme",
    "Satürn":"sorumluluk","Uranüs":"değişim",
    "Neptün":"idealler","Plüton":"dönüşüm"
}

ASPECT_MEANING = {
    "Kavuşum":"hayatınızda güçlü bir etki yaratır",
    "Kare":"zorlayıcı ama geliştirici bir süreçtir",
    "Karşıt":"denge kurmanız gereken bir temayı gösterir",
    "Üçgen":"doğal ve destekleyici bir akış sağlar",
    "Sekstil":"fırs
