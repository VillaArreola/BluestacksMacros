import subprocess, time, cv2, numpy as np, os, pytesseract, csv
from difflib import get_close_matches

# --- CONFIG ---
ADB_PATH = r"C:\Program Files\BlueStacks_nxt\HD-Adb.exe"
DEVICE = "127.0.0.1:5555"
TXT_MAESTRO = "jugadores_maestro.txt"
CSV_FILE = "reporte_alianza.csv"
pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

CONFIG_NIVELES = [("🔺Lvl6", "level_6"), ("🟡Lvl5", "level_5"), ("🟣Lvl4", "level_4"), 
                  ("🔵Lvl3", "level_3"), ("🟢Lvl2", "level_2"), ("🟤Lvl1", "level_1")]

registro_jugadores, nombres_maestros = {}, []

def cargar_datos():
    global nombres_maestros, registro_jugadores
    if os.path.exists(TXT_MAESTRO):
        with open(TXT_MAESTRO, 'r', encoding='utf-8') as f:
            nombres_maestros = [l.strip().replace('*','') for l in f if l.strip()]
    if os.path.exists(CSV_FILE):
        with open(CSV_FILE, 'r', encoding='utf-8') as f:
            for row in csv.DictReader(f):
                jug = row["Jugador"]
                registro_jugadores[jug] = {k: int(row.get(e, 0)) for e, k in CONFIG_NIVELES}

def guardar_csv():
    with open(CSV_FILE, 'w', newline='', encoding='utf-8') as f:
        w = csv.writer(f)
        w.writerow(["Jugador", "Lvl 1", "Lvl 2", "Lvl 3", "Lvl 4", "Lvl 5", "Lvl 6"])
        for jug, d in registro_jugadores.items():
            w.writerow([jug, d.get("level_1",0), d.get("level_2",0), d.get("level_3",0), d.get("level_4",0), d.get("level_5",0), d.get("level_6",0)])

def get_name(img, i):
    y1, y2 = 484 + (i * 186), 526 + (i * 186)
    crop = cv2.threshold(cv2.cvtColor(img[y1:y2, 430:830], cv2.COLOR_BGR2GRAY), 120, 255, cv2.THRESH_BINARY_INV)[1]
    txt = pytesseract.image_to_string(crop, config='--psm 7 -c tessedit_char_whitelist=abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789').strip()
    
    # Correcciones fijas
    corrections = {"Lyd": "Lyr4", "Lw4": "Lyr4", "rVUASInBan": "FOXSinBan"}
    txt = corrections.get(txt, txt)
    
    # Si lee basura muy larga o palabras clave vacías, lo marcamos como desconocido
    if txt.lower() in ["re", "r", "e", ""] or len(txt) > 16: return "unknown_player"
    
    match = get_close_matches(txt, nombres_maestros or list(registro_jugadores.keys()), n=1, cutoff=0.65)
    return match[0] if match else txt

def get_level(img, i):
    hsv = cv2.cvtColor(img[517 + (i * 186)-15:517 + (i * 186)+15, 140-15:140+15], cv2.COLOR_BGR2HSV)
    # Prioridad 1: Colores definidos (El azul ahora tiene un rango más amplio)
    if cv2.countNonZero(cv2.inRange(hsv, np.array([90, 40, 40]), np.array([130, 255, 255]))) > 20: return "level_3" # Azul
    if cv2.countNonZero(cv2.inRange(hsv, np.array([35, 40, 40]), np.array([85, 255, 255]))) > 20: return "level_2"  # Verde
    if cv2.countNonZero(cv2.inRange(hsv, np.array([130, 40, 40]), np.array([170, 255, 255]))) > 20: return "level_4" # Morado
    if cv2.countNonZero(cv2.inRange(hsv, np.array([20, 100, 100]), np.array([35, 255, 255]))) > 20: return "level_5" # Amarillo
    
    mask_red = cv2.bitwise_or(cv2.inRange(hsv, np.array([0, 100, 100]), np.array([10, 255, 255])), cv2.inRange(hsv, np.array([170, 100, 100]), np.array([180, 255, 255])))
    if cv2.countNonZero(mask_red) > 20: return "level_6" # Rojo
    
    # Prioridad 2: Gris/Madera (Solo si la saturación es muy baja)
    if cv2.countNonZero(cv2.inRange(hsv, np.array([0, 0, 40]), np.array([180, 80, 200]))) > 20: return "level_1" 
    
    return "level_Unknown"

