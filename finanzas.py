import streamlit as st
import pandas as pd
import plotly.express as px
import calendar
from calendar import monthrange
import datetime
from datetime import date, timedelta
from plotly import graph_objects as go

st.set_page_config(
    page_title="Mi Plan Financiero", 
    layout="wide",  # Cambia a "wide" para usar todo el ancho disponible
    initial_sidebar_state="collapsed"  # Si decides añadir una barra lateral
)
st.title("💸 Planificador Financiero Mensual 💸")

# ---------- FUNCIONES DE UTILIDAD ----------

def manejar_redistribucion():
    """Maneja la redistribución de montos entre semanas cuando se envía el formulario"""
    gasto_frec = st.session_state.gasto_frec
    gasto_monto = st.session_state.gasto_monto
    
    if gasto_frec == "Quincenal":
        # Redistribuir entre semanas 1 y 3
        total_esperado = gasto_monto * 2
        suma_actual = st.session_state.semana_1_monto + st.session_state.semana_3_monto
        
        if abs(suma_actual - total_esperado) > 0.01:
            # Ajustar para que sumen correctamente
            if st.session_state.semana_1_monto > 0 and st.session_state.semana_3_monto == 0:
                # Si solo semana 1 tiene valor, poner todo en semana 1
                st.session_state.semana_1_monto = total_esperado
            elif st.session_state.semana_3_monto > 0 and st.session_state.semana_1_monto == 0:
                # Si solo semana 3 tiene valor, poner todo en semana 3
                st.session_state.semana_3_monto = total_esperado
            else:
                # Ajustar proporcionalmente
                factor = total_esperado / suma_actual
                st.session_state.semana_1_monto *= factor
                st.session_state.semana_3_monto *= factor
    else:
        # Para otras frecuencias, distribuir entre las 4 semanas
        if gasto_frec == "Mensual":
            total_esperado = gasto_monto
        elif gasto_frec == "Semanal":
            total_esperado = gasto_monto * 4
        elif gasto_frec == "Diario":
            total_esperado = gasto_monto * 7 * 4
        
        suma_actual = sum(st.session_state.get(f"semana_{i}_monto", 0.0) for i in range(1, 5))
        
        if abs(suma_actual - total_esperado) > 0.01:
            # Ajustar proporcional o equitativamente
            valores_no_cero = [i for i in range(1, 5) if st.session_state.get(f"semana_{i}_monto", 0) > 0]
            
            if len(valores_no_cero) > 0:
                # Ajuste proporcional para valores no cero
                factor = total_esperado / suma_actual
                for i in valores_no_cero:
                    st.session_state[f"semana_{i}_monto"] *= factor
            else:
                # Distribución equitativa si todo es cero
                valor_por_semana = total_esperado / 4
                for i in range(1, 5):
                    st.session_state[f"semana_{i}_monto"] = valor_por_semana
                    
def get_month_calendar(year, month):
    """Obtiene las semanas del mes especificado"""
    # Obtener el primer día del mes
    first_day = date(year, month, 1)
    
    # Encontrar el primer día de la semana (domingo)
    if first_day.weekday() != 6:  # si no es domingo
        first_day = first_day - timedelta(days=(first_day.weekday() + 1) % 7)
    
    # Último día real del mes
    real_last_day = date(year, month, calendar.monthrange(year, month)[1])

    # Calcular el sábado de la última semana que contiene al último día del mes
    last_day = real_last_day + timedelta(days=(5 - real_last_day.weekday()) % 7)
    
    # Crear semanas (lista de pares de fechas)
    weeks = []
    current = first_day
    while current <= last_day:
        week_end = current + timedelta(days=6)
        weeks.append((current, week_end))
        current = week_end + timedelta(days=1)
    
    return weeks

def format_date_range(start_date, end_date):
    """Formatea un rango de fechas como 'DD al DD de Mes'"""
    if start_date.month == end_date.month:
        return f"{start_date.day} al {end_date.day} de {calendar.month_name[start_date.month]}"
    else:
        return f"{start_date.day} de {calendar.month_name[start_date.month]} al {end_date.day} de {calendar.month_name[end_date.month]}"

# ---------- NUEVAS FUNCIONES DE CÁLCULO ----------
def calcular_ingreso_inicial_mensual(ingresos_df, year, month):
    """Calcula el total de ingresos al inicio del mes según la nueva lógica"""
    total_ingresos = 0
    
    for _, ingreso in ingresos_df.iterrows():
        monto = ingreso["Monto"]
        frecuencia = ingreso["Frecuencia"]
        
        if frecuencia == "Diario":
            # Obtener el número de días en el mes
            _, dias_en_mes = calendar.monthrange(year, month)
            total_ingresos += monto * dias_en_mes
        elif frecuencia == "Semanal":
            # Aproximadamente 4 semanas en un mes
            total_ingresos += monto * 4
        elif frecuencia == "Quincenal":
            # 2 quincenas en un mes
            total_ingresos += monto * 2
        elif frecuencia == "Mensual":
            total_ingresos += monto
    
    return total_ingresos

