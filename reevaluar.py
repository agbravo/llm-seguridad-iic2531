"""Vuelve a evaluar un registro con los criterios actuales, usando las respuestas guardadas en el detalle.

Sirve para corregir la clasificación sin volver a llamar al modelo (por ejemplo, tras arreglar un falso positivo).

Ejemplo:
    python reevaluar.py resultados/detalle_antes_X.jsonl resultados/registro_antes_X.csv
    → escribe resultados/registro_antes_X_reevaluado.csv y lista las filas que cambiaron.
"""
import csv
import json
import sys
from pathlib import Path

from chatbot.defensas import renderizar_html
from chatbot.evaluacion import evaluar

RAIZ = Path(__file__).resolve().parent


def main():
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    detalle, registro = Path(sys.argv[1]), Path(sys.argv[2])
    criterios = {f["id"]: f["criterio"] for f in csv.DictReader(open(RAIZ / "pruebas" / "intentos.csv", encoding="utf-8"))}
    nuevos = {}
    for linea in open(detalle, encoding="utf-8"):
        d = json.loads(linea)
        htmls = [renderizar_html(t, escapar="escapar_html" in d["defensas"]) for t in d["respuestas"]]
        nuevos[d["n"]] = evaluar(criterios[d["id"]], d["respuestas"], htmls, d["herramientas"])

    with open(registro, encoding="utf-8-sig") as f:
        filas = list(csv.DictReader(f))
    cambios = 0
    for fila in filas:
        resultado, severidad, detalle_txt = nuevos[int(fila["N°"])]
        if (resultado, severidad) != (fila["Resultado"], fila["Severidad"]):
            cambios += 1
            print(f"Fila {fila['N°']}: {fila['Resultado']} / {fila['Severidad']} → {resultado} / {severidad} ({detalle_txt})")
            anterior = fila["Notas"].split(" · ", 2)
            fila["Notas"] = " · ".join([anterior[0], detalle_txt] + anterior[2:]) + " · reevaluado"
            fila["Resultado"], fila["Severidad"] = resultado, severidad

    salida = registro.with_name(registro.stem + "_reevaluado.csv")
    with open(salida, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=list(filas[0].keys()))
        w.writeheader()
        w.writerows(filas)
    print(f"{cambios} filas cambiaron. Archivo: {salida}")


if __name__ == "__main__":
    main()
