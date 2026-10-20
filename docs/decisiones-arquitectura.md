# Decisiones de arquitectura de Patitas

## Alcance

Patitas integra la atención clínica de una red veterinaria con la derivación de
análisis a un laboratorio central. El agregado crítico es la muestra biológica:
su estado solo puede avanzar mediante reglas explícitas y cada cambio genera un
evento de custodia que no puede editarse ni borrarse.

## Persistencia elegida: SQLite

Se eligió SQLite para cumplir el requisito de la cátedra y mantener el proyecto
fácil de ejecutar en cualquier equipo:

1. Transacciones ACID para cambiar estados y registrar su evento en una misma operación.
2. Restricciones relacionales y de unicidad para documentos, matrículas, códigos y relaciones 1:1.
3. Un archivo único, sin instalación ni administración de un servidor externo.
4. Índices parciales y triggers para reforzar la inmutabilidad, la agenda y la trazabilidad.

Las claves foráneas se activan en cada conexión y Alembic crea tanto las tablas
como las protecciones específicas de SQLite. En producción con múltiples
servidores de API habría que reevaluar el motor, pero para el alcance académico
y una única instancia SQLite resulta adecuado.

## Agregados principales

- **Cliente y mascota:** toda mascota tiene exactamente un responsable y una historia clínica.
- **Agenda y atención:** un turno pertenece a una clínica, un profesional y una mascota. La atención registra consulta, control o urgencia y deja constancia del esquema de vacunación.
- **Derivación:** una orden nace de una atención e incluye uno o más análisis solicitados. Cada muestra pertenece a una orden.
- **Custodia:** las muestras se agrupan en un contenedor isotérmico, protegido por un precinto único y documentado con un remito biológico. El envío registra el transporte físico.
- **Laboratorio:** la recepción valida precinto y temperatura. Un precinto roto rechaza automáticamente el remito y todas sus muestras, que ya no pueden analizarse.
- **Facturación:** una factura pertenece a un cliente y clínica, y desglosa componentes clínicos, de laboratorio e insumos.

## Patrones de diseño

### State

`CicloVidaMuestra` y `CicloVidaRemito` delegan cada operación en un objeto de
estado concreto. Así, una muestra analizada o rechazada no puede volver a
transitar y una muestra extraída no puede recibirse sin haber sido empaquetada y
despachada.

```text
EXTRAIDA -> EMPAQUETADA -> EN_TRANSITO -> RECIBIDA -> ANALIZADA
                                  |
                                  +-> RECHAZADA (precinto roto)
```

El remito sigue `BORRADOR -> EMITIDO -> EN_TRANSITO -> RECIBIDO`, con salida a
`RECHAZADO` durante la recepción.

### Singleton

`RegistroEstados` mantiene una única instancia thread-safe del catálogo de
objetos State. Los servicios reconstruyen la máquina desde el valor persistido
sin duplicar estados ni dispersar el mapa de transiciones.

## Invariantes

- No existe una mascota sin cliente responsable.
- No se aceptan turnos cuyo intervalo se superponga con otro turno activo del mismo profesional.
- Al registrar una atención se calcula y conserva qué vacunas obligatorias están pendientes.
- Un resultado solo puede cargarse para una muestra recibida y viable.
- Un precinto roto provoca rechazo; ese camino es terminal.
- Cada transición de una muestra genera un `EventoCustodia` en la misma transacción.
- Las transferencias intermedias agregan eventos `EN_TRANSITO -> EN_TRANSITO`, conservando custodio, ubicación y temperatura sin inventar un cambio de estado.
- `EventoCustodia` es append-only: SQLAlchemy bloquea modificaciones y SQLite instala un trigger que rechaza `UPDATE` y `DELETE`.
- Los importes de factura se calculan en el servidor a partir de sus componentes.

## Reportes implementados

1. **Atenciones y derivaciones:** cantidades por clínica y tipo de atención, con total y porcentaje derivado.
2. **Muestras rechazadas:** rechazos por clínica, motivo y período, incluyendo tasa sobre muestras enviadas.
3. **Tratamientos y vacunas pendientes:** tratamientos registrados y vacunas obligatorias vencidas o nunca aplicadas por mascota.
4. **Facturación desglosada:** importes por clínica y tipo de componente, separando atención y laboratorio.
5. **Tiempos de muestras:** promedio, mínimo y máximo de tránsito y procesamiento, además de muestras que exceden el tiempo estimado.
