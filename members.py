import subprocess
import time
import cv2
import numpy as np
import os
import pytesseract
from difflib import get_close_matches

# --- CONFIGURACIÓN ---
ADB_PATH = r"C:\Program Files\BlueStacks_nxt\HD-Adb.exe"
DEVICE = "127.0.0.1:5555"
TXT_MAESTRO = "jugadores_maestro.txt"
# --- CONFIGURACIÓN DE RUTAS ---
ADB_PATH = r"C:\Program Files\BlueStacks_nxt\HD-Adb.exe"
DEVICE = "127.0.0.1:5555"
TXT_MAESTRO = "jugadores_maestro.txt"
pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

# --- CONFIGURACIÓN DE COORDENADAS Y SCROLL (Variables Globales) ---
X_START_COL, X_END_COL = 50, 430
Y_START_COL, Y_END_COL = 180, 1650
X_SWIPE, Y_SWIPE_INICIO, Y_SWIPE_FIN = 500, 1300, 700
DURACION_SWIPE_MS = 1500
pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

# --- CARGA DE LISTA NEGRA EXTERNA ---
def cargar_lista_negra():
    if os.path.exists("blacklist.txt"):
        with open("blacklist.txt", mode='r', encoding='utf-8') as f:
            # Cargamos todo en minúsculas para comparaciones insensibles al caso
            return [linea.strip().lower() for linea in f if linea.strip()]
    return []

def capturar_pantalla():
    archivo_android = "/sdcard/screen_tmp_miembros.png"
    archivo_local = "adb_tmp_miembros.png"
    try:
        subprocess.run(f'"{ADB_PATH}" -s {DEVICE} shell screencap -p {archivo_android}', shell=True, check=True, stdout=subprocess.DEVNULL)
        subprocess.run(f'"{ADB_PATH}" -s {DEVICE} pull {archivo_android} {archivo_local}', shell=True, check=True, stdout=subprocess.DEVNULL)
        subprocess.run(f'"{ADB_PATH}" -s {DEVICE} shell rm {archivo_android}', shell=True, check=True, stdout=subprocess.DEVNULL)
        img = cv2.imread(archivo_local)
        if os.path.exists(archivo_local): os.remove(archivo_local)
        return img
    except Exception as e:
        print(f"[ERROR ADB] {e}")
        return None

def hacer_scroll():
    print("  [Acción] Scroll controlado (Hold & Drag)...")
    comando = f'"{ADB_PATH}" -s {DEVICE} shell input touchscreen swipe {X_SWIPE} {Y_SWIPE_INICIO} {X_SWIPE} {Y_SWIPE_FIN} {DURACION_SWIPE_MS}'
    subprocess.run(comando, shell=True)
    time.sleep(2.0)

def leer_nombres_limpios(img, lista_negra):
    crop = img[180:1650, 50:430]
    hsv = cv2.cvtColor(crop, cv2.COLOR_BGR2HSV)
    mask = cv2.inRange(hsv, np.array([5, 80, 50]), np.array([30, 180, 160]))
    mask_inv = cv2.bitwise_not(mask)
    mask_dilated = cv2.dilate(mask, np.ones((1, 20), np.uint8), iterations=1)

    contours, _ = cv2.findContours(mask_dilated, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    contours = sorted(contours, key=lambda c: cv2.boundingRect(c)[1])
    
    nombres_lote = []
    for contour in contours:
        x, y, w, h = cv2.boundingRect(contour)
        
        # --- FILTRO GEOGRÁFICO (Adiós a los nombres cortados) ---
        # Si el nombre termina a menos de 10 píxeles del final de la ROI (y+h), es basura cortada
        if (y + h) > (Y_END_COL - Y_START_COL - 10):
            continue
        
        # Filtro de dimensiones físicas
        if w < 45 or h < 12: continue
            
        name_roi = mask_inv[max(0, y-4):min(mask_inv.shape[0], y+h+4), max(0, x-5):min(mask_inv.shape[1], x+w+5)]
        nombre = pytesseract.image_to_string(name_roi, config='--psm 7 -c tessedit_char_whitelist=abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789 ').strip()
        
        # Filtros
        if len(nombre) < 3 or "Rank" in nombre: continue
        if len(nombre) == 3 and nombre.islower(): continue
        
        # Filtro de lista negra (insensible a mayúsculas)
        if nombre.lower() in lista_negra: continue

        letras = sum(c.isalpha() for c in nombre)
        numeros = sum(c.isdigit() for c in nombre)
        if numeros > letras or numeros > 5: continue
        
        cambios_caso = sum(1 for i in range(len(nombre) - 1) if nombre[i].isupper() != nombre[i+1].isupper())
        if cambios_caso > 4: continue

        if nombre not in nombres_lote:
            nombres_lote.append(nombre)
    return nombres_lote

def main():
    print("=============================================\n 🔍 EXTRACTOR DE ALIANZA: AUTO-CORRECCIÓN\n=============================================")
    
    lista_negra = cargar_lista_negra()
    nombres_curados = []
    if os.path.exists(TXT_MAESTRO):
        with open(TXT_MAESTRO, mode='r', encoding='utf-8') as f:
            nombres_curados = [linea.replace('*', '').strip() for linea in f if linea.strip()]
            nombres_curados = [n for n in nombres_curados if n.lower() not in lista_negra]
        print(f"[MEMORIA] Se cargaron {len(nombres_curados)} nombres curados.")

    jugadores_totales = []
    scrolls = 0
    vacios = 0
    
    while scrolls < 25:
        img = capturar_pantalla()
        if img is None: break
            
        lote = leer_nombres_limpios(img, lista_negra)
        nuevos = 0
        
        for nombre in lote:
            # Duplicados y similitud
            if any(nombre.lower() == j.lower() for j in jugadores_totales): continue
            similares = get_close_matches(nombre, jugadores_totales, n=1, cutoff=0.75)
            if similares: continue  
            
            # Autocorrector
            if nombres_curados:
                match = get_close_matches(nombre, nombres_curados, n=1, cutoff=0.70)
                if match: nombre = match[0] 

            jugadores_totales.append(nombre)
            nuevos += 1
            print(f" -> [+ Miembro] {nombre}")
                
        vacios = vacios + 1 if nuevos == 0 else 0
        if vacios >= 2: break
        hacer_scroll()
        scrolls += 1

    # Guardado
    try:
        with open(TXT_MAESTRO, mode='w', encoding='utf-8') as f:
            for nombre in jugadores_totales:
                f.write(f"{nombre}\n")
        print("[ÉXITO] Lista maestra actualizada con los detectados hoy.")
    except Exception as e:
        print(f"[ERROR] No se pudo escribir el archivo: {e}")

if __name__ == "__main__":
    main()