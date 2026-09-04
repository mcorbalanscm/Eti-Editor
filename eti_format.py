# -*- coding: utf-8 -*-
"""
eti_format.py
Modelo de datos y lectura/escritura de archivos .eti (formato XML de etiquetas).

El formato original contiene <literal> (texto) y <codigo_barras>.
Añadimos, de forma retrocompatible, dos elementos nuevos para cubrir las
necesidades del editor: <imagen> y <forma> (línea, rectángulo, círculo).
Si abres un .eti que no los tiene, simplemente no aparecerán objetos de
ese tipo; si los añades desde el editor y guardas, se escribirán con estas
mismas etiquetas para que el archivo se pueda volver a abrir sin perder nada.
"""

import xml.etree.ElementTree as ET
from xml.dom import minidom
import copy


# ---------------------------------------------------------------------------
# Conversión de unidades
# ---------------------------------------------------------------------------
# El <formato ancho= alto=> y las coordenadas x/y/w/h de los elementos del
# .eti NO están en píxeles: están en milímetros (unidad lógica del diseñador
# original "LabelTWO"). Ese programa los convertía a píxeles de pantalla con
# un factor fijo:
#       PX = mm * RATIO_MM_A_PX      (RATIO_MM_A_PX = 3.4)
# Lo reproducimos aquí para que el editor y la impresión coincidan con el
# comportamiento del programa original.
RATIO_MM_A_PX = 3.4


# ---------------------------------------------------------------------------
# Utilidades
# ---------------------------------------------------------------------------

def _text(elem, tag, default=""):
    child = elem.find(tag)
    if child is not None and child.text is not None:
        return child.text.strip()
    return default


def _int(elem, tag, default=0):
    val = _text(elem, tag, None)
    if val is None or val == "":
        return default
    try:
        return int(float(val))
    except ValueError:
        return default


def _posicion(elem, default=(0, 0)):
    pos = elem.find("posicion")
    if pos is None:
        return default
    try:
        return int(float(pos.get("x", default[0]))), int(float(pos.get("y", default[1])))
    except (TypeError, ValueError):
        return default


def _rotacion(elem, default=0):
    rot = elem.find("rotacion")
    if rot is None:
        return default
    try:
        return int(float(rot.get("grados", default)))
    except (TypeError, ValueError):
        return default


def _sub(parent, tag, text=None):
    e = ET.SubElement(parent, tag)
    if text is not None:
        e.text = str(text)
    return e


# ---------------------------------------------------------------------------
# Elementos
# ---------------------------------------------------------------------------

class Literal:
    """Texto / campo de la etiqueta."""
    KIND = "literal"

    def __init__(self, id_lit, texto="Texto", fuente="Arial", x=10, y=10,
                 w=100, h=30, tamano_letra=16, rotacion=0, negrita=False,
                 cursiva=False):
        self.id_lit = int(id_lit)
        self.texto = texto
        self.fuente = fuente
        self.x = int(x)
        self.y = int(y)
        self.w = int(w)
        self.h = int(h)
        self.tamano_letra = int(tamano_letra)
        self.rotacion = int(rotacion)
        self.negrita = bool(negrita)
        self.cursiva = bool(cursiva)

    @classmethod
    def from_xml(cls, elem):
        x, y = _posicion(elem)
        return cls(
            id_lit=elem.get("id_lit", 0),
            texto=_text(elem, "texto", ""),
            fuente=_text(elem, "fuente", "Arial"),
            x=x, y=y,
            w=_int(elem, "w", 100),
            h=_int(elem, "h", 30),
            tamano_letra=_int(elem, "tamano_letra", 16),
            rotacion=_rotacion(elem),
            negrita=_text(elem, "negrita", "False") == "True",
            cursiva=_text(elem, "cursiva", "False") == "True",
        )

    def to_xml(self):
        e = ET.Element("literal", {"id_lit": str(self.id_lit)})
        _sub(e, "texto", self.texto)
        _sub(e, "fuente", self.fuente)
        pos = ET.SubElement(e, "posicion")
        pos.set("x", str(self.x))
        pos.set("y", str(self.y))
        _sub(e, "w", self.w)
        _sub(e, "h", self.h)
        _sub(e, "tamano_letra", self.tamano_letra)
        rot = ET.SubElement(e, "rotacion")
        rot.set("grados", str(self.rotacion))
        if self.negrita:
            _sub(e, "negrita", "True")
        if self.cursiva:
            _sub(e, "cursiva", "True")
        return e

    def bbox(self):
        return (self.x, self.y, self.x + self.w, self.y + self.h)


