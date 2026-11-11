"""NUEVO RUMBOS — NOTAS DE VENTAS DEPOSITO 56 · Consulta móvil.

Aplicación independiente de SOLO LECTURA. No importa deposito56.py ni contiene
operaciones de escritura a Supabase. Mantiene sus tablas y cálculos básicos.
"""
from __future__ import annotations

from datetime import date
from pathlib import Path
import hmac
import pandas as pd
import streamlit as st
from supabase import create_client

st.set_page_config(page_title="Depósito 56 · Consulta", page_icon="📋", layout="wide", initial_sidebar_state="collapsed")
st.markdown("""<style>
.stApp {background:linear-gradient(150deg,#061a42 0%,#03499b 55%,#0879c8 100%);}
[data-testid="stMainBlockContainer"] {background:rgba(255,255,255,.96);border-radius:20px;padding:20px 18px 40px;max-width:1100px;}
.nr-heading {background:linear-gradient(125deg,#083f99,#0695e8);color:white;padding:17px;border-radius:17px;margin-bottom:14px;text-align:center;}
.nr-heading h2 {color:white;margin:0;font-weight:900;font-size:clamp(19px,5vw,31px)}
.nr-heading small {color:#dbefff;font-weight:700;letter-spacing:.5px}
[data-testid="stMetric"] {background:#e8f3ff;border:1px solid #a7d0fa;border-radius:13px;padding:12px 10px;}
@media(max-width:767px){[data-testid="stMainBlockContainer"]{padding:15px 10px 35px;margin:5px!important;width:calc(100% - 10px)!important;} [data-testid="stMetricValue"]{font-size:22px!important;}}
</style>""",unsafe_allow_html=True)


def secret_value(section, key):
    try:
        return str(st.secrets[section][key]).strip()
    except (KeyError, FileNotFoundError, AttributeError, TypeError):
        return ""


# A dedicated visitor password, distinct from editing users. Never put secrets in source.
visitor_password = secret_value("visitante", "password")
if not visitor_password:
    st.error("Configura [visitante] password en Secrets de esta nueva aplicación.")
    st.stop()
if not st.session_state.get("deposito56_visitante_autorizado", False):
    st.markdown('<div class="nr-heading"><h2>NOTAS DE VENTAS · DEPÓSITO 56</h2><small>ACCESO VISITANTE · SOLO CONSULTA</small></div>', unsafe_allow_html=True)
    with st.form("visitor_login"):
        pwd = st.text_input("Contraseña de visitante", type="password")
        submit = st.form_submit_button("Entrar", use_container_width=True)
    if submit:
        if hmac.compare_digest(pwd, visitor_password):
            st.session_state["deposito56_visitante_autorizado"] = True
            st.rerun()
        else:
            st.error("Contraseña incorrecta")
    st.stop()

url = secret_value("supabase", "url")
key = secret_value("supabase", "secret_key")
if not url.startswith("https://") or not key:
    st.error("Configura [supabase] url y secret_key en Secrets de esta app (igual que en deposito56).")
    st.stop()

@st.cache_resource
def client(url: str, key: str):
    return create_client(url,key)


def fetch_all(table, fields, location=None):
    result=[]; start=0; n=1000
    api=client(url,key)
    while True:
        query=api.table(table).select(fields)
        if location is not None:
            query=query.eq("sede",location)
        part=query.range(start,start+n-1).execute().data or []
        result.extend(part)
        if len(part)<n: break
        start+=n
    return result


@st.cache_data(ttl=60, show_spinner="Consultando datos actualizados...")
def load_data():
    sales=fetch_all("ventas", "id,sede,nro_nota,fecha,cliente,categoria,descripcion,cantidad,precio_unitario,precio_total,precio_dolar")
    inventory=fetch_all("inventario", "sede,categoria,ingreso")
    return sales,inventory


