import subprocess, time, os, re, csv, sys, threading
import tkinter as tk
from tkinter import ttk, messagebox
from datetime import datetime, timedelta
from PIL import Image, ImageEnhance
import pytesseract
import xml.etree.ElementTree as ET

# ==========================================
# 1. CONFIGURACIÓN DE RUTAS (Magia _MEIPASS)
# ==========================================
if getattr(sys, 'frozen', False):
    RUN_DIR = os.path.dirname(sys.executable)
else:
    RUN_DIR = os.path.dirname(os.path.abspath(__file__))

if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
    TOOLS_DIR = sys._MEIPASS
else:
    TOOLS_DIR = os.path.dirname(os.path.abspath(__file__))

ESCRITORIO_DIR = os.path.join(os.path.expanduser("~"), "Desktop")
RUTA_CSV = os.path.join(ESCRITORIO_DIR, "Reporte_Yape_Ninja.csv")

ADB_EXE = os.path.join(TOOLS_DIR, "tools", "adb", "adb.exe")
TESS_EXE = os.path.join(TOOLS_DIR, "tools", "Tesseract-OCR", "tesseract.exe")
os.environ['TESSDATA_PREFIX'] = os.path.join(TOOLS_DIR, "tools", "Tesseract-OCR", "tessdata")
pytesseract.pytesseract.tesseract_cmd = TESS_EXE

