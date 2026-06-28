import subprocess
import time
import cv2
import numpy as np
import os
import pytesseract
from difflib import get_close_matches

# --- CONFIGURACIÓN DE RUTAS ---
ADB_PATH = r"C:\Program Files\BlueStacks_nxt\HD-Adb.exe"
DEVICE = "127.0.0.1:5555"
TXT_MAESTRO = "jugadores_maestro.txt"

pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
# --- AJUSTE DE VISIÓN ---
X_START_COL = 50
X_END_COL = 450
# Bajamos esto a 240 para atrapar al líder y los Rango 5 que están al puro principio
Y_START_COL = 240  
Y_END_COL = 1600   

# --- AJUSTE DE SCROLL (MÁS CORTO PARA CREAR SOLAPAMIENTO) ---
X_SWIPE = 500
Y_SWIPE_INICIO = 1300 
Y_SWIPE_FIN = 700     # Cambiamos de 400 a 700 para que el "dy" sea de -600 en vez de -1100
DURACION_SWIPE_MS = 1000

def capturar_pantalla():
    archivo_android = "/sdcard/screen_tmp_miembros.png"
    archivo_local = "adb_tmp_miembros.png"
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

def hacer_scroll():
    print("  [Acción] Haciendo scroll hacia abajo...")
    comando = f'"{ADB_PATH}" -s {DEVICE} shell input swipe {X_SWIPE} {Y_SWIPE_INICIO} {X_SWIPE} {Y_SWIPE_FIN} {DURACION_SWIPE_MS}'
    subprocess.run(comando, shell=True)
    time.sleep(2.0) # Dar tiempo a que el juego renderice la nueva lista

def leer_nombres_columna(img):
    crop = img[Y_START_COL:Y_END_COL, X_START_COL:X_END_COL]
    
    hsv = cv2.cvtColor(crop, cv2.COLOR_BGR2HSV)
    
    lower_brown = np.array([5, 80, 50])
    upper_brown = np.array([30, 180, 160])
    mask = cv2.inRange(hsv, lower_brown, upper_brown)
    
    mask_inv = cv2.bitwise_not(mask)
    
    config_ocr = r'--psm 6 -c tessedit_char_whitelist=abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789 '
    texto_crudo = pytesseract.image_to_string(mask_inv, config=config_ocr)
    
    nombres_encontrados = set()
    for linea in texto_crudo.split('\n'):
        nombre_limpio = linea.strip()
        
        # 1. Cortar el paréntesis del nickname primero
        if "(" in nombre_limpio:
            nombre_limpio = nombre_limpio.split("(")[0].strip()
            
        # 2. Filtros básicos de longitud y cabeceras
        if len(nombre_limpio) < 3: continue
        if "Rank" in nombre_limpio: continue
        
        # --- 3. EL NUEVO FILTRO ANTI-BASURA ---
        letras = sum(c.isalpha() for c in nombre_limpio)
        numeros = sum(c.isdigit() for c in nombre_limpio)
        
        # Si la palabra tiene más números que letras (ej. M426887956 o 45399723)
        # o si tiene más de 6 números en total, lo descartamos por ser nivel de poder.
        if numeros > letras or numeros > 6:
            continue
            
        nombres_encontrados.add(nombre_limpio)
        
    return nombres_encontrados

def main():
    print("Iniciando escaneo inteligente de la alianza...")
    jugadores_totales = set()
    intentos_vacios = 0
    scrolls_realizados = 0
    MAX_SCROLLS = 25  # Límite duro de seguridad (25 scrolls son más de 150 jugadores)
    
    while scrolls_realizados < MAX_SCROLLS:
        img = capturar_pantalla()
        if img is None: break
            
        nombres_lote = leer_nombres_columna(img)
        
        # Filtro inteligente para detectar nombres REALMENTE nuevos
        nuevos_nombres_reales = set()
        lista_existentes = list(jugadores_totales)
        
        for nombre in nombres_lote:
            if nombre in jugadores_totales:
                continue # Ya existe exactamente igual
                
            # Si el nombre es un 85% similar a uno que ya tenemos, es un error del OCR, lo ignoramos
            similares = get_close_matches(nombre, lista_existentes, n=1, cutoff=0.85)
            if not similares:
                nuevos_nombres_reales.add(nombre)
        
        if nuevos_nombres_reales:
            print(f" -> Detectados {len(nuevos_nombres_reales)} nuevos: {', '.join(nuevos_nombres_reales)[:80]}...")
            jugadores_totales.update(nuevos_nombres_reales)
            intentos_vacios = 0
        else:
            print(f" -> Sin nombres nuevos. (Intento vacío {intentos_vacios + 1}/3)")
            intentos_vacios += 1
            
        # Si hacemos 3 scrolls seguidos sin encontrar gente nueva, estamos en el fondo.
        if intentos_vacios >= 3:
            print("\n[FIN] Llegamos al fondo de la lista (3 rebotes vacíos).")
            break
            
        hacer_scroll()
        scrolls_realizados += 1
        
    if scrolls_realizados >= MAX_SCROLLS:
        print("\n[FIN] Se alcanzó el límite máximo de scrolls de seguridad.")

    # Guardado
    print(f"\n💾 Guardando {len(jugadores_totales)} jugadores en '{TXT_MAESTRO}'...")
    with open(TXT_MAESTRO, mode='w', encoding='utf-8') as f:
        for j in sorted(jugadores_totales):
            f.write(f"{j}\n")
    print("[ÉXITO] Archivo maestro generado correctamente.")

if __name__ == "__main__":
    main()