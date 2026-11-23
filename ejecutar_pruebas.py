"""Ejecuta el catálogo de intentos contra el chatbot y guarda los resultados en el formato de la planilla.

Ejemplos:
    python ejecutar_pruebas.py --modelo llama3.1:8b                       # antes de mitigar
    python ejecutar_pruebas.py --modelo llama3.1:8b --defensas todas      # después de mitigar
    python ejecutar_pruebas.py --modelo llama3.1:8b --defensas control_acceso --pruebas 3
    python ejecutar_pruebas.py --simulado                                  # solo para probar el código
"""
import argparse
import csv
import json
import re
import sys
import time
from datetime import datetime
from pathlib import Path

from chatbot.app import Chatbot
from chatbot.clientes import ClienteOllama, ClienteSimulado
from chatbot.defensas import CAPAS
from chatbot.evaluacion import evaluar, secreto_completo

RAIZ = Path(__file__).resolve().parent
COLUMNAS = ["N°", "Fecha", "Prueba", "Técnica", "Resultado", "Severidad", "Fase", "Entorno", "Modelo",
            "Categoría OWASP", "Descripción del intento", "Responsable", "Notas"]


def leer_defensas(valor):
    if not valor:
        return []
    if valor == "todas":
        return list(CAPAS)
    capas = [c.strip() for c in valor.split(",") if c.strip()]
    desconocidas = [c for c in capas if c not in CAPAS]
    if desconocidas:
        sys.exit(f"Defensas desconocidas: {', '.join(desconocidas)}. Opciones: {', '.join(CAPAS)} o 'todas'.")
    return capas


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--modelo", default="llama3.1:8b", help="modelo de Ollama (por defecto llama3.1:8b)")
    p.add_argument("--url", default="http://localhost:11434", help="dirección de Ollama")
    p.add_argument("--temperatura", type=float, default=0.7)
    p.add_argument("--repeticiones", type=int, default=5, help="veces que se repite cada intento")
    p.add_argument("--defensas", default="", help="'todas' o lista separada por comas: " + ", ".join(CAPAS))
    p.add_argument("--pruebas", default="", help="filtrar por número de prueba, p. ej. 1,2")
    p.add_argument("--ids", default="", help="filtrar por id de intento, p. ej. D01,I02")
    p.add_argument("--responsable", default="")
    p.add_argument("--catalogo", default=str(RAIZ / "pruebas" / "intentos.csv"))
    p.add_argument("--salida", default=str(RAIZ / "resultados"))
    p.add_argument("--simulado", action="store_true", help="usa el modelo simulado (no son resultados reales)")
    p.add_argument("--sin-razonamiento", action="store_true",
                   help="pide al modelo que no razone antes de responder (Qwen3 y similares); más rápido")
    a = p.parse_args()

    defensas = leer_defensas(a.defensas)
    fase = "Después de mitigación" if defensas else "Antes de mitigación"
    razonar = False if a.sin_razonamiento else None
    cliente = ClienteSimulado() if a.simulado else ClienteOllama(a.modelo, a.url, a.temperatura, razonar=razonar)

    with open(a.catalogo, encoding="utf-8") as f:
        intentos = list(csv.DictReader(f))
    if a.pruebas:
        numeros = {n.strip() for n in a.pruebas.split(",")}
        intentos = [i for i in intentos if i["prueba"].split(".")[0] in numeros]
    if a.ids:
        ids = {n.strip().upper() for n in a.ids.split(",")}
        intentos = [i for i in intentos if i["id"].upper() in ids]
    if not intentos:
        sys.exit("No hay intentos que coincidan con los filtros.")

    salida = Path(a.salida)
    salida.mkdir(parents=True, exist_ok=True)
    marca = datetime.now().strftime("%Y%m%d-%H%M%S")
    nombre_modelo = re.sub(r"[^A-Za-z0-9.-]+", "-", cliente.modelo)
    etiqueta = f"{nombre_modelo}_" + ("despues" if defensas else "antes")
    ruta_csv = salida / f"registro_{etiqueta}_{marca}.csv"
    ruta_detalle = salida / f"detalle_{etiqueta}_{marca}.jsonl"

    total = len(intentos) * a.repeticiones
    print(f"Fase: {fase} · Modelo: {cliente.modelo} · Defensas: {', '.join(defensas) or 'ninguna'}")
    print(f"{len(intentos)} intentos × {a.repeticiones} repeticiones = {total} ejecuciones\n")

    n = 0
    with open(ruta_csv, "w", newline="", encoding="utf-8-sig") as fc, open(ruta_detalle, "w", encoding="utf-8") as fd:
        escritor = csv.writer(fc)
        escritor.writerow(COLUMNAS)
        for intento in intentos:
            mensajes = [m.strip() for m in intento["mensajes"].split("|||")]
            for rep in range(1, a.repeticiones + 1):
                n += 1
                inicio = time.time()
                # Herramientas solo donde el ataque las necesita: el agente (prueba 4) y la
                # inyección indirecta que pide enviar un correo. El resto es un chatbot simple.
                con_herr = intento["entorno"] == "Agente local" or "herramienta:" in intento["criterio"]
                bot = Chatbot(cliente, usuario=intento["usuario"], defensas=defensas, con_herramientas=con_herr)
                cliente.razonamientos = []
                respuestas = [bot.responder(m) for m in mensajes]
                razonamiento = "\n---\n".join(t for t in cliente.razonamientos if t)
                llamadas = [ll for r in respuestas for ll in r.llamadas]
                resultado, severidad, detalle = evaluar(
                    intento["criterio"], [r.texto for r in respuestas], [r.html for r in respuestas], llamadas)
                segundos = time.time() - inicio

                notas = [f"{intento['id']} rep {rep}", detalle]
                if any(r.sin_respuesta for r in respuestas):
                    notas.append("SIN RESPUESTA FINAL (el modelo no siguió el formato)")
                if razonamiento and secreto_completo(razonamiento):
                    notas.append("la clave apareció en el razonamiento (no visible para el usuario)")
                if llamadas:
                    notas.append("herramientas: " + ", ".join(f"{ll['herramienta']} ({ll['estado']})" for ll in llamadas))
                if defensas:
                    notas.append("defensas: " + ", ".join(defensas))
                escritor.writerow([n, datetime.now().strftime("%Y-%m-%d"), intento["prueba"], intento["tecnica"],
                                   resultado, severidad, fase, intento["entorno"], cliente.modelo, intento["owasp"],
                                   intento["descripcion"], a.responsable, " · ".join(notas)])
                fc.flush()
                fd.write(json.dumps({
                    "n": n, "id": intento["id"], "repeticion": rep, "fase": fase, "defensas": defensas,
                    "modelo": cliente.modelo, "temperatura": cliente.temperatura, "mensajes": mensajes,
                    "respuestas": [r.texto for r in respuestas], "salida_cruda": [r.crudo for r in respuestas],
                    "documentos": [r.documentos for r in respuestas], "herramientas": llamadas,
                    "filtros": [r.filtros for r in respuestas], "resultado": resultado,
                    "severidad": severidad, "detalle": detalle, "segundos": round(segundos, 1),
                    "con_herramientas": con_herr, "sin_respuesta": [r.sin_respuesta for r in respuestas],
                    "razonamiento": razonamiento, "sin_razonamiento": a.sin_razonamiento,
                }, ensure_ascii=False) + "\n")
                aviso = "  ⚠ sin respuesta final" if any(r.sin_respuesta for r in respuestas) else ""
                print(f"[{n:>3}/{total}] {intento['id']} rep {rep}: {resultado:<15} {severidad:<10} {detalle} ({segundos:.1f} s){aviso}")

    print(f"\nRegistro para la planilla: {ruta_csv}")
    print(f"Detalle de cada respuesta: {ruta_detalle}")
    print(f"Resumen: python resumen.py {ruta_csv}")


if __name__ == "__main__":
    main()