class CodigoBarras:
    """Código de barras."""
    KIND = "codigo_barras"

    CODIFICACIONES = [
        "Code128", "Code128C", "Code39", "EAN13", "EAN8", "UPCA", "ITF",
    ]

    def __init__(self, id_barras, codigo="000000", x=10, y=10, w=150, h=60,
                 magnificacion=2, codificacion="Code128", alto=60,
                 rotacion=0, human_valor=False):
        self.id_barras = int(id_barras)
        self.codigo = codigo
        self.x = int(x)
        self.y = int(y)
        self.w = int(w)
        self.h = int(h)
        self.magnificacion = int(magnificacion)
        self.codificacion = codificacion
        self.alto = int(alto)
        self.rotacion = int(rotacion)
        self.human_valor = bool(human_valor)

    @classmethod
    def from_xml(cls, elem):
        x, y = _posicion(elem)
        return cls(
            id_barras=elem.get("id_barras", 0),
            codigo=_text(elem, "codigo", "000000"),
            x=x, y=y,
            w=_int(elem, "w", 150),
            h=_int(elem, "h", 60),
            magnificacion=_int(elem, "magnificacion", 2),
            codificacion=_text(elem, "codificacion", "Code128"),
            alto=_int(elem, "alto", 60),
            rotacion=_rotacion(elem),
            human_valor=(elem.get("human_valor", "False") == "True"),
        )

    def to_xml(self):
        e = ET.Element("codigo_barras", {
            "id_barras": str(self.id_barras),
            "human_valor": "True" if self.human_valor else "False",
        })
        _sub(e, "codigo", self.codigo)
        pos = ET.SubElement(e, "posicion")
        pos.set("x", str(self.x))
        pos.set("y", str(self.y))
        _sub(e, "magnificacion", self.magnificacion)
        _sub(e, "codificacion", self.codificacion)
        _sub(e, "alto", self.alto)
        _sub(e, "w", self.w)
        _sub(e, "h", self.h)
        rot = ET.SubElement(e, "rotacion")
        rot.set("grados", str(self.rotacion))
        return e

    def bbox(self):
        return (self.x, self.y, self.x + self.w, self.y + self.h)


class Imagen:
    """Imagen embebida por ruta (relativa o absoluta)."""
    KIND = "imagen"

    def __init__(self, id_img, ruta="", x=10, y=10, w=100, h=100, rotacion=0):
        self.id_img = int(id_img)
        self.ruta = ruta
        self.x = int(x)
        self.y = int(y)
        self.w = int(w)
        self.h = int(h)
        self.rotacion = int(rotacion)

    @classmethod
    def from_xml(cls, elem):
        x, y = _posicion(elem)
        return cls(
            id_img=elem.get("id_img", 0),
            ruta=_text(elem, "ruta", ""),
            x=x, y=y,
            w=_int(elem, "w", 100),
            h=_int(elem, "h", 100),
            rotacion=_rotacion(elem),
        )

    def to_xml(self):
        e = ET.Element("imagen", {"id_img": str(self.id_img)})
        _sub(e, "ruta", self.ruta)
        pos = ET.SubElement(e, "posicion")
        pos.set("x", str(self.x))
        pos.set("y", str(self.y))
        _sub(e, "w", self.w)
        _sub(e, "h", self.h)
        rot = ET.SubElement(e, "rotacion")
        rot.set("grados", str(self.rotacion))
        return e

    def bbox(self):
        return (self.x, self.y, self.x + self.w, self.y + self.h)


class Forma:
    """Forma simple: linea, rectangulo o circulo."""
    KIND = "forma"
    TIPOS = ["linea", "rectangulo", "circulo"]

    def __init__(self, id_forma, tipo="rectangulo", x=10, y=10, w=100, h=60,
                 grosor=2, color="#000000", relleno=False, rotacion=0):
        self.id_forma = int(id_forma)
        self.tipo = tipo if tipo in Forma.TIPOS else "rectangulo"
        self.x = int(x)
        self.y = int(y)
        self.w = int(w)
        self.h = int(h)
        self.grosor = int(grosor)
        self.color = color
        self.relleno = bool(relleno)
        self.rotacion = int(rotacion)

    @classmethod
    def from_xml(cls, elem):
        x, y = _posicion(elem)
        return cls(
            id_forma=elem.get("id_forma", 0),
            tipo=elem.get("tipo", "rectangulo"),
            x=x, y=y,
            w=_int(elem, "w", 100),
            h=_int(elem, "h", 60),
            grosor=_int(elem, "grosor", 2),
            color=_text(elem, "color", "#000000"),
            relleno=(elem.get("relleno", "False") == "True"),
            rotacion=_rotacion(elem),
        )

    def to_xml(self):
        e = ET.Element("forma", {
            "id_forma": str(self.id_forma),
            "tipo": self.tipo,
            "relleno": "True" if self.relleno else "False",
        })
        pos = ET.SubElement(e, "posicion")
        pos.set("x", str(self.x))
        pos.set("y", str(self.y))
        _sub(e, "w", self.w)
        _sub(e, "h", self.h)
        _sub(e, "grosor", self.grosor)
        _sub(e, "color", self.color)
        rot = ET.SubElement(e, "rotacion")
        rot.set("grados", str(self.rotacion))
        return e

    def bbox(self):
        return (self.x, self.y, self.x + self.w, self.y + self.h)