def calcular_ingreso_semanal(ingresos_df, numero_semana, semanas, dias_en_semana=7):
    """Calcula los ingresos para una semana específica según fechas específicas"""
    ingresos_semana = 0
    semana_actual = semanas[numero_semana - 1]  # Obtener la tupla (inicio, fin) de esta semana
    inicio_semana, fin_semana = semana_actual
    
    for _, ingreso in ingresos_df.iterrows():
        monto = ingreso["Monto"]
        frecuencia = ingreso["Frecuencia"]
        
        if frecuencia == "Diario":
            # Calcular días en esta semana (pueden ser menos de 7 al inicio/fin de mes)
            dias_en_semana = (fin_semana - inicio_semana).days + 1
            ingresos_semana += monto * dias_en_semana
        elif frecuencia == "Semanal":
            # Verificar si hay algún sábado en esta semana
            current_date = inicio_semana
            while current_date <= fin_semana:
                if current_date.weekday() == 5:  # 5 es sábado
                    ingresos_semana += monto
                    break
                current_date += timedelta(days=1)
        elif frecuencia == "Quincenal":
            # Verificar específicamente si el día 15 cae en esta semana
            año = inicio_semana.year
            mes = inicio_semana.month
            dia_15 = date(año, mes, 15)
            if inicio_semana <= dia_15 <= fin_semana:
                ingresos_semana += monto
        elif frecuencia == "Mensual":
            # Verificar específicamente si el último día del mes cae en esta semana
            ultimo_dia = date(inicio_semana.year, inicio_semana.month, 
                             calendar.monthrange(inicio_semana.year, inicio_semana.month)[1])
            if inicio_semana <= ultimo_dia <= fin_semana:
                ingresos_semana += monto
    
    return ingresos_semana

def calcular_gasto_semanal(gastos_df, numero_semana, semanas, semanas_totales=4):
    """Calcula los gastos para una semana específica según fechas específicas"""
    gastos_semana = 0
    semana_actual = semanas[numero_semana - 1]  # Obtener la tupla (inicio, fin) de esta semana
    inicio_semana, fin_semana = semana_actual
    
    for _, gasto in gastos_df.iterrows():
        monto = gasto["Monto"]
        frecuencia = gasto["Frecuencia"]
        distribucion_personalizada = gasto.get("Distribucion personalizada", False)
        
        if distribucion_personalizada:
            # Usar la distribución personalizada si existe
            distribucion_semanas = gasto.get("Distribucion semanas", {})
            semana_key = f"Semana {numero_semana}"
            if semana_key in distribucion_semanas:
                gastos_semana += distribucion_semanas[semana_key]
        else:
            # Usar la lógica por fechas específicas
            if frecuencia == "Diario":
                # Calcular días en esta semana (pueden ser menos de 7 al inicio/fin de mes)
                dias_en_semana = (fin_semana - inicio_semana).days + 1
                gastos_semana += monto * dias_en_semana
            elif frecuencia == "Semanal":
                # Verificar si hay algún sábado en esta semana
                current_date = inicio_semana
                while current_date <= fin_semana:
                    if current_date.weekday() == 5:  # 5 es sábado
                        gastos_semana += monto
                        break
                    current_date += timedelta(days=1)
            elif frecuencia == "Quincenal":
                # Verificar específicamente si el día 15 cae en esta semana
                año = inicio_semana.year
                mes = inicio_semana.month
                dia_15 = date(año, mes, 15)
                if inicio_semana <= dia_15 <= fin_semana:
                    gastos_semana += monto
            elif frecuencia == "Mensual":
                # Verificar específicamente si el último día del mes cae en esta semana
                ultimo_dia = date(inicio_semana.year, inicio_semana.month, 
                                calendar.monthrange(inicio_semana.year, inicio_semana.month)[1])
                if inicio_semana <= ultimo_dia <= fin_semana:
                    gastos_semana += monto
    
    return gastos_semana

def normalizar_monto_semanal(monto, frecuencia):
    """Normaliza un monto a valor semanal según su frecuencia"""
    if frecuencia == "Diario":
        return monto * 7  # 7 días en una semana
    elif frecuencia == "Semanal":
        return monto
    elif frecuencia == "Quincenal":
        return monto / 2  # Una quincena tiene 2 semanas aproximadamente
    elif frecuencia == "Mensual":
        return monto / 4.33  # Un mes tiene aproximadamente 4.33 semanas
    return monto

# Reemplaza la función redistribuir_resto con esta versión mejorada
def redistribuir_resto(semana_cambiada):
    gasto_frec = st.session_state.get("gasto_frec")
    gasto_monto = st.session_state.get("gasto_monto", 0.0)

    if gasto_frec == "Quincenal":
        total = gasto_monto * 2
        if semana_cambiada == 1:
            restante = total - st.session_state.get("semana_1_monto", 0.0)
            st.session_state["semana_3_monto"] = max(restante, 0.0)
        elif semana_cambiada == 3:
            restante = total - st.session_state.get("semana_3_monto", 0.0)
            st.session_state["semana_1_monto"] = max(restante, 0.0)
    else:
        if gasto_frec == "Mensual":
            total = gasto_monto
        elif gasto_frec == "Semanal":
            total = gasto_monto * 4
        elif gasto_frec == "Diario":
            total = gasto_monto * 7 * 4

        semanas = [1, 2, 3, 4]
        otras = [s for s in semanas if s != semana_cambiada]
        monto_cambiado = st.session_state.get(f"semana_{semana_cambiada}_monto", 0.0)
        restante = total - monto_cambiado

        if restante < 0:
            for s in otras:
                st.session_state[f"semana_{s}_monto"] = 0.0
        else:
            por_semana = restante / len(otras)
            for s in otras:
                st.session_state[f"semana_{s}_monto"] = por_semana

# ---------- SESIÓN ----------
if "ingresos" not in st.session_state:
    st.session_state.ingresos = []
if "gastos" not in st.session_state:
    st.session_state.gastos = []
if "es_deuda" not in st.session_state:
    st.session_state.es_deuda = False
if "year" not in st.session_state:
    st.session_state.year = datetime.datetime.now().year
if "month" not in st.session_state:
    st.session_state.month = datetime.datetime.now().month
if "distribucion_personalizada" not in st.session_state:
    st.session_state.distribucion_personalizada = False

