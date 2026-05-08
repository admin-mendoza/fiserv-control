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
        terminal = m.group(2)
        lote = m.group(3)
        cupon = m.group(4).zfill(4)
        tarj_num = m.group(5)
        importe_str = m.group(6).replace('.', '').replace(',', '.')
        try:
            importe = float(importe_str)
        except:
            importe = 0.0

        cupones.append({
            "comercio": comercio,
            "sucursal": COMERCIOS.get(comercio, comercio),
            "tarjeta": tarjeta,
            "fecha": fecha_str,
            "terminal": terminal,
            "lote": lote,
            "cupon": cupon,
            "tarj_num": tarj_num,
            "importe": importe,
            "clave": f"{comercio}_{lote}_{cupon}",
        })

    return cupones, comercio, tarjeta

tab1, tab2, tab3 = st.tabs(["📄 Liquidaciones PDF", "🧾 Cupones físicos", "✅ Resultado del cruce"])

with tab1:
    st.subheader("Subí los PDFs de Fiserv")
    st.info("Podés subir todos los archivos a la vez. Visa Débito, Crédito, Mastercard, todas las sucursales juntas.")

    pdfs = st.file_uploader(
        "Seleccioná los PDFs de liquidación",
        type="pdf",
        accept_multiple_files=True,
        key="pdfs"
    )

    if pdfs:
        todos_cupones = []
        resumen = []
        errores = []

        with st.spinner("Procesando PDFs..."):
            for pdf in pdfs:
                try:
                    cups, com, tarj = extraer_cupones_pdf(pdf)
                    todos_cupones.extend(cups)
                    resumen.append({
                        "Archivo": pdf.name,
                        "Comercio": COMERCIOS.get(com, com),
                        "Tarjeta": tarj,
                        "Cupones encontrados": len(cups)
                    })
                except Exception as e:
                    errores.append(f"{pdf.name}: {e}")

        st.session_state["liq_cupones"] = todos_cupones

        col1, col2 = st.columns(2)
        with col1:
            st.metric("Total cupones en liquidaciones", len(todos_cupones))
        with col2:
            st.metric("Archivos procesados", len(pdfs))

        st.dataframe(pd.DataFrame(resumen), use_container_width=True, hide_index=True)

        if errores:
            with st.expander("⚠️ Advertencias"):
                for e in errores:
                    st.warning(e)

        if todos_cupones:
            df_liq = pd.DataFrame(todos_cupones)
            st.subheader("Vista previa de cupones detectados")
            st.dataframe(
                df_liq[["sucursal", "tarjeta", "fecha", "lote", "cupon", "importe"]].head(30),
                use_container_width=True,
                hide_index=True
            )

with tab2:
    st.subheader("Ingresá los cupones físicos")
    st.caption("Completá los datos de cada cupón que tenés en papel del punto de venta.")

    if "cupones_fisicos" not in st.session_state:
        st.session_state["cupones_fisicos"] = []

    with st.form("form_cupon", clear_on_submit=True):
        col1, col2, col3 = st.columns(3)
        with col1:
            fecha = st.date_input("Fecha", value=datetime.today())
            comercio_sel = st.selectbox("Comercio / Sucursal", options=list(COMERCIOS.keys()),
                                        format_func=lambda x: f"{COMERCIOS[x]}")
        with col2:
            tarjeta_sel = st.selectbox("Tarjeta", ["Visa Débito", "Visa Crédito", "Mastercard Débito", "Mastercard Crédito"])
            lote_inp = st.text_input("N° Lote", placeholder="ej: 149")
        with col3:
            cupon_inp = st.text_input("N° Cupón", placeholder="ej: 0699")
            importe_inp = st.text_input("Importe $", placeholder="ej: 9477.42")

        submitted = st.form_submit_button("➕ Agregar cupón", use_container_width=True)
        if submitted:
            if not lote_inp or not cupon_inp or not importe_inp:
                st.error("Completá lote, cupón e importe.")
            else:
                try:
                    importe_val = float(importe_inp.replace(',', '.'))
                    cupon_pad = cupon_inp.strip().zfill(4)
                    clave = f"{comercio_sel}_{lote_inp.strip()}_{cupon_pad}"
                    st.session_state["cupones_fisicos"].append({
                        "comercio": comercio_sel,
                        "sucursal": COMERCIOS.get(comercio_sel, comercio_sel),
                        "tarjeta": tarjeta_sel,
                        "fecha": fecha.strftime("%d/%m/%y"),
                        "lote": lote_inp.strip(),
                        "cupon": cupon_pad,
                        "importe": importe_val,
                        "clave": clave,
                    })
                    st.success(f"Cupón {cupon_pad} agregado.")
                except ValueError:
                    st.error("El importe debe ser un número.")

    cups_fis = st.session_state.get("cupones_fisicos", [])
    if cups_fis:
        st.subheader(f"Cupones ingresados: {len(cups_fis)}")
        df_fis = pd.DataFrame(cups_fis)
        st.dataframe(
            df_fis[["sucursal", "tarjeta", "fecha", "lote", "cupon", "importe"]],
            use_container_width=True,
            hide_index=True
        )
        if st.button("🗑️ Limpiar todos los cupones"):
            st.session_state["cupones_fisicos"] = []
            st.rerun()

        csv = df_fis.to_csv(index=False).encode("utf-8")
        st.download_button("⬇️ Descargar cupones como CSV", csv, "cupones_fisicos.csv", "text/csv")
    else:
        st.info("Todavía no ingresaste ningún cupón.")

