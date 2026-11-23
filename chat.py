"""Chat interactivo con el chatbot de prueba, para la demo en vivo.

Ejemplos:
    python chat.py --modelo llama3.1:8b
    python chat.py --modelo llama3.1:8b --defensas todas
    python chat.py --simulado

Comandos dentro del chat:
    /herramientas   muestra lo que el agente intentó hacer
    /html           guarda la última respuesta como página web en resultados/ultima_respuesta.html
    /defensas       muestra las defensas activas
    /salir          termina
"""
import argparse
import json
from pathlib import Path

from chatbot.app import Chatbot
from chatbot.clientes import ClienteOllama, ClienteSimulado
from ejecutar_pruebas import leer_defensas

RAIZ = Path(__file__).resolve().parent


def confirmar(nombre, args):
    print(f"\n  ⚠ El asistente quiere usar {nombre} con {json.dumps(args, ensure_ascii=False)}")
    return input("  ¿Autorizar? (s/N): ").strip().lower() == "s"


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--modelo", default="llama3.1:8b")
    p.add_argument("--url", default="http://localhost:11434")
    p.add_argument("--temperatura", type=float, default=0.7)
    p.add_argument("--usuario", default="ana", choices=["ana", "bruno"])
    p.add_argument("--defensas", default="")
    p.add_argument("--simulado", action="store_true")
    p.add_argument("--sin-herramientas", action="store_true", help="chatbot simple, sin agente (útil con modelos pequeños)")
    p.add_argument("--sin-razonamiento", action="store_true", help="pide al modelo que no razone antes de responder (Qwen3 y similares)")
    a = p.parse_args()

    defensas = leer_defensas(a.defensas)
    razonar = False if a.sin_razonamiento else None
    cliente = ClienteSimulado() if a.simulado else ClienteOllama(a.modelo, a.url, a.temperatura, razonar=razonar)
    bot = Chatbot(cliente, usuario=a.usuario, defensas=defensas, confirmar=confirmar, con_herramientas=not a.sin_herramientas)
    ultima = None
    print(f"Asistente Interno de Andes Logística (ficticio) · usuario: {a.usuario} · modelo: {cliente.modelo}")
    print(f"Defensas: {', '.join(defensas) or 'ninguna'} · /salir para terminar\n")

    while True:
        try:
            mensaje = input("Tú: ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if not mensaje:
            continue
        if mensaje == "/salir":
            break
        if mensaje == "/defensas":
            print("  " + (", ".join(defensas) or "ninguna"))
            continue
        if mensaje == "/herramientas":
            for ll in bot.herramientas.registro or [{"herramienta": "(ninguna)", "args": {}, "estado": "", "motivo": ""}]:
                print(f"  {ll['herramienta']} {json.dumps(ll['args'], ensure_ascii=False)} → {ll['estado']} {ll['motivo']}")
            continue
        if mensaje == "/html":
            if ultima:
                ruta = RAIZ / "resultados" / "ultima_respuesta.html"
                ruta.parent.mkdir(exist_ok=True)
                ruta.write_text(f"<!doctype html><meta charset='utf-8'><title>Respuesta</title>{ultima.html}", encoding="utf-8")
                print(f"  Guardado en {ruta}")
            continue

        ultima = bot.responder(mensaje)
        for ll in ultima.llamadas:
            print(f"  [herramienta] {ll['herramienta']} → {ll['estado']} {ll['motivo']}")
        if ultima.filtros:
            print(f"  [filtro] {', '.join(ultima.filtros)}")
        print(f"Asistente: {ultima.texto}\n")


if __name__ == "__main__":
    main()