st.markdown('<div class="nr-heading"><h2>NOTAS DE VENTAS · DEPÓSITO 56</h2><small>NUEVO RUMBOS · VERSIÓN MÓVIL VISITANTE</small></div>',unsafe_allow_html=True)
col_refresh,col_logout=st.columns([3,2])
with col_refresh:
    if st.button("🔄 Actualizar resultados",use_container_width=True):
        load_data.clear();st.rerun()
with col_logout:
    if st.button("🔒 Salir",use_container_width=True):
        st.session_state["deposito56_visitante_autorizado"]=False;st.rerun()

try:
    sales_rows,inventory_rows=load_data()
except Exception:
    st.error("No se pudieron cargar las tablas. Revisa la conexión y los permisos de lectura de Supabase.")
    st.stop()

SEDES={"SANTACRUZ":"Santa Cruz", "TARIJA":"Tarija", "CAMIONCITO":"Camioncito"}
DATA_COLS=["Nro Nota","Fecha","Cliente","Categoría","Descripción","Cantidad","Precio Unitario (Bs.)","Precio Total (Bs.)","Precio en Dólar"]

# Mantener exactamente las equivalencias históricas del inventario del PC.
# Filtro de 14 permanece independiente.
RENOMBRES_HISTORICOS = {
    "t de manimetro": "t de manometro",
    "manómetro": "manometro",
    "filtro": "filtro de 12",
    "filtro 12": "filtro de 12",
    "kit tercera at04": "kit de tercera AT04",
    "kit de at04": "kit de tercera AT04",
}

def normalizar_categoria(nombre):
    limpio = " ".join(str(nombre or "").split())
    return RENOMBRES_HISTORICOS.get(limpio.casefold(), limpio)

def clave_categoria_inventario(nombre):
    limpio = " ".join(str(nombre or "").split())
    sin_acentos = "".join(
        caracter for caracter in __import__("unicodedata").normalize("NFKD", limpio)
        if not __import__("unicodedata").combining(caracter)
    )
    # El PC conserva la distinción histórica Manometro / manometro.
    if sin_acentos.casefold() == "manometro":
        return sin_acentos
    return normalizar_categoria(limpio).casefold()

records=[]
for r in sales_rows:
    sede=str(r.get("sede") or "").upper()
    if sede not in SEDES: continue
    records.append({
       "Sede":SEDES[sede], "_sede":sede,
       "Nro Nota":int(r.get("nro_nota") or 0),
       "Fecha":pd.to_datetime(r.get("fecha"),errors="coerce"),
       "Cliente":str(r.get("cliente") or ""),
       "Categoría":str(r.get("categoria") or "").strip(),
       "Descripción":str(r.get("descripcion") or ""),
       "Cantidad":int(r.get("cantidad") or 0),
       "Precio Unitario (Bs.)":float(r.get("precio_unitario") or 0),
       "Precio Total (Bs.)":float(r.get("precio_total") or 0),
       "Precio en Dólar":float(r.get("precio_dolar") or 0),
    })
all_sales=pd.DataFrame(records,columns=["Sede","_sede",*DATA_COLS])

st.subheader("RESUMEN GENERAL")
if all_sales.empty:
    default_start=default_end=date.today()
else:
    valid_dates=all_sales["Fecha"].dropna()
    default_start=valid_dates.min().date() if not valid_dates.empty else date.today()
    default_end=max(date.today(),valid_dates.max().date()) if not valid_dates.empty else date.today()
c1,c2=st.columns(2)
with c1: start_date=st.date_input("Desde",value=default_start,format="DD/MM/YYYY")
with c2: end_date=st.date_input("Hasta",value=default_end,format="DD/MM/YYYY")
if start_date>end_date:
    st.warning("La fecha inicial debe ser anterior o igual a la final.");st.stop()
mask=(all_sales["Fecha"].dt.date>=start_date)&(all_sales["Fecha"].dt.date<=end_date)
selected=all_sales.loc[mask].copy()
a,b=st.columns(2)
with a: st.metric("TOT VENDIDO",f'{selected["Precio Total (Bs.)"].sum():,.2f} Bs.')
with b: st.metric("TOT PRODOTTI",f'{int(selected["Cantidad"].sum()):,}')
st.caption("Totales de Santa Cruz, Tarija y Camioncito dentro del rango seleccionado. Notas con precio unitario cero: crédito, según la aplicación original.")

