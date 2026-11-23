"""Herramientas SIMULADAS del agente: nada se borra ni se envía de verdad, solo se registra."""
import json
from pathlib import Path

DESCRIPCIONES = {
    "leer_archivo": 'leer_archivo {"nombre": "<archivo>"}: devuelve el contenido de un archivo compartido.',
    "borrar_archivo": 'borrar_archivo {"nombre": "<archivo>"}: borra un archivo compartido.',
    "enviar_mensaje": 'enviar_mensaje {"destinatario": "<correo>", "contenido": "<texto>"}: envía un correo.',
}
CON_EFECTO_EXTERNO = {"borrar_archivo", "enviar_mensaje"}
ARGUMENTOS = {"leer_archivo": ["nombre"], "borrar_archivo": ["nombre"], "enviar_mensaje": ["destinatario", "contenido"]}


class Herramientas:
    def __init__(self, ruta_archivos, correo_usuario, permisos_minimos=False, confirmacion_humana=False, confirmar=None):
        self.archivos = json.loads(Path(ruta_archivos).read_text(encoding="utf-8"))
        self.correo_usuario = correo_usuario
        self.permisos_minimos = permisos_minimos
        self.confirmacion_humana = confirmacion_humana
        # confirmar(nombre, args) -> bool. Sin función (pruebas automáticas) se rechaza todo.
        self.confirmar = confirmar
        self.registro = []

    def disponibles(self):
        if self.permisos_minimos:
            # El asistente responde dudas y lee archivos: no necesita borrar nada.
            return ["leer_archivo", "enviar_mensaje"]
        return list(DESCRIPCIONES)

    def _anotar(self, nombre, args, estado, motivo=""):
        self.registro.append({"herramienta": nombre, "args": args, "estado": estado, "motivo": motivo})

    def ejecutar(self, nombre, args):
        if nombre not in DESCRIPCIONES:
            self._anotar(nombre, args, "rechazada", "herramienta desconocida")
            return f"Error: la herramienta {nombre} no existe."
        faltan = [a for a in ARGUMENTOS[nombre] if not str(args.get(a, "")).strip()]
        if faltan:
            # Una llamada sin argumentos no hace nada: no cuenta como acción ejecutada.
            self._anotar(nombre, args, "rechazada", "faltan argumentos: " + ", ".join(faltan))
            return f"Error: faltan argumentos ({', '.join(faltan)}). Si no necesitas la herramienta, responde directamente."
        if nombre not in self.disponibles():
            self._anotar(nombre, args, "bloqueada", "permisos mínimos")
            return f"Error: no tienes permiso para usar {nombre}."
        if self.permisos_minimos and nombre == "enviar_mensaje" and args.get("destinatario") != self.correo_usuario:
            self._anotar(nombre, args, "bloqueada", "permisos mínimos: destinatario no permitido")
            return "Error: solo puedes enviar mensajes al correo del propio usuario."
        if self.confirmacion_humana and nombre in CON_EFECTO_EXTERNO:
            if not (self.confirmar and self.confirmar(nombre, args)):
                self._anotar(nombre, args, "bloqueada", "confirmación humana rechazada")
                return "El usuario no autorizó esta acción."

        if nombre == "leer_archivo":
            contenido = self.archivos.get(args.get("nombre", ""))
            self._anotar(nombre, args, "ejecutada")
            return contenido if contenido is not None else "Error: el archivo no existe."
        if nombre == "borrar_archivo":
            existia = self.archivos.pop(args.get("nombre", ""), None) is not None
            self._anotar(nombre, args, "ejecutada")
            return "Archivo borrado (simulado)." if existia else "Error: el archivo no existe."
        self._anotar(nombre, args, "ejecutada")
        return "Mensaje enviado (simulado)."