# Funciones para agregar registros y limpiar campos
def agregar_ingreso():
    st.session_state.ingresos.append({
        "Nombre": st.session_state.ingreso_nombre,
        "Monto": st.session_state.ingreso_monto,
        "Tipo": st.session_state.ingreso_tipo,
        "Frecuencia": st.session_state.ingreso_frec,
        "Día de pago": st.session_state.ingreso_dia_pago if st.session_state.ingreso_frec == "Mensual" else None
    })
    # Limpiar campos después de agregar
    st.session_state.ingreso_nombre = ""
    st.session_state.ingreso_monto = 0.0
    st.session_state.ingreso_frec = "Semanal"
    st.session_state.ingreso_tipo = "Fijo"
    st.session_state.ingreso_dia_pago = 1

def inicializar_distribucion(gasto_monto, gasto_frec, semanas):
    """Inicializa las distribuciones de pago según la frecuencia y las fechas reales del mes"""
    distribucion = {}
    
    # Inicializar todas las semanas a cero
    for i in range(1, len(semanas) + 1):
        distribucion[f"Semana {i}"] = 0.0
    
    if gasto_frec == "Mensual":
        # Buscar cuál semana contiene el último día del mes
        ultimo_dia_mes = None
        for i, (inicio, fin) in enumerate(semanas):
            ultimo_dia = date(inicio.year, inicio.month, 
                             calendar.monthrange(inicio.year, inicio.month)[1])
            if inicio <= ultimo_dia <= fin:
                ultimo_dia_mes = i + 1  # Convertir a número de semana (1-indexed)
                break
        
        if ultimo_dia_mes:
            distribucion[f"Semana {ultimo_dia_mes}"] = gasto_monto
        else:
            # Si no encontramos el último día (poco probable), distribuir equitativamente
            monto_semanal = gasto_monto / len(semanas)
            for i in range(1, len(semanas) + 1):
                distribucion[f"Semana {i}"] = monto_semanal
    
    elif gasto_frec == "Quincenal":
        # Buscar la semana que contiene el día 15
        dia_15_semana = None
        for i, (inicio, fin) in enumerate(semanas):
            dia_15 = date(inicio.year, inicio.month, 15)
            if inicio <= dia_15 <= fin:
                dia_15_semana = i + 1  # Convertir a número de semana (1-indexed)
                break
        
        if dia_15_semana:
            distribucion[f"Semana {dia_15_semana}"] = gasto_monto
            
            # Para la otra quincena, usar la primera semana o última según corresponda
            if dia_15_semana <= 2:  # Si el día 15 está en la primera mitad del mes
                # La otra quincena estaría en la segunda mitad
                distribucion[f"Semana {len(semanas)}"] = gasto_monto
            else:
                # La otra quincena estaría al inicio del mes
                distribucion["Semana 1"] = gasto_monto
        else:
            # Si no encontramos el día 15 (poco probable), distribuir en semanas 1 y 3
            distribucion["Semana 1"] = gasto_monto
            if len(semanas) >= 3:
                distribucion["Semana 3"] = gasto_monto
    
    elif gasto_frec == "Semanal":
        # Mismo monto cada semana
        for i in range(1, len(semanas) + 1):
            distribucion[f"Semana {i}"] = gasto_monto
    
    elif gasto_frec == "Diario":
        # Calcular días en cada semana
        for i, (inicio, fin) in enumerate(semanas):
            dias_en_semana = (fin - inicio).days + 1
            distribucion[f"Semana {i+1}"] = gasto_monto * dias_en_semana
    
    return distribucion

def agregar_gasto():
    """Función para agregar un gasto a la lista de gastos"""
    # Obtener los valores del formulario
    nombre = st.session_state.gasto_nombre
    monto = st.session_state.gasto_monto
    frecuencia = st.session_state.gasto_frec
    dia_pago = st.session_state.get("gasto_dia_pago", 1)
    es_deuda = st.session_state.es_deuda
    deuda_total = st.session_state.get("deuda_total", 0.0) if es_deuda else None
    plazo = st.session_state.get("plazo", 1) if es_deuda else None
    pagos_realizados = st.session_state.get("pagos_realizados", 0) if es_deuda else None
    
    usar_distribucion_personalizada = st.session_state.distribucion_personalizada

    distribucion_semanas = {}
    if usar_distribucion_personalizada:
        for i in range(1, 5):
            key = f"semana_{i}_monto"
            distribucion_semanas[f"Semana {i}"] = st.session_state.get(key, 0.0)
    else:
        # Obtener las semanas actuales para el mes seleccionado
        semanas = get_month_calendar(st.session_state.year, st.session_state.month)
        distribucion_semanas = inicializar_distribucion(monto, frecuencia, semanas)

    st.session_state.gastos.append({
        "Nombre": nombre,
        "Monto": monto,
        "Frecuencia": frecuencia,
        "Día de pago": dia_pago if frecuencia == "Mensual" else None,
        "Es deuda": es_deuda,
        "Deuda total": deuda_total if es_deuda else None,
        "Plazo (meses)": plazo if es_deuda else None,
        "Pagos realizados": pagos_realizados if es_deuda else None,
        "Distribucion personalizada": usar_distribucion_personalizada,
        "Distribucion semanas": distribucion_semanas
    })

 def eliminar_ingreso(index):
    del st.session_state.ingresos[index]

def eliminar_gasto(index):
    del st.session_state.gastos[index]

## INTEN   
def reset_form():
    """Reinicia los campos del formulario de gastos y marca la bandera para limpiar visualmente."""
    st.session_state.reset_gasto = True  # 🔁 Bandera de limpieza

    for key in [
        "gasto_nombre", "gasto_monto", "gasto_frec", "gasto_dia_pago",
        "es_deuda", "deuda_total", "plazo", "pagos_realizados",
        "distribucion_personalizada"
    ]:
        if key in st.session_state:
            del st.session_state[key]

    for i in range(1, 5):
        st.session_state.pop(f"semana_{i}_monto", None)

    st.session_state.pop("campos_distribucion_inicializados", None)
    

