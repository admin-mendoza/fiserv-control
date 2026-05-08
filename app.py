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

st.title("💳 Control de Liquidaciones Fiserv")
st.caption("Isabel Tomas SRL — Pinturerias Mendoza")

COMERCIOS = {
    "29992214": "Pbro Daniel Segundo",
    "29992250": "Dorrego – Villa Constitución",
    "29992255": "Empalme Villa Cons",
    "29992257": "Arroyo Seco",
    "29992269": "Pueblo Esther",
    "29992282": "Villa Gdor Galvez",
    "29992506": "Sucursal 506",
    "29992551": "Sucursal 551",
    "29992575": "Sucursal 575",
    "29992142": "Sucursal 142",
}

def extraer_comercio(contenido):
    """
    El PDF dice: N° Comercio: 002999214/ 2
    Fiserv parte el número de comercio en dos partes:
      - Antes de la barra: 002999214 (con ceros adelante)
      - Después de la barra: 2 (último dígito)
    El número real es: lstrip('0') de la parte1 + parte2
    Ejemplo: 002999214 / 2 → 2999214 + 2 = 29992142
    """
    # Capturar el patrón completo: dígitos / dígito
    m = re.search(r'N[°º\.]\s*Comercio[:\s]+([\d]+)\s*/\s*(\d+)', contenido)
    if not m:
        m = re.search(r'Comercio[:\s]+([\d]+)\s*/\s*(\d+)', contenido)
    if m:
        parte1 = m.group(1).strip().lstrip('0') or '0'
        parte2 = m.group(2).strip()
        return parte1 + parte2

    # Fallback: sin barra, tomar solo los dígitos
    m = re.search(r'N[°º\.]\s*Comercio[:\s]+([\d]+)', contenido)
    if not m:
        m = re.search(r'Comercio[:\s]+([\d]+)', contenido)
    if m:
        return m.group(1).strip().lstrip('0') or '0'
    return "0"

def detectar_tarjeta_nombre(nombre_archivo, contenido):
    """
    Detecta el tipo de tarjeta primero por nombre de archivo (más confiable),
    luego por contenido del texto.
    """
    nombre = nombre_archivo.upper()
    # Por nombre de archivo
    if "VISADEBITO" in nombre or "VISA-DEBITO" in nombre or "VISA_DEBITO" in nombre or "VISAD" in nombre:
        return "Visa Débito"
    if "VISACREDITO" in nombre or "VISA-CREDITO" in nombre or "VISAC" in nombre:
        return "Visa Crédito"
    if ("MASTERCARDDEBIT" in nombre or "MASTERCARD-DEBIT" in nombre or
            "MASTERCARDDEBIT" in nombre or "MCDEBIT" in nombre):
        return "Mastercard Débito"
    if ("MASTERCARDCREDIT" in nombre or "MASTERCARD-CREDIT" in nombre or
            "MCCREDIT" in nombre):
        return "Mastercard Crédito"
    if "VISA" in nombre and "DEBIT" in nombre:
        return "Visa Débito"
    if "VISA" in nombre and "CREDIT" in nombre:
        return "Visa Crédito"
    if "MASTER" in nombre and "DEBIT" in nombre:
        return "Mastercard Débito"
    if "MASTER" in nombre and "CREDIT" in nombre:
        return "Mastercard Crédito"
    if "VISA" in nombre:
        return "Visa Débito"
    if "MASTER" in nombre:
        return "Mastercard Débito"

    # Por contenido del texto
    c = contenido.upper()
    if "DEBITO" in c and ("VISA" in c or "TARJETA DE DEBITO" in c):
        return "Visa Débito"
    if "CREDITO" in c and "VISA" in c:
        return "Visa Crédito"
    if "DEBITO" in c and "MASTER" in c:
        return "Mastercard Débito"
    if "CREDITO" in c and "MASTER" in c:
        return "Mastercard Crédito"
    if "DEBITO" in c:
        return "Débito"
    if "CREDITO" in c:
        return "Crédito"
    return "Otra"

