# Tarea 2: repartir ramas de cada tablero

El proceso 0 lee los IDs **en orden** y resuelve **un tablero a la vez**; las ramas de ese tablero se exploran en paralelo.

1. **Ramas**: se expanden por niveles las primeras casillas vacías (en el mismo orden que el backtracking serial), conservando solo los valores válidos, hasta tener al menos `--ramas-por-proceso × N` ramas (por defecto 4 × N). Cada rama es un tablero con ese prefijo ya colocado.
2. **Reparto dinámico**: cada proceso recibe una rama; al terminarla (sin solución) recibe otra. Así no depende de que todas las ramas cuesten lo mismo.
3. **Parada anticipada**: el proceso que encuentra la solución la envía al proceso 0, que manda `stop` a quienes siguen buscando; estos revisan mensajes cada ~1000 nodos y abortan. El tablero termina cuando todos contestaron, y recién entonces empieza el siguiente.
4. El proceso 0 también explora ramas (y atiende mensajes desde el gancho de su búsqueda), así que **los N procesos trabajan**.

Imprime estado y tiempo parcial de cada ID al terminarlo, el tiempo total real (`MPI.Wtime()` desde el inicio del reparto hasta tener los 30 tableros), `IDs procesados: 30/30` y la verificación de las soluciones.

## Ejecutar con el contenedor

Desde la carpeta raíz del proyecto, con `N` igual al valor de la calibración.

macOS (Terminal):

```
# un tablero
docker run --rm -v "$(pwd):/app" augustosalazar/slim-mpi:2 mpiexec --allow-run-as-root --use-hwthread-cpus --oversubscribe -n N python /app/mpi_por_ramas/mpi_por_ramas.py --id 7
# los 30 tableros
docker run --rm -v "$(pwd):/app" augustosalazar/slim-mpi:2 mpiexec --allow-run-as-root --use-hwthread-cpus --oversubscribe -n N python /app/mpi_por_ramas/mpi_por_ramas.py --all
```

Windows (PowerShell): igual, con `-v "${PWD}:/app"`.

`--ramas-por-proceso K` (opcional) cambia la granularidad (más ramas = mejor balance pero más mensajes).

## Resultados

Se registran en `../INFORME.md`.
