import subprocess
import time
import cv2
import numpy as np
import os

# --- CONFIGURACIÓN ---
ADB_PATH = r"C:\Program Files\BlueStacks_nxt\HD-Adb.exe"
DEVICE = "127.0.0.1:5555"
COFRES_POR_LOTE = 6

# 1. COORDENADAS PARA VISIÓN (Detectar color en la tapa)
BASE_Y_COLOR = 517
PASO_Y = 186
TAPAS_COFRES = [(140, BASE_Y_COLOR + (i * PASO_Y)) for i in range(COFRES_POR_LOTE)]

# 2. COORDENADAS PARA ACCIÓN (Tus coordenadas originales confirmadas)
BOTONES_OPEN = [
    (950, 570), 
    (920, 750), 
    (910, 930), 
    (900, 1110), 
    (890, 1314), 
    (880, 1501)
]
X_CLEAR_ALL, Y_CLEAR_ALL = 230, 1780

cajas_totales = 0
stats_globales = {
    "Amarillo_Nivel_5": 0,
    "Azul_Nivel_3": 0,
    "Verde_Nivel_2": 0,
    "Nivel_Desconocido": 0
}

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
    # Expandimos un poco el área de recorte (de 10 a 15) para tolerar mejor las variaciones
    crop = img[y-15:y+15, x-15:x+15]
    hsv = cv2.cvtColor(crop, cv2.COLOR_BGR2HSV)
    
    if cv2.countNonZero(cv2.inRange(hsv, np.array([10, 150, 150]), np.array([25, 255, 255]))) > 30:
        return "Amarillo_Nivel_5"
    elif cv2.countNonZero(cv2.inRange(hsv, np.array([40, 100, 100]), np.array([60, 255, 255]))) > 30:
        return "Verde_Nivel_2"
    elif cv2.countNonZero(cv2.inRange(hsv, np.array([90, 100, 100]), np.array([115, 255, 255]))) > 30:
        return "Azul_Nivel_3"
        
    return "Nivel_Desconocido"

def tap(x, y, delay_personalizado=1.0):
    subprocess.run(f'"{ADB_PATH}" -s {DEVICE} shell input tap {x} {y}', shell=True)
    # Delay dinámico para controlar el lag de internet
    time.sleep(delay_personalizado)

def ejecutar_lote(num_ciclo):
    global cajas_totales
    print(f"\n--- Ciclo {num_ciclo} | Analizando lote de {COFRES_POR_LOTE} ---")
    
    img = capturar_pantalla()
    if img is None:
        print("Saltando lote por falla en captura.")
        return

    # 1. Analizamos la pantalla
    for i in range(COFRES_POR_LOTE):
        nivel = detectar_nivel(img, *TAPAS_COFRES[i])
        stats_globales[nivel] += 1
        cajas_totales += 1
        print(f"  -> Espacio {i+1} detectado como: {nivel}")

    # 2. Hacemos los clics con delays más seguros para el lag
    print("\n  [Acción] Ejecutando clics en los botones Open...")
    for i in range(COFRES_POR_LOTE):
        x_btn, y_btn = BOTONES_OPEN[i]
        print(f"    [*] Enviando clic al botón {i+1} en ({x_btn}, {y_btn})")
        # Subimos el delay a 1.0 segundos por botón para no saturar al servidor
        tap(x_btn, y_btn, delay_personalizado=1.0)
    
    # 3. Limpiamos lista
    print("\n  -> Limpiando lista (Clear All)...")
    # 3.5 segundos de espera total tras limpiar para asegurar la recarga por red
    tap(X_CLEAR_ALL, Y_CLEAR_ALL, delay_personalizado=2.0)
    
    print(f"Progreso actual: {cajas_totales} cofres procesados.")

if __name__ == "__main__":
    ciclos_deseados = 2
    ciclo_actual = 0
    
    print("Iniciando Bot Clasificador de Cofres (Modo Anti-Lag)...")
    try:
        while ciclo_actual < ciclos_deseados:
            ciclo_actual += 1
            ejecutar_lote(ciclo_actual)
            
        print(f"\n[ÉXITO] Meta completada.\nResultado final: {stats_globales}")
    except KeyboardInterrupt:
        print(f"\n[BOT DETENIDO]\nResumen guardado: {stats_globales}")