def extraer_cupones_pdf(pdf_file):
    cupones = []
    contenido = ""
    with pdfplumber.open(pdf_file) as pdf:
        for page in pdf.pages:
            texto = page.extract_text()
            if texto:
                contenido += texto + "\n"

    comercio = extraer_comercio(contenido)
    tarjeta  = detectar_tarjeta_nombre(pdf_file.name, contenido)

    patron = re.compile(
        r'Venta\s+(?:ctdo|cuo)\s+'
        r'(\d{2}/\d{2}/\d{2})\s+'   # fecha
        r'(\d+)\s+'                   # terminal
        r'(\d+)\s+'                   # lote
        r'(\d+)\s+'                   # cupon
        r'(\d+)\s+'                   # tarj num
        r'[\d,\.]+\s+'               # T.N.A
        r'([\d\.,]+)'                 # importe ventas
    )

    for m in patron.finditer(contenido):
        fecha_str   = m.group(1)
        lote        = str(int(m.group(3)))   # sin ceros adelante
        cupon       = m.group(4).zfill(4)
        importe_str = m.group(6).replace('.', '').replace(',', '.')
        try:
            importe = float(importe_str)
        except:
            importe = 0.0

        clave = f"{comercio}_{lote}_{cupon}"
        cupones.append({
            "comercio": comercio,
            "sucursal": COMERCIOS.get(comercio, f"COM {comercio}"),
            "tarjeta":  tarjeta,
            "fecha":    fecha_str,
            "lote":     lote,
            "cupon":    cupon,
            "importe":  importe,
            "clave":    clave,
        })

    return cupones, comercio, tarjeta


def generar_excel_plantilla():
    df = pd.DataFrame({
        "comercio": ["29992214", "29992250", "29992255", "29992257"],
        "lote":     [149,        160,        138,        153],
        "cupon":    ["0699",     "1111",     "0360",     "0536"],
        "importe":  [9477.42,    243914.57,  12348.98,   196744.77],
    })
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="Cupones")
        ws = writer.sheets["Cupones"]
        for col, w in [("A",15),("B",10),("C",10),("D",15)]:
            ws.column_dimensions[col].width = w
    buf.seek(0)
    return buf


# ─── TABS ───────────────────────────────────────────────────────────────────
tab1, tab2, tab3 = st.tabs([
    "📄 1. Liquidaciones PDF",
    "🧾 2. Cupones físicos (Excel)",
    "✅ 3. Resultado del cruce"
])

# ── TAB 1 ──────────────────────────────────────────────────────────────────
with tab1:
    st.subheader("Subí los PDFs de Fiserv")
    st.info("Podés subir todos los archivos a la vez: Visa Débito, Crédito, Mastercard, todas las sucursales.")

    pdfs = st.file_uploader(
        "Seleccioná los PDFs de liquidación",
        type="pdf",
        accept_multiple_files=True,
        key="pdfs"
    )

    if pdfs:
        todos_cupones = []
        resumen = []

        with st.spinner("Procesando PDFs..."):
            for pdf in pdfs:
                try:
                    cups, com, tarj = extraer_cupones_pdf(pdf)
                    todos_cupones.extend(cups)
                    resumen.append({
                        "Archivo": pdf.name,
                        "Sucursal": COMERCIOS.get(com, f"COM {com}"),
                        "Tarjeta": tarj,
                        "Cupones detectados": len(cups)
                    })
                except Exception as e:
                    st.warning(f"Error en {pdf.name}: {e}")

        st.session_state["liq_cupones"] = todos_cupones

        col1, col2 = st.columns(2)
        col1.metric("Total cupones en liquidaciones", len(todos_cupones))
        col2.metric("Archivos procesados", len(pdfs))

        st.dataframe(pd.DataFrame(resumen), use_container_width=True, hide_index=True)

        if todos_cupones:
            with st.expander("Ver todos los cupones detectados"):
                df_liq = pd.DataFrame(todos_cupones)
                st.dataframe(
                    df_liq[["sucursal","tarjeta","fecha","lote","cupon","importe"]],
                    use_container_width=True,
                    hide_index=True
                )

        st.success("✅ PDFs cargados. Pasá a la pestaña **2. Cupones físicos**.")


