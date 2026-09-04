# -*- coding: utf-8 -*-
"""
Editor de Etiquetas (.eti)
===========================
Aplicación de escritorio, multiplataforma (Windows / macOS / Linux),
escrita en Python + Tkinter, para abrir, editar, guardar e imprimir
etiquetas en formato .eti (XML).

Ejecutar:
    python etiqueta_editor.py [archivo.eti]

Dependencias (ver requirements.txt):
    Pillow
    python-barcode
"""

import os
import sys
import copy
import tempfile
import subprocess
import platform

import tkinter as tk
from tkinter import ttk, filedialog, messagebox, simpledialog, colorchooser

from PIL import Image, ImageTk, ImageFont

from eti_format import Diseno, Literal, CodigoBarras, Imagen, Forma, RATIO_MM_A_PX
import render


APP_TITLE = "Editor de Etiquetas"
FUENTES_DISPONIBLES = ["Arial", "Helvetica", "Times New Roman", "Courier New",
                        "Verdana", "Tahoma", "Consolas", "DejaVu Sans"]

# --- Paleta de colores (estilo moderno / plano) ---------------------------
COLOR_FONDO_APP = "#eef0f3"
COLOR_TOOLBAR = "#ffffff"
COLOR_TOOLBAR_BORDE = "#e0e2e7"
COLOR_CANVAS_FONDO = "#c9ccd3"     # mesa de trabajo (gris)
COLOR_HOJA = "#ffffff"             # la etiqueta en sí (blanco)
COLOR_HOJA_SOMBRA = "#aeb1b8"
COLOR_HOJA_BORDE = "#c3c6cc"
COLOR_GUIA_OK = "#2f6fed"          # tamaño configurado, coincide con contenido
COLOR_GUIA_WARN = "#e0762d"        # el contenido se sale del tamaño configurado
COLOR_ACENTO = "#2f6fed"
COLOR_SELECCION = "#2f6fed"
COLOR_CAMPO_VARIABLE_TEXTO = "#2f6fed"
COLOR_CAMPO_VARIABLE_FONDO = "#eaf1ff"
COLOR_PANEL_FONDO = "#ffffff"
COLOR_DANGER = "#d64545"
COLOR_DANGER_HOVER = "#bb3a3a"


# ---------------------------------------------------------------------------
# Diálogo: configurar etiqueta (ancho / alto / continuo)
# ---------------------------------------------------------------------------

class DialogoConfigEtiqueta(simpledialog.Dialog):
    def __init__(self, parent, diseno):
        self.diseno = diseno
        super().__init__(parent, title="Configurar etiqueta")

    def body(self, master):
        tk.Label(master, text="Ancho (mm):").grid(row=0, column=0, sticky="e", padx=4, pady=4)
        tk.Label(master, text="Alto (mm):").grid(row=1, column=0, sticky="e", padx=4, pady=4)

        self.var_ancho = tk.IntVar(value=self.diseno.ancho)
        self.var_alto = tk.IntVar(value=self.diseno.alto)
        self.var_continuo = tk.BooleanVar(value=self.diseno.continuo)

        tk.Entry(master, textvariable=self.var_ancho, width=10).grid(row=0, column=1, padx=4, pady=4)
        tk.Entry(master, textvariable=self.var_alto, width=10).grid(row=1, column=1, padx=4, pady=4)
        tk.Checkbutton(master, text="Etiqueta continua", variable=self.var_continuo).grid(
            row=2, column=0, columnspan=2, sticky="w", padx=4, pady=4)
        tk.Label(master, text="Este es el tamaño físico real de la etiqueta.\n"
                              "Todo lo que quede fuera de esta área no se\n"
                              "verá ni se imprimirá.",
                 fg="gray40", justify="left", font=("Segoe UI", 8)).grid(
            row=3, column=0, columnspan=2, sticky="w", padx=4, pady=(6, 0))
        return None

    def apply(self):
        self.diseno.ancho = max(1, self.var_ancho.get())
        self.diseno.alto = max(1, self.var_alto.get())
        self.diseno.continuo = self.var_continuo.get()
        self.result = True


# ---------------------------------------------------------------------------
# Aplicación principal
# ---------------------------------------------------------------------------

