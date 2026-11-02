"""Estrategia 1: cada ID es una tarea que se asigna dinámicamente a un proceso.

El proceso 0 guarda la cola de IDs, también resuelve tableros y, entre cada
tanda de ~1000 nodos de su búsqueda, atiende las peticiones de los demás.
Cada tablero lo resuelve UN solo proceso con sudoku.resolver_con_tiempo.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from comun_mpi import (MPI, ServidorIDs, argumentos_comunes, buscar,  # noqa: E402
                       imprimir_resultado, informe_final, pedir_trabajo,
                       resolver_con_tiempo, seleccionar)

import time  # noqa: E402


def trabajador(comm):
    resultado = None
    while True:
        tarea = pedir_trabajo(comm, resultado)
        if tarea is None:
            return
        ident, tablero = tarea
        resuelto, segundos = resolver_con_tiempo(tablero)
        resultado = (ident, resuelto, segundos, tablero if resuelto else None)


def coordinador(comm, seleccionados):
    servidor = ServidorIDs(
        comm, seleccionados,
        al_recibir=lambda ident, ok, seg, proc: imprimir_resultado(ident, ok, seg, proc))

    def gancho():
        servidor.servir()
        return False

    comm.Barrier()
    inicio = MPI.Wtime()
    while True:
        tarea = servidor.tomar()
        if tarea is None:
            break
        ident, tablero = tarea
        t0 = time.perf_counter()
        resuelto = buscar(tablero, gancho)
        segundos = time.perf_counter() - t0
        servidor.registrar(ident, resuelto, segundos, tablero if resuelto else None, 0)
    servidor.esperar_todo()
    total = MPI.Wtime() - inicio

    resultados = {i: (r[0], r[1], r[2]) for i, r in servidor.resultados.items()}
    ok = informe_final(seleccionados, resultados, total, comm.size)
    return 0 if ok else 1


def main():
    comm = MPI.COMM_WORLD
    parser = argumentos_comunes("Sudoku con MPI: reparto dinámico de tableros.")
    args = parser.parse_args()
    if comm.rank == 0:
        codigo = coordinador(comm, seleccionar(parser, args))
        sys.exit(codigo)
    comm.Barrier()
    trabajador(comm)


if __name__ == "__main__":
    main()