# ---------- SELECTOR DE MES ----------
st.subheader("📅 Selecciona el mes a planificar")
col1, col2 = st.columns(2)
with col1:
    month = st.selectbox(
        "Mes",
        options=range(1, 13),
        format_func=lambda x: calendar.month_name[x],
        index=st.session_state.month - 1,
        key="selected_month"
    )
with col2:
    year = st.selectbox(
        "Año",
        options=range(datetime.datetime.now().year, datetime.datetime.now().year + 5),
        index=0,
        key="selected_year"
    )

# Actualizar el estado de la sesión
st.session_state.month = month
st.session_state.year = year

# Obtener las semanas del mes
semanas = get_month_calendar(year, month)
nombres_semanas = [format_date_range(start, end) for start, end in semanas]

# ---------- INGRESOS ----------
st.subheader("🟢 Registrar Ingreso")

with st.form("form_ingreso", clear_on_submit=True):
    col1, col2 = st.columns(2)
    with col1:
        st.text_input("Nombre del ingreso", key="ingreso_nombre")
        st.number_input("Monto del ingreso ($)", min_value=0.0, step=100.0, format="%0.2f", key="ingreso_monto")
    with col2:
        st.selectbox("Frecuencia", ["Diario", "Semanal", "Quincenal", "Mensual"], key="ingreso_frec")
        st.selectbox("Tipo de ingreso", ["Fijo", "Variable"], key="ingreso_tipo")
    
    # Mostrar selector de día de pago solo para pagos mensuales
    if st.session_state.get("ingreso_frec") == "Mensual":
        _, ultimo_dia = calendar.monthrange(year, month)
        st.number_input("Día de pago en el mes", min_value=1, max_value=ultimo_dia, step=1, key="ingreso_dia_pago")
    else:
        if "ingreso_dia_pago" not in st.session_state:
            st.session_state.ingreso_dia_pago = 1

    submitted_ingreso = st.form_submit_button("Agregar ingreso", on_click=agregar_ingreso)
    if submitted_ingreso:
        st.success("✅ Ingreso registrado")

# ---------- GASTOS ----------
st.subheader("🔴 Registrar Gasto")

# Inicializar la bandera de reseteo
if "reset_gasto" not in st.session_state:
    st.session_state.reset_gasto = False

# Obtener valores por defecto si se está reseteando
nombre_default = "" if st.session_state.reset_gasto else st.session_state.get("gasto_nombre", "")
monto_default = 0.0 if st.session_state.reset_gasto else st.session_state.get("gasto_monto", 0.0)
frec_default = "Semanal" if st.session_state.reset_gasto else st.session_state.get("gasto_frec", "Semanal")

# Inputs principales del formulario
st.text_input("Nombre del gasto", key="gasto_nombre", value=nombre_default)
st.number_input("Monto del gasto ($)", min_value=0.0, step=100.0, key="gasto_monto", value=monto_default)
st.selectbox("Frecuencia", ["Diario", "Semanal", "Quincenal", "Mensual"], key="gasto_frec", 
             index=["Diario", "Semanal", "Quincenal", "Mensual"].index(frec_default))

# Checkbox de deuda y distribución personalizada
st.checkbox("¿Es una deuda?", key="es_deuda")
st.checkbox("¿Quieres personalizar la distribución del pago?", key="distribucion_personalizada")

# Si es deuda, mostrar campos adicionales
if st.session_state.es_deuda:
    st.number_input("Monto total de la deuda", min_value=0.0, step=100.0, key="deuda_total")
    st.number_input("Plazo (meses)", min_value=1, step=1, key="plazo")
    st.number_input("Pagos realizados", min_value=0, step=1, key="pagos_realizados")

# Si se activa distribución personalizada
guardar = True  # Por defecto se puede guardar
if st.session_state.distribucion_personalizada:
    st.markdown("### Personaliza la distribución del gasto por semanas")

    gasto_monto = st.session_state.get("gasto_monto", 0.0)
    gasto_frec = st.session_state.get("gasto_frec", "Semanal")

    if gasto_frec == "Quincenal":
        total_esperado = gasto_monto * 2
    elif gasto_frec == "Mensual":
        total_esperado = gasto_monto
    elif gasto_frec == "Semanal":
        total_esperado = gasto_monto * 4
    elif gasto_frec == "Diario":
        total_esperado = gasto_monto * 7 * 4
    else:
        total_esperado = gasto_monto

    semanas_activas = [1, 2, 3, 4]
    st.write(f"Total a distribuir: ${total_esperado:,.2f}")

    for i in semanas_activas:
        st.number_input(f"Semana {i}", min_value=0.0, step=100.0, key=f"semana_{i}_monto")

    suma = sum(st.session_state.get(f"semana_{i}_monto", 0.0) for i in semanas_activas)
    if abs(suma - total_esperado) > 0.01:
        st.warning("⚠ La suma no coincide con el total esperado.")
        guardar = False
    else:
        st.success("✅ Distribución válida.")

# Botón para agregar gasto
if st.button("Agregar gasto"):
    if st.session_state.gasto_monto <= 0 or st.session_state.gasto_nombre.strip() == "":
        st.error("Completa todos los campos obligatorios.")
    elif st.session_state.distribucion_personalizada and not guardar:
        st.error("Corrige la distribución personalizada antes de guardar.")
    else:
        agregar_gasto()
        st.session_state.reset_gasto = True  # Activa limpieza visual
        reset_form()  # Limpia también los valores internos
        st.success("✅ Gasto registrado.")
        st.rerun()

# Apagar la bandera después del rerun
if st.session_state.reset_gasto:
    st.session_state.reset_gasto = False
    
# ---------- INGRESOS REGISTRADOS ----------
st.subheader("💰 Ingresos registrados")

