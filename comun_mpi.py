"""Piezas compartidas por las tres implementaciones MPI.

- buscar():          el mismo backtracking de sudoku.py, con un "gancho" que se
                     invoca cada cierto número de nodos (para atender mensajes
                     MPI o para abortar la búsqueda).
- generar_ramas():   divide un tablero en subproblemas independientes.
- ServidorIDs:       cola dinámica de IDs atendida por el proceso 0.
- GrupoRamas:        reparto de las ramas de UN tablero entre los procesos de
                     un comunicador (líder = rank 0 del comunicador).
- es_solucion_valida(): comprobación final de cada solución.
"""

import sys
import time
from collections import deque
from pathlib import Path

RAIZ = Path(__file__).resolve().parent
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

from mpi4py import MPI  # noqa: E402

from baseline_secuencial import leer_seeds  # noqa: E402,F401  (se reexporta)
from sudoku import puede_colocar, resolver_con_tiempo  # noqa: E402,F401


# --------------------------------------------------------------------------
# Búsqueda
# --------------------------------------------------------------------------
class _Abortado(Exception):
    pass


def buscar(tablero, gancho=None, cada=1000):
    """Backtracking idéntico a sudoku.resolver (primera casilla vacía, valores
    1..9, puede_colocar de sudoku.py) con un gancho opcional.

    Devuelve True (resuelto, in situ), False (sin solución) o None (abortado
    porque gancho() devolvió True).
    """
    contador = 0

    def rec():
        nonlocal contador
        if gancho is not None:
            contador += 1
            if contador % cada == 0 and gancho():
                raise _Abortado
        for fila in range(9):
            for columna in range(9):
                if tablero[fila][columna] != 0:
                    continue
                for valor in range(1, 10):
                    if puede_colocar(tablero, fila, columna, valor):
                        tablero[fila][columna] = valor
                        if rec():
                            return True
                        tablero[fila][columna] = 0
                return False
        return True

    try:
        return rec()
    except _Abortado:
        return None


def _primera_vacia(tablero):
    for fila in range(9):
        for columna in range(9):
            if tablero[fila][columna] == 0:
                return fila, columna
    return None


def generar_ramas(tablero, minimo, profundidad_maxima=6):
    """Expande por niveles las primeras casillas vacías (en el mismo orden que
    el backtracking serial) hasta tener al menos `minimo` ramas.

    Cada rama es un tablero completo con ese prefijo ya colocado. Las ramas
    cuyo prefijo viola las reglas se descartan. Puede devolver una lista vacía
    (tablero sin solución).
    """
    ramas = [[fila[:] for fila in tablero]]
    for _ in range(profundidad_maxima):
        if len(ramas) >= minimo:
            break
        nuevas = []
        expandio = False
        for rama in ramas:
            posicion = _primera_vacia(rama)
            if posicion is None:
                nuevas.append(rama)
                continue
            expandio = True
            fila, columna = posicion
            for valor in range(1, 10):
                if puede_colocar(rama, fila, columna, valor):
                    nueva = [f[:] for f in rama]
                    nueva[fila][columna] = valor
                    nuevas.append(nueva)
        ramas = nuevas
        if not expandio:
            break
    return ramas


# --------------------------------------------------------------------------
# Verificación
# --------------------------------------------------------------------------
def es_solucion_valida(solucion, original):
    """True si `solucion` es un Sudoku completo y respeta las pistas."""
    if solucion is None:
        return False
    digitos = set(range(1, 10))
    for f in range(9):
        for c in range(9):
            if original[f][c] != 0 and solucion[f][c] != original[f][c]:
                return False
    for i in range(9):
        if set(solucion[i]) != digitos:
            return False
        if {solucion[f][i] for f in range(9)} != digitos:
            return False
    for bf in range(0, 9, 3):
        for bc in range(0, 9, 3):
            bloque = {solucion[f][c] for f in range(bf, bf + 3)
                      for c in range(bc, bc + 3)}
            if bloque != digitos:
                return False
    return True


def imprimir_resultado(ident, resuelto, segundos, proceso=None):
    """Mismo formato que baseline_secuencial.py (+ el proceso que lo resolvió)."""
    print(f"\nID: {ident}")
    print("Resuelto" if resuelto else "Sin solución")
    extra = f"  (proceso {proceso})" if proceso is not None else ""
    print(f"Tiempo parcial: {segundos:.6f} segundos{extra}", flush=True)


