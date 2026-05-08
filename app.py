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

def extraer_cupones_pdf(pdf_file):
    cupones = []
    contenido = ""
    with pdfplumber.open(pdf_file) as pdf:
        for page in pdf.pages:
            texto = page.extract_text()
            if texto:
                contenido += texto + "\n"

    comercio_match = re.search(r'N[°º]\s*Comercio[:\s]+(\d{9})', contenido)
    comercio = comercio_match.group(1).strip() if comercio_match else "Desconocido"

    if "DEBITO" in contenido.upper() and "VISA" in contenido.upper():
        tarjeta = "Visa Débito"
    elif "CREDITO" in contenido.upper() and "VISA" in contenido.upper():
        tarjeta = "Visa Crédito"
    elif "DEBITO" in contenido.upper() and "MASTER" in contenido.upper():
        tarjeta = "Mastercard Débito"
    elif "CREDITO" in contenido.upper() and "MASTER" in contenido.upper():
        tarjeta = "Mastercard Crédito"
    else:
        tarjeta = "Otra"

    patron = re.compile(
        r'Venta\s+(?:ctdo|cuo)\s+'
        r'(\d{2}/\d{2}/\d{2})\s+'
        r'(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s+'
        r'[\d,\.]+\s+'
        r'([\d\.,]+)'
    )

    for m in patron.finditer(contenido):
        fecha_str = m.group(1)
        lote = m.group(3)
        cupon = m.group(4).zfill(4)
        importe_str = m.group(6).replace('.', '').replace(',', '.')
        try:
            importe = float(importe_str)
        except:
            importe = 0.0

        cupones.append({
            "comercio": str(comercio).strip(),
            "sucursal": COMERCIOS.get(str(comercio).strip(), comercio),
            "tarjeta": tarjeta,
            "fecha": fecha_str,
            "lote": str(lote).strip().lstrip('0') or '0',
            "cupon": cupon.zfill(4),
            "importe": importe,
            "clave": f"{str(comercio).strip()}_{str(lote).strip().lstrip('0') or '0'}_{cupon.zfill(4)}",
        })

    return cupones, comercio, tarjeta


def generar_excel_plantilla():
    df = pd.DataFrame({
        "comercio": ["29992214", "29992250"],
        "lote": [149, 160],
        "cupon": ["0699", "1111"],
        "importe": [9477.42, 243914.57],
    })
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="Cupones")
        ws = writer.sheets["Cupones"]
        ws.column_dimensions["A"].width = 15
        ws.column_dimensions["B"].width = 10
        ws.column_dimensions["C"].width = 10
        ws.column_dimensions["D"].width = 15
    buf.seek(0)
    return buf


tab1, tab2, tab3 = st.tabs(["📄 1. Liquidaciones PDF", "🧾 2. Cupones físicos (Excel)", "✅ 3. Resultado del cruce"])

# ─── TAB 1: PDFs ────────────────────────────────────────────────────────────
with tab1:
    st.subheader("Subí los PDFs de Fiserv")
    st.info("Podés subir todos los archivos a la vez: Visa Débito, Crédito, Mastercard, todas las sucursales juntas.")

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
                        "Sucursal": COMERCIOS.get(str(com).strip(), com),
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
            df_liq = pd.DataFrame(todos_cupones)
            with st.expander("Ver cupones detectados"):
                st.dataframe(
                    df_liq[["sucursal", "tarjeta", "fecha", "lote", "cupon", "importe"]],
                    use_container_width=True,
                    hide_index=True
                )

        st.success("✅ PDFs cargados. Pasá a la pestaña **2. Cupones físicos**.")