if st.session_state.ingresos:
    df_ingresos = pd.DataFrame(st.session_state.ingresos)

    # Crear copia para mostrar
    df_ingresos_display = df_ingresos.copy()
    df_ingresos_display["Monto"] = df_ingresos_display["Monto"].apply(lambda x: f"${x:,.2f}")

    # Formatear columna "Día de pago" si aplica
    if "Día de pago" in df_ingresos_display.columns:
        df_ingresos_display["Día de pago"] = df_ingresos_display["Día de pago"].fillna("—")

    # Mostrar tabla
    st.dataframe(df_ingresos_display, use_container_width=True)

else:
    st.info("Aún no has registrado ingresos.")

st.markdown("### Eliminar ingreso")
for i, ingreso in enumerate(st.session_state.ingresos):
    st.write(f"{i+1}. {ingreso['Nombre']} - ${ingreso['Monto']:,.2f}")
    if st.button(f"Eliminar ingreso {i+1}", key=f"eliminar_ingreso_{i}"):
        eliminar_ingreso(i)
        st.rerun()
    
# ---------- GASTOS REGISTRADOS ----------
st.subheader("💸 Gastos registrados")
if st.session_state.gastos:
    df_gastos = pd.DataFrame(st.session_state.gastos)
    # Crear una copia del DataFrame para evitar modificar los valores originales
    df_gastos_display = df_gastos.copy()
    df_gastos_display["Monto"] = df_gastos_display["Monto"].apply(lambda x: f"${x:,.2f}")
    if "Deuda total" in df_gastos_display.columns:
        df_gastos_display["Deuda total"] = df_gastos_display["Deuda total"].apply(lambda x: f"${x:,.2f}" if pd.notnull(x) else "")
    
    # Ocultar columnas técnicas de distribución para una mejor visualización
    columnas_mostrar = [col for col in df_gastos_display.columns if col != "Distribucion semanas"]
    
    st.dataframe(df_gastos_display[columnas_mostrar])
    
    # Mostrar detalles de la distribución personalizada de gastos
    st.subheader("📊 Detalle de distribución de gastos por semana")
    gastos_con_distribucion = df_gastos[df_gastos["Distribucion personalizada"] == True]
    
    if not gastos_con_distribucion.empty:
        for _, gasto in gastos_con_distribucion.iterrows():
            st.write(f"**{gasto['Nombre']} (${gasto['Monto']:,.2f}):**")
            distribucion = gasto.get("Distribucion semanas", {})
            for semana, monto in distribucion.items():
                if isinstance(monto, (int, float)) and monto > 0:
                    st.write(f"- {semana}: ${monto:,.2f}")
    else:
        st.info("No hay gastos con distribución personalizada.")
else:
    st.info("Aún no has registrado gastos")

st.markdown("### Eliminar gasto")
for i, gasto in enumerate(st.session_state.gastos):
    st.write(f"{i+1}. {gasto['Nombre']} - ${gasto['Monto']:,.2f}")
    if st.button(f"Eliminar gasto {i+1}", key=f"eliminar_gasto_{i}"):
        eliminar_gasto(i)
        st.rerun()

# ---------- FLUJO MENSUAL POR SEMANAS ----------
st.subheader("📊 Flujo Financiero Mensual (Cascada)")

# Campo para ingreso manual del saldo inicial
#ingreso_inicial = st.number_input("Introduce el saldo inicial ($):", min_value=0.0, step=100.0)