def run_batch():
    subprocess.run(f'"{ADB_PATH}" -s {DEVICE} shell screencap -p /sdcard/s.png', shell=True, stdout=subprocess.DEVNULL)
    subprocess.run(f'"{ADB_PATH}" -s {DEVICE} pull /sdcard/s.png adb_tmp.png', shell=True, stdout=subprocess.DEVNULL)
    img = cv2.imread("adb_tmp.png")
    if img is None: return False
    
    lote = []
    cofres_validos = 0
    
    for i in range(6):
        jug, niv = get_name(img, i), get_level(img, i)
        
        # --- TOLERANCIA CERO A LA BASURA ---
        if jug == "unknown_player" or niv == "level_Unknown":
            print(f" -> [{i+1}] Vacío/Basura ignorado")
            continue
            
        cofres_validos += 1
        if jug not in registro_jugadores:
            registro_jugadores[jug] = {k: 0 for _, k in CONFIG_NIVELES}
            
        lote.append((i, jug, niv))
        print(f" -> [{i+1}] {jug} => {niv}")
        
    # Si de los 6 espacios, ninguno fue válido, la lista se acabó.
    if cofres_validos == 0:
        print(" [!] No se detectaron cofres válidos. Deteniendo lectura.")
        return False
        
    # Acción: Solo abrimos los cofres que sabemos que existen
    for i, j, n in lote:
        x, y = [(950, 570), (920, 750), (910, 930), (900, 1110), (890, 1314), (880, 1501)][i]
        subprocess.run(f'"{ADB_PATH}" -s {DEVICE} shell input tap {x} {y}', shell=True)
        if n not in registro_jugadores[j]: registro_jugadores[j][n] = 0
        registro_jugadores[j][n] += 1
        time.sleep(1.0)
        
    guardar_csv()
    subprocess.run(f'"{ADB_PATH}" -s {DEVICE} shell input tap 230 1780', shell=True)
    return True

def generar_reporte_bonito():
    total_gral = sum(sum(d.values()) for d in registro_jugadores.values())
    totales_niv = {k: sum(d.get(k, 0) for d in registro_jugadores.values()) for _, k in CONFIG_NIVELES}
    
    print("\n" + "="*45 + "\n 📜 HUNT REPORT\n" + "="*45)
    print(f"Time (UTC): {time.strftime('%Y-%m-%d %H:%M:%S', time.gmtime())}")
    print("-" * 45 + f"\n 📊 TOTAL TODAY: {total_gral}")
    resumen = [f"{e}: {totales_niv[k]}" for e, k in CONFIG_NIVELES if totales_niv[k] > 0]
    print(f" 🎯 BREAKDOWN: {' | '.join(resumen)}\n" + "-"*45)

    for i, (jug, d) in enumerate(sorted(registro_jugadores.items(), key=lambda x: sum(x[1].values()), reverse=True)):
        if sum(d.values()) == 0: continue
        det = " | ".join([f"{e}: {d[k]}" for e, k in CONFIG_NIVELES if d.get(k, 0) > 0])
        print(f"{i+1:02d}. 👤 {jug:<15} 📦 Total: {sum(d.values())} | {det}")

    if nombres_maestros:
        inact = sorted([j for j in nombres_maestros if j not in registro_jugadores or sum(registro_jugadores[j].values()) == 0])
        if inact:
            print("\n" + "-"*45 + "\n 💤 MEMBERS DID NOT HUNT\n" + "-"*45)
            mitad = (len(inact) + 1) // 2
            for i in range(mitad):
                izq, der = inact[i], (inact[i+mitad] if i+mitad < len(inact) else "")
                print(f"  ❌ {izq:<20} | ❌ {der}")

if __name__ == "__main__":
    cargar_datos()
    for i in range(20):
        print(f"\n--- Ciclo {i+1} ---")
        if not run_batch(): break
        time.sleep(2)
    generar_reporte_bonito()