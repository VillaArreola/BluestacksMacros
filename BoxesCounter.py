import subprocess
import time
import cv2
import numpy as np
import os
import pytesseract
import csv
from difflib import get_close_matches

# --- CONFIGURACIÓN DE RUTAS ---
ADB_PATH = r"C:\Program Files\BlueStacks_nxt\HD-Adb.exe"
DEVICE = "127.0.0.1:5555"
COFRES_POR_LOTE = 6
CSV_FILE = "reporte_alianza.csv"

# Configuración de Tesseract
pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

# --- COORDENADAS DE VISIÓN ---
BASE_Y_COLOR = 517
PASO_Y = 186
TAPAS_COFRES = [(140, BASE_Y_COLOR + (i * PASO_Y)) for i in range(COFRES_POR_LOTE)]

X_START_TEXT, X_END_TEXT = 430, 830
BASE_Y_TEXT_START = 484
BASE_Y_TEXT_END = 526

# --- COORDENADAS DE ACCIÓN ---
BOTONES_OPEN = [
    (950, 570), (920, 750), (910, 930), (900, 1110), (890, 1314), (880, 1501)
]
X_CLEAR_ALL, Y_CLEAR_ALL = 230, 1780

# --- ALMACENAMIENTO ---
cajas_totales = 0
registro_jugadores = {}  # Se cargará automáticamente del CSV si existe