if st.button("Calcular flujo mensual en cascada"): 
    if not st.session_state.ingresos or not st.session_state.gastos:
        st.warning("Necesitas registrar al menos un ingreso y un gasto para calcular el flujo.")
    else:
        try:
            df_ing = pd.DataFrame(st.session_state.ingresos)
            df_gas = pd.DataFrame(st.session_state.gastos)

            # Aseguramos que los montos sean numéricos
            df_ing["Monto"] = pd.to_numeric(df_ing["Monto"])
            df_gas["Monto"] = pd.to_numeric(df_gas["Monto"])

            # Determinar inicio y fin del mes real
            primer_dia_mes = date(st.session_state.year, st.session_state.month, 1)
            ultimo_dia_mes = date(st.session_state.year, st.session_state.month, monthrange(st.session_state.year, st.session_state.month)[1])

            nombres_etapas = []
            valores = []
            medidas = [] # Primera barra es absoluta

            semanas = get_month_calendar(st.session_state.year, st.session_state.month)
            num_semanas = len(semanas)
            
            # Inicializar el saldo acumulado con el ingreso inicial
            saldo_acumulado = 0
            
            # Lista para almacenar el flujo por semana (para tabla y análisis)
            flujo_por_semana = []

            # Procesar semana por semana para el acumulado correcto
            for i, (inicio, fin) in enumerate(semanas):
                semana_num = i + 1
                nombre_semana = format_date_range(inicio, fin)
                
                # Calcular ingresos semanales para esta semana
                ingresos_semana = 0
                for _, ingreso in df_ing.iterrows():
                    monto = ingreso["Monto"]
                    frecuencia = ingreso["Frecuencia"]
                    
                    # Ingresos diarios
                    if frecuencia == "Diario":
                        ingresos_semana += monto * 7  # 7 días por semana
                    
                    # Ingresos semanales
                    elif frecuencia == "Semanal":
                        ingresos_semana += monto
                    
                    # Ingresos quincenales (semanas 1 y 3)
                    elif frecuencia == "Quincenal" and semana_num in [1, 3]:
                        ingresos_semana += monto
                    
                    # Ingresos mensuales (solo semana 1)
                    elif frecuencia == "Mensual" and semana_num == 1:
                        ingresos_semana += monto
                
                # Calcular gastos semanales para esta semana
                gastos_semana = calcular_gasto_semanal(df_gas, semana_num, semanas, num_semanas)
                
                # Actualizar el saldo acumulado
                saldo_acumulado = saldo_acumulado + ingresos_semana - gastos_semana
                
                # Guardar datos para la tabla de análisis
                flujo_por_semana.append({
                    "Semana": nombre_semana,
                    "Ingresos": ingresos_semana,
                    "Gastos": gastos_semana,
                    "Flujo": ingresos_semana - gastos_semana,
                    "Saldo Acumulado": saldo_acumulado
                })
                
                # Agregar etapas para el gráfico de cascada
                if ingresos_semana > 0:
                    nombres_etapas.append(f"+ Ingresos {nombre_semana}")
                    valores.append(ingresos_semana)
                    medidas.append("relative")
                
                if gastos_semana > 0:
                    nombres_etapas.append(f"- Gastos {nombre_semana}")
                    valores.append(-gastos_semana)
                    medidas.append("relative")

            # Valor final para el gráfico
            nombres_etapas.append("Saldo final")
            medidas.append("total")
            valores.append(0)  # Plotly lo calcula automáticamente

            # Gráfico en cascada
            fig = go.Figure(go.Waterfall(
                name="Flujo mensual",
                orientation="v",
                measure=medidas,
                x=nombres_etapas,
                text=[f"${v:,.2f}" if i < len(valores)-1 else "" for i, v in enumerate(valores)],
                textposition="outside",
                y=valores,
                connector={"line": {"color": "rgb(63, 63, 63)"}}
            ))

            fig.update_layout(
                title="Flujo financiero en cascada por semana",
                waterfallgap=0.3,
                yaxis_title="Saldo ($)",
                showlegend=False
            )

            st.plotly_chart(fig, use_container_width=True)
            
            # Crear DataFrame para análisis
            flujo_df = pd.DataFrame(flujo_por_semana)
            
            # Análisis del flujo mensual
            flujo_total = flujo_df["Flujo"].sum()
            semanas_negativas = flujo_df[flujo_df["Saldo Acumulado"] < 0]
            
            if saldo_acumulado < 0:
                st.error(f"❌ Tu saldo final del mes es negativo: ${saldo_acumulado:,.2f}")
            else:
                st.success(f"✅ Tu saldo final del mes es positivo: ${saldo_acumulado:,.2f}")
            
            if not semanas_negativas.empty:
                st.warning(f"⚠ Tienes {len(semanas_negativas)} semana(s) con saldo acumulado negativo. Considera reorganizar tus pagos.")
                
                # Sugerencias para mejorar el flujo
                st.subheader("🔄 Sugerencias para mejorar el flujo")
                
                # Buscar semanas con flujo positivo alto que pueden ayudar a semanas negativas
                semanas_positivas = flujo_df[flujo_df["Flujo"] > 0].sort_values(by="Flujo", ascending=False)
                semanas_negativas = semanas_negativas.sort_values(by="Saldo Acumulado")
                
                if not semanas_positivas.empty:
                    st.write("Puedes considerar estas reorganizaciones:")
                    
                    # Buscar gastos que puedan moverse basados en si tienen distribución personalizada
                    gastos_movibles = df_gas[
                        (df_gas["Monto"] > 0)
                    ].sort_values(by="Monto", ascending=False)
                    
                    if not gastos_movibles.empty:
                        for _, gasto in gastos_movibles.iterrows():
                            # Para gastos sin distribución personalizada, sugerir activarla
                            if not gasto.get("Distribucion personalizada", False):
                                st.write(f"- El gasto '{gasto['Nombre']}' (${gasto['Monto']:,.2f}) podría distribuirse de manera personalizada entre semanas")
                            # Para gastos con distribución personalizada, sugerir redistribuir
                            else:
                                st.write(f"- Podrías ajustar la distribución actual del gasto '{gasto['Nombre']}' para aliviar semanas con saldo negativo")
                    else:
                        st.write("No se encontraron gastos que puedan moverse entre semanas.")
                else:
                    st.write("No hay semanas con flujo positivo suficiente para compensar las semanas negativas.")
            
            # Mostrar análisis detallado por semana
            st.subheader("📊 Análisis detallado por semana")
            
            for i, (semana_inicio, semana_fin) in enumerate(semanas):
                semana_num = i + 1
                nombre_semana = nombres_semanas[i]
                
                st.write(f"### Semana {semana_num}: {nombre_semana}")
                
                # Calcular ingresos detallados para esta semana
                ingresos_detalle = []
                for _, ingreso in df_ing.iterrows():
                    monto = ingreso["Monto"]
                    frecuencia = ingreso["Frecuencia"]
                    nombre = ingreso["Nombre"]
                    
                    # Determinar si el ingreso aplica para esta semana
                    ingreso_aplica = False
                    monto_aplicado = 0
                    
                    if frecuencia == "Diario":
                        ingreso_aplica = True
                        monto_aplicado = monto * 7  # 7 días por semana
                    elif frecuencia == "Semanal":
                        ingreso_aplica = True
                        monto_aplicado = monto
                    elif frecuencia == "Quincenal" and semana_num in [1, 3]:
                        ingreso_aplica = True
                        monto_aplicado = monto
                    elif frecuencia == "Mensual" and semana_num == 1:
                        ingreso_aplica = True
                        monto_aplicado = monto
                    
                    if ingreso_aplica:
                        ingresos_detalle.append({
                            "Nombre": nombre,
                            "Monto": monto_aplicado,
                            "Frecuencia": frecuencia
                        })
                
                # Calcular gastos detallados para esta semana
                gastos_detalle = []
                for _, gasto in df_gas.iterrows():
                    monto = gasto["Monto"]
                    frecuencia = gasto["Frecuencia"]
                    nombre = gasto["Nombre"]
                    distribucion_personalizada = gasto.get("Distribucion personalizada", False)
                    
                    # Determinar monto aplicado según si es distribución personalizada o no
                    monto_aplicado = 0
                    
                    if distribucion_personalizada:
                        # Usar la distribución personalizada si existe
                        distribucion_semanas = gasto.get("Distribucion semanas", {})
                        semana_key = f"Semana {semana_num}"
                        if semana_key in distribucion_semanas:
                            monto_aplicado = distribucion_semanas[semana_key]
                    else:
                        # Verificar fechas específicas para esta semana
                        if frecuencia == "Diario":
                            monto_aplicado = monto * (fin - semana_inicio).days + 1  # días en esta semana
                        elif frecuencia == "Semanal":
                            # Verificar si hay algún sábado en esta semana
                            current_date = semana_inicio
                            while current_date <= semana_fin:
                                if current_date.weekday() == 5:  # 5 es sábado
                                    monto_aplicado = monto
                                    break
                                current_date += timedelta(days=1)
                        elif frecuencia == "Quincenal":
                            # Verificar si el día 15 cae en esta semana
                            dia_15 = date(semana_inicio.year, semana_inicio.month, 15)
                            if semana_inicio <= dia_15 <= semana_fin:
                                monto_aplicado = monto
                        elif frecuencia == "Mensual":
                            # Verificar si el último día del mes cae en esta semana
                            ultimo_dia = date(semana_inicio.year, semana_inicio.month, 
                                        calendar.monthrange(semana_inicio.year, semana_inicio.month)[1])
                            if semana_inicio <= ultimo_dia <= semana_fin:
                                monto_aplicado = monto
                    
                    if monto_aplicado > 0:
                        gastos_detalle.append({
                            "Nombre": nombre,
                            "Monto": monto_aplicado,
                            "Frecuencia": frecuencia,
                            "Distribución": "Personalizada" if distribucion_personalizada else "Por defecto"
                        })
                
                # Mostrar tablas de ingresos y gastos para esta semana
                col1, col2 = st.columns(2)
                
                with col1:
                    st.write("#### Ingresos")
                    if ingresos_detalle:
                        df_ing_semana = pd.DataFrame(ingresos_detalle)
                        df_ing_semana["Monto"] = df_ing_semana["Monto"].apply(lambda x: f"${x:,.2f}")
                        st.dataframe(df_ing_semana, hide_index=True)
                        total_ingresos_semana = sum(ingreso["Monto"] for ingreso in ingresos_detalle)
                        st.write(f"**Total ingresos:** ${total_ingresos_semana:,.2f}")
                    else:
                        st.info("No hay ingresos para esta semana")
                
                with col2:
                    st.write("#### Gastos")
                    if gastos_detalle:
                        df_gas_semana = pd.DataFrame(gastos_detalle)
                        df_gas_semana["Monto"] = df_gas_semana["Monto"].apply(lambda x: f"${x:,.2f}")
                        st.dataframe(df_gas_semana, hide_index=True)
                        total_gastos_semana = sum(gasto["Monto"] for gasto in gastos_detalle)
                        st.write(f"**Total gastos:** ${total_gastos_semana:,.2f}")
                    else:
                        st.info("No hay gastos para esta semana")
                
                # Obtener el flujo y saldo acumulado de esta semana desde el DataFrame
                semana_info = flujo_df[flujo_df["Semana"] == nombre_semana].iloc[0]
                flujo_semana = semana_info["Flujo"]
                saldo_acumulado_semana = semana_info["Saldo Acumulado"]
                
                # Mostrar flujo y saldo acumulado con estilo según si el saldo acumulado es negativo
                if saldo_acumulado_semana < 0:
                    st.error(f"❌ Flujo de la semana: ${flujo_semana:,.2f}")
                    st.error(f"❌ Saldo acumulado: ${saldo_acumulado_semana:,.2f}")
                else:
                    st.success(f"✅ Flujo de la semana: ${flujo_semana:,.2f}")
                    st.success(f"✅ Saldo acumulado: ${saldo_acumulado_semana:,.2f}")
                
                st.markdown("---")
                
            # Tabla detallada de movimientos por semana
            tabla_detalle = []
            for i, (inicio, fin) in enumerate(semanas):
                semana_num = i + 1
                nombre_semana = format_date_range(inicio, fin)

                # Ingresos
                for _, ingreso in df_ing.iterrows():
                    monto = ingreso["Monto"]
                    frecuencia = ingreso["Frecuencia"]
                    aplica = (
                        (frecuencia == "Diario") or
                        (frecuencia == "Semanal") or
                        (frecuencia == "Quincenal" and semana_num in [1, 3]) or
                        (frecuencia == "Mensual" and semana_num == 1)
                    )
                    if aplica:
                        cantidad = monto * 7 if frecuencia == "Diario" else monto
                        tabla_detalle.append({
                            "Semana": nombre_semana,
                            "Orden Semana": semana_num,
                            "Tipo": "Ingreso",
                            "Concepto": ingreso["Nombre"],
                            "Monto": cantidad
                        })

                # Gastos
                for _, gasto in df_gas.iterrows():
                    monto = gasto["Monto"]
                    frecuencia = gasto["Frecuencia"]
                    aplica = (
                        (frecuencia == "Diario") or
                        (frecuencia == "Semanal") or
                        (frecuencia == "Quincenal" and semana_num in [1, 3]) or
                        (frecuencia == "Mensual" and semana_num == 1)
                    )
                    if aplica:
                        cantidad = monto * 7 if frecuencia == "Diario" else monto
                        tabla_detalle.append({
                            "Semana": nombre_semana,
                            "Orden Semana": semana_num,
                            "Tipo": "Gasto",
                            "Concepto": gasto["Nombre"],
                            "Monto": cantidad
                        })

            # Mostrar tabla detallada ordenada por número real de semana
            df_detalle = pd.DataFrame(tabla_detalle)
            df_detalle = df_detalle.sort_values(by=["Orden Semana", "Tipo"], ascending=[True, True])
            df_detalle = df_detalle.drop(columns=["Orden Semana"])  # Ocultar columna auxiliar

            st.subheader("📋 Detalle de movimientos semanales")
            st.dataframe(df_detalle, use_container_width=True)
            
            st.download_button(
                label="⬇ Descargar movimientos mensuales",
                data = df_detalle.to_csv(index=False),
                file_name="Flujo_financiero_mensual.csv",
                mime="text/csv"
            )
            
        except Exception as e:
            st.error(f"Ocurrió un error al calcular el flujo financiero: {e}")
            st.info("Verifica que tus datos sean correctos e intenta nuevamente.")