# ==========================================
# 2. CEREBRO DEL BOT
# ==========================================
class YapeBotPro:
    def __init__(self, fecha_inicio, fecha_fin, filtro_tipo):
        self.f_inicio = fecha_inicio 
        self.f_fin = fecha_fin       
        self.filtro_tipo = filtro_tipo 
        self.temp_pc = os.path.join(RUN_DIR, "temp_fotos")
        os.makedirs(self.temp_pc, exist_ok=True)
        self.vistos = set()
        self.abortar = False
        
        res = self.adb("shell wm size")
        m = re.search(r"(\d+)x(\d+)", res)
        self.ancho, self.alto = (int(m.group(1)), int(m.group(2))) if m else (1080, 2280)

    def adb(self, comando):
        return subprocess.run(f'"{ADB_EXE}" {comando}', shell=True, capture_output=True, text=True).stdout.strip()

    def traducir_yape_fecha(self, txt):
        meses = {"ene":1,"feb":2,"mar":3,"abr":4,"may":5,"jun":6,"jul":7,"ago":8,"sep":9,"oct":10,"nov":11,"dic":12}
        txt = txt.lower()
        if "hoy" in txt: return datetime.now()
        if "ayer" in txt: return datetime.now() - timedelta(days=1)
        m = re.search(r"(\d+)\s+(ene|feb|mar|abr|may|jun|jul|ago|sep|oct|nov|dic)", txt)
        if m: return datetime(datetime.now().year, meses[m.group(2)], int(m.group(1)))
        return None

    def ejecutar(self, progreso_callback):
        progreso_callback("🚀 Iniciando búsqueda inteligente...")
        coleccion = []
        intentos_vacios = 0
        ruta_view = os.path.join(self.temp_pc, 'view.xml')
        ruta_check = os.path.join(self.temp_pc, 'check.xml')
        
        while intentos_vacios < 3:
            if self.abortar: break

            self.adb("shell uiautomator dump /sdcard/view.xml")
            self.adb(f"pull /sdcard/view.xml \"{ruta_view}\"")
            try: root = ET.parse(ruta_view).getroot()
            except: break

            nodos = list(root.iter('node'))
            encontrados_en_vista = 0

            for i, node in enumerate(nodos):
                if self.abortar: break
                txt = node.attrib.get('text', '')
                f_obj = self.traducir_yape_fecha(txt)
                
                if f_obj:
                    f_obj_pura = f_obj.replace(hour=0, minute=0, second=0, microsecond=0)
                    inicio_puro = self.f_inicio.replace(hour=0, minute=0, second=0, microsecond=0)
                    fin_puro = self.f_fin.replace(hour=23, minute=59, second=59)

                    if inicio_puro <= f_obj_pura <= fin_puro:
                        nombre = nodos[i-1].attrib.get('text', 'Desc')
                        monto_raw = nodos[i+1].attrib.get('text', '0')
                        es_egreso = "-" in monto_raw
                        
                        if (self.filtro_tipo == 1 and es_egreso) or (self.filtro_tipo == 2 and not es_egreso):
                            continue

                        id_u = f"{nombre}|{txt}|{monto_raw}"
                        if id_u in self.vistos: continue
                        
                        self.vistos.add(id_u)
                        encontrados_en_vista += 1
                        intentos_vacios = 0
                        
                        progreso_callback(f"📍 Abriendo: {nombre}")
                        bnd = node.attrib.get('bounds', '')
                        coords = list(map(int, re.findall(r'\d+', bnd)))
                        self.adb(f"shell input tap {(coords[0]+coords[2])//2} {(coords[1]+coords[3])//2}")
                        time.sleep(2.5)
                        
                        self.adb("shell uiautomator dump /sdcard/check.xml")
                        self.adb(f"pull /sdcard/check.xml \"{ruta_check}\"")
                        con_compartir = "Compartir" in open(ruta_check, encoding='utf-8').read()
                        
                        if con_compartir:
                            n_f = f"rec_{int(time.time())}.png"
                            p_f = os.path.join(self.temp_pc, n_f)
                            self.adb(f"shell screencap -p /sdcard/{n_f}")
                            self.adb(f"pull /sdcard/{n_f} \"{p_f}\"")
                            self.adb(f"shell rm /sdcard/{n_f}")
                            
                            resp = {"n": nombre, "m": monto_raw.replace('S/', '').replace('-','').strip(), 
                                    "t": "EGRESO" if es_egreso else "INGRESO", "f_raw": txt}
                            coleccion.append((p_f, resp))
                            
                            progreso_callback("🔙 Volviendo a la lista...")
                            self.adb("shell input keyevent 4")
                            time.sleep(1.8)
                        else:
                            progreso_callback("⚠️ No abrió el detalle. Saltando...")

                    elif f_obj_pura < inicio_puro:
                        intentos_vacios = 99
                        break

            if self.abortar: break
            if encontrados_en_vista == 0: 
                intentos_vacios += 1
                progreso_callback(f"😴 Nada nuevo... scroll {intentos_vacios}/3")
            
            self.adb(f"shell input swipe 500 1500 500 800 600")
            time.sleep(2)
        
        return self.procesar_final(coleccion, progreso_callback)

    def procesar_final(self, col, callback):
        header = not os.path.exists(RUTA_CSV)
        with open(RUTA_CSV, 'a', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            if header: writer.writerow(['Tipo','Fecha','Hora','Contacto','Monto','Cel','Op'])
            for p, r in col:
                callback(f"🧠 Procesando {r['n']}...")
                
                f_obj = self.traducir_yape_fecha(r['f_raw'])
                fecha_clean = f_obj.strftime("%d/%m/%Y") if f_obj else r['f_raw']
                h_m = re.search(r"(\d{1,2}:\d{2}\s*[ap]\.?\s*m\.?)", r['f_raw'].lower())
                hora_clean = h_m.group(1).upper().replace(".", "") if h_m else "--:--"

                img = Image.open(p).convert('L')
                img = img.resize((img.width * 2, img.height * 2), Image.Resampling.LANCZOS)
                img = ImageEnhance.Contrast(img).enhance(2.0)
                
                txt_ocr = pytesseract.image_to_string(img, config='--psm 6').lower()
                
                c_m = re.search(r"(?:celular|destino).*?(\d{3})\b", txt_ocr)
                if not c_m: c_m = re.search(r"[\*\.\- ]+(\d{3})$", txt_ocr, re.MULTILINE)
                cel = c_m.group(1) if c_m else "---"
                
                op_m = re.search(r"operaci[oó]n.*?(\d{7,11})", txt_ocr)
                if not op_m: op_m = re.search(r"\b\d{8,10}\b", txt_ocr)
                op = op_m.group(1) if op_m and len(op_m.groups())>0 else op_m.group(0) if op_m else "???"
                
                writer.writerow([r['t'], fecha_clean, hora_clean, r['n'], r['m'], cel, op])
                os.remove(p)
        return True

# ==========================================
# 3. INTERFAZ GRÁFICA LAVANDA
# ==========================================
class AppNinja:
    def __init__(self, root):
        self.root = root
        self.root.title("Yape Bot Pro v15.0 (Portable)")
        self.root.geometry("450x720")
        self.root.configure(bg="#E6E6FA")
        
        # --- LIMPIEZA FINAL (Al cerrar con la X) ---
        self.root.protocol("WM_DELETE_WINDOW", self.cerrar_aplicacion)

        self.style = ttk.Style()
        self.style.theme_use('clam')
        self.style.configure("TCombobox", padding=5)
        self.style.configure("TButton", padding=5, font=("Arial", 10, "bold"))
        self.style.configure("TEntry", padding=5)

        tk.Label(root, text="⚠️ INSTRUCCIONES", bg="#FFD700", fg="black", font=("Arial", 10, "bold")).pack(pady=(10,0), fill="x")
        tk.Label(root, text="1. Abre Yape.  2. Ve a 'Movimientos'.  3. ¡Dale a Iniciar!", bg="#FFFACD", fg="black", font=("Arial", 9)).pack(pady=(0,10), fill="x")

        self.crear_label("📱 EQUIPO:")
        modelo = subprocess.run(f'"{ADB_EXE}" shell getprop ro.product.model', shell=True, capture_output=True, text=True).stdout.strip()
        self.lbl_modelo = tk.Label(root, text=modelo if modelo else "SIN CONEXIÓN", bg="white", width=40, relief="sunken")
        self.lbl_modelo.pack(pady=5)

        btn_ayuda = tk.Button(root, text="⚙️ ¿Cómo preparar el celular para conectar?", command=self.mostrar_ayuda_celular, bg="#E6E6FA", fg="#1E90FF", font=("Arial", 8, "underline"), bd=0, cursor="hand2")
        btn_ayuda.pack(pady=(0, 5))

        self.crear_label("📅 RANGO:")
        self.rango_var = tk.StringVar(value="Últimos 3 días")
        mes_act = datetime.now().strftime("%B")
        self.combo_rango = ttk.Combobox(root, textvariable=self.rango_var, values=["Día Específico", "Hoy", "Ayer", "Últimos 3 días", "Esta Semana", f"Todo {mes_act}"], state="readonly", width=38)
        self.combo_rango.pack(pady=5)
        self.combo_rango.bind("<<ComboboxSelected>>", self.toggle_fecha_manual)

        self.frame_fecha = tk.Frame(root, bg="#E6E6FA")
        tk.Label(self.frame_fecha, text="Fecha:", bg="#E6E6FA").pack(side="left")
        self.fecha_manual_var = tk.StringVar(value=datetime.now().strftime("%d/%m/%Y"))
        ttk.Entry(self.frame_fecha, textvariable=self.fecha_manual_var, width=15).pack(side="left", padx=5)
        self.lbl_hint = tk.Label(root, text="(Ejemplo: 25/03/2026)", bg="#E6E6FA", fg="gray", font=("Arial", 7))

        self.crear_label("💰 TIPO:")
        self.tipo_var = tk.StringVar(value="Ingresos")
        ttk.Combobox(root, textvariable=self.tipo_var, values=["Ingresos", "Egresos", "Todos"], state="readonly", width=38).pack(pady=5)

        self.crear_label("📜 BITÁCORA:")
        self.log_text = tk.Text(root, height=10, width=52, font=("Consolas", 8), state="disabled", relief="flat")
        self.log_text.pack(padx=20, pady=5)

        self.btn_start = tk.Button(root, text="🚀 INICIAR BOT", command=self.arrancar_hilo, bg="#4CAF50", fg="white", font=("Arial", 11, "bold"), width=25, bd=0, cursor="hand2")
        self.btn_start.pack(pady=10)

        self.btn_stop = tk.Button(root, text="🛑 DETENER", command=self.detener_bot, bg="#F44336", fg="white", font=("Arial", 10, "bold"), width=25, bd=0, state="disabled")
        self.btn_stop.pack()

        tk.Button(root, text="📂 ABRIR REPORTE (ESCRITORIO)", command=self.abrir_csv, bg="#2196F3", fg="white", width=30, bd=0).pack(pady=10)
        self.bot_instancia = None

    def mostrar_ayuda_celular(self):
        instrucciones = (
            "Para que el bot pueda mandar clics desde CUALQUIER PC sin errores de permisos, "
            "debes tener esto activo en tu celular (solo se hace una vez):\n\n"
            "1. Ve a Ajustes > Acerca del teléfono > Información de software.\n"
            "2. Toca 7 veces rápidas sobre 'Número de compilación' (te pedirá tu PIN).\n"
            "3. Regresa a los Ajustes principales, baja del todo y entra a 'Opciones de desarrollador'.\n"
            "4. Activa 'Depuración por USB'.\n"
            "5. Conecta el cable a la PC. En tu pantalla saldrá un cartel de '¿Permitir depuración USB?', "
            "marca la casilla 'Permitir siempre desde esta computadora' y dale a Aceptar."
        )
        messagebox.showinfo("⚙️ Preparar Celular (Modo Desarrollador)", instrucciones)

    def crear_label(self, texto):
        tk.Label(self.root, text=texto, bg="#E6E6FA", fg="#4B0082", font=("Arial", 9, "bold")).pack(pady=(10, 0))

    def toggle_fecha_manual(self, event=None):
        if self.rango_var.get() == "Día Específico":
            self.frame_fecha.pack(pady=5)
            self.lbl_hint.pack()
        else:
            self.frame_fecha.pack_forget()
            self.lbl_hint.pack_forget()

    def log(self, msg):
        self.log_text.config(state="normal")
        self.log_text.insert(tk.END, f"{msg}\n")
        self.log_text.see(tk.END)
        self.log_text.config(state="disabled")
        self.root.update_idletasks()

    def arrancar_hilo(self):
        threading.Thread(target=self.proceso_bot, daemon=True).start()

    def proceso_bot(self):
        self.btn_start.config(state="disabled")
        self.btn_stop.config(state="normal")
        hoy = datetime.now()
        r = self.rango_var.get()
        f_fin = hoy
        try:
            if r == "Día Específico":
                f_inicio = datetime.strptime(self.fecha_manual_var.get(), "%d/%m/%Y")
                f_fin = f_inicio
            elif "Hoy" in r: f_inicio = hoy
            elif "Ayer" in r: f_inicio = hoy - timedelta(days=1)
            elif "3 días" in r: f_inicio = hoy - timedelta(days=3)
            elif "Semana" in r: f_inicio = hoy - timedelta(days=7)
            else: f_inicio = hoy.replace(day=1)

            t = {"Ingresos": 1, "Egresos": 2, "Todos": 3}[self.tipo_var.get()]
            self.bot_instancia = YapeBotPro(f_inicio, f_fin, t)
            if self.bot_instancia.ejecutar(self.log):
                if not self.bot_instancia.abortar:
                    messagebox.showinfo("Éxito", "Misión terminada u.u\nGuardado en tu Escritorio.")
        except Exception as e:
            messagebox.showerror("Error", f"Verifica datos: {e}")
        self.btn_start.config(state="normal")
        self.btn_stop.config(state="disabled")

    def detener_bot(self):
        if self.bot_instancia:
            self.bot_instancia.abortar = True
            self.log("🛑 Deteniendo... cerrando sesión.")

    def abrir_csv(self):
        if os.path.exists(RUTA_CSV): os.startfile(RUTA_CSV)

    def cerrar_aplicacion(self):
        # Detenemos el bot de forma segura si estaba corriendo
        if self.bot_instancia:
            self.bot_instancia.abortar = True
        
        # Asesinamos al fantasma de ADB sin piedad
        subprocess.run('taskkill /F /IM adb.exe /T', shell=True, capture_output=True)
        
        # Cerramos la ventana y matamos el proceso de Python
        self.root.destroy()
        sys.exit()

if __name__ == "__main__":
    root = tk.Tk()
    app = AppNinja(root)
    root.mainloop()