def cargar_desde_csv():
    """Busca si existe un reporte previo y lo carga en memoria para no perder datos"""
    global registro_jugadores
    if os.path.exists(CSV_FILE):
        try:
            with open(CSV_FILE, mode='r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    jugador = row["Jugador"]
                    registro_jugadores[jugador] = {
                        "Verde_Nivel_2": int(row["Verde Nivel 2"]),
                        "Azul_Nivel_3": int(row["Azul Nivel 3"]),
                        "Amarillo_Nivel_5": int(row["Amarillo Nivel 5"]),
                        "Nivel_Desconocido": int(row["Desconocido"])
                    }
            print(f"[MEMORIA] Se cargaron {len(registro_jugadores)} jugadores del archivo existente.")
        except Exception as e:
            print(f"[WARN] Archivo CSV corrupto o vacío, iniciando historial nuevo. {e}")
            registro_jugadores = {}
    else:
        print("[MEMORIA] No se encontró archivo previo. Iniciando base de datos limpia.")
        registro_jugadores = {}

def guardar_en_csv():
    """Guarda o actualiza el archivo CSV en tiempo real"""
    try:
        with open(CSV_FILE, mode='w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(["Jugador", "Verde Nivel 2", "Azul Nivel 3", "Amarillo Nivel 5", "Desconocido"])
            for jug, datos in registro_jugadores.items():
                writer.writerow([
                    jug, 
                    datos["Verde_Nivel_2"], 
                    datos["Azul_Nivel_3"], 
                    datos["Amarillo_Nivel_5"], 
                    datos["Nivel_Desconocido"]
                ])
    except Exception as e:
        print(f"[ERROR EXCEL] {e}")

def capturar_pantalla():
    archivo_android = "/sdcard/screen_tmp.png"
    archivo_local = "adb_tmp.png"
    try:
        subprocess.run(f'"{ADB_PATH}" -s {DEVICE} shell screencap -p {archivo_android}', shell=True, check=True, stdout=subprocess.DEVNULL)
        subprocess.run(f'"{ADB_PATH}" -s {DEVICE} pull {archivo_android} {archivo_local}', shell=True, check=True, stdout=subprocess.DEVNULL)
        subprocess.run(f'"{ADB_PATH}" -s {DEVICE} shell rm {archivo_android}', shell=True, check=True, stdout=subprocess.DEVNULL)
        img = cv2.imread(archivo_local)
        if os.path.exists(archivo_local):
            os.remove(archivo_local)
        return img
    except Exception as e:
        print(f"[ERROR ADB] {e}")
        return None

def detectar_nivel(img, x, y):
    crop = img[y-15:y+15, x-15:x+15]
    hsv = cv2.cvtColor(crop, cv2.COLOR_BGR2HSV)
    if cv2.countNonZero(cv2.inRange(hsv, np.array([10, 150, 150]), np.array([25, 255, 255]))) > 30:
        return "Amarillo_Nivel_5"
    elif cv2.countNonZero(cv2.inRange(hsv, np.array([40, 100, 100]), np.array([60, 255, 255]))) > 30:
        return "Verde_Nivel_2"
    elif cv2.countNonZero(cv2.inRange(hsv, np.array([90, 100, 100]), np.array([115, 255, 255]))) > 30:
        return "Azul_Nivel_3"
    return "Nivel_Desconocido"

def leer_nombre_jugador(img, indice_cofre):
    y_start = BASE_Y_TEXT_START + (indice_cofre * PASO_Y)
    y_end = BASE_Y_TEXT_END + (indice_cofre * PASO_Y)
    
    crop = img[y_start:y_end, X_START_TEXT:X_END_TEXT]
    gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
    _, thresh = cv2.threshold(gray, 150, 255, cv2.THRESH_BINARY_INV)
    
    config_ocr = r'--psm 7 -c tessedit_char_whitelist=abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789'
    texto = pytesseract.image_to_string(thresh, config=config_ocr).strip()
    
    for basurilla in ["Brought by", "Brought", "by"]:
        texto = texto.replace(basurilla, "").strip()
        
    if not texto:
        return "Desconocido_OCR"
        
    nombres_existentes = list(registro_jugadores.keys())
    coincidencias = get_close_matches(texto, nombres_existentes, n=1, cutoff=0.80)
    
    if coincidencias:
        return coincidencias[0]
    return texto

def tap(x, y, delay=1.0):
    subprocess.run(f'"{ADB_PATH}" -s {DEVICE} shell input tap {x} {y}', shell=True)
    time.sleep(delay)

def generar_reporte_bonito():
    """Genera un formato de texto limpio optimizado para chats de comunidad"""
    print("\n=============================================")
    print(" 📜 REPORTE DE RECOLECCIÓN (Listo para copiar)")
    print("=============================================")
    print(f"Fecha/Hora local: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print("---------------------------------------------")
    
    # Ordenamos a los jugadores por el que más cofres totales aportó
    jugadores_ordenados = sorted(
        registro_jugadores.items(), 
        key=lambda x: sum(x[1].values()), 
        reverse=True
    )
    
    for i, (jugador, datos) in enumerate(jugadores_ordenados):
        total = sum(datos.values())
        if total == 0: continue
        # Generamos una línea estética por jugador
        print(f"{i+1:02d}. 👤 {jugador:<15} 📦 Total: {total} [🟡x{datos['Amarillo_Nivel_5']} | 🔵x{datos['Azul_Nivel_3']} | 🟢x{datos['Verde_Nivel_2']}]")
    print("=============================================\n")

def ejecutar_lote(num_ciclo):
    global cajas_totales
    print(f"\n--- Ciclo {num_ciclo} ---")
    
    img = capturar_pantalla()
    if img is None:
        print("Saltando lote por falla en captura.")
        return

    lote_actual = []
    # 1. ANALIZAR Y GUARDAR EN CALIENTE (Para permitir auto-corrección en el mismo lote)
    for i in range(COFRES_POR_LOTE):
        nivel = detectar_nivel(img, *TAPAS_COFRES[i])
        jugador = leer_nombre_jugador(img, i)
        
        # FILTRO ANTI-BASURA: Ignora nombres de menos de 3 caracteres (como "re")
        if len(jugador) < 3 and jugador != "Desconocido_OCR":
            jugador = "Desconocido_OCR"
            
        lote_actual.append((jugador, nivel))
        cajas_totales += 1
        print(f"  -> [{i+1}] {jugador} => {nivel}")
        
        # Guardamos en memoria INMEDIATAMENTE para que el siguiente cofre pueda usarlo de referencia
        if jugador not in registro_jugadores:
            registro_jugadores[jugador] = {"Amarillo_Nivel_5": 0, "Azul_Nivel_3": 0, "Verde_Nivel_2": 0, "Nivel_Desconocido": 0}

    # 2. ACCIÓN (Abrir cofres físicos y sumar los contadores)
    print("\n  [Acción] Abriendo cofres...")
    for i in range(COFRES_POR_LOTE):
        x_btn, y_btn = BOTONES_OPEN[i]
        tap(x_btn, y_btn, delay=1.0)
        
        jugador, nivel = lote_actual[i]
        registro_jugadores[jugador][nivel] += 1
    
    # 3. Guardado en Excel
    guardar_en_csv()
    
    # 4. Limpiar lista
    print("\n  -> Limpiando lista (Clear All)...")
    tap(X_CLEAR_ALL, Y_CLEAR_ALL, delay=2.0)

if __name__ == "__main__":
    # --- CONTROL DE CICLOS ---
    ciclos_deseados = 2  # Pon los ciclos que quieras procesar en esta ejecución
    ciclo_actual = 0
    
    print("Iniciando Bot Analizador Histórico de Alianza...")
    # PASO CLAVE: Cargamos lo que ya se había hecho antes en el día
    cargar_desde_csv()
    
    try:
        while ciclo_actual < ciclos_deseados:
            ciclo_actual += 1
            ejecutar_lote(ciclo_actual)
            
        print("\n[PROCESO TERMINADO CON ÉXITO]")
        generar_reporte_bonito()
        
    except KeyboardInterrupt:
        print("\n[BOT INTERRUMPIDO]")
        generar_reporte_bonito()