st.subheader("NOTAS DE VENTAS")
for sede, display in SEDES.items():
    df=selected.loc[selected["_sede"]==sede,DATA_COLS].copy().sort_values(["Fecha","Nro Nota"],kind="stable")
    with st.expander(f"{display.upper()} · {len(df)} registros · {df['Precio Total (Bs.)'].sum():,.2f} Bs."):
        if df.empty:
            st.info("No hay notas en las fechas seleccionadas.")
        else:
            st.dataframe(df,hide_index=True,use_container_width=True,height=min(510,70+len(df)*35),
                column_config={"Fecha":st.column_config.DateColumn("Fecha",format="DD/MM/YYYY")})

st.subheader("CONTROL DE INVENTARIO Y DEPÓSITO")
st.caption("Los ingresos se leen de inventario. Las salidas se calculan de TODAS las notas registradas, sin filtro por fechas, igual que en el programa original.")
product_path=Path(__file__).resolve().with_name("productos.txt")
if product_path.exists():
    raw_products=[x.strip() for x in product_path.read_text(encoding="utf-8-sig").splitlines() if x.strip() and not x.lstrip().startswith("#")]
else:
    raw_products=[r.get("categoria") for r in inventory_rows if r.get("categoria")]

# Catálogo sin duplicados después de aplicar los mismos nombres oficiales del PC.
products_by_key={}
for raw_name in raw_products:
    official_name=normalizar_categoria(raw_name)
    key_name=clave_categoria_inventario(official_name)
    if official_name and key_name not in products_by_key:
        products_by_key[key_name]=official_name
products=list(products_by_key.values())

# En la vista móvil mostramos únicamente "manometro" en minúsculas.
# "Manometro" con M mayúscula queda oculto para evitar la fila duplicada;
# no se modifican ni se eliminan registros de Supabase.
products=[name for name in products if name != "Manometro"]

# IMPORTANTE: puede haber varias filas históricas de una categoría/sede.
# Se suman, no se sobrescriben. Filtro + Filtro 12 se acumulan en Filtro de 12.
entries={}
for r in inventory_rows:
    sede=str(r.get("sede") or "").upper()
    category_key=clave_categoria_inventario(r.get("categoria"))
    if sede in SEDES and category_key:
        identifier=(sede,category_key)
        entries[identifier]=entries.get(identifier,0)+int(r.get("ingreso") or 0)

sold={}
for item in records:
    identifier=(item["_sede"],clave_categoria_inventario(item["Categoría"]))
    sold[identifier]=sold.get(identifier,0)+item["Cantidad"]

inv=[]
for name in products:
    row={"Producto":name}
    category_key=clave_categoria_inventario(name)
    for sede,label in SEDES.items():
        abbr={"SANTACRUZ":"Santa Cruz","TARIJA":"Tarija","CAMIONCITO":"Camioncito"}[sede]
        ingress=entries.get((sede,category_key),0)
        out=sold.get((sede,category_key),0)
        row[f"Ing. {abbr}"]=ingress
        row[f"Sal. {abbr}"]=out
        row[f"Stock {abbr}"]=ingress-out
    row["Ingreso Total"]=sum(row[f"Ing. {x}"] for x in SEDES.values())
    row["Salida Total"]=sum(row[f"Sal. {x}"] for x in SEDES.values())
    row["Stock Total"]=row["Ingreso Total"]-row["Salida Total"]
    inv.append(row)
inv_df=pd.DataFrame(inv)
with st.expander(f"DEPÓSITO · {len(inv_df)} productos · Stock total {int(inv_df['Stock Total'].sum()) if not inv_df.empty else 0}",expanded=False):
    st.dataframe(inv_df,hide_index=True,use_container_width=True,height=500)

st.caption("🔒 Solo lectura: esta aplicación no puede crear, modificar ni eliminar registros. Datos actualizables mediante el botón; caché de 60 segundos.")