# ─── TAB 2: EXCEL ───────────────────────────────────────────────────────────
with tab2:
    st.subheader("Cargá los cupones físicos desde Excel")

    with st.expander("📥 ¿Cómo armar el Excel?", expanded=True):
        st.markdown("""
El Excel debe tener exactamente **4 columnas** (el importe es opcional pero recomendado):

| comercio | lote | cupon | importe |
|---|---|---|---|
| 29992214 | 149 | 0699 | 9477.42 |
| 29992250 | 160 | 1111 | 243914.57 |

**¿Dónde encontrar cada dato en el cupón físico?**
- **comercio** → dice `COM: 29992214`
- **lote** → dice `N° LOTE: 149`
- **cupon** → dice `CUPON: 0699`
- **importe** → el importe en $ impreso en el ticket

El número de comercio identifica la sucursal automáticamente.
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
        type=["xlsx", "xls"],
        key="excel_cupones"
    )

    if excel_file:
        try:
            df_excel = pd.read_excel(excel_file, dtype=str)
            df_excel.columns = [c.lower().strip() for c in df_excel.columns]

            columnas_req = ["comercio", "lote", "cupon"]
            faltantes = [c for c in columnas_req if c not in df_excel.columns]
            if faltantes:
                st.error(f"Faltan columnas en el Excel: {', '.join(faltantes)}")
            else:
                df_excel["comercio"] = df_excel["comercio"].str.strip()
                df_excel["lote"] = df_excel["lote"].str.strip().str.lstrip('0').fillna('0')
                df_excel["cupon"] = df_excel["cupon"].str.strip().str.zfill(4)
                df_excel["sucursal"] = df_excel["comercio"].map(COMERCIOS).fillna(df_excel["comercio"])

                if "importe" in df_excel.columns:
                    df_excel["importe"] = pd.to_numeric(
                        df_excel["importe"].str.replace(',', '.', regex=False),
                        errors='coerce'
                    ).fillna(0)
                else:
                    df_excel["importe"] = None

                df_excel["clave"] = df_excel["comercio"] + "_" + df_excel["lote"] + "_" + df_excel["cupon"]

                st.session_state["cupones_excel"] = df_excel

                st.metric("Cupones cargados desde Excel", len(df_excel))
                st.dataframe(
                    df_excel[["sucursal", "lote", "cupon", "importe"] if "importe" in df_excel.columns else ["sucursal", "lote", "cupon"]],
                    use_container_width=True,
                    hide_index=True
                )
                st.success("✅ Excel cargado. Pasá a la pestaña **3. Resultado del cruce**.")

        except Exception as e:
            st.error(f"Error al leer el Excel: {e}")


# ─── TAB 3: CRUCE ───────────────────────────────────────────────────────────
with tab3:
    st.subheader("Resultado del cruce")

    liq = st.session_state.get("liq_cupones", [])
    df_fis = st.session_state.get("cupones_excel", None)

    if not liq:
        st.warning("⬅️ Primero subí los PDFs en la pestaña **1. Liquidaciones PDF**.")
        st.stop()

    if df_fis is None:
        st.warning("⬅️ Primero cargá el Excel en la pestaña **2. Cupones físicos**.")
        st.stop()

    df_liq = pd.DataFrame(liq)
    liq_dict = {r["clave"]: r for r in liq}
    fis_claves = set(df_fis["clave"].tolist())

    resultados = []

    # Cupones físicos vs liquidación
    for _, row in df_fis.iterrows():
        clave = row["clave"]
        if clave in liq_dict:
            l = liq_dict[clave]
            imp_fis = row.get("importe")
            imp_liq = l["importe"]
            if imp_fis is not None and imp_fis != 0:
                diff = abs(imp_liq - float(imp_fis))
                if diff < 1:
                    estado = "✅ Coincide"
                else:
                    estado = f"⚠️ Dif. importe ${diff:,.2f}"
            else:
                estado = "✅ Encontrado (sin importe)"
            resultados.append({
                "Estado": estado,
                "Sucursal": COMERCIOS.get(row["comercio"], row["comercio"]),
                "Lote": row["lote"],
                "Cupón": row["cupon"],
                "Importe físico": f"${float(imp_fis):,.2f}" if imp_fis else "-",
                "Importe liquidación": f"${imp_liq:,.2f}",
                "Fecha liq.": l["fecha"],
                "Tarjeta": l["tarjeta"],
            })
        else:
            resultados.append({
                "Estado": "❌ No en liquidación",
                "Sucursal": COMERCIOS.get(row["comercio"], row["comercio"]),
                "Lote": row["lote"],
                "Cupón": row["cupon"],
                "Importe físico": f"${float(row['importe']):,.2f}" if row.get("importe") else "-",
                "Importe liquidación": "-",
                "Fecha liq.": "-",
                "Tarjeta": "-",
            })

    # Cupones en liquidación sin físico
    for clave, l in liq_dict.items():
        if clave not in fis_claves:
            resultados.append({
                "Estado": "⚠️ En liq. sin cupón físico",
                "Sucursal": l["sucursal"],
                "Lote": l["lote"],
                "Cupón": l["cupon"],
                "Importe físico": "-",
                "Importe liquidación": f"${l['importe']:,.2f}",
                "Fecha liq.": l["fecha"],
                "Tarjeta": l["tarjeta"],
            })

    df_res = pd.DataFrame(resultados)

    ok   = df_res["Estado"].str.startswith("✅").sum()
    warn = df_res["Estado"].str.startswith("⚠️").sum()
    err  = df_res["Estado"].str.startswith("❌").sum()

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Total registros", len(df_res))
    col2.metric("✅ Coinciden", int(ok))
    col3.metric("⚠️ Atención", int(warn))
    col4.metric("❌ No encontrados", int(err))

    filtro = st.selectbox(
        "Filtrar por estado",
        ["Todos", "✅ Coinciden", "⚠️ Atención", "❌ No en liquidación"]
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

    # Exportar resultado
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        df_res.to_excel(writer, index=False, sheet_name="Resultado")
        df_liq[["sucursal","tarjeta","fecha","lote","cupon","importe"]].to_excel(
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
