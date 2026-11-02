"""Ejecuta serial + las tres versiones MPI varias veces y resume las medianas.

Uso dentro del contenedor (desde la raíz del proyecto, montada en /app):

  python /app/medir_comparacion.py --n 4
  python /app/medir_comparacion.py --n 4 --barrido-grupos 1,2,4      # elegir tamaño de grupo
  python /app/medir_comparacion.py --n 4 --tiempo-serial 111.72      # reutilizar el serial ya medido

Cada ejecución completa resuelve los 30 IDs, así que tarda (el serial ~2 min).
Genera una tabla en Markdown lista para pegar en INFORME.md y la guarda en
resultados_medicion.md.
"""

import argparse
import re
import statistics
import subprocess
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent
MPIEXEC = ["mpiexec", "--allow-run-as-root", "--use-hwthread-cpus", "--oversubscribe"]
PATRON_SERIAL = re.compile(r"Tiempo total:\s*([\d.]+)")
PATRON_MPI = re.compile(r"Tiempo total \(real\):\s*([\d.]+)")


def ejecutar(comando, patron, etiqueta, indice):
    resultado = subprocess.run(comando, capture_output=True, text=True)
    coincidencia = patron.search(resultado.stdout)
    if resultado.returncode != 0 or not coincidencia:
        print(resultado.stdout[-1500:])
        print(resultado.stderr[-1500:])
        sys.exit(f"Falló {etiqueta} (código {resultado.returncode}).")
    if "Soluciones verificadas: 30/30" not in resultado.stdout and patron is PATRON_MPI:
        sys.exit(f"{etiqueta}: no se verificaron 30/30 soluciones.\n{resultado.stdout[-800:]}")
    segundos = float(coincidencia.group(1))
    print(f"  {etiqueta} #{indice}: {segundos:.3f} s", flush=True)
    return segundos


def medir(etiqueta, comando, patron, repeticiones):
    print(f"{etiqueta}:", flush=True)
    tiempos = [ejecutar(comando, patron, etiqueta, i + 1) for i in range(repeticiones)]
    mediana = statistics.median(tiempos)
    print(f"  mediana: {mediana:.3f} s\n", flush=True)
    return mediana, tiempos


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--n", type=int, required=True, help="N elegido con detectar_procesos_mpi.py")
    parser.add_argument("--reps", type=int, default=3, help="repeticiones por medición (por defecto: 3)")
    parser.add_argument("--tam-grupo", type=int, default=2, help="tamaño de grupo del híbrido (por defecto: 2)")
    parser.add_argument("--barrido-grupos", help="lista, p. ej. 1,2,4: prueba esos tamaños de grupo y no mide el resto")
    parser.add_argument("--ramas-por-proceso", type=int, default=4)
    parser.add_argument("--tiempo-serial", type=float, help="mediana serial ya conocida (omite medirla)")
    parser.add_argument("--archivo", type=Path, default=RAIZ / "seeds.txt")
    args = parser.parse_args()

    py = sys.executable
    n = str(args.n)
    comun = ["--all", "--archivo", str(args.archivo)]
    filas = []

    if args.barrido_grupos:
        print(f"Barrido de tamaño de grupo del híbrido con N={args.n}\n")
        for t in [int(x) for x in args.barrido_grupos.split(",")]:
            comando = MPIEXEC + ["-n", n, py, str(RAIZ / "mpi_hibrido/mpi_hibrido.py"),
                                 "--tam-grupo", str(t),
                                 "--ramas-por-proceso", str(args.ramas_por_proceso)] + comun
            mediana, _ = medir(f"híbrido tam-grupo={t}", comando, PATRON_MPI, args.reps)
            filas.append((t, mediana))
        mejor = min(filas, key=lambda f: f[1])
        texto = ["| Tamaño de grupo | Grupos | Mediana (s) |", "| ---: | ---: | ---: |"]
        for t, m in filas:
            texto.append(f"| {t} | {max(1, args.n // t)} | {m:.2f} |")
        texto.append(f"\nMejor tamaño de grupo: **{mejor[0]}**")
        salida = "\n".join(texto)
        print(salida)
        (RAIZ / "resultados_barrido_grupos.md").write_text(salida + "\n", encoding="utf-8")
        return

    if args.tiempo_serial is not None:
        serial = args.tiempo_serial
        print(f"Secuencial: usando mediana dada = {serial:.3f} s\n")
    else:
        serial, _ = medir("Secuencial", [py, str(RAIZ / "baseline_secuencial.py")] + comun,
                          PATRON_SERIAL, args.reps)

    mpi = [
        ("MPI por tableros", "mpi_por_tableros/mpi_por_tableros.py", []),
        ("MPI por ramas", "mpi_por_ramas/mpi_por_ramas.py",
         ["--ramas-por-proceso", str(args.ramas_por_proceso)]),
        ("MPI híbrido", "mpi_hibrido/mpi_hibrido.py",
         ["--tam-grupo", str(args.tam_grupo), "--ramas-por-proceso", str(args.ramas_por_proceso)]),
    ]
    resultados = [("Secuencial", 1, serial)]
    for nombre, script, extra in mpi:
        comando = MPIEXEC + ["-n", n, py, str(RAIZ / script)] + extra + comun
        mediana, _ = medir(nombre, comando, PATRON_MPI, args.reps)
        resultados.append((nombre, args.n, mediana))

    lineas = ["| Implementación | Caso | Procesos | Mediana del tiempo total (s) | Aceleración | Eficiencia |",
              "| --- | --- | ---: | ---: | ---: | ---: |"]
    for nombre, procesos, mediana in resultados:
        aceleracion = serial / mediana
        eficiencia = aceleracion / procesos
        caso = "Todos los IDs, uno después de otro" if "ramas" in nombre else "Todos los IDs"
        lineas.append(f"| {nombre} | {caso} | {procesos} | {mediana:.2f} | "
                      f"{aceleracion:.2f} | {eficiencia:.0%} |".replace(".", ","))
    salida = "\n".join(lineas)
    print(salida)
    (RAIZ / "resultados_medicion.md").write_text(salida + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
