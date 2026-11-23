"""Recuperación de documentos muy simple (por palabras en común), con control de acceso opcional."""
import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path

PALABRAS_VACIAS = {
    "para", "como", "esta", "este", "esto", "sobre", "segun", "cual", "cuales", "cuanto", "cuantos",
    "tengo", "tiene", "dime", "dice", "todas", "todos", "quiero", "necesito", "puedes", "favor",
    "donde", "cuando", "porque", "que", "una", "unos", "unas", "las", "los", "del", "con",
}


@dataclass
class Documento:
    nombre: str
    propietario: str  # "todos" o el id de un usuario
    texto: str


def _normalizar(texto):
    sin_tildes = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode()
    return sin_tildes.lower()


def _raiz(palabra):
    # Singular aproximado: "fichas" -> "ficha", "políticas" -> "politica".
    return palabra[:-1] if len(palabra) > 4 and palabra.endswith("s") else palabra


def _palabras(texto):
    return {_raiz(p) for p in re.findall(r"[a-z0-9]+", _normalizar(texto)) if len(p) >= 4 and p not in PALABRAS_VACIAS}


def _titulo(doc):
    encabezado = next((l for l in doc.texto.splitlines() if l.startswith("#")), "")
    return doc.nombre.replace("_", " ") + " " + encabezado


def cargar_documentos(directorio):
    documentos = []
    for ruta in sorted(Path(directorio).glob("*.md")):
        crudo = ruta.read_text(encoding="utf-8")
        propietario = "todos"
        texto = crudo
        cabecera = re.match(r"---\n(.*?)\n---\n", crudo, re.S)
        if cabecera:
            for linea in cabecera.group(1).splitlines():
                clave, _, valor = linea.partition(":")
                if clave.strip() == "propietario":
                    propietario = valor.strip()
            texto = crudo[cabecera.end():]
        documentos.append(Documento(ruta.stem, propietario, texto.strip()))
    return documentos


def recuperar(documentos, consulta, usuario, k=2, control_acceso=False):
    """Devuelve hasta k documentos cuyo título comparte palabras con la consulta.

    Sin control de acceso (la versión vulnerable) se buscan TODOS los documentos,
    incluidos los de otros usuarios. Con control de acceso, el filtro ocurre aquí,
    antes de que el modelo vea nada.
    """
    consulta_palabras = _palabras(consulta)
    puntajes = []
    for doc in documentos:
        if control_acceso and doc.propietario not in ("todos", usuario):
            continue
        en_titulo = len(consulta_palabras & _palabras(_titulo(doc)))
        if en_titulo == 0:
            continue
        puntaje = 3 * en_titulo + len(consulta_palabras & _palabras(doc.texto))
        puntajes.append((puntaje, doc.nombre, doc))
    puntajes.sort(key=lambda t: (-t[0], t[1]))
    return [doc for _, _, doc in puntajes[:k]]
