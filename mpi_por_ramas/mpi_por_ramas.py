"""Estrategia 2: los tableros se resuelven en orden, uno tras otro, y las
ramas de cada tablero (valores válidos de sus primeras casillas vacías) se
reparten dinámicamente entre todos los procesos. Al hallar la solución, los
demás abortan su búsqueda; solo entonces se pasa al siguiente tablero.
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from comun_mpi import (MPI, GrupoRamas, argumentos_comunes,  # noqa: E402
                       imprimir_resultado, informe_final, seleccionar)


def main():
    comm = MPI.COMM_WORLD
    parser = argumentos_comunes("Sudoku con MPI: reparto de las ramas de cada tablero.")
    parser.add_argument("--ramas-por-proceso", type=int, default=4,
                        help="ramas mínimas por proceso en que se divide cada tablero (por defecto: 4)")
    args = parser.parse_args()
    grupo = GrupoRamas(comm, args.ramas_por_proceso)

    if comm.rank != 0:
        comm.Barrier()
        grupo.trabajar()
        return

    seleccionados = seleccionar(parser, args)
    comm.Barrier()
    inicio = MPI.Wtime()
    resultados = {}
    for ident, tablero in seleccionados:
        resuelto, solucion, segundos = grupo.resolver_tablero(tablero)
        resultados[ident] = (resuelto, segundos, solucion)
        imprimir_resultado(ident, resuelto, segundos)
    total = MPI.Wtime() - inicio
    grupo.terminar()

    ok = informe_final(seleccionados, resultados, total, comm.size,
                       f"; ramas mínimas por proceso: {args.ramas_por_proceso}")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
