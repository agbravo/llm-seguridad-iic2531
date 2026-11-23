"""Resume uno o más registros CSV: intentos, éxitos y tasa por modelo, prueba y fase (tabla Markdown).

Ejemplo:
    python resumen.py resultados/registro_*.csv
    python resumen.py resultados/registro_*.csv --por tecnica
"""
import argparse
import csv
from collections import defaultdict


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("archivos", nargs="+")
    p.add_argument("--por", choices=["prueba", "tecnica"], default="prueba")
    a = p.parse_args()

    grupos = defaultdict(lambda: {"intentos": 0, "exitosos": 0, "parciales": 0, "sin_respuesta": 0})
    for ruta in a.archivos:
        with open(ruta, encoding="utf-8-sig") as f:
            for fila in csv.DictReader(f):
                clave = fila["Prueba"] if a.por == "prueba" else f"{fila['Prueba']} · {fila['Técnica']}"
                g = grupos[(fila["Modelo"], clave, fila["Fase"])]
                g["intentos"] += 1
                g["exitosos"] += fila["Resultado"] == "Ataque exitoso"
                g["parciales"] += fila["Resultado"] == "Parcial"
                g["sin_respuesta"] += "SIN RESPUESTA FINAL" in fila["Notas"]

    print(f"| Modelo | {'Prueba' if a.por == 'prueba' else 'Prueba · técnica'} | Fase | Intentos | Exitosos | Parciales | Tasa de éxito | Sin respuesta |")
    print("| --- | --- | --- | --- | --- | --- | --- | --- |")
    for (modelo, clave, fase), g in sorted(grupos.items(), key=lambda kv: (kv[0][0], kv[0][1], kv[0][2] != "Antes de mitigación")):
        tasa = g["exitosos"] / g["intentos"] if g["intentos"] else 0
        print(f"| {modelo} | {clave} | {fase} | {g['intentos']} | {g['exitosos']} | {g['parciales']} | {tasa:.0%} | {g['sin_respuesta']} |")
    total_sr = sum(g["sin_respuesta"] for g in grupos.values())
    if total_sr:
        print(f"\nAviso: {total_sr} ejecuciones terminaron sin respuesta final; sus resultados no son confiables.")


if __name__ == "__main__":
    main()
