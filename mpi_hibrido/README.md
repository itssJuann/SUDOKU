# Tarea 3: combinar tableros y ramas

Los N procesos se dividen en **grupos** con `Comm.Split` (bloques contiguos de tamaño balanceado):

- **Entre grupos** (reparto de IDs): el líder de cada grupo pide el siguiente ID al proceso 0 (cola dinámica, igual que en `mpi_por_tableros`). Cada grupo trabaja en un tablero a la vez.
- **Dentro de un grupo** (reparto de ramas): el líder genera las ramas del tablero y las reparte dinámicamente entre los procesos del grupo con parada anticipada (igual que en `mpi_por_ramas`, pero sobre el comunicador del grupo).
- El proceso 0 es líder del grupo 0, explora ramas y atiende desde su gancho tanto a su grupo como a los demás líderes. Todos los procesos trabajan.

`--tam-grupo T` fija el tamaño objetivo: hay `max(1, N // T)` grupos (tamaños que difieren como mucho en 1). `T = 1` es repartir solo tableros; `T = N`, solo ramas.

## Cómo elegir el tamaño de los grupos

Hay una tensión: grupos pequeños (muchos grupos) tienen poca comunicación y aprovechan bien los 30 IDs, pero al final puede quedar un grupo resolviendo un tablero lento mientras los demás esperan; grupos grandes balancean mejor cada tablero (las ramas de un tablero lento se reparten) pero tienen más mensajes y trabajo especulativo. No hay un valor universal: depende de N y del equipo, así que se **mide**:

```
docker run --rm -v "$(pwd):/app" augustosalazar/slim-mpi:2 python /app/medir_comparacion.py --n N --barrido-grupos 1,2,4
```

(usa como candidatos los divisores razonables de N; cada uno se repite 3 veces y se toma la mediana). Se elige el tamaño con menor mediana y se anota en `../INFORME.md`. Valor por defecto del código: `--tam-grupo 2`.

## Ejecutar con el contenedor

Desde la carpeta raíz del proyecto, con `N` igual al valor de la calibración y `T` al tamaño de grupo elegido.

macOS (Terminal):

```
docker run --rm -v "$(pwd):/app" augustosalazar/slim-mpi:2 mpiexec --allow-run-as-root --use-hwthread-cpus --oversubscribe -n N python /app/mpi_hibrido/mpi_hibrido.py --all --tam-grupo T
```

Windows (PowerShell): igual, con `-v "${PWD}:/app"`.

Un solo tablero: `--id 7`. Imprime tiempo total real, `IDs procesados: 30/30` y la verificación de soluciones.
