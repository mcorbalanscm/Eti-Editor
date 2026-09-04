# Editor de Etiquetas (.eti)

Aplicación de escritorio en **Python + Tkinter** para abrir, editar, guardar
e imprimir etiquetas en el formato `.eti` (XML) que ya usáis.

Funciona igual en Windows, macOS y Linux: Tkinter viene incluido con Python,
así que no hace falta instalar ningún framework de interfaz aparte.

## 1. Instalación

Necesitas Python 3.9 o superior (en Windows, márcalo como "Add to PATH" al instalarlo).

```bash
cd etiqueta_app
pip install -r requirements.txt
```

En Linux, si `tkinter` no viniera instalado con tu Python:
```bash
sudo apt install python3-tk      # Debian/Ubuntu
```

## 2. Ejecutar

```bash
python etiqueta_editor.py
```

o abriendo directamente un archivo:

```bash
python etiqueta_editor.py mi_etiqueta.eti
```

## 3. Unidades: la hoja en mm, los elementos en px (importante)

El `<formato ancho= alto=>` del `.eti` está en **milímetros**: es el tamaño
físico real de la etiqueta. El programa original lo convertía a píxeles de
pantalla con un factor fijo:

```
PX_hoja = mm × 3.4
```

Este editor reproduce exactamente ese mismo factor (`RATIO_MM_A_PX = 3.4` en
`eti_format.py`), pero **solo para el tamaño de la hoja**. Las coordenadas
x/y/w/h de cada elemento (texto, código de barras, imagen, forma) ya están
en píxeles dentro del archivo y **no se multiplican por nada** (aparte del
zoom manual que aplique el usuario).

El tamaño de la hoja es **siempre** el configurado en "Etiqueta > Configurar"
(en mm, convertido a esos píxeles fijos) y **nunca** se agranda por el
contenido: cualquier elemento colocado fuera de esa área queda recortado —
tanto en el editor como en la vista previa, la impresión y la exportación.

Técnicamente, el recorte se consigue dibujando la etiqueta en un canvas de
Tkinter de tamaño fijo (ancho_mm × 3.4 × zoom, alto_mm × 3.4 × zoom) embebido
dentro del área de trabajo gris: al ser un widget con tamaño propio, Tkinter
recorta automáticamente cualquier dibujo que se salga de sus límites. Para
imprimir y exportar se aplica el mismo criterio sobre la imagen generada con
Pillow (que también recorta automáticamente lo que sobresalga).

## 4. Qué hace ahora mismo

- **Archivo**: Nuevo, Abrir, Guardar, Guardar como, Cerrar etiqueta, Salir.
- **Etiqueta**: Configurar ancho/alto (mm) / continuo.
- **Insertar**: Texto, Código de barras, Imagen, Línea, Rectángulo, Círculo.
- **Canvas interactivo**: seleccionar con clic, mover arrastrando, redimensionar
  desde el tirador azul de la esquina inferior derecha. Zoom manual (+/-,
  ajustar a ventana); por defecto siempre a 100% (1 mm = 3.4 px, igual que el
  programa original).
- **Campos variables resaltados**: los códigos tipo `A000FECALT` o
  `A130NUMDOC` (que en el sistema real se sustituyen por datos de la base de
  datos) se muestran resaltados en azul, y en la vista previa/impresión se
  sustituyen automáticamente por datos de ejemplo (`XXXXXXXXXX`, código de
  barras válido de muestra) para poder haceros una idea del resultado final.
- **Panel de propiedades** a la derecha: texto, fuente, tamaño de letra,
  posición (x/y en mm), tamaño (ancho/alto en mm), rotación, color/grosor de
  formas, codificación y valor del código de barras, ruta de la imagen.
- **Guardar** escribe de nuevo sobre el mismo archivo `.eti` abierto,
  respetando la estructura XML original (`<literal>`, `<codigo_barras>`, etc.).
  Los objetos nuevos (imágenes y formas) se guardan con dos etiquetas propias
  (`<imagen>`, `<forma>`) que no rompen la compatibilidad si luego abrís el
  archivo con vuestro programa antiguo (simplemente las ignorará).
- **Vista previa de impresión real**: el botón "Vista previa / Imprimir"
  muestra el resultado final tal cual se imprimiría (recortado al tamaño de
  etiqueta, con datos de ejemplo en los campos variables) antes de mandarlo
  a la impresora predeterminada del sistema, o exportarlo a PNG/PDF.

## 5. Estructura del proyecto

```
etiqueta_app/
├── etiqueta_editor.py   # Interfaz gráfica (Tkinter) — punto de entrada
├── eti_format.py        # Modelo de datos + lectura/escritura del XML .eti
├── render.py            # Dibuja la etiqueta a una imagen (para imprimir/exportar)
└── requirements.txt
```

Está separado en tres módulos a propósito, para que sea fácil ir afinando
cada parte por separado (por ejemplo, mejorar el motor de impresión o añadir
más tipos de código de barras) sin tocar el resto.

## 6. Cosas a pulir en la siguiente vuelta

- Rotación real de formas (ahora mismo solo rota bien el texto y las imágenes).
- Snap/rejilla al mover objetos y guías de alineación.
- Deshacer/rehacer (Ctrl+Z).
- Selección de impresora y bandeja/tamaño de papel real desde el diálogo de impresión.
- Multi-selección y copiar/pegar.
- Confirmar el factor 3.4 y la unidad mm contra `WCore/40-Etiquetado` si en
  algún momento tenéis acceso a ese proyecto, para descartar cualquier duda
  definitivamente.

Todo esto se puede añadir sin romper el archivo `.eti` que ya generáis, así
que dime por dónde quieres que sigamos afinando.

---

# BUILD E INSTALACIÓ

Crear executable:
- instalar pyinstall:

```bash
python -m install pyinstaller
```


- executar el seguent:

```bash
python -m PyInstaller --onefile etiqueta_editor.py
```

el executable esta a la carpeta dist