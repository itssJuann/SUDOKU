# Informe de resultados

## Entorno

- Equipo: MacBook Pro, chip Apple M1 Pro, 16 GB de RAM
- Núcleos de la CPU: 10 (8 de rendimiento + 2 de eficiencia), sin hilos adicionales por núcleo
- Procesadores visibles en el contenedor (`nproc`, según Docker Desktop): 10
- Versión del contenedor: augustosalazar/slim-mpi:2
- Repeticiones por medición: 3 (se reporta la mediana)
- Valor común de `N` (calibración con `detectar_procesos_mpi.py`): 8 (mediana 0,554 s)
- Tamaño de grupo del híbrido (`--tam-grupo`): 2 (4 grupos de 2 procesos)
- Ramas mínimas por proceso (`--ramas-por-proceso`): 4

## Procedimiento

Todas las mediciones usan el mismo `seeds.txt` (30 tableros), el mismo equipo y el mismo contenedor. `mpiexec` se ejecuta con `--allow-run-as-root --use-hwthread-cpus --oversubscribe`. Cada ejecución verifica que se procesen los 30 IDs y que las 30 soluciones sean válidas.

```
# N (calibración)
docker run --rm -v "$(pwd):/app" augustosalazar/slim-mpi:2 python /app/detectar_procesos_mpi.py
# tamaño de grupo del híbrido
docker run --rm -v "$(pwd):/app" augustosalazar/slim-mpi:2 python /app/medir_comparacion.py --n N --barrido-grupos 1,2,4
# comparación final (serial + tres versiones MPI, 3 repeticiones)
docker run --rm -v "$(pwd):/app" augustosalazar/slim-mpi:2 python /app/medir_comparacion.py --n N --tam-grupo T
```

(En PowerShell: `-v "${PWD}:/app"`.)

## Elección del tamaño de grupo (híbrido)

| Tamaño de grupo | Grupos | Mediana (s) |
| ---: | ---: | ---: |
| 1 | 8 | 10,28 |
| 2 | 4 | 9,61 |
| 4 | 2 | 9,79 |
| 8 | 1 | 11,60 |

Tamaño elegido y motivo: 2, por tener la menor mediana. Los tamaños 2 y 4 quedan casi empatados (diferencia de 0,18 s); los extremos son peores. Con grupos de 1 proceso (solo reparto de tableros) se pierde tiempo al final, cuando quedan pocos IDs y algunos procesos esperan; con un único grupo de 8 (solo reparto de ramas) cada tablero exige más mensajes y búsqueda especulativa.

## Comparación final con el mismo `N`

| Implementación | Caso | Procesos | Mediana del tiempo total (s) | Aceleración frente a secuencial |
| --- | --- | ---: | ---: | ---: |
| Secuencial | Todos los IDs | 1 | 62,71 | 1,00 |
| MPI por tableros | Todos los IDs | 8 | 10,27 | 6,11 |
| MPI por ramas | Todos los IDs, uno después de otro | 8 | 11,72 | 5,35 |
| MPI híbrido | Todos los IDs | 8 | 9,51 | 6,60 |

Aceleración = tiempo secuencial / tiempo MPI; eficiencia = aceleración / N (por tableros 76 %, por ramas 67 %, híbrido 82 %). El tiempo MPI es tiempo real (`MPI.Wtime()`) desde el inicio del reparto hasta recibir los 30 resultados, no la suma de los tiempos de los procesos.

## Conclusiones

- **Menor tiempo para los 30 tableros:** el híbrido, con 9,51 s frente a 62,71 s del secuencial: el tiempo bajó cerca de un 85 % (aceleración de 6,60 con 8 procesos, eficiencia del 82 %). Le siguen por tableros (10,27 s) y por ramas (11,72 s).
- **Efecto de la comunicación y de la duración desigual de los tableros:**
  - Por tableros hay muy poca comunicación (un mensaje de ida y vuelta por tablero), pero el tiempo queda acotado por el tablero más lento y por la cola final, cuando quedan pocos IDs y procesos libres esperan.
  - Por ramas cada tablero genera decenas de mensajes y no empieza el siguiente hasta que todos los procesos contestan, pero ningún proceso queda esperando a un tablero lento.
  - En ramas el trabajo total no coincide con el serial: se exploran ramas que el serial no visitaría antes de hallar la solución, o se llega antes a la rama que la contiene. Por eso la aceleración puede no ser lineal.
- **Repartir tableros frente a repartir ramas de cada uno (y el híbrido):** repartir tableros ganó a repartir ramas (10,27 s frente a 11,72 s) porque cada tablero lo resuelve un solo proceso sin coordinación y los 30 IDs dan trabajo de sobra para ocupar los 8 procesos. Repartir ramas obliga a terminar un tablero, con sus mensajes y su parada anticipada, antes de empezar el siguiente, y parte del trabajo de las ramas es especulativo. El híbrido combina lo mejor de ambos: usa los IDs para mantener ocupados los grupos y las ramas para repartir mejor los tableros lentos, y por eso obtuvo el menor tiempo.
- **Límite del hardware:** el equipo tiene 10 núcleos (8 de rendimiento y 2 de eficiencia). La calibración eligió N = 8: con N = 9 y 10 entran los núcleos de eficiencia, que son más lentos, y el tiempo sube (0,733 s y 0,664 s frente a 0,554 s). Por eso la aceleración máxima ideal es cercana a 8 y la obtenida (6,60 en el híbrido) queda por debajo.
