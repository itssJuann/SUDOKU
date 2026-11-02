# Tarea 1: repartir tableros

Cada ID de `seeds.txt` es una tarea. Se asignan **dinámicamente**: el proceso 0 guarda la cola de IDs; cuando un proceso termina su tablero pide el siguiente. Así los tableros rápidos (~2 s) y lentos (~10 s) se balancean solos, mejor que un reparto fijo (ID % N).

- Cada tablero lo resuelve **un solo proceso** con `resolver_con_tiempo` de `../sudoku.py` (los procesos 1..N-1).
- El proceso 0 también resuelve tableros (con el mismo backtracking, más un "gancho" que cada ~1000 nodos atiende las peticiones de los demás), de modo que **los N procesos trabajan**.
- Los resultados (estado, tiempo parcial, solución) llegan al proceso 0, que los imprime según llegan, verifica que cada solución sea un Sudoku válido que respeta las pistas y confirma `IDs procesados: 30/30`.
- **Tiempo total (real)**: `MPI.Wtime()` desde que arranca el reparto (tras un `Barrier`) hasta que el proceso 0 recibió los 30 resultados. No es la suma de los tiempos parciales (esa suma se imprime solo como dato informativo).

## Ejecutar con el contenedor

Desde la carpeta raíz del proyecto (`mpi_sudoku_solver`), con `N` igual al valor que dio `detectar_procesos_mpi.py`.

macOS (Terminal):

```
docker run --rm -v "$(pwd):/app" augustosalazar/slim-mpi:2 mpiexec --allow-run-as-root --use-hwthread-cpus --oversubscribe -n N python /app/mpi_por_tableros/mpi_por_tableros.py --all
```

Windows (PowerShell):

```
docker run --rm -v "${PWD}:/app" augustosalazar/slim-mpi:2 mpiexec --allow-run-as-root --use-hwthread-cpus --oversubscribe -n N python /app/mpi_por_tableros/mpi_por_tableros.py --all
```

Un solo tablero: cambia `--all` por `--id 7`. Otro archivo: `--archivo /app/mis_seeds.txt`.
