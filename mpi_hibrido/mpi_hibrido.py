"""Estrategia 3 (híbrida): los N procesos se dividen en grupos con Comm.Split.
Los IDs se reparten dinámicamente entre grupos (un ID por grupo a la vez) y,
dentro de cada grupo, el líder reparte las ramas de su tablero entre los
procesos del grupo (misma mecánica que mpi_por_ramas).

--tam-grupo T fija el tamaño objetivo de grupo: hay max(1, N // T) grupos, con
tamaños que difieren como mucho en 1. T=1 equivale a repartir solo tableros;
T=N equivale a repartir solo ramas.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from comun_mpi import (MPI, GrupoRamas, ServidorIDs, argumentos_comunes,  # noqa: E402
                       imprimir_resultado, informe_final, pedir_trabajo,
                       seleccionar)


def color_de(rank, size, grupos):
    """Grupo (0..grupos-1) de un rank; bloques contiguos de tamaño balanceado."""
    base, resto = divmod(size, grupos)
    limite = 0
    for g in range(grupos):
        limite += base + (1 if g < resto else 0)
        if rank < limite:
            return g
    return grupos - 1


def main():
    mundo = MPI.COMM_WORLD
    parser = argumentos_comunes("Sudoku con MPI híbrido: grupos de procesos.")
    parser.add_argument("--tam-grupo", type=int, default=2,
                        help="tamaño objetivo de cada grupo (por defecto: 2)")
    parser.add_argument("--ramas-por-proceso", type=int, default=4,
                        help="ramas mínimas por proceso dentro de cada grupo (por defecto: 4)")
    args = parser.parse_args()
    if args.tam_grupo < 1:
        parser.error("--tam-grupo debe ser al menos 1")

    grupos = max(1, mundo.size // args.tam_grupo)
    color = color_de(mundo.rank, mundo.size, grupos)
    comm_grupo = mundo.Split(color, mundo.rank)
    es_lider = comm_grupo.rank == 0

    if mundo.rank == 0:
        seleccionados = seleccionar(parser, args)
        servidor = ServidorIDs(
            mundo, seleccionados,
            al_recibir=lambda i, ok, seg, p: imprimir_resultado(i, ok, seg, p))
        # Los líderes de los demás grupos son los únicos que piden IDs.
        servidor.remotos = grupos - 1
        grupo = GrupoRamas(comm_grupo, args.ramas_por_proceso,
                           gancho_extra=servidor.servir)
        mundo.Barrier()
        inicio = MPI.Wtime()
        while True:
            tarea = servidor.tomar()
            if tarea is None:
                break
            ident, tablero = tarea
            resuelto, solucion, segundos = grupo.resolver_tablero(tablero)
            servidor.registrar(ident, resuelto, segundos, solucion, 0)
        grupo.terminar()
        servidor.esperar_todo()
        total = MPI.Wtime() - inicio

        resultados = {i: (r[0], r[1], r[2]) for i, r in servidor.resultados.items()}
        tamanos = sorted({comm_grupo_size for comm_grupo_size in
                          (sum(1 for r in range(mundo.size)
                               if color_de(r, mundo.size, grupos) == g)
                           for g in range(grupos))})
        ok = informe_final(seleccionados, resultados, total, mundo.size,
                           f"; grupos: {grupos} (tamaños {tamanos}); "
                           f"ramas mínimas por proceso: {args.ramas_por_proceso}")
        sys.exit(0 if ok else 1)

    grupo = GrupoRamas(comm_grupo, args.ramas_por_proceso)
    mundo.Barrier()
    if not es_lider:
        grupo.trabajar()
        return
    resultado = None
    while True:
        tarea = pedir_trabajo(mundo, resultado)
        if tarea is None:
            break
        ident, tablero = tarea
        resuelto, solucion, segundos = grupo.resolver_tablero(tablero)
        resultado = (ident, resuelto, segundos, solucion)
    grupo.terminar()


if __name__ == "__main__":
    main()