# ── TAB 2 ──────────────────────────────────────────────────────────────────
with tab2:
    st.subheader("Cargá los cupones físicos desde Excel")

    with st.expander("📥 ¿Cómo armar el Excel?", expanded=True):
        st.markdown("""
El Excel debe tener estas **4 columnas** (importe opcional pero recomendado):

| comercio | lote | cupon | importe |
|---|---|---|---|
| 29992214 | 149 | 0699 | 9477.42 |
| 29992250 | 160 | 1111 | 243914.57 |

**¿Dónde encontrar cada dato en el cupón físico?**
- **comercio** → dice `COM: 29992214`
- **lote** → dice `N° LOTE: 149`
- **cupon** → dice `CUPON: 0699`
- **importe** → el monto en $ del ticket

El importe puede tener punto o coma decimal (ej: 9477.42 o 9477,42).
        """)
        st.download_button(
            "⬇️ Descargar plantilla Excel de ejemplo",
            data=generar_excel_plantilla(),
            file_name="plantilla_cupones.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True
        )

    excel_file = st.file_uploader(
        "Subí tu Excel con los cupones físicos",
        type=["xlsx","xls"],
        key="excel_cupones"
    )

    if excel_file:
        try:
            df_excel = pd.read_excel(excel_file, dtype=str)
            df_excel.columns = [c.lower().strip() for c in df_excel.columns]

            faltantes = [c for c in ["comercio","lote","cupon"] if c not in df_excel.columns]
            if faltantes:
                st.error(f"Faltan columnas en el Excel: {', '.join(faltantes)}")
            else:
                # Normalizar igual que los PDFs
                df_excel["comercio"] = df_excel["comercio"].str.strip().str.lstrip('0')
                df_excel["lote"]     = df_excel["lote"].str.strip().apply(
                    lambda x: str(int(float(x))) if pd.notna(x) and x != '' else '0'
                )
                df_excel["cupon"]    = df_excel["cupon"].str.strip().str.zfill(4)
                df_excel["sucursal"] = df_excel["comercio"].map(COMERCIOS).fillna(
                    df_excel["comercio"].apply(lambda x: f"COM {x}")
                )

                if "importe" in df_excel.columns:
                    df_excel["importe"] = pd.to_numeric(
                        df_excel["importe"].str.replace(',','.', regex=False),
                        errors='coerce'
                    ).fillna(0)
                else:
                    df_excel["importe"] = 0

                df_excel["clave"] = (
                    df_excel["comercio"] + "_" +
                    df_excel["lote"]     + "_" +
                    df_excel["cupon"]
                )

                st.session_state["cupones_excel"] = df_excel

                st.metric("Cupones cargados desde Excel", len(df_excel))
                st.dataframe(
                    df_excel[["sucursal","lote","cupon","importe"]],
                    use_container_width=True,
                    hide_index=True
                )
                st.success("✅ Excel cargado. Pasá a la pestaña **3. Resultado del cruce**.")

        except Exception as e:
            st.error(f"Error al leer el Excel: {e}")