# ---------------------------------------------------------------------------
# Diseño completo (la etiqueta)
# ---------------------------------------------------------------------------

class Diseno:
    def __init__(self):
        self.version = "verion 10 labeltwo"
        self.ancho = 100
        self.alto = 100
        self.continuo = False
        self.literales = []
        self.barras = []
        self.imagenes = []
        self.formas = []
        self.filepath = None

    # -- carga / guardado -------------------------------------------------

    @classmethod
    def nuevo(cls):
        return cls()

    @classmethod
    def from_file(cls, path):
        tree = ET.parse(path)
        root = tree.getroot()
        d = cls()
        d.filepath = path

        ver = root.find("version")
        if ver is not None and ver.text:
            d.version = ver.text.strip()

        fmt = root.find("formato")
        if fmt is not None:
            d.ancho = int(float(fmt.get("ancho", 100)))
            d.alto = int(float(fmt.get("alto", 100)))
            d.continuo = fmt.get("continuo", "False") == "True"

        for lit in root.findall("literal"):
            d.literales.append(Literal.from_xml(lit))
        for cb in root.findall("codigo_barras"):
            d.barras.append(CodigoBarras.from_xml(cb))
        for img in root.findall("imagen"):
            d.imagenes.append(Imagen.from_xml(img))
        for fm in root.findall("forma"):
            d.formas.append(Forma.from_xml(fm))

        return d

    def to_xml_string(self):
        root = ET.Element("diseno")
        _sub(root, "version", self.version)
        fmt = ET.SubElement(root, "formato")
        fmt.set("ancho", str(self.ancho))
        fmt.set("alto", str(self.alto))
        fmt.set("continuo", "True" if self.continuo else "False")

        for lit in self.literales:
            root.append(lit.to_xml())
        for cb in self.barras:
            root.append(cb.to_xml())
        for img in self.imagenes:
            root.append(img.to_xml())
        for fm in self.formas:
            root.append(fm.to_xml())

        rough = ET.tostring(root, encoding="utf-8")
        pretty = minidom.parseString(rough).toprettyxml(indent="  ", encoding="utf-8")
        # Insertar cabecera/comentario compatible con el formato original
        pretty = pretty.decode("utf-8")
        lines = pretty.splitlines()
        # quitar la línea <?xml ...?> generada por minidom, la sustituimos
        if lines and lines[0].startswith("<?xml"):
            lines = lines[1:]
        header = '<?xml version="1.0" standalone="no"?>\n<!--Archivo tfi-->\n<!DOCTYPE Diseno>\n'
        # eliminar líneas en blanco que deja minidom
        body = "\n".join(l for l in lines if l.strip() != "")
        return header + body + "\n"

    def to_file(self, path=None):
        path = path or self.filepath
        if not path:
            raise ValueError("No hay ruta de archivo para guardar.")
        with open(path, "w", encoding="utf-8") as f:
            f.write(self.to_xml_string())
        self.filepath = path

    # -- gestión de objetos -------------------------------------------------

    def _next_id(self, coleccion, attr):
        existentes = [getattr(o, attr) for o in coleccion]
        return (max(existentes) + 1) if existentes else 1

    def nuevo_literal(self, **kwargs):
        nid = self._next_id(self.literales, "id_lit")
        lit = Literal(id_lit=nid, **kwargs)
        self.literales.append(lit)
        return lit

    def nuevo_codigo_barras(self, **kwargs):
        nid = self._next_id(self.barras, "id_barras")
        cb = CodigoBarras(id_barras=nid, **kwargs)
        self.barras.append(cb)
        return cb

    def nueva_imagen(self, **kwargs):
        nid = self._next_id(self.imagenes, "id_img")
        img = Imagen(id_img=nid, **kwargs)
        self.imagenes.append(img)
        return img

    def nueva_forma(self, **kwargs):
        nid = self._next_id(self.formas, "id_forma")
        fm = Forma(id_forma=nid, **kwargs)
        self.formas.append(fm)
        return fm

    def eliminar(self, obj):
        for coleccion in (self.literales, self.barras, self.imagenes, self.formas):
            if obj in coleccion:
                coleccion.remove(obj)
                return True
        return False

    def todos_los_objetos(self):
        return list(self.literales) + list(self.barras) + list(self.imagenes) + list(self.formas)

    def bbox_total(self, margen=20):
        objs = self.todos_los_objetos()
        if not objs:
            return (0, 0, max(self.ancho, 200), max(self.alto, 200))
        xs0 = [o.bbox()[0] for o in objs]
        ys0 = [o.bbox()[1] for o in objs]
        xs1 = [o.bbox()[2] for o in objs]
        ys1 = [o.bbox()[3] for o in objs]
        x0, y0 = min(0, min(xs0)), min(0, min(ys0))
        x1, y1 = max(xs1) + margen, max(ys1) + margen
        return (int(x0), int(y0), int(x1), int(y1))

    def clone(self):
        return copy.deepcopy(self)
