import subprocess
import time
import cv2
import numpy as np
import os
import pytesseract

# --- CONFIGURACIÓN DE RUTAS ---
ADB_PATH = r"C:\Program Files\BlueStacks_nxt\HD-Adb.exe"
DEVICE = "127.0.0.1:5555"
COFRES_POR_LOTE = 6

# Configuración de Tesseract (Ajusta la ruta si se instaló en otra carpeta)
pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

# --- COORDENADAS DE VISIÓN (Tapas y Nombres) ---
BASE_Y_COLOR = 517
PASO_Y = 186
TAPAS_COFRES = [(140, BASE_Y_COLOR + (i * PASO_Y)) for i in range(COFRES_POR_LOTE)]

# Coordenadas que me pasaste para los recuadros de los nombres
X_START_TEXT, X_END_TEXT = 430, 830
BASE_Y_TEXT_START = 484
BASE_Y_TEXT_END = 526

# --- COORDENADAS DE ACCIÓN (Tus coordenadas originales confirmadas)
BOTONES_OPEN = [
    (950, 570), 
    (920, 750), 
    (910, 930), 
    (900, 1110), 
    (890, 1314), 
    (880, 1501)
]
X_CLEAR_ALL, Y_CLEAR_ALL = 230, 1780

# --- ESTRUCTURAS DE ALMACENAMIENTO DE DATOS ---
cajas_totales = 0
registro_jugadores = {}  # Formato: {"JugadorName": {"Azul_Nivel_3": X, ...}}

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
    """Recorta el área del texto, aplica filtros de imagen y extrae el nombre con OCR"""
    # Calculamos la Y dinámicamente para el cofre actual
    y_start = BASE_Y_TEXT_START + (indice_cofre * PASO_Y)
    y_end = BASE_Y_TEXT_END + (indice_cofre * PASO_Y)
    
    # Recorte de la zona del texto
    crop = img[y_start:y_end, X_START_TEXT:X_END_TEXT]
    
    # Procesamiento de imagen para mejorar la lectura del OCR
    gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
    # Convertimos a blanco y negro puro (Thresholding binarizado)
    _, thresh = cv2.threshold(gray, 150, 255, cv2.THRESH_BINARY_INV)
    
    # Pasar a Tesseract config `--psm 7` (Asume que es una sola línea de texto)
    config_ocr = r'--psm 7 -c tessedit_char_whitelist=abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789'
    texto_extraido = pytesseract.image_to_string(thresh, config=config_ocr).strip()
    
    # Limpieza básica: quitar el "Brought by" si el OCR lo llega a capturar
    if "Brought by" in texto_extraido:
        texto_extraido = texto_extraido.replace("Brought by", "").strip()
    elif "Brought" in texto_extraido:
        texto_extraido = texto_extraido.replace("Brought", "").strip()
    
    # Si el OCR devuelve vacío, le asignamos un flag genérico
    return texto_extraido if texto_extraido else "Desconocido_OCR"

def tap(x, y, delay_personalizado=1.0):
    subprocess.run(f'"{ADB_PATH}" -s {DEVICE} shell input tap {x} {y}', shell=True)
    time.sleep(delay_personalizado)

def ejecutar_lote(num_ciclo):
    global cajas_totales
    print(f"\n--- Ciclo {num_ciclo} | Analizando lote de {COFRES_POR_LOTE} ---")
    
    img = capturar_pantalla()
    if img is None:
        print("Saltando lote por falla en captura.")
        return

    # 1. ANALIZAR (Color + Nombre en memoria)
    lote_actual = []
    for i in range(COFRES_POR_LOTE):
        nivel = detectar_nivel(img, *TAPAS_COFRES[i])
        jugador = leer_nombre_jugador(img, i)
        
        lote_actual.append((jugador, nivel))
        cajas_totales += 1
        print(f"  -> Espacio {i+1} | Jugador: {jugador} | Cofre: {nivel}")

    # 2. ACCIÓN (Clics uno a uno)
    print("\n  [Acción] Ejecutando clics en los botones Open...")
    for i in range(COFRES_POR_LOTE):
        x_btn, y_btn = BOTONES_OPEN[i]
        tap(x_btn, y_btn, delay_personalizado=1.0)
        
        # Guardamos en el diccionario global en este micro-segundo muerto
        jugador, nivel = lote_actual[i]
        if jugador not in registro_jugadores:
            registro_jugadores[jugador] = {"Amarillo_Nivel_5": 0, "Azul_Nivel_3": 0, "Verde_Nivel_2": 0, "Nivel_Desconocido": 0}
        registro_jugadores[jugador][nivel] += 1
    
    # 3. LIMPIAR LISTA (Aprovechamos el delay largo aquí)
    print("\n  -> Limpiando lista (Clear All)...")
    tap(X_CLEAR_ALL, Y_CLEAR_ALL, delay_personalizado=2.0)
    
    print(f"\nProgreso: {cajas_totales} cofres procesados.")
    print("Estadísticas acumuladas por jugador:")
    for jug, datos in registro_jugadores.items():
        print(f"  * {jug}: {datos}")

if __name__ == "__main__":
    ciclos_deseados = 2
    ciclo_actual = 0
    
    print("Iniciando Bot Analizador e Historial de Alianza...")
    try:
        while ciclo_actual < ciclos_deseados:
            ciclo_actual += 1
            ejecutar_lote(ciclo_actual)
            
        print(f"\n[ÉXITO] Ejecución terminada.\nReporte Final de la Alianza:\n{registro_jugadores}")
    except KeyboardInterrupt:
        print(f"\n[BOT DETENIDO] Reporte acumulado hasta el momento:\n{registro_jugadores}")