# ── TAB 3 ──────────────────────────────────────────────────────────────────
with tab3:
    st.subheader("Resultado del cruce")

    liq    = st.session_state.get("liq_cupones", [])
    df_fis = st.session_state.get("cupones_excel", None)

    if not liq:
        st.warning("⬅️ Primero subí los PDFs en la pestaña **1. Liquidaciones PDF**.")
        st.stop()
    if df_fis is None:
        st.warning("⬅️ Primero cargá el Excel en la pestaña **2. Cupones físicos**.")
        st.stop()

    liq_dict   = {r["clave"]: r for r in liq}
    fis_claves = set(df_fis["clave"].tolist())
    resultados = []

    # Cupones físicos vs liquidación
    for _, row in df_fis.iterrows():
        clave = row["clave"]
        if clave in liq_dict:
            l       = liq_dict[clave]
            imp_fis = float(row.get("importe", 0) or 0)
            imp_liq = l["importe"]
            if imp_fis > 0:
                diff   = abs(imp_liq - imp_fis)
                estado = "✅ Coincide" if diff < 1 else f"⚠️ Dif. importe ${diff:,.2f}"
            else:
                estado = "✅ Encontrado"
            resultados.append({
                "Estado":              estado,
                "Sucursal":            COMERCIOS.get(row["comercio"], f"COM {row['comercio']}"),
                "Tarjeta":             l["tarjeta"],
                "Fecha liq.":          l["fecha"],
                "Lote":                row["lote"],
                "Cupón":               row["cupon"],
                "Importe físico":      f"${imp_fis:,.2f}" if imp_fis else "-",
                "Importe liquidación": f"${imp_liq:,.2f}",
            })
        else:
            imp_fis = float(row.get("importe", 0) or 0)
            resultados.append({
                "Estado":              "❌ No en liquidación",
                "Sucursal":            COMERCIOS.get(row["comercio"], f"COM {row['comercio']}"),
                "Tarjeta":             "-",
                "Fecha liq.":          "-",
                "Lote":                row["lote"],
                "Cupón":               row["cupon"],
                "Importe físico":      f"${imp_fis:,.2f}" if imp_fis else "-",
                "Importe liquidación": "-",
            })

    # En liquidación sin cupón físico
    for clave, l in liq_dict.items():
        if clave not in fis_claves:
            resultados.append({
                "Estado":              "⚠️ En liq. sin cupón físico",
                "Sucursal":            l["sucursal"],
                "Tarjeta":             l["tarjeta"],
                "Fecha liq.":          l["fecha"],
                "Lote":                l["lote"],
                "Cupón":               l["cupon"],
                "Importe físico":      "-",
                "Importe liquidación": f"${l['importe']:,.2f}",
            })

    df_res = pd.DataFrame(resultados)

    ok   = df_res["Estado"].str.startswith("✅").sum()
    warn = df_res["Estado"].str.startswith("⚠️").sum()
    err  = df_res["Estado"].str.startswith("❌").sum()

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Total registros",   len(df_res))
    col2.metric("✅ Coinciden",      int(ok))
    col3.metric("⚠️ Atención",      int(warn))
    col4.metric("❌ No encontrados", int(err))

    filtro = st.selectbox(
        "Filtrar por estado",
        ["Todos","✅ Coinciden","⚠️ Atención","❌ No en liquidación"]
    )
    if filtro == "✅ Coinciden":
        df_show = df_res[df_res["Estado"].str.startswith("✅")]
    elif filtro == "⚠️ Atención":
        df_show = df_res[df_res["Estado"].str.startswith("⚠️")]
    elif filtro == "❌ No en liquidación":
        df_show = df_res[df_res["Estado"].str.startswith("❌")]
    else:
        df_show = df_res

    st.dataframe(df_show, use_container_width=True, hide_index=True)

    # Exportar a Excel
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        df_res.to_excel(writer, index=False, sheet_name="Resultado")
        pd.DataFrame(liq)[["sucursal","tarjeta","fecha","lote","cupon","importe"]].to_excel(
            writer, index=False, sheet_name="Liquidaciones"
        )
    buf.seek(0)

    st.download_button(
        "⬇️ Descargar resultado completo (Excel)",
        data=buf,
        file_name=f"resultado_cruce_{datetime.today().strftime('%Y%m')}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        use_container_width=True
    )