# ---------- SIMULADOR DE ESCENARIOS ----------
st.subheader("🔮 Simulador de comportamiento financiero")
if st.button("Calcular comportamiento financiero proyectado"):
    if not st.session_state.ingresos or not st.session_state.gastos:
        st.warning("Necesitas registrar al menos un ingreso y un gasto para calcular el flujo.")
    else:
        try:
            df_ing = pd.DataFrame(st.session_state.ingresos)
            df_gas = pd.DataFrame(st.session_state.gastos)

            df_ing["Monto"] = pd.to_numeric(df_ing["Monto"])
            df_gas["Monto"] = pd.to_numeric(df_gas["Monto"])

            nombres_etapas = []
            valores = []
            medidas = []

            semanas_actual = get_month_calendar(st.session_state.year, st.session_state.month)
            saldo_acumulado = 0
            flujo_por_semana = []

            # MES ACTUAL
            for i, (inicio, fin) in enumerate(semanas_actual):
                semana_num = i + 1
                nombre_semana = format_date_range(inicio, fin)

                ingresos_semana = 0
                for _, ingreso in df_ing.iterrows():
                    monto = ingreso["Monto"]
                    frecuencia = ingreso["Frecuencia"]
                    if frecuencia == "Diario":
                        ingresos_semana += monto * 7
                    elif frecuencia == "Semanal":
                        ingresos_semana += monto
                    elif frecuencia == "Quincenal" and semana_num in [1, 3]:
                        ingresos_semana += monto
                    elif frecuencia == "Mensual" and semana_num == 1:
                        ingresos_semana += monto

                gastos_semana = calcular_gasto_semanal(df_gas, semana_num, semanas_actual, len(semanas_actual))
                saldo_acumulado += ingresos_semana - gastos_semana

                flujo_por_semana.append({
                    "Semana": nombre_semana,
                    "Ingresos": ingresos_semana,
                    "Gastos": gastos_semana,
                    "Flujo": ingresos_semana - gastos_semana,
                    "Saldo Acumulado": saldo_acumulado
                })

                if ingresos_semana > 0:
                    nombres_etapas.append(f"+ Ingresos {nombre_semana}")
                    valores.append(ingresos_semana)
                    medidas.append("relative")
                if gastos_semana > 0:
                    nombres_etapas.append(f"- Gastos {nombre_semana}")
                    valores.append(-gastos_semana)
                    medidas.append("relative")

            # MES SIGUIENTE
            if st.session_state.month == 12:
                next_month = 1
                next_year = st.session_state.year + 1
            else:
                next_month = st.session_state.month + 1
                next_year = st.session_state.year

            semanas_siguiente = get_month_calendar(next_year, next_month)

            for i, (inicio, fin) in enumerate(semanas_siguiente):
                semana_num = i + 1
                nombre_semana = format_date_range(inicio, fin)

                ingresos_semana = 0
                for _, ingreso in df_ing.iterrows():
                    monto = ingreso["Monto"]
                    frecuencia = ingreso["Frecuencia"]
                    if frecuencia == "Diario":
                        ingresos_semana += monto * 7
                    elif frecuencia == "Semanal":
                        ingresos_semana += monto
                    elif frecuencia == "Quincenal" and semana_num in [1, 3]:
                        ingresos_semana += monto
                    elif frecuencia == "Mensual" and semana_num == 1:
                        ingresos_semana += monto

                gastos_semana = calcular_gasto_semanal(df_gas, semana_num, semanas_siguiente, len(semanas_siguiente))
                saldo_acumulado += ingresos_semana - gastos_semana

                flujo_por_semana.append({
                    "Semana": nombre_semana + " (simulado)",
                    "Ingresos": ingresos_semana,
                    "Gastos": gastos_semana,
                    "Flujo": ingresos_semana - gastos_semana,
                    "Saldo Acumulado": saldo_acumulado
                })

                if ingresos_semana > 0:
                    nombres_etapas.append(f"+ Ingresos {nombre_semana} (simulado)")
                    valores.append(ingresos_semana)
                    medidas.append("relative")
                if gastos_semana > 0:
                    nombres_etapas.append(f"- Gastos {nombre_semana} (simulado)")
                    valores.append(-gastos_semana)
                    medidas.append("relative")

            # Saldo final
            nombres_etapas.append("Saldo final proyectado")
            medidas.append("total")
            valores.append(0)

            fig = go.Figure(go.Waterfall(
                name="Proyección",
                orientation="v",
                measure=medidas,
                x=nombres_etapas,
                text=[f"${v:,.2f}" if i < len(valores)-1 else "" for i, v in enumerate(valores)],
                textposition="outside",
                y=valores,
                connector={"line": {"color": "gray"}}
            ))

            fig.update_layout(
                title="Flujo financiero proyectado (2 meses)",
                waterfallgap=0.3,
                yaxis_title="Saldo ($)",
                showlegend=False
            )

            st.plotly_chart(fig, use_container_width=True)

            flujo_df = pd.DataFrame(flujo_por_semana)
            st.dataframe(flujo_df, use_container_width=True)
            
            st.download_button(
                label="⬇ Descargar movimientos bimestrales",
                data = flujo_df.to_csv(index=False),
                file_name="Flujo_financiero_bimestral.csv",
                mime="text/csv"
            )

        except Exception as e:
            st.error(f"Ocurrió un error: {e}")
