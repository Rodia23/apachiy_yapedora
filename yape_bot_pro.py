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

ADB_EXE  = os.path.join(TOOLS_DIR, "tools", "adb", "adb.exe")
TESS_EXE = os.path.join(TOOLS_DIR, "tools", "Tesseract-OCR", "tesseract.exe")
os.environ['TESSDATA_PREFIX'] = os.path.join(TOOLS_DIR, "tools", "Tesseract-OCR", "tessdata")
pytesseract.pytesseract.tesseract_cmd = TESS_EXE

# Delays configurables (segundos) — ajusta según la velocidad de tu dispositivo
DELAY_ABRIR_DETALLE = 2.5
DELAY_VOLVER_LISTA  = 1.8
DELAY_SCROLL        = 2.0

# ==========================================
# 2. CEREBRO DEL BOT
# ==========================================
class YapeBotPro:
    def __init__(self, fecha_inicio, fecha_fin, filtro_tipo):
        self.f_inicio    = fecha_inicio
        self.f_fin       = fecha_fin
        self.filtro_tipo = filtro_tipo
        self.temp_pc     = os.path.join(RUN_DIR, "temp_fotos")
        os.makedirs(self.temp_pc, exist_ok=True)
        self.vistos  = set()
        self.abortar = False

        # Regex compiladas una sola vez (mejor performance en loops largos)
        self._re_fecha   = re.compile(r"(\d+)\s+(ene|feb|mar|abr|may|jun|jul|ago|sep|oct|nov|dic)")
        self._re_hora    = re.compile(r"(\d{1,2}:\d{2}\s*[ap]\.?\s*m\.?)")
        self._re_op      = re.compile(r"operaci[oó]n.*?(\d{7,11})")
        self._re_op_alt  = re.compile(r"\b\d{8,10}\b")
        self._re_cel     = re.compile(r"(?:celular|destino).*?(\d{3})\b")
        self._re_cel_alt = re.compile(r"[\*\.\- ]+(\d{3})$", re.MULTILINE)

        res = self.adb("shell", "wm", "size")
        m   = re.search(r"(\d+)x(\d+)", res)
        self.ancho, self.alto = (int(m.group(1)), int(m.group(2))) if m else (1080, 2280)

    def adb(self, *args):
        """Ejecuta un comando ADB pasando los argumentos como lista (sin shell=True)."""
        return subprocess.run(
            [ADB_EXE] + list(args),
            capture_output=True,
            text=True
        ).stdout.strip()

    def _descargar_xml(self, nombre_remoto, ruta_local):
        """Captura el XML de UI del dispositivo y lo descarga al PC."""
        self.adb("shell", "uiautomator", "dump", f"/sdcard/{nombre_remoto}")
        self.adb("pull", f"/sdcard/{nombre_remoto}", ruta_local)

    def traducir_yape_fecha(self, txt):
        meses = {
            "ene": 1, "feb": 2, "mar": 3, "abr": 4,
            "may": 5, "jun": 6, "jul": 7, "ago": 8,
            "sep": 9, "oct": 10, "nov": 11, "dic": 12,
        }
        txt = txt.lower()
        if "hoy"  in txt: return datetime.now()
        if "ayer" in txt: return datetime.now() - timedelta(days=1)
        m = self._re_fecha.search(txt)
        if m:
            year  = datetime.now().year
            fecha = datetime(year, meses[m.group(2)], int(m.group(1)))
            # Si la fecha queda más de 30 días en el futuro, pertenece al año anterior
            # (ej: transacción de diciembre vista en enero)
            if fecha > datetime.now() + timedelta(days=30):
                fecha = fecha.replace(year=year - 1)
            return fecha
        return None

    def ejecutar(self, progreso_callback):
        progreso_callback("🚀 Iniciando búsqueda inteligente...")
        coleccion      = []
        intentos_vacios = 0
        ruta_view  = os.path.join(self.temp_pc, 'view.xml')
        ruta_check = os.path.join(self.temp_pc, 'check.xml')

        while intentos_vacios < 3:
            if self.abortar: break

            self._descargar_xml("view.xml", ruta_view)
            try:
                root = ET.parse(ruta_view).getroot()
            except (ET.ParseError, FileNotFoundError, OSError):
                break

            nodos = list(root.iter('node'))
            encontrados_en_vista = 0

            for i, node in enumerate(nodos):
                if self.abortar: break
                txt   = node.attrib.get('text', '')
                f_obj = self.traducir_yape_fecha(txt)

                if f_obj:
                    f_obj_pura  = f_obj.replace(hour=0, minute=0, second=0, microsecond=0)
                    inicio_puro = self.f_inicio.replace(hour=0,  minute=0, second=0, microsecond=0)
                    fin_puro    = self.f_fin.replace(hour=23, minute=59, second=59)

                    if inicio_puro <= f_obj_pura <= fin_puro:
                        # Guardia contra IndexError si el nodo es el primero o el último
                        if i == 0 or i >= len(nodos) - 1:
                            continue

                        nombre    = nodos[i - 1].attrib.get('text', 'Desc')
                        monto_raw = nodos[i + 1].attrib.get('text', '0')
                        es_egreso = "-" in monto_raw

                        if (self.filtro_tipo == 1 and es_egreso) or (self.filtro_tipo == 2 and not es_egreso):
                            continue

                        id_u = f"{nombre}|{txt}|{monto_raw}"
                        if id_u in self.vistos: continue

                        self.vistos.add(id_u)
                        encontrados_en_vista += 1
                        intentos_vacios = 0

                        progreso_callback(f"📍 Abriendo: {nombre}")
                        bnd    = node.attrib.get('bounds', '')
                        coords = list(map(int, re.findall(r'\d+', bnd)))
                        if len(coords) >= 4:
                            cx = str((coords[0] + coords[2]) // 2)
                            cy = str((coords[1] + coords[3]) // 2)
                            self.adb("shell", "input", "tap", cx, cy)
                        time.sleep(DELAY_ABRIR_DETALLE)

                        self._descargar_xml("check.xml", ruta_check)
                        with open(ruta_check, encoding='utf-8') as f:
                            con_compartir = "Compartir" in f.read()

                        if con_compartir:
                            n_f = f"rec_{int(time.time())}.png"
                            p_f = os.path.join(self.temp_pc, n_f)
                            self.adb("shell", "screencap", "-p", f"/sdcard/{n_f}")
                            self.adb("pull", f"/sdcard/{n_f}", p_f)
                            self.adb("shell", "rm", f"/sdcard/{n_f}")

                            resp = {
                                "n": nombre,
                                "m": monto_raw.replace('S/', '').replace('-', '').strip(),
                                "t": "EGRESO" if es_egreso else "INGRESO",
                                "f_raw": txt,
                            }
                            coleccion.append((p_f, resp))

                            progreso_callback("🔙 Volviendo a la lista...")
                            self.adb("shell", "input", "keyevent", "4")
                            time.sleep(DELAY_VOLVER_LISTA)
                        else:
                            progreso_callback("⚠️ No abrió el detalle. Saltando...")

                    elif f_obj_pura < inicio_puro:
                        intentos_vacios = 99
                        break

            if self.abortar: break
            if encontrados_en_vista == 0:
                intentos_vacios += 1
                progreso_callback(f"😴 Nada nuevo... scroll {intentos_vacios}/3")

            # Swipe adaptado a la resolución detectada del dispositivo
            cx = str(self.ancho // 2)
            sy = str(int(self.alto * 0.65))
            ey = str(int(self.alto * 0.35))
            self.adb("shell", "input", "swipe", cx, sy, cx, ey, "600")
            time.sleep(DELAY_SCROLL)

        return self.procesar_final(coleccion, progreso_callback)

    def procesar_final(self, col, callback):
        header = not os.path.exists(RUTA_CSV)
        with open(RUTA_CSV, 'a', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            if header:
                writer.writerow(['Tipo', 'Fecha', 'Hora', 'Contacto', 'Monto', 'Cel', 'Op'])
            for p, r in col:
                callback(f"🧠 Procesando {r['n']}...")

                f_obj      = self.traducir_yape_fecha(r['f_raw'])
                fecha_clean = f_obj.strftime("%d/%m/%Y") if f_obj else r['f_raw']
                h_m        = self._re_hora.search(r['f_raw'].lower())
                hora_clean  = h_m.group(1).upper().replace(".", "") if h_m else "--:--"

                img = Image.open(p).convert('L')
                img = img.resize((img.width * 2, img.height * 2), Image.Resampling.LANCZOS)
                img = ImageEnhance.Contrast(img).enhance(2.0)

                txt_ocr = pytesseract.image_to_string(img, config='--psm 6').lower()

                c_m = self._re_cel.search(txt_ocr)
                if not c_m: c_m = self._re_cel_alt.search(txt_ocr)
                cel = c_m.group(1) if c_m else "---"

                op_m = self._re_op.search(txt_ocr)
                if not op_m: op_m = self._re_op_alt.search(txt_ocr)
                op = (op_m.group(1) if op_m and op_m.lastindex else
                      op_m.group(0) if op_m else "???")

                writer.writerow([r['t'], fecha_clean, hora_clean, r['n'], r['m'], cel, op])
                os.remove(p)
        return True

# ==========================================
# 3. INTERFAZ GRÁFICA PROFESIONAL
# ==========================================
class AppNinja:
    def __init__(self, root):
        self.root = root
        self.root.title("Yape Bot Pro v15.0 | Edición Ninja")
        self.root.geometry("480x780")

        # --- PALETA DE COLORES ---
        self.COLOR_BG           = "#F8F9FA"
        self.COLOR_MORADO       = "#8B5CF6"
        self.COLOR_TEXTO        = "#1F2937"
        self.COLOR_TEXTO_SEC    = "#6B7280"
        self.COLOR_INSTRUCCIONES = "#FFFBEB"
        self.COLOR_BORDE_INS    = "#FBBF24"

        self.root.configure(bg=self.COLOR_BG)
        self.root.protocol("WM_DELETE_WINDOW", self.cerrar_aplicacion)

        # --- ESTILOS TTK ---
        self.style = ttk.Style()
        self.style.theme_use('clam')
        self.style.configure("TCombobox", padding=6, font=("Segoe UI", 10))
        self.style.configure("TEntry",    padding=6, font=("Segoe UI", 10))
        self.style.configure("Bitacora.TLabelframe",       background=self.COLOR_BG, bordercolor="#E5E7EB")
        self.style.configure("Bitacora.TLabelframe.Label", background=self.COLOR_BG, foreground=self.COLOR_MORADO, font=("Segoe UI", 9, "bold"))
        self.style.configure("Pro.TButton", padding=8, font=("Segoe UI", 10, "bold"), borderwidth=1)
        self.style.configure("Start.Pro.TButton", foreground="white", background=self.COLOR_MORADO, bordercolor="#7C3AED")
        self.style.map("Start.Pro.TButton",
            background=[('active', '#7C3AED'), ('disabled', '#E5E7EB')],
            foreground=[('disabled', '#9CA3AF')]
        )
        self.style.configure("Stop.Pro.TButton",   foreground="white", background="#EF4444", bordercolor="#DC2626")
        self.style.map("Stop.Pro.TButton",   background=[('active', '#DC2626'), ('disabled', '#FCA5A5')])
        self.style.configure("Report.Pro.TButton", foreground="white", background="#3B82F6", bordercolor="#2563EB")
        self.style.map("Report.Pro.TButton", background=[('active', '#2563EB')])

        # --- LAYOUT ---
        main_frame = tk.Frame(root, bg=self.COLOR_BG)
        main_frame.pack(fill="both", expand=True, padx=20, pady=15)

        # Instrucciones
        ins_frame = tk.Frame(main_frame, bg=self.COLOR_INSTRUCCIONES, bd=1, relief="solid",
                             highlightbackground=self.COLOR_BORDE_INS, highlightthickness=1)
        ins_frame.pack(fill="x", pady=(0, 20))
        tk.Label(ins_frame, text="⚡ PASOS CLAVE", bg=self.COLOR_INSTRUCCIONES,
                 fg="#92400E", font=("Segoe UI", 10, "bold")).pack(pady=(8, 2))
        tk.Label(ins_frame, text="1. Abre Yape  >  2. Entra a 'Movimientos'  >  3. Clic en 'Iniciar Bot'",
                 bg=self.COLOR_INSTRUCCIONES, fg="#B45309", font=("Segoe UI", 9)).pack(pady=(0, 8))

        # Estado del equipo
        self.crear_label(main_frame, "🖥️ ESTADO DEL EQUIPO")
        modelo = subprocess.run(
            [ADB_EXE, "shell", "getprop", "ro.product.model"],
            capture_output=True, text=True
        ).stdout.strip()
        self.lbl_modelo = tk.Label(
            main_frame,
            text=modelo if modelo else "ESPERANDO CONEXIÓN...",
            bg="#374151", fg="#D1D5DB",
            font=("Consolas", 10, "bold"), width=40, height=2, relief="flat"
        )
        self.lbl_modelo.pack(pady=(5, 0), fill="x")

        btn_ayuda = tk.Button(main_frame, text="¿Problemas de conexión? Ver guía de configuración",
                              command=self.mostrar_ayuda_celular, bg=self.COLOR_BG,
                              fg=self.COLOR_MORADO, font=("Segoe UI", 8, "underline"),
                              bd=0, cursor="hand2", activebackground=self.COLOR_BG)
        btn_ayuda.pack(pady=(3, 15))

        # Rango + Tipo en fila
        config_frame = tk.Frame(main_frame, bg=self.COLOR_BG)
        config_frame.pack(fill="x", pady=10)

        range_subframe = tk.Frame(config_frame, bg=self.COLOR_BG)
        range_subframe.pack(side="left", fill="x", expand=True, padx=(0, 10))
        self.crear_label(range_subframe, "📅 RANGO DE TIEMPO")
        self.rango_var = tk.StringVar(value="Últimos 3 días")
        mes_act = datetime.now().strftime("%B").capitalize()
        self.combo_rango = ttk.Combobox(
            range_subframe, textvariable=self.rango_var, state="readonly",
            values=["Día Específico", "Hoy", "Ayer", "Últimos 3 días", "Esta Semana", f"Todo {mes_act}"]
        )
        self.combo_rango.pack(pady=5, fill="x")
        self.combo_rango.bind("<<ComboboxSelected>>", self.toggle_fecha_manual)

        type_subframe = tk.Frame(config_frame, bg=self.COLOR_BG)
        type_subframe.pack(side="left", fill="x", expand=True)
        self.crear_label(type_subframe, "💰 TIPO DE FLUJO")
        self.tipo_var = tk.StringVar(value="Ingresos")
        ttk.Combobox(type_subframe, textvariable=self.tipo_var,
                     values=["Ingresos", "Egresos", "Todos"], state="readonly").pack(pady=5, fill="x")

        # Campo fecha manual (oculto por defecto)
        self.frame_fecha = tk.Frame(main_frame, bg=self.COLOR_BG)
        tk.Label(self.frame_fecha, text="Confirmar Fecha:", bg=self.COLOR_BG,
                 fg=self.COLOR_TEXTO, font=("Segoe UI", 9)).pack(side="left")
        self.fecha_manual_var = tk.StringVar(value=datetime.now().strftime("%d/%m/%Y"))
        ttk.Entry(self.frame_fecha, textvariable=self.fecha_manual_var, width=15).pack(side="left", padx=5)
        self.lbl_hint = tk.Label(main_frame, text="(Formato: DD/MM/AAAA)",
                                 bg=self.COLOR_BG, fg="gray", font=("Segoe UI", 7))

        # Bitácora
        log_frame = ttk.LabelFrame(main_frame, text=" 📜 BITÁCORA DE OPERACIONES ", style="Bitacora.TLabelframe")
        log_frame.pack(fill="both", expand=True, pady=20)
        self.log_text = tk.Text(log_frame, height=10, font=("Consolas", 8), state="disabled",
                                relief="flat", bg="white", highlightthickness=1,
                                highlightbackground="#E5E7EB", fg="#374151")
        self.log_text.pack(padx=10, pady=10, fill="both", expand=True)

        # Botonera
        button_frame = tk.Frame(main_frame, bg=self.COLOR_BG)
        button_frame.pack(fill="x", side="bottom", pady=(10, 0))
        button_frame.columnconfigure(0, weight=1)
        button_frame.columnconfigure(1, weight=1)

        self.btn_start = ttk.Button(button_frame, text="🚀 INICIAR BOT",
                                    command=self.arrancar_hilo, style="Start.Pro.TButton", cursor="hand2")
        self.btn_start.grid(row=0, column=0, padx=(0, 5), sticky="ew")

        self.btn_stop = ttk.Button(button_frame, text="🛑 DETENER",
                                   command=self.detener_bot, style="Stop.Pro.TButton", state="disabled")
        self.btn_stop.grid(row=0, column=1, padx=(5, 0), sticky="ew")

        ttk.Button(main_frame, text="📂 ABRIR REPORTE EXCEL (ESCRITORIO)",
                   command=self.abrir_csv, style="Report.Pro.TButton",
                   cursor="hand2").pack(side="bottom", fill="x", pady=(0, 10))

        self.bot_instancia = None

    # --- HELPERS ---
    def crear_label(self, contenedor, texto):
        tk.Label(contenedor, text=texto, bg=self.COLOR_BG, fg=self.COLOR_TEXTO_SEC,
                 font=("Segoe UI", 8, "bold"), anchor="w").pack(pady=(0, 0), fill="x")

    def toggle_fecha_manual(self, event=None):
        if self.rango_var.get() == "Día Específico":
            self.frame_fecha.pack(pady=5, anchor="w")
            self.lbl_hint.pack(anchor="w", padx=100)
        else:
            self.frame_fecha.pack_forget()
            self.lbl_hint.pack_forget()

    def log(self, msg):
        self.log_text.config(state="normal")
        self.log_text.insert(tk.END, f"> {msg}\n")
        self.log_text.see(tk.END)
        self.log_text.config(state="disabled")
        self.root.update_idletasks()

    def arrancar_hilo(self):
        self.log_text.config(state="normal")
        self.log_text.delete('1.0', tk.END)
        self.log_text.config(state="disabled")
        threading.Thread(target=self.proceso_bot, daemon=True).start()

    def proceso_bot(self):
        self.btn_start.config(state="disabled")
        self.btn_stop.config(state="normal")
        hoy   = datetime.now()
        r     = self.rango_var.get()
        f_fin = hoy
        try:
            if r == "Día Específico":
                f_inicio = datetime.strptime(self.fecha_manual_var.get().strip(), "%d/%m/%Y")
                f_fin    = f_inicio
            elif "Hoy"    in r: f_inicio = hoy
            elif "Ayer"   in r: f_inicio = hoy - timedelta(days=1)
            elif "3 días" in r: f_inicio = hoy - timedelta(days=3)
            elif "Semana" in r: f_inicio = hoy - timedelta(days=7)
            else:               f_inicio = hoy.replace(day=1)

            t = {"Ingresos": 1, "Egresos": 2, "Todos": 3}[self.tipo_var.get()]
            self.bot_instancia = YapeBotPro(f_inicio, f_fin, t)
            if self.bot_instancia.ejecutar(self.log):
                if not self.bot_instancia.abortar:
                    messagebox.showinfo("Éxito", "¡Misión terminada con éxito! 🎉\nEl reporte te espera en el Escritorio.")
        except ValueError as e:
            messagebox.showerror("Error de fecha", f"Formato incorrecto. Usa DD/MM/AAAA.\nDetalle: {e}")
        except Exception as e:
            messagebox.showerror("Error inesperado", str(e))
        self.btn_start.config(state="normal")
        self.btn_stop.config(state="disabled")

    def detener_bot(self):
        if self.bot_instancia:
            self.bot_instancia.abortar = True
            self.log("🛑 Solicitando parada de emergencia... cerrando sesión ADB.")

    def mostrar_ayuda_celular(self):
        instrucciones = (
            "Para que el bot funcione correctamente, necesitas activar el Modo Desarrollador en tu celular:\n\n"
            "1. Ve a Ajustes > Acerca del teléfono.\n"
            "2. Toca 7 veces sobre 'Número de compilación' (pon tu PIN si lo pide).\n"
            "3. Vuelve a Ajustes, entra a 'Opciones de desarrollador' (al final).\n"
            "4. Activa 'Depuración por USB'.\n"
            "5. Conecta el cable a la PC. Acepta el permiso en la pantalla del celular, "
            "marcando 'Permitir siempre desde esta computadora'."
        )
        messagebox.showinfo("Guía de Configuración USB", instrucciones)

    def abrir_csv(self):
        if os.path.exists(RUTA_CSV):
            os.startfile(RUTA_CSV)

    def cerrar_aplicacion(self):
        if self.bot_instancia:
            self.bot_instancia.abortar = True
        subprocess.run(['taskkill', '/F', '/IM', 'adb.exe', '/T'], capture_output=True)
        self.root.destroy()
        sys.exit()

if __name__ == "__main__":
    root = tk.Tk()
    app  = AppNinja(root)
    root.mainloop()
