import streamlit as st
import pdfplumber
import pandas as pd
import re
import io
from datetime import datetime

st.set_page_config(
    page_title="Control de Liquidaciones Fiserv",
    page_icon="💳",
    layout="wide"
)

st.title("💳 Control de Liquidaciones Fiserv — DEBUG")

# Subir un solo PDF para ver qué extrae
pdf_debug = st.file_uploader("Subí UN solo PDF para diagnóstico", type="pdf")

if pdf_debug:
    contenido = ""
    with pdfplumber.open(pdf_debug) as pdf:
        for i, page in enumerate(pdf.pages):
            texto = page.extract_text()
            if texto:
                contenido += texto + "\n"

    st.subheader("Primeras 3000 caracteres del texto extraído:")
    st.code(contenido[:3000])

    st.subheader("Búsqueda de número de comercio:")
    # Probar distintos patrones
    patrones_com = [
        r'N[°º\.]\s*Comercio[:\s]+(\d+)',
        r'Comercio[:\s]+(\d+)',
        r'N°\s*Comercio[:\s]*([\d\s/]+)',
        r'(\d{9})',
        r'(\d{7,10})',
    ]
    for p in patrones_com:
        m = re.search(p, contenido)
        if m:
            st.write(f"✅ Patrón `{p}` → encontró: `{m.group(0)}` → grupo: `{m.group(1)}`")
        else:
            st.write(f"❌ Patrón `{p}` → no encontró nada")

    st.subheader("Búsqueda de VISA / MASTER / DEBITO / CREDITO:")
    for palabra in ["VISA", "MASTER", "DEBITO", "CREDITO", "DEBIT", "CREDIT", "Débito", "Crédito"]:
        if palabra.upper() in contenido.upper():
            idx = contenido.upper().find(palabra.upper())
            st.write(f"✅ `{palabra}` encontrado en posición {idx}: `...{contenido[max(0,idx-20):idx+30]}...`")
        else:
            st.write(f"❌ `{palabra}` NO encontrado")

    st.subheader("Primeras líneas que contienen 'Venta':")
    lineas_venta = [l for l in contenido.split('\n') if 'Venta' in l or 'venta' in l]
    for l in lineas_venta[:10]:
        st.code(l)