# --------------------------------------------------------------------------
# Cola dinámica de IDs (rank 0 de un comunicador)
# --------------------------------------------------------------------------
class ServidorIDs:
    """Cola de tareas (ident, tablero) atendida por el rank 0 de `comm`.

    Protocolo: cada proceso remoto envía ("pedir", resultado_anterior|None) y
    recibe ("tarea", ident, tablero) o ("fin",). El rank 0 también extrae
    tareas directamente con tomar() y llama a servir() desde su gancho para
    atender a los demás mientras resuelve.
    """

    def __init__(self, comm, seleccionados, al_recibir=None):
        self.comm = comm
        self.tareas = deque(seleccionados)
        self.total = len(self.tareas)
        self.resultados = {}  # ident -> (resuelto, segundos, solucion, proceso)
        self.fin_enviados = 0
        self.remotos = comm.size - 1
        self.al_recibir = al_recibir

    def tomar(self):
        return self.tareas.popleft() if self.tareas else None

    def registrar(self, ident, resuelto, segundos, solucion, proceso):
        self.resultados[ident] = (resuelto, segundos, solucion, proceso)
        if self.al_recibir:
            self.al_recibir(ident, resuelto, segundos, proceso)

    def servir(self):
        """Atiende sin bloquear todas las peticiones pendientes."""
        estado = MPI.Status()
        while self.comm.Iprobe(source=MPI.ANY_SOURCE, status=estado):
            origen = estado.Get_source()
            mensaje = self.comm.recv(source=origen)
            if mensaje[1] is not None:
                ident, resuelto, segundos, solucion = mensaje[1]
                self.registrar(ident, resuelto, segundos, solucion, origen)
            if self.tareas:
                ident, tablero = self.tareas.popleft()
                self.comm.send(("tarea", ident, tablero), dest=origen)
            else:
                self.comm.send(("fin",), dest=origen)
                self.fin_enviados += 1

    def completo(self):
        return (len(self.resultados) == self.total
                and self.fin_enviados == self.remotos)

    def esperar_todo(self):
        while not self.completo():
            self.servir()
            time.sleep(0.0005)


def pedir_trabajo(comm, resultado_anterior):
    """Lado remoto del protocolo de ServidorIDs. Devuelve la tarea o None."""
    comm.send(("pedir", resultado_anterior), dest=0)
    mensaje = comm.recv(source=0)
    if mensaje[0] == "fin":
        return None
    return mensaje[1], mensaje[2]