class EtiquetaEditorApp(tk.Tk):

    HANDLE = 7  # tamaño del tirador de redimensionado (px pantalla)

    def __init__(self, archivo_inicial=None):
        super().__init__()
        self.title(APP_TITLE)
        self.geometry("1220x780")
        self.minsize(940, 580)
        self.configure(bg=COLOR_FONDO_APP)

        self._configurar_estilos()
        self._configurar_opciones_por_defecto()

        self.diseno = Diseno.nuevo()
        self.dirty = False
        self.zoom = 1.0
        self.margen_base = 40
        self._mx = self.margen_base
        self._my = self.margen_base
        self.vista_mock = False    # vista previa con datos de ejemplo en el canvas

        self.seleccionado = None
        self._tag_a_obj = {}
        self._img_cache = {}       # id(obj) -> (hash, PhotoImage)
        self._drag_info = None
        self._preview_photo = None

        self._construir_menu()
        self._construir_toolbar()
        self._construir_cuerpo()
        self._construir_statusbar()

        self.protocol("WM_DELETE_WINDOW", self.cerrar_app)
        self.bind_all("<Delete>", lambda e: self.eliminar_seleccionado())
        self.bind_all("<Control-o>", lambda e: self.abrir_archivo())
        self.bind_all("<Control-s>", lambda e: self.guardar_archivo())
        self.bind_all("<Control-p>", lambda e: self.imprimir())
        self.bind_all("<Control-n>", lambda e: self.nuevo_archivo())

        if archivo_inicial and os.path.isfile(archivo_inicial):
            self._cargar_diseno_desde(archivo_inicial)
        else:
            self._refrescar_todo()

    # ------------------------------------------------------------------
    # Estilos ttk (look moderno y consistente entre plataformas)
    # ------------------------------------------------------------------

    def _configurar_estilos(self):
        style = ttk.Style(self)
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass

        style.configure("TFrame", background=COLOR_FONDO_APP)
        style.configure("Toolbar.TFrame", background=COLOR_TOOLBAR)
        style.configure("Panel.TFrame", background=COLOR_PANEL_FONDO)

        style.configure("Tool.TButton", background=COLOR_TOOLBAR, foreground="#2b2d33",
                         borderwidth=0, focusthickness=0, padding=(10, 7),
                         font=("Segoe UI", 9))
        style.map("Tool.TButton",
                  background=[("active", "#eef2fb"), ("pressed", "#e2e8fa")],
                  foreground=[("disabled", "#a9acb3")])

        style.configure("ToolAccent.TButton", background=COLOR_ACENTO, foreground="white",
                         borderwidth=0, padding=(12, 7), font=("Segoe UI", 9, "bold"))
        style.map("ToolAccent.TButton",
                  background=[("active", "#255bc4"), ("pressed", "#1f4ea3")])

        style.configure("ToolDanger.TButton", background=COLOR_TOOLBAR, foreground=COLOR_DANGER,
                         borderwidth=0, padding=(10, 7), font=("Segoe UI", 9))
        style.map("ToolDanger.TButton",
                  background=[("active", "#fdecec")])

        style.configure("ToolToggle.TButton", background=COLOR_TOOLBAR, foreground="#2b2d33",
                         borderwidth=0, padding=(10, 7), font=("Segoe UI", 9))
        style.map("ToolToggle.TButton",
                  background=[("active", "#eef2fb")])

        style.configure("Danger.TButton", background=COLOR_DANGER, foreground="white",
                         borderwidth=0, padding=(8, 8), font=("Segoe UI", 9, "bold"))
        style.map("Danger.TButton", background=[("active", COLOR_DANGER_HOVER)])

        style.configure("Group.TLabel", background=COLOR_TOOLBAR, foreground="#9a9da5",
                         font=("Segoe UI", 7, "bold"))
        style.configure("Status.TLabel", background="#f4f5f7", foreground="#4a4d55",
                         font=("Segoe UI", 9), padding=(8, 4))
        style.configure("PanelTitle.TLabel", background=COLOR_PANEL_FONDO,
                         foreground="#1c1d21", font=("Segoe UI", 12, "bold"))
        style.configure("PanelSection.TLabel", background=COLOR_PANEL_FONDO,
                         foreground="#3a3c42", font=("Segoe UI", 10, "bold"))
        style.configure("PanelField.TLabel", background=COLOR_PANEL_FONDO,
                         foreground="#55575e", font=("Segoe UI", 9))
        style.configure("TSeparator", background=COLOR_TOOLBAR_BORDE)

    def _configurar_opciones_por_defecto(self):
        """Aplica una apariencia moderna y consistente a los widgets tk 'clásicos'
        (panel de propiedades y diálogos), sin tener que tocar cada uno."""
        self.option_add("*Font", "{Segoe UI} 9")
        self.option_add("*Label.background", COLOR_PANEL_FONDO)
        self.option_add("*Label.foreground", "#33353b")
        self.option_add("*Entry.background", "white")
        self.option_add("*Entry.relief", "solid")
        self.option_add("*Entry.highlightThickness", 1)
        self.option_add("*Entry.highlightColor", COLOR_ACENTO)
        self.option_add("*Entry.highlightBackground", COLOR_TOOLBAR_BORDE)
        self.option_add("*Spinbox.background", "white")
        self.option_add("*Spinbox.relief", "solid")
        self.option_add("*Spinbox.highlightThickness", 1)
        self.option_add("*Spinbox.highlightBackground", COLOR_TOOLBAR_BORDE)
        self.option_add("*Checkbutton.background", COLOR_PANEL_FONDO)
        self.option_add("*Checkbutton.activebackground", COLOR_PANEL_FONDO)
        self.option_add("*Button.background", "#f0f2f5")
        self.option_add("*Button.activeBackground", "#e2e6ea")
        self.option_add("*Button.relief", "flat")
        self.option_add("*Button.borderWidth", 1)

    # ------------------------------------------------------------------
    # Construcción de la interfaz
    # ------------------------------------------------------------------

    def _construir_menu(self):
        barra = tk.Menu(self)

        m_archivo = tk.Menu(barra, tearoff=0)
        m_archivo.add_command(label="Nuevo", accelerator="Ctrl+N", command=self.nuevo_archivo)
        m_archivo.add_command(label="Abrir...", accelerator="Ctrl+O", command=self.abrir_archivo)
        m_archivo.add_command(label="Guardar", accelerator="Ctrl+S", command=self.guardar_archivo)
        m_archivo.add_command(label="Guardar como...", command=self.guardar_como)
        m_archivo.add_separator()
        m_archivo.add_command(label="Exportar a PNG...", command=self.exportar_png)
        m_archivo.add_command(label="Exportar a PDF...", command=self.exportar_pdf)
        m_archivo.add_separator()
        m_archivo.add_command(label="Imprimir...", accelerator="Ctrl+P", command=self.imprimir)
        m_archivo.add_separator()
        m_archivo.add_command(label="Cerrar etiqueta", command=self.cerrar_etiqueta)
        m_archivo.add_command(label="Salir", command=self.cerrar_app)
        barra.add_cascade(label="Archivo", menu=m_archivo)

        m_etiqueta = tk.Menu(barra, tearoff=0)
        m_etiqueta.add_command(label="Configurar etiqueta...", command=self.configurar_etiqueta)
        barra.add_cascade(label="Etiqueta", menu=m_etiqueta)

        m_insertar = tk.Menu(barra, tearoff=0)
        m_insertar.add_command(label="Texto", command=self.insertar_texto)
        m_insertar.add_command(label="Código de barras", command=self.insertar_codigo_barras)
        m_insertar.add_command(label="Imagen...", command=self.insertar_imagen)
        m_insertar.add_separator()
        m_insertar.add_command(label="Línea", command=lambda: self.insertar_forma("linea"))
        m_insertar.add_command(label="Rectángulo", command=lambda: self.insertar_forma("rectangulo"))
        m_insertar.add_command(label="Círculo", command=lambda: self.insertar_forma("circulo"))
        barra.add_cascade(label="Insertar", menu=m_insertar)

        m_ver = tk.Menu(barra, tearoff=0)
        m_ver.add_command(label="Acercar (+)", command=lambda: self.cambiar_zoom(1.25))
        m_ver.add_command(label="Alejar (-)", command=lambda: self.cambiar_zoom(0.8))
        m_ver.add_command(label="Ajustar a la ventana", command=self.ajustar_zoom_ventana)
        m_ver.add_command(label="Restablecer zoom (100%)", command=lambda: self.cambiar_zoom(None))
        m_ver.add_separator()
        m_ver.add_command(label="Vista con datos de ejemplo (activar/desactivar)",
                           command=self.alternar_vista_mock)
        barra.add_cascade(label="Ver", menu=m_ver)

        m_ayuda = tk.Menu(barra, tearoff=0)
        m_ayuda.add_command(label="Acerca de", command=self.acerca_de)
        barra.add_cascade(label="Ayuda", menu=m_ayuda)

        self.config(menu=barra)

    def _construir_toolbar(self):
        contenedor = tk.Frame(self, bg=COLOR_TOOLBAR)
        contenedor.pack(side="top", fill="x")
        tb = ttk.Frame(contenedor, style="Toolbar.TFrame", padding=(10, 6))
        tb.pack(side="top", fill="x")
        tk.Frame(contenedor, height=1, bg=COLOR_TOOLBAR_BORDE).pack(side="top", fill="x")

        def grupo(titulo):
            g = ttk.Frame(tb, style="Toolbar.TFrame")
            g.pack(side="left", padx=(0, 4))
            fila_botones = ttk.Frame(g, style="Toolbar.TFrame")
            fila_botones.pack(side="top")
            ttk.Label(g, text=titulo, style="Group.TLabel").pack(side="top", anchor="w", pady=(2, 0))
            return fila_botones

        def separador():
            ttk.Separator(tb, orient="vertical").pack(side="left", fill="y", padx=8, pady=2)

        def boton(parent, texto, cmd, estilo="Tool.TButton"):
            b = ttk.Button(parent, text=texto, command=cmd, style=estilo)
            b.pack(side="left", padx=2)
            return b

        g_archivo = grupo("ARCHIVO")
        boton(g_archivo, "🆕  Nuevo", self.nuevo_archivo)
        boton(g_archivo, "📂  Abrir", self.abrir_archivo)
        boton(g_archivo, "💾  Guardar", self.guardar_archivo)
        boton(g_archivo, "✕  Cerrar", self.cerrar_etiqueta)
        separador()

        g_etiqueta = grupo("ETIQUETA")
        boton(g_etiqueta, "⚙  Configurar", self.configurar_etiqueta)
        boton(g_etiqueta, "🖨  Vista previa / Imprimir", self.imprimir, "ToolAccent.TButton")
        separador()

        g_insertar = grupo("INSERTAR")
        boton(g_insertar, "🔤 Texto", self.insertar_texto)
        boton(g_insertar, "▥ Barras", self.insertar_codigo_barras)
        boton(g_insertar, "🖼 Imagen", self.insertar_imagen)
        boton(g_insertar, "╱ Línea", lambda: self.insertar_forma("linea"))
        boton(g_insertar, "▭ Rectángulo", lambda: self.insertar_forma("rectangulo"))
        boton(g_insertar, "○ Círculo", lambda: self.insertar_forma("circulo"))
        separador()

        g_vista = grupo("VISTA")
        boton(g_vista, "－", lambda: self.cambiar_zoom(0.8))
        self.lbl_zoom = ttk.Label(g_vista, text="100%", style="Group.TLabel",
                                   background=COLOR_TOOLBAR, foreground="#3a3c42",
                                   font=("Segoe UI", 9), width=5, anchor="center")
        self.lbl_zoom.pack(side="left", padx=2)
        boton(g_vista, "＋", lambda: self.cambiar_zoom(1.25))
        boton(g_vista, "⛶ Ajustar", self.ajustar_zoom_ventana)
        self.btn_mock = boton(g_vista, "👁 Datos ejemplo", self.alternar_vista_mock, "ToolToggle.TButton")
        separador()

        g_del = grupo("")
        boton(g_del, "🗑  Eliminar", self.eliminar_seleccionado, "ToolDanger.TButton")

    def _construir_cuerpo(self):
        cuerpo = tk.Frame(self, bg=COLOR_FONDO_APP)
        cuerpo.pack(side="top", fill="both", expand=True)

        # --- "Mesa de trabajo": canvas exterior gris, con scrollbars ---
        frame_canvas = tk.Frame(cuerpo, bg=COLOR_FONDO_APP)
        frame_canvas.pack(side="left", fill="both", expand=True, padx=(6, 3), pady=6)

        self.canvas = tk.Canvas(frame_canvas, bg=COLOR_CANVAS_FONDO, highlightthickness=0)
        hbar = ttk.Scrollbar(frame_canvas, orient="horizontal", command=self.canvas.xview)
        vbar = ttk.Scrollbar(frame_canvas, orient="vertical", command=self.canvas.yview)
        self.canvas.configure(xscrollcommand=hbar.set, yscrollcommand=vbar.set)

        self.canvas.grid(row=0, column=0, sticky="nsew")
        vbar.grid(row=0, column=1, sticky="ns")
        hbar.grid(row=1, column=0, sticky="ew")
        frame_canvas.rowconfigure(0, weight=1)
        frame_canvas.columnconfigure(0, weight=1)
        self.canvas.bind("<Configure>", self._on_canvas_resize)

        # --- "Hoja": canvas interior de TAMAÑO FIJO (ancho/alto mm x RATIO x zoom).
        # Al ser un widget hijo con tamaño propio, Tkinter recorta automáticamente
        # cualquier cosa que se dibuje fuera de sus límites: es la garantía de que
        # nada de lo que sobresalga se vea, ni en el editor ni en la vista previa.
        self.hoja_canvas = tk.Canvas(self.canvas, bg=COLOR_HOJA, highlightthickness=1,
                                      highlightbackground=COLOR_HOJA_BORDE)
        self._sombra_id = None
        self._hoja_window_id = self.canvas.create_window(0, 0, window=self.hoja_canvas,
                                                           anchor="nw")

        self.hoja_canvas.bind("<ButtonPress-1>", self._on_canvas_press)
        self.hoja_canvas.bind("<B1-Motion>", self._on_canvas_drag)
        self.hoja_canvas.bind("<ButtonRelease-1>", self._on_canvas_release)

        # --- Panel de propiedades ---
        panel_contenedor = tk.Frame(cuerpo, bg=COLOR_FONDO_APP)
        panel_contenedor.pack(side="right", fill="y", padx=(3, 6), pady=6)

        self.panel = tk.Frame(panel_contenedor, width=290, bg=COLOR_PANEL_FONDO,
                               highlightbackground=COLOR_TOOLBAR_BORDE, highlightthickness=1)
        self.panel.pack(fill="both", expand=True)
        self.panel.pack_propagate(False)

        ttk.Label(self.panel, text="Propiedades", style="PanelTitle.TLabel").pack(
            anchor="w", padx=14, pady=(14, 6))
        tk.Frame(self.panel, height=1, bg=COLOR_TOOLBAR_BORDE).pack(fill="x", padx=14)
        self.panel_contenido = tk.Frame(self.panel, bg=COLOR_PANEL_FONDO)
        self.panel_contenido.pack(fill="both", expand=True, padx=14, pady=10)
        self._mostrar_propiedades(None)

    def _construir_statusbar(self):
        self.status = ttk.Label(self, text="Listo", anchor="w", style="Status.TLabel")
        self.status.pack(side="bottom", fill="x")

    def _on_canvas_resize(self, event):
        # Recoloca la hoja centrada al cambiar el tamaño de la ventana
        self._redibujar_canvas()

    # ------------------------------------------------------------------
    # Utilidades generales
    # ------------------------------------------------------------------

    def _set_status(self, msg):
        self.status.config(text=msg)

    def _marcar_dirty(self, valor=True):
        self.dirty = valor
        nombre = os.path.basename(self.diseno.filepath) if self.diseno.filepath else "Sin título"
        marca = "*" if valor else ""
        self.title(f"{APP_TITLE} - {nombre}{marca}")

    def _confirmar_descarte_si_hace_falta(self):
        if not self.dirty:
            return True
        resp = messagebox.askyesnocancel(
            "Cambios sin guardar",
            "Hay cambios sin guardar en la etiqueta actual.\n¿Quieres guardarlos?")
        if resp is None:
            return False
        if resp:
            return self.guardar_archivo()
        return True

    def cambiar_zoom(self, factor):
        if factor is None:
            self.zoom = 1.0
        else:
            self.zoom = max(0.1, min(6.0, self.zoom * factor))
        self._refrescar_todo()

    def ajustar_zoom_ventana(self):
        """Calcula el zoom para que la hoja completa quepa en la ventana visible."""
        self.canvas.update_idletasks()
        vp_w = max(50, self.canvas.winfo_width())
        vp_h = max(50, self.canvas.winfo_height())
        ancho_hoja, alto_hoja = self._tamano_hoja()  # mm
        margen = self.margen_base
        zoom_w = (vp_w - 2 * margen) / max(1, ancho_hoja * RATIO_MM_A_PX)
        zoom_h = (vp_h - 2 * margen) / max(1, alto_hoja * RATIO_MM_A_PX)
        self.zoom = max(0.1, min(6.0, min(zoom_w, zoom_h)))
        self._refrescar_todo()

    def alternar_vista_mock(self):
        self.vista_mock = not self.vista_mock
        self._redibujar_canvas()
        self._set_status("Vista con datos de ejemplo: " + ("activada" if self.vista_mock else "desactivada"))

    def acerca_de(self):
        messagebox.showinfo(
            APP_TITLE,
            f"{APP_TITLE}\nEdición de etiquetas .eti (XML)\nPython + Tkinter + Pillow")

    # ------------------------------------------------------------------
    # Archivo: nuevo / abrir / guardar / cerrar / imprimir / exportar
    # ------------------------------------------------------------------

    def nuevo_archivo(self):
        if not self._confirmar_descarte_si_hace_falta():
            return
        self.diseno = Diseno.nuevo()
        self.seleccionado = None
        self.zoom = 1.0
        self._marcar_dirty(False)
        self._refrescar_todo()
        self._set_status("Etiqueta nueva creada.")

    def abrir_archivo(self):
        if not self._confirmar_descarte_si_hace_falta():
            return
        ruta = filedialog.askopenfilename(
            title="Abrir etiqueta",
            filetypes=[("Etiquetas (*.eti)", "*.eti"), ("Todos los archivos", "*.*")])
        if ruta:
            self._cargar_diseno_desde(ruta)

    def _cargar_diseno_desde(self, ruta):
        try:
            self.diseno = Diseno.from_file(ruta)
        except Exception as exc:
            messagebox.showerror("Error al abrir", f"No se pudo abrir el archivo:\n{exc}")
            return
        self.seleccionado = None
        self.zoom = 1.0
        self._marcar_dirty(False)
        self._refrescar_todo()
        self._set_status(f"Abierto: {ruta}")

    def guardar_archivo(self):
        if not self.diseno.filepath:
            return self.guardar_como()
        try:
            self.diseno.to_file()
        except Exception as exc:
            messagebox.showerror("Error al guardar", f"No se pudo guardar el archivo:\n{exc}")
            return False
        self._marcar_dirty(False)
        self._set_status(f"Guardado: {self.diseno.filepath}")
        return True

    def guardar_como(self):
        ruta = filedialog.asksaveasfilename(
            title="Guardar etiqueta como",
            defaultextension=".eti",
            filetypes=[("Etiquetas (*.eti)", "*.eti"), ("Todos los archivos", "*.*")])
        if not ruta:
            return False
        try:
            self.diseno.to_file(ruta)
        except Exception as exc:
            messagebox.showerror("Error al guardar", f"No se pudo guardar el archivo:\n{exc}")
            return False
        self._marcar_dirty(False)
        self._set_status(f"Guardado: {ruta}")
        return True

    def cerrar_etiqueta(self):
        if not self._confirmar_descarte_si_hace_falta():
            return
        self.diseno = Diseno.nuevo()
        self.seleccionado = None
        self.zoom = 1.0
        self._marcar_dirty(False)
        self._refrescar_todo()
        self._set_status("Etiqueta cerrada.")

    def cerrar_app(self):
        if not self._confirmar_descarte_si_hace_falta():
            return
        self.destroy()

    def configurar_etiqueta(self):
        dlg = DialogoConfigEtiqueta(self, self.diseno)
        if getattr(dlg, "result", None):
            self._marcar_dirty(True)
            self._refrescar_todo()

    def exportar_png(self):
        ruta = filedialog.asksaveasfilename(defaultextension=".png",
                                             filetypes=[("Imagen PNG", "*.png")])
        if not ruta:
            return
        try:
            render.exportar_png(self.diseno, ruta, escala=3.0, usar_datos_mock=True)
            messagebox.showinfo("Exportar", f"Imagen exportada a:\n{ruta}")
        except Exception as exc:
            messagebox.showerror("Error al exportar", str(exc))

    def exportar_pdf(self):
        ruta = filedialog.asksaveasfilename(defaultextension=".pdf",
                                             filetypes=[("Documento PDF", "*.pdf")])
        if not ruta:
            return
        try:
            render.exportar_pdf(self.diseno, ruta, escala=3.0, usar_datos_mock=True)
            messagebox.showinfo("Exportar", f"PDF exportado a:\n{ruta}")
        except Exception as exc:
            messagebox.showerror("Error al exportar", str(exc))

    def imprimir(self):
        """Abre una vista previa fiel al resultado final (con datos de ejemplo
        en los campos variables) desde la que se puede imprimir o exportar."""
        try:
            img = render.render_diseno(self.diseno, escala=3.0, usar_datos_mock=True)
        except Exception as exc:
            messagebox.showerror("Error al generar la vista previa", str(exc))
            return
        self._abrir_dialogo_vista_previa(img)

    def _abrir_dialogo_vista_previa(self, img_full):
        top = tk.Toplevel(self)
        top.title("Vista previa de impresión")
        top.configure(bg=COLOR_FONDO_APP)
        top.geometry("640x740")
        top.transient(self)
        top.grab_set()

        aviso = ("Los campos con datos variables (p. ej. A000FECALT) se muestran con "
                 "datos de ejemplo (XXXX) para hacerse una idea del resultado final; "
                 "en el sistema real se sustituyen por el valor correspondiente.")
        ttk.Label(top, text=aviso, wraplength=600, justify="left",
                  style="PanelField.TLabel", background=COLOR_FONDO_APP).pack(
            anchor="w", padx=14, pady=(12, 6))

        marco_img = tk.Frame(top, bg="#dddfe3", bd=1, relief="sunken")
        marco_img.pack(fill="both", expand=True, padx=14, pady=6)

        # Escalar la imagen para que quepa en el diálogo sin deformarse
        max_w, max_h = 590, 520
        factor = min(max_w / img_full.width, max_h / img_full.height, 1.0)
        prev_w, prev_h = max(1, int(img_full.width * factor)), max(1, int(img_full.height * factor))
        img_preview = img_full.resize((prev_w, prev_h))
        self._preview_photo = ImageTk.PhotoImage(img_preview)

        lbl_img = tk.Label(marco_img, image=self._preview_photo, bg="white")
        lbl_img.pack(expand=True)

        botones = tk.Frame(top, bg=COLOR_FONDO_APP)
        botones.pack(fill="x", padx=14, pady=(6, 14))

        def hacer_imprimir():
            self._enviar_a_impresora(img_full)

        def hacer_exportar_png():
            ruta = filedialog.asksaveasfilename(defaultextension=".png",
                                                 filetypes=[("Imagen PNG", "*.png")],
                                                 parent=top)
            if ruta:
                img_full.save(ruta, "PNG")
                messagebox.showinfo("Exportar", f"Imagen exportada a:\n{ruta}", parent=top)

        def hacer_exportar_pdf():
            ruta = filedialog.asksaveasfilename(defaultextension=".pdf",
                                                 filetypes=[("Documento PDF", "*.pdf")],
                                                 parent=top)
            if ruta:
                img_full.convert("RGB").save(ruta, "PDF")
                messagebox.showinfo("Exportar", f"PDF exportado a:\n{ruta}", parent=top)

        ttk.Button(botones, text="🖨 Imprimir", style="ToolAccent.TButton",
                   command=hacer_imprimir).pack(side="left")
        ttk.Button(botones, text="Exportar PNG", style="Tool.TButton",
                   command=hacer_exportar_png).pack(side="left", padx=6)
        ttk.Button(botones, text="Exportar PDF", style="Tool.TButton",
                   command=hacer_exportar_pdf).pack(side="left")
        ttk.Button(botones, text="Cerrar", style="Tool.TButton",
                   command=top.destroy).pack(side="right")

    def _enviar_a_impresora(self, img):
        tmp = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
        tmp_path = tmp.name
        tmp.close()
        img.save(tmp_path, "PNG")

        sistema = platform.system()
        try:
            if sistema == "Windows":
                os.startfile(tmp_path, "print")
            else:
                subprocess.run(["lp", tmp_path], check=True)
            self._set_status("Enviado a la impresora predeterminada.")
        except Exception as exc:
            resp = messagebox.askyesno(
                "No se pudo imprimir automáticamente",
                "No se ha podido enviar directamente a la impresora del sistema "
                f"({exc}).\n\nSe ha generado una imagen en:\n{tmp_path}\n\n"
                "¿Quieres abrirla ahora para imprimirla manualmente?")
            if resp:
                self._abrir_con_visor(tmp_path)

    def _abrir_con_visor(self, ruta):
        sistema = platform.system()
        try:
            if sistema == "Windows":
                os.startfile(ruta)
            elif sistema == "Darwin":
                subprocess.run(["open", ruta])
            else:
                subprocess.run(["xdg-open", ruta])
        except Exception as exc:
            messagebox.showwarning("Aviso", f"No se pudo abrir el visor:\n{exc}")

    # ------------------------------------------------------------------
    # Inserción de objetos
    # ------------------------------------------------------------------

    def _punto_insercion(self):
        # Coloca los nuevos objetos escalonados para que no se apilen exactos
        base = 10 + 15 * (len(self.diseno.todos_los_objetos()) % 8)
        return base, base

    def insertar_texto(self):
        x, y = self._punto_insercion()
        lit = self.diseno.nuevo_literal(texto="Nuevo texto", x=x, y=y, w=140, h=30, tamano_letra=16)
        self._marcar_dirty(True)
        self._refrescar_todo()
        self.seleccionar_objeto(lit)

    def insertar_codigo_barras(self):
        x, y = self._punto_insercion()
        cb = self.diseno.nuevo_codigo_barras(codigo="123456789012", x=x, y=y, w=180, h=60)
        self._marcar_dirty(True)
        self._refrescar_todo()
        self.seleccionar_objeto(cb)

    def insertar_imagen(self):
        ruta = filedialog.askopenfilename(
            title="Seleccionar imagen",
            filetypes=[("Imágenes", "*.png *.jpg *.jpeg *.bmp *.gif"), ("Todos los archivos", "*.*")])
        if not ruta:
            return
        try:
            with Image.open(ruta) as im:
                w, h = im.size
        except Exception:
            w, h = 100, 100
        # Limitar tamaño inicial para que no ocupe toda la etiqueta
        max_lado = 200
        if max(w, h) > max_lado:
            factor = max_lado / max(w, h)
            w, h = int(w * factor), int(h * factor)
        x, y = self._punto_insercion()
        img_obj = self.diseno.nueva_imagen(ruta=ruta, x=x, y=y, w=w, h=h)
        self._marcar_dirty(True)
        self._refrescar_todo()
        self.seleccionar_objeto(img_obj)

    def insertar_forma(self, tipo):
        x, y = self._punto_insercion()
        if tipo == "linea":
            fm = self.diseno.nueva_forma(tipo="linea", x=x, y=y, w=120, h=0, grosor=2)
        elif tipo == "circulo":
            fm = self.diseno.nueva_forma(tipo="circulo", x=x, y=y, w=80, h=80, grosor=2)
        else:
            fm = self.diseno.nueva_forma(tipo="rectangulo", x=x, y=y, w=120, h=80, grosor=2)
        self._marcar_dirty(True)
        self._refrescar_todo()
        self.seleccionar_objeto(fm)

    def eliminar_seleccionado(self):
        if self.seleccionado is None:
            return
        if self.diseno.eliminar(self.seleccionado):
            self.seleccionado = None
            self._marcar_dirty(True)
            self._refrescar_todo()

    # ------------------------------------------------------------------
    # Dibujo del canvas
    # ------------------------------------------------------------------

    def _refrescar_todo(self):
        self._redibujar_canvas()
        self._mostrar_propiedades(self.seleccionado)

    def _u2p(self, valor):
        """Coordenadas de los ELEMENTOS (x/y/w/h, ya en píxeles dentro del
        .eti) -> píxeles de pantalla. Solo se aplica el zoom manual, SIN
        ningún factor de conversión: los elementos no se multiplican."""
        return valor * self.zoom

    def _mm2p(self, valor_mm):
        """SOLO para el tamaño de la HOJA: el <formato ancho= alto=> del
        .eti está en mm y el programa original lo convertía a píxeles con
        un factor fijo (RATIO_MM_A_PX = 3.4) para dimensionar el panel de
        la etiqueta. Este factor NO se aplica a los elementos."""
        return valor_mm * RATIO_MM_A_PX * self.zoom

    def _obj_a_canvas_xy(self, x, y):
        """Coordenadas del objeto (px) -> coordenadas dentro de self.hoja_canvas.
        El origen de la hoja ES el origen de este canvas: no hace falta offset."""
        return self._u2p(x), self._u2p(y)

    def _tamano_hoja(self):
        """Tamaño de la hoja en mm: SIEMPRE el configurado en
        Etiqueta > Configurar (<formato ancho= alto=>). Fijo, no depende
        del contenido."""
        return max(1, self.diseno.ancho), max(1, self.diseno.alto)

    def _redibujar_canvas(self):
        self.hoja_canvas.delete("all")
        self.canvas.delete("sombra")
        self._tag_a_obj = {}
        self.update_idletasks()

        ancho_hoja, alto_hoja = self._tamano_hoja()
        sheet_w = max(1, int(round(self._mm2p(ancho_hoja))))
        sheet_h = max(1, int(round(self._mm2p(alto_hoja))))

        # Tamaño FIJO del canvas interior: al ser un widget con tamaño propio,
        # Tkinter recorta automáticamente cualquier dibujo que se salga de
        # estos límites (ni el editor ni la impresión pueden mostrar nada
        # fuera de la hoja).
        self.hoja_canvas.configure(width=sheet_w, height=sheet_h)

        vp_w = max(self.canvas.winfo_width(), sheet_w + 2 * self.margen_base)
        vp_h = max(self.canvas.winfo_height(), sheet_h + 2 * self.margen_base)

        # La hoja se centra en el área visible de la mesa de trabajo.
        mx = max(self.margen_base, (vp_w - sheet_w) / 2)
        my = max(self.margen_base, (vp_h - sheet_h) / 2)

        total_w = max(vp_w, sheet_w + 2 * mx)
        total_h = max(vp_h, sheet_h + 2 * my)
        self.canvas.configure(scrollregion=(0, 0, total_w, total_h))

        # Sombra de "papel" en la mesa, y reposicionar/redimensionar la hoja
        self.canvas.create_rectangle(mx + 4, my + 4, mx + sheet_w + 4, my + sheet_h + 4,
                                      fill=COLOR_HOJA_SOMBRA, outline="", tags=("sombra",))
        self.canvas.tag_lower("sombra")
        self.canvas.coords(self._hoja_window_id, mx, my)
        self.canvas.itemconfig(self._hoja_window_id, width=sheet_w, height=sheet_h)

        # Formas
        for fm in self.diseno.formas:
            self._dibujar_forma(fm)
        # Imágenes
        for im in self.diseno.imagenes:
            self._dibujar_imagen(im)
        # Códigos de barras
        for cb in self.diseno.barras:
            self._dibujar_codigo_barras(cb)
        # Textos (arriba del todo)
        for lit in self.diseno.literales:
            self._dibujar_literal(lit)

        if self.seleccionado is not None:
            self._dibujar_seleccion(self.seleccionado)

        if hasattr(self, "lbl_zoom"):
            self.lbl_zoom.configure(text=f"{int(round(self.zoom * 100))}%")

    def _tag_para(self, obj):
        return f"{obj.KIND}_{id(obj)}"

    def _dibujar_forma(self, fm):
        x0, y0 = self._obj_a_canvas_xy(fm.x, fm.y)
        x1, y1 = self._obj_a_canvas_xy(fm.x + fm.w, fm.y + fm.h)
        tag = self._tag_para(fm)
        relleno = fm.color if fm.relleno else ""
        if fm.tipo == "linea":
            item = self.hoja_canvas.create_line(x0, y0, x1, y1, fill=fm.color,
                                                 width=max(1, fm.grosor), tags=(tag, "objeto"))
        elif fm.tipo == "circulo":
            item = self.hoja_canvas.create_oval(x0, y0, x1, y1, outline=fm.color,
                                                 fill=relleno, width=max(1, fm.grosor),
                                                 tags=(tag, "objeto"))
        else:
            item = self.hoja_canvas.create_rectangle(x0, y0, x1, y1, outline=fm.color,
                                                      fill=relleno, width=max(1, fm.grosor),
                                                      tags=(tag, "objeto"))
        self._tag_a_obj[tag] = fm

    def _obtener_photoimage_imagen(self, im):
        clave = id(im)
        firma = (im.ruta, im.w, im.h, im.rotacion, self.zoom)
        cache = self._img_cache.get(clave)
        if cache and cache[0] == firma:
            return cache[1]
        try:
            pic = Image.open(im.ruta).convert("RGBA")
            w = max(1, int(self._u2p(im.w)))
            h = max(1, int(self._u2p(im.h)))
            pic = pic.resize((w, h))
            if im.rotacion:
                pic = pic.rotate(-im.rotacion, expand=True)
            foto = ImageTk.PhotoImage(pic)
        except Exception:
            foto = None
        self._img_cache[clave] = (firma, foto)
        return foto

    def _dibujar_imagen(self, im):
        tag = self._tag_para(im)
        x, y = self._obj_a_canvas_xy(im.x, im.y)
        foto = self._obtener_photoimage_imagen(im)
        if foto is not None:
            item = self.hoja_canvas.create_image(x, y, image=foto, anchor="nw", tags=(tag, "objeto"))
        else:
            x1, y1 = self._obj_a_canvas_xy(im.x + im.w, im.y + im.h)
            self.hoja_canvas.create_rectangle(x, y, x1, y1, outline="red", dash=(2, 2),
                                               tags=(tag, "objeto"))
            self.hoja_canvas.create_text((x + x1) / 2, (y + y1) / 2, text="imagen\nno encontrada",
                                          fill="red", tags=(tag, "objeto"))
        self._tag_a_obj[tag] = im

    def _obtener_photoimage_barras(self, cb, codigo_override=None):
        clave = (id(cb), "mock" if codigo_override else "real")
        firma = (codigo_override or cb.codigo, cb.codificacion, cb.magnificacion,
                 cb.human_valor, cb.w, cb.h, self.zoom)
        cache = self._img_cache.get(clave)
        if cache and cache[0] == firma:
            return cache[1]
        bimg = render.generar_imagen_codigo_barras(cb, codigo_override=codigo_override)
        if bimg is not None:
            w = max(1, int(self._u2p(cb.w)))
            h = max(1, int(self._u2p(cb.h)))
            bimg = bimg.convert("RGB").resize((w, h))
            foto = ImageTk.PhotoImage(bimg)
        else:
            foto = None
        self._img_cache[clave] = (firma, foto)
        return foto

    def _dibujar_codigo_barras(self, cb):
        tag = self._tag_para(cb)
        x, y = self._obj_a_canvas_xy(cb.x, cb.y)
        x1, y1 = self._obj_a_canvas_xy(cb.x + cb.w, cb.y + cb.h)
        es_variable = render.es_campo_variable(cb.codigo)

        if es_variable and self.vista_mock:
            codigo_mostrado = render.valor_mock_barras(cb)
            foto = self._obtener_photoimage_barras(cb, codigo_override=codigo_mostrado)
        else:
            foto = self._obtener_photoimage_barras(cb)

        if es_variable:
            self.hoja_canvas.create_rectangle(x, y, x1, y1, fill=COLOR_CAMPO_VARIABLE_FONDO,
                                               outline="", tags=(tag, "objeto"))
        if foto is not None:
            self.hoja_canvas.create_image(x, y, image=foto, anchor="nw", tags=(tag, "objeto"))
        else:
            self.hoja_canvas.create_rectangle(x, y, x1, y1, outline="black", width=2,
                                               tags=(tag, "objeto"))
            self.hoja_canvas.create_text((x + x1) / 2, (y + y1) / 2,
                                          text=f"|| {cb.codigo} ||", tags=(tag, "objeto"))
        if es_variable:
            self.hoja_canvas.create_text(x + 3, y1 - 2, anchor="sw", text="campo variable",
                                          fill=COLOR_CAMPO_VARIABLE_TEXTO,
                                          font=("Segoe UI", 7, "italic"), tags=(tag, "objeto"))
        self._tag_a_obj[tag] = cb

    def _dibujar_literal(self, lit):
        tag = self._tag_para(lit)
        x, y = self._obj_a_canvas_xy(lit.x, lit.y)
        tam = max(6, int(lit.tamano_letra * self.zoom))
        estilo = []
        if lit.negrita:
            estilo.append("bold")
        if lit.cursiva:
            estilo.append("italic")
        fuente = (lit.fuente, tam, " ".join(estilo)) if estilo else (lit.fuente, tam)

        es_variable = render.es_campo_variable(lit.texto)
        texto_mostrado = lit.texto
        if es_variable and self.vista_mock:
            texto_mostrado = render.valor_mock_texto(lit.texto)

        if es_variable:
            x1, y1 = self._obj_a_canvas_xy(lit.x + lit.w, lit.y + lit.h)
            self.hoja_canvas.create_rectangle(x, y, x1, y1, fill=COLOR_CAMPO_VARIABLE_FONDO,
                                               outline="", tags=(tag, "objeto"))

        color_texto = COLOR_CAMPO_VARIABLE_TEXTO if es_variable else "black"
        kwargs = dict(anchor="nw", font=fuente, fill=color_texto, text=texto_mostrado,
                      tags=(tag, "objeto"), width=max(10, int(self._u2p(lit.w))))
        try:
            self.hoja_canvas.create_text(x, y, angle=lit.rotacion, **kwargs)
        except tk.TclError:
            # Tk sin soporte de "angle" (muy improbable en 8.6+)
            self.hoja_canvas.create_text(x, y, **kwargs)
        self._tag_a_obj[tag] = lit

    def _dibujar_seleccion(self, obj):
        x0, y0 = self._obj_a_canvas_xy(obj.x, obj.y)
        x1, y1 = self._obj_a_canvas_xy(obj.x + obj.w, obj.y + max(obj.h, 1))
        self.hoja_canvas.create_rectangle(x0 - 3, y0 - 3, x1 + 3, y1 + 3, outline=COLOR_SELECCION,
                                           dash=(3, 2), width=2, tags=("seleccion",))
        h = self.HANDLE
        self.hoja_canvas.create_rectangle(x1 - h / 2, y1 - h / 2, x1 + h / 2, y1 + h / 2,
                                           fill=COLOR_SELECCION, outline="white", width=1,
                                           tags=("seleccion", "handle"))

    # ------------------------------------------------------------------
    # Interacción con el ratón: seleccionar / mover / redimensionar
    # ------------------------------------------------------------------

    def _obj_bajo_puntero(self, cx, cy):
        items = self.hoja_canvas.find_overlapping(cx - 1, cy - 1, cx + 1, cy + 1)
        for item in reversed(items):  # el último dibujado está "encima"
            for etiqueta in self.hoja_canvas.gettags(item):
                if etiqueta in self._tag_a_obj:
                    return self._tag_a_obj[etiqueta], etiqueta
        return None, None

    def _es_handle(self, cx, cy):
        items = self.hoja_canvas.find_overlapping(cx - 1, cy - 1, cx + 1, cy + 1)
        for item in items:
            if "handle" in self.hoja_canvas.gettags(item):
                return True
        return False

    def _on_canvas_press(self, event):
        cx, cy = event.x, event.y

        if self.seleccionado is not None and self._es_handle(cx, cy):
            self._drag_info = {"modo": "resize", "x0": cx, "y0": cy,
                                "w0": self.seleccionado.w, "h0": self.seleccionado.h}
            return

        obj, _ = self._obj_bajo_puntero(cx, cy)
        self.seleccionar_objeto(obj)
        if obj is not None:
            self._drag_info = {"modo": "mover", "x0": cx, "y0": cy,
                                "ox0": obj.x, "oy0": obj.y}
        else:
            self._drag_info = None

    def _on_canvas_drag(self, event):
        if not self._drag_info or self.seleccionado is None:
            return
        cx, cy = event.x, event.y
        info = self._drag_info
        dx = (cx - info["x0"]) / self.zoom
        dy = (cy - info["y0"]) / self.zoom

        if info["modo"] == "mover":
            self.seleccionado.x = max(0, int(info["ox0"] + dx))
            self.seleccionado.y = max(0, int(info["oy0"] + dy))
        elif info["modo"] == "resize":
            nuevo_w = max(1, int(info["w0"] + dx))
            nuevo_h = max(1, int(info["h0"] + dy))
            self.seleccionado.w = nuevo_w
            if not (isinstance(self.seleccionado, Forma) and self.seleccionado.tipo == "linea"):
                self.seleccionado.h = nuevo_h

        self._redibujar_canvas()
        self._actualizar_campos_posicion()

    def _on_canvas_release(self, event):
        if self._drag_info:
            self._marcar_dirty(True)
        self._drag_info = None

    def seleccionar_objeto(self, obj):
        self.seleccionado = obj
        self._redibujar_canvas()
        self._mostrar_propiedades(obj)

    # ------------------------------------------------------------------
    # Panel de propiedades (dinámico según tipo de objeto)
    # ------------------------------------------------------------------

    def _limpiar_panel(self):
        for w in self.panel_contenido.winfo_children():
            w.destroy()

    def _fila(self, parent, etiqueta, fila):
        tk.Label(parent, text=etiqueta).grid(row=fila, column=0, sticky="w", pady=3)

    def _actualizar_campos_posicion(self):
        """Refresca sólo los campos de x/y/w/h tras arrastrar, sin reconstruir todo el panel."""
        if self.seleccionado is None:
            return
        if hasattr(self, "_var_x"):
            self._var_x.set(self.seleccionado.x)
            self._var_y.set(self.seleccionado.y)
            self._var_w.set(self.seleccionado.w)
            self._var_h.set(getattr(self.seleccionado, "h", 0))

    def _mostrar_propiedades(self, obj):
        self._limpiar_panel()
        if obj is None:
            tk.Label(self.panel_contenido, text="Ningún objeto seleccionado.\n\n"
                     "Haz clic sobre un elemento del\ncanvas o inserta uno nuevo.",
                     justify="left", fg="gray30").pack(anchor="w", pady=10)
            return

        p = self.panel_contenido
        fila = 0

        tipo_legible = {
            "literal": "Texto", "codigo_barras": "Código de barras",
            "imagen": "Imagen", "forma": f"Forma ({getattr(obj, 'tipo', '')})",
        }[obj.KIND]
        tk.Label(p, text=tipo_legible, font=("Arial", 10, "bold")).grid(
            row=fila, column=0, columnspan=2, sticky="w", pady=(0, 8))
        fila += 1

        # --- Campos comunes: posición y tamaño ---
        self._var_x = tk.IntVar(value=obj.x)
        self._var_y = tk.IntVar(value=obj.y)
        self._var_w = tk.IntVar(value=obj.w)
        self._var_h = tk.IntVar(value=getattr(obj, "h", 0))

        def aplicar_geometria(*_):
            obj.x = self._var_x.get()
            obj.y = self._var_y.get()
            obj.w = max(1, self._var_w.get())
            if hasattr(obj, "h"):
                obj.h = max(0, self._var_h.get())
            self._marcar_dirty(True)
            self._redibujar_canvas()

        for etiqueta, var in (("X:", self._var_x), ("Y:", self._var_y),
                              ("Ancho:", self._var_w), ("Alto:", self._var_h)):
            self._fila(p, etiqueta, fila)
            sp = tk.Spinbox(p, from_=-9999, to=9999, textvariable=var, width=10,
                             command=aplicar_geometria)
            sp.grid(row=fila, column=1, sticky="w", pady=3)
            sp.bind("<Return>", aplicar_geometria)
            sp.bind("<FocusOut>", aplicar_geometria)
            fila += 1

        self._var_rot = tk.IntVar(value=obj.rotacion)

        def aplicar_rotacion(*_):
            obj.rotacion = self._var_rot.get() % 360
            self._marcar_dirty(True)
            self._redibujar_canvas()

        self._fila(p, "Rotación:", fila)
        sp = tk.Spinbox(p, from_=0, to=359, textvariable=self._var_rot, width=10,
                         command=aplicar_rotacion)
        sp.grid(row=fila, column=1, sticky="w", pady=3)
        sp.bind("<Return>", aplicar_rotacion)
        sp.bind("<FocusOut>", aplicar_rotacion)
        fila += 1

        ttk.Separator(p, orient="horizontal").grid(row=fila, column=0, columnspan=2,
                                                     sticky="ew", pady=8)
        fila += 1

        # --- Campos específicos según el tipo ---
        if isinstance(obj, Literal):
            fila = self._panel_literal(p, obj, fila)
        elif isinstance(obj, CodigoBarras):
            fila = self._panel_barras(p, obj, fila)
        elif isinstance(obj, Imagen):
            fila = self._panel_imagen(p, obj, fila)
        elif isinstance(obj, Forma):
            fila = self._panel_forma(p, obj, fila)

        ttk.Separator(p, orient="horizontal").grid(row=fila, column=0, columnspan=2,
                                                     sticky="ew", pady=8)
        fila += 1
        tk.Button(p, text="Eliminar objeto", fg="white", bg="#c0392b",
                  command=self.eliminar_seleccionado).grid(
            row=fila, column=0, columnspan=2, sticky="ew", pady=4)

    def _panel_literal(self, p, lit, fila):
        self._fila(p, "Texto:", fila)
        var_txt = tk.StringVar(value=lit.texto)

        def aplicar_texto(*_):
            lit.texto = var_txt.get()
            self._marcar_dirty(True)
            self._redibujar_canvas()

        e = tk.Entry(p, textvariable=var_txt, width=20)
        e.grid(row=fila, column=1, sticky="w", pady=3)
        e.bind("<KeyRelease>", aplicar_texto)
        fila += 1

        self._fila(p, "Fuente:", fila)
        var_fuente = tk.StringVar(value=lit.fuente)

        def aplicar_fuente(*_):
            lit.fuente = var_fuente.get()
            self._marcar_dirty(True)
            self._redibujar_canvas()

        combo = ttk.Combobox(p, textvariable=var_fuente, values=FUENTES_DISPONIBLES, width=17)
        combo.grid(row=fila, column=1, sticky="w", pady=3)
        combo.bind("<<ComboboxSelected>>", aplicar_fuente)
        combo.bind("<Return>", aplicar_fuente)
        combo.bind("<FocusOut>", aplicar_fuente)
        fila += 1

        self._fila(p, "Tamaño letra:", fila)
        var_tam = tk.IntVar(value=lit.tamano_letra)

        def aplicar_tam(*_):
            lit.tamano_letra = max(4, var_tam.get())
            self._marcar_dirty(True)
            self._redibujar_canvas()

        sp = tk.Spinbox(p, from_=4, to=200, textvariable=var_tam, width=10, command=aplicar_tam)
        sp.grid(row=fila, column=1, sticky="w", pady=3)
        sp.bind("<Return>", aplicar_tam)
        sp.bind("<FocusOut>", aplicar_tam)
        fila += 1

        var_negrita = tk.BooleanVar(value=lit.negrita)
        var_cursiva = tk.BooleanVar(value=lit.cursiva)

        def aplicar_estilo(*_):
            lit.negrita = var_negrita.get()
            lit.cursiva = var_cursiva.get()
            self._marcar_dirty(True)
            self._redibujar_canvas()

        tk.Checkbutton(p, text="Negrita", variable=var_negrita, command=aplicar_estilo).grid(
            row=fila, column=0, sticky="w")
        tk.Checkbutton(p, text="Cursiva", variable=var_cursiva, command=aplicar_estilo).grid(
            row=fila, column=1, sticky="w")
        fila += 1
        return fila

    def _panel_barras(self, p, cb, fila):
        self._fila(p, "Código:", fila)
        var_cod = tk.StringVar(value=cb.codigo)

        def aplicar_codigo(*_):
            cb.codigo = var_cod.get()
            self._marcar_dirty(True)
            self._redibujar_canvas()

        e = tk.Entry(p, textvariable=var_cod, width=20)
        e.grid(row=fila, column=1, sticky="w", pady=3)
        e.bind("<KeyRelease>", aplicar_codigo)
        fila += 1

        self._fila(p, "Codificación:", fila)
        var_enc = tk.StringVar(value=cb.codificacion)

        def aplicar_enc(*_):
            cb.codificacion = var_enc.get()
            self._marcar_dirty(True)
            self._redibujar_canvas()

        combo = ttk.Combobox(p, textvariable=var_enc, values=CodigoBarras.CODIFICACIONES,
                              width=17, state="readonly")
        combo.grid(row=fila, column=1, sticky="w", pady=3)
        combo.bind("<<ComboboxSelected>>", aplicar_enc)
        fila += 1

        self._fila(p, "Magnificación:", fila)
        var_mag = tk.IntVar(value=cb.magnificacion)

        def aplicar_mag(*_):
            cb.magnificacion = max(1, var_mag.get())
            self._marcar_dirty(True)
            self._redibujar_canvas()

        sp = tk.Spinbox(p, from_=1, to=10, textvariable=var_mag, width=10, command=aplicar_mag)
        sp.grid(row=fila, column=1, sticky="w", pady=3)
        sp.bind("<Return>", aplicar_mag)
        sp.bind("<FocusOut>", aplicar_mag)
        fila += 1

        var_hv = tk.BooleanVar(value=cb.human_valor)

        def aplicar_hv():
            cb.human_valor = var_hv.get()
            self._marcar_dirty(True)
            self._redibujar_canvas()

        tk.Checkbutton(p, text="Mostrar valor legible", variable=var_hv,
                       command=aplicar_hv).grid(row=fila, column=0, columnspan=2, sticky="w")
        fila += 1
        return fila

    def _panel_imagen(self, p, im, fila):
        self._fila(p, "Archivo:", fila)
        nombre = os.path.basename(im.ruta) if im.ruta else "(ninguno)"
        tk.Label(p, text=nombre, wraplength=150, justify="left").grid(
            row=fila, column=1, sticky="w", pady=3)
        fila += 1

        def cambiar_imagen():
            ruta = filedialog.askopenfilename(
                title="Seleccionar imagen",
                filetypes=[("Imágenes", "*.png *.jpg *.jpeg *.bmp *.gif")])
            if ruta:
                im.ruta = ruta
                self._marcar_dirty(True)
                self._mostrar_propiedades(im)
                self._redibujar_canvas()

        tk.Button(p, text="Cambiar imagen...", command=cambiar_imagen).grid(
            row=fila, column=0, columnspan=2, sticky="ew", pady=4)
        fila += 1
        return fila

    def _panel_forma(self, p, fm, fila):
        self._fila(p, "Tipo:", fila)
        tk.Label(p, text=fm.tipo).grid(row=fila, column=1, sticky="w", pady=3)
        fila += 1

        self._fila(p, "Grosor:", fila)
        var_gr = tk.IntVar(value=fm.grosor)

        def aplicar_grosor(*_):
            fm.grosor = max(1, var_gr.get())
            self._marcar_dirty(True)
            self._redibujar_canvas()

        sp = tk.Spinbox(p, from_=1, to=40, textvariable=var_gr, width=10, command=aplicar_grosor)
        sp.grid(row=fila, column=1, sticky="w", pady=3)
        sp.bind("<Return>", aplicar_grosor)
        sp.bind("<FocusOut>", aplicar_grosor)
        fila += 1

        self._fila(p, "Color:", fila)

        def elegir_color():
            color = colorchooser.askcolor(color=fm.color, title="Color de la forma")
            if color and color[1]:
                fm.color = color[1]
                self._marcar_dirty(True)
                self._mostrar_propiedades(fm)
                self._redibujar_canvas()

        btn_color = tk.Button(p, text="  ", bg=fm.color, width=6, command=elegir_color)
        btn_color.grid(row=fila, column=1, sticky="w", pady=3)
        fila += 1

        if fm.tipo != "linea":
            var_rel = tk.BooleanVar(value=fm.relleno)

            def aplicar_relleno():
                fm.relleno = var_rel.get()
                self._marcar_dirty(True)
                self._redibujar_canvas()

            tk.Checkbutton(p, text="Rellenar", variable=var_rel, command=aplicar_relleno).grid(
                row=fila, column=0, columnspan=2, sticky="w")
            fila += 1
        return fila


def main():
    archivo_inicial = sys.argv[1] if len(sys.argv) > 1 else None
    app = EtiquetaEditorApp(archivo_inicial)
    app.mainloop()


if __name__ == "__main__":
    main()