with tab3:
    st.subheader("Resultado del cruce")

    liq = st.session_state.get("liq_cupones", [])
    fis = st.session_state.get("cupones_fisicos", [])

    if not liq:
        st.warning("Primero subí los PDFs en la pestaña 'Liquidaciones PDF'.")
    elif not fis:
        st.warning("Primero ingresá los cupones físicos en la pestaña 'Cupones físicos'.")
    else:
        liq_dict = {c["clave"]: c for c in liq}
        fis_dict = {c["clave"]: c for c in fis}

        resultados = []

        for clave, c in fis_dict.items():
            if clave in liq_dict:
                l = liq_dict[clave]
                diff = abs(l["importe"] - c["importe"])
                if diff < 1:
                    estado = "✅ Coincide"
                    color = "success"
                else:
                    estado = f"⚠️ Diferencia ${diff:,.2f}"
                    color = "warning"
            else:
                estado = "❌ No en liquidación"
                color = "error"
            resultados.append({
                "Estado": estado,
                "Sucursal": c["sucursal"],
                "Tarjeta": c["tarjeta"],
                "Fecha": c["fecha"],
                "Lote": c["lote"],
                "Cupón": c["cupon"],
                "Importe físico": c["importe"],
                "Importe liq.": liq_dict.get(clave, {}).get("importe", "-"),
                "_color": color
            })

        for clave, l in liq_dict.items():
            if clave not in fis_dict:
                resultados.append({
                    "Estado": "⚠️ Sin cupón físico",
                    "Sucursal": l["sucursal"],
                    "Tarjeta": l["tarjeta"],
                    "Fecha": l["fecha"],
                    "Lote": l["lote"],
                    "Cupón": l["cupon"],
                    "Importe físico": "-",
                    "Importe liq.": l["importe"],
                    "_color": "warning"
                })

        df_res = pd.DataFrame(resultados)

        total = len(resultados)
        ok = len([r for r in resultados if "Coincide" in r["Estado"]])
        warn = len([r for r in resultados if "⚠️" in r["Estado"]])
        err = len([r for r in resultados if "❌" in r["Estado"]])

        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Total registros", total)
        col2.metric("✅ Coinciden", ok)
        col3.metric("⚠️ Atención", warn)
        col4.metric("❌ No encontrados", err)

        filtro = st.selectbox("Filtrar por estado", ["Todos", "✅ Coincide", "⚠️ Atención", "❌ No en liquidación"])
        if filtro != "Todos":
            df_show = df_res[df_res["Estado"].str.contains(filtro[:2])]
        else:
            df_show = df_res

        st.dataframe(
            df_show.drop(columns=["_color"]),
            use_container_width=True,
            hide_index=True
        )

        csv_res = df_show.drop(columns=["_color"]).to_csv(index=False).encode("utf-8")
        st.download_button(
            "⬇️ Descargar resultado completo (CSV)",
            csv_res,
            "resultado_cruce.csv",
            "text/csv",
            use_container_width=True
        )