# --------------------------------------------------------------------------
# Ramas de un tablero dentro de un comunicador
# --------------------------------------------------------------------------
class GrupoRamas:
    """Reparte las ramas de un tablero entre los procesos de `comm`.

    - El rank 0 de `comm` es el líder: genera las ramas, las asigna de forma
      dinámica (cuando un proceso termina una rama recibe otra), explora ramas
      él mismo y atiende mensajes desde su gancho.
    - Los demás procesos ejecutan trabajar().
    - Cuando alguien encuentra la solución, el líder envía ("stop",) a los que
      siguen buscando y estos abortan; el tablero termina cuando todos los
      procesos que tenían una rama contestaron.
    - `gancho_extra` (opcional, solo líder) se invoca junto con el gancho de
      búsqueda; el híbrido lo usa para atender la cola global de IDs.
    """

    def __init__(self, comm, ramas_por_proceso=4, gancho_extra=None, cada=1000):
        self.comm = comm
        self.ramas_por_proceso = ramas_por_proceso
        self.gancho_extra = gancho_extra
        self.cada = cada
        self.cola = deque()
        self.ocupados = set()
        self.encontrada = None

    # ---- líder ----------------------------------------------------------
    def _enviar(self, destino):
        self.comm.send(("rama", self.cola.popleft()), dest=destino)
        self.ocupados.add(destino)

    def _detener(self):
        for destino in self.ocupados:
            self.comm.send(("stop",), dest=destino)

    def _procesar(self, origen, mensaje):
        _, resuelto, tablero = mensaje
        self.ocupados.discard(origen)
        if self.encontrada is not None:
            return
        if resuelto:
            self.encontrada = tablero
            self._detener()
        elif self.cola:
            self._enviar(origen)

    def _servir(self, bloquear=False):
        estado = MPI.Status()
        if bloquear:
            mensaje = self.comm.recv(source=MPI.ANY_SOURCE, status=estado)
            self._procesar(estado.Get_source(), mensaje)
        while self.comm.Iprobe(source=MPI.ANY_SOURCE, status=estado):
            origen = estado.Get_source()
            self._procesar(origen, self.comm.recv(source=origen))

    def _gancho_lider(self):
        self._servir()
        if self.gancho_extra:
            self.gancho_extra()
        return self.encontrada is not None

    def resolver_tablero(self, original):
        """Solo el líder. Devuelve (resuelto, solucion|None, segundos)."""
        inicio = time.perf_counter()
        n = self.comm.size
        self.encontrada = None
        self.ocupados = set()
        self.cola = deque(generar_ramas(original,
                                        max(1, self.ramas_por_proceso * n)))
        for destino in range(1, n):
            if self.cola:
                self._enviar(destino)
        while self.cola and self.encontrada is None:
            rama = self.cola.popleft()
            if buscar(rama, self._gancho_lider, self.cada):
                self.encontrada = rama
                self._detener()
            self._servir()
        while self.ocupados:
            self._servir(bloquear=True)
        return (self.encontrada is not None, self.encontrada,
                time.perf_counter() - inicio)

    def terminar(self):
        """Solo el líder: avisa a los demás que ya no habrá más tableros."""
        for destino in range(1, self.comm.size):
            self.comm.send(("fin",), dest=destino)

    # ---- demás procesos ---------------------------------------------------
    def _gancho_trabajador(self):
        if self.comm.Iprobe(source=0):
            self.comm.recv(source=0)  # solo puede ser ("stop",)
            return True
        return False

    def trabajar(self):
        while True:
            mensaje = self.comm.recv(source=0)
            if mensaje[0] == "fin":
                return
            if mensaje[0] == "stop":
                continue  # parada atrasada de un tablero ya terminado
            rama = mensaje[1]
            resultado = buscar(rama, self._gancho_trabajador, self.cada)
            if resultado:
                self.comm.send(("res", True, rama), dest=0)
            else:  # sin solución en la rama, o abortada
                self.comm.send(("res", False, None), dest=0)


# --------------------------------------------------------------------------
# Argumentos y selección de tableros (igual que baseline_secuencial.py)
# --------------------------------------------------------------------------
def argumentos_comunes(descripcion):
    import argparse
    parser = argparse.ArgumentParser(description=descripcion)
    parser.add_argument("--archivo", type=Path, default=RAIZ / "seeds.txt",
                        help="archivo de seeds (por defecto: seeds.txt de la raíz del proyecto)")
    seleccion = parser.add_mutually_exclusive_group()
    seleccion.add_argument("--id", "--seed", dest="id",
                           help="resolver solo la seed con este ID")
    seleccion.add_argument("--all", action="store_true",
                           help="resolver todos los seeds (opción por defecto)")
    return parser


def seleccionar(parser, args):
    """Devuelve la lista [(id, tablero)] pedida (solo el rank 0 la necesita)."""
    seeds = leer_seeds(args.archivo)
    if not seeds:
        parser.error(f"no se encontraron seeds en {args.archivo}")
    if args.id:
        if args.id not in seeds:
            parser.error(f"ID '{args.id}' no existe. Disponibles: {', '.join(seeds)}")
        return [(args.id, seeds[args.id])]
    return list(seeds.items())


def informe_final(seleccionados, resultados, total_real, procesos, extra=""):
    """Imprime totales y verifica las soluciones. `resultados`: ident ->
    (resuelto, segundos, solucion)."""
    originales = dict(seleccionados)
    suma = sum(r[1] for r in resultados.values())
    validas = sum(1 for ident, r in resultados.items()
                  if r[0] and es_solucion_valida(r[2], originales[ident]))
    print(f"\nTiempo total (real): {total_real:.6f} segundos")
    print(f"Suma de tiempos parciales: {suma:.6f} segundos (informativo)")
    print(f"Procesos: {procesos}{extra}")
    print(f"IDs procesados: {len(resultados)}/{len(seleccionados)}")
    print(f"Soluciones verificadas: {validas}/{len(seleccionados)}", flush=True)
    return validas == len(seleccionados) and len(resultados) == len(seleccionados)
