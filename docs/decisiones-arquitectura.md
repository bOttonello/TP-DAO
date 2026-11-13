# Decisiones de arquitectura de Patitas

## Punto de partida

Desarrollamos Patitas para unir la atención clínica de una red veterinaria con
la derivación de estudios a un laboratorio central. Al analizar la consigna
vimos que la parte más sensible no era solamente registrar una consulta, sino
conservar la historia completa de cada muestra biológica.

Por ese motivo tratamos a la muestra y a su cadena de custodia como el centro
del modelo. Una muestra no puede saltar etapas ni cambiar de estado libremente,
y cada transición debe dejar un evento que indique qué ocurrió, cuándo, dónde y
bajo la responsabilidad de quién.

## Organización del backend

Separamos el backend por responsabilidades para que las reglas no quedaran
mezcladas con la comunicación HTTP o con la estructura de la base:

- En `api` recibimos las peticiones, abrimos las transacciones y armamos las
  respuestas.
- En `schemas.py` validamos la forma y los valores básicos de los datos de
  entrada con Pydantic.
- En `services` concentramos los casos de uso y las reglas que necesitan
  consultar varias entidades.
- En `domain` implementamos los ciclos de vida de muestras y remitos mediante
  State y Singleton.
- En `models` representamos con SQLAlchemy las tablas, relaciones y
  restricciones persistentes.
- En Alembic mantenemos el esquema inicial y los cambios posteriores de la base.

Con esta separación evitamos colocar reglas importantes en las rutas o en el
frontend. La interfaz solicita una operación, pero es el backend el que decide si
esa operación es válida.

## Persistencia con SQLite

Elegimos SQLite para cumplir el requisito de la cátedra y para que el proyecto
se pueda ejecutar en cualquier equipo sin instalar ni administrar un servidor
adicional. La información queda almacenada en un solo archivo y aun así contamos
con transacciones, claves foráneas, restricciones, índices y triggers.

Usamos SQLAlchemy como ORM. Las clases del modelo representan las tablas y la
sesión agrupa los cambios de cada caso de uso. Las rutas abren una transacción
con `with sesion.begin()`: si la operación termina correctamente se confirma de
forma automática y, si ocurre una excepción, se revierte.

Alembic se encarga de crear y actualizar la estructura de la base. Las
migraciones no solo crean tablas; también instalan protecciones específicas de
SQLite para las reglas que no queremos dejar solamente en la aplicación.

En cada conexión activamos las claves foráneas. Si el sistema tuviera que atender
muchas instancias de la API escribiendo al mismo tiempo, tendríamos que volver a
evaluar el motor. Para esta entrega y una instancia de la aplicación, SQLite
cubre lo que necesitamos.

## Partes principales del modelo

- **Cliente y mascota:** cada mascota tiene un responsable y una única historia
  clínica. Desde esa historia podemos recuperar sus atenciones.
- **Agenda y atención:** el turno relaciona una mascota, una clínica y un
  profesional dentro de un intervalo. La atención puede ser una consulta, un
  control o una urgencia y conserva el estado de vacunación observado en ese
  momento.
- **Derivación:** la orden nace de una atención e incluye uno o varios análisis
  solicitados. Las muestras se extraen para responder a esas solicitudes.
- **Transporte y custodia:** agrupamos las muestras en un contenedor isotérmico,
  colocamos un precinto único y emitimos un remito. El envío representa el
  traslado físico y los eventos dejan constancia de cada transferencia de
  custodia.
- **Laboratorio:** durante la recepción controlamos el precinto y las
  temperaturas. Si las condiciones no son correctas, rechazamos el remito y sus
  muestras y bloqueamos la carga de resultados sobre ellas.
- **Facturación:** la factura pertenece a un cliente y a una clínica. Sus
  componentes permiten separar los conceptos de atención, laboratorio e
  insumos.

## State para los ciclos de vida

Aplicamos State porque las acciones posibles dependen de la etapa en la que se
encuentra cada objeto. Un `CicloVidaMuestra` delega la operación en el estado
actual: una muestra extraída permite empaquetar, una empaquetada permite iniciar
el traslado y una recibida permite registrar los análisis. Las demás acciones se
rechazan.

```text
EXTRAÍDA -> EMPAQUETADA -> EN TRÁNSITO -> RECIBIDA -> ANALIZADA
                                  |
                                  +-> RECHAZADA
```

`ANALIZADA` y `RECHAZADA` son estados terminales. Con esto evitamos repartir
condicionales por distintos servicios y dejamos las transiciones permitidas en
un solo modelo de comportamiento.

El remito tiene su propio ciclo:
`BORRADOR -> EMITIDO -> EN TRÁNSITO -> RECIBIDO`. Durante la recepción también
puede terminar en `RECHAZADO`. Mantuvimos ambos ciclos separados porque el
remito es el documento del traslado y la muestra es el material biológico; se
relacionan, pero no representan lo mismo.

## Singleton para el registro de estados

Implementamos `RegistroEstados` como Singleton thread-safe. Los objetos State
no guardan información particular de una muestra: representan comportamientos
compartidos. Por eso no necesitamos crear una instancia nueva cada vez que
reconstruimos un ciclo de vida.

El registro mantiene las instancias canónicas, centraliza la correspondencia
entre el valor persistido y su objeto State y evita que el mapa de estados quede
duplicado en diferentes partes del sistema.

La regla de un único laboratorio central no depende de este patrón. Esa
unicidad es una regla de negocio protegida por una restricción en SQLite.

## Trazabilidad e inmutabilidad

Cada transición de una muestra crea un `EventoCustodia` dentro de la misma
transacción. Para el remito usamos `EventoRemito`. Además de conservar el estado
anterior y el nuevo, estos eventos permiten registrar ubicación, responsable,
fecha, temperatura y observaciones cuando corresponde.

Las transferencias durante un viaje son un caso particular: agregamos eventos
`EN_TRANSITO -> EN_TRANSITO`. No inventamos un estado nuevo porque la muestra
continúa en traslado, pero dejamos constancia del cambio de custodio o de
ubicación.

Protegemos el historial en dos niveles:

1. SQLAlchemy impide modificar o eliminar eventos ya persistidos.
2. SQLite instala triggers que rechazan `UPDATE` y `DELETE` sobre esos eventos.

También impedimos cambiar directamente el estado actual si no coincide con el
último evento válido. Esta segunda protección evita que una operación SQL por
fuera del servicio pueda adelantar o retroceder una muestra sin dejar rastro.

## Reglas que reforzamos en más de una capa

Validamos las operaciones en los servicios para poder devolver errores claros,
pero las invariantes más importantes también se encuentran protegidas en la
base. Entre ellas incluimos:

- Toda mascota debe tener un cliente responsable.
- Los turnos activos de un mismo profesional no pueden superponerse.
- Si una atención se genera desde un turno, deben coincidir mascota, clínica,
  profesional y tipo.
- Al registrar una atención calculamos y conservamos las vacunas obligatorias
  que estaban pendientes en esa fecha.
- Las aplicaciones futuras no intervienen en ese cálculo. Para un refuerzo
  tomamos primero la próxima dosis indicada y, si no existe, el intervalo
  configurado para la vacuna.
- Un contenedor no puede estar asociado a dos remitos activos.
- Un precinto roto lleva las muestras a un rechazo terminal.
- Solo aceptamos resultados para muestras recibidas y viables.
- Los eventos de trazabilidad no pueden modificarse ni eliminarse.
- El subtotal de cada componente y el total de la factura se calculan en el
  servidor. El modelo también controla que los importes sean consistentes.

Esta duplicación es intencional: el servicio protege el caso de uso y explica el
motivo del rechazo, mientras que SQLite evita que los datos pierdan coherencia
si alguien intenta saltear la aplicación.

## Reportes implementados

La consigna solicita por lo menos cuatro reportes no triviales. Desarrollamos
cinco para cubrir las áreas clínica, sanitaria, logística y contable:

1. **Atenciones y derivaciones:** agrupa cantidades por clínica y tipo de
   atención, e informa el porcentaje de atenciones derivadas.
2. **Muestras rechazadas:** muestra rechazos por clínica, motivo y período, junto
   con su tasa respecto de las muestras enviadas.
3. **Tratamientos y vacunas pendientes:** relaciona los tratamientos registrados
   con las vacunas obligatorias vencidas o nunca aplicadas de cada mascota.
4. **Facturación desglosada:** agrupa los importes por clínica y tipo de
   componente, diferenciando la atención de los servicios de laboratorio.
5. **Tiempos de muestras:** calcula promedios, mínimos y máximos de traslado y
   procesamiento, además de detectar muestras que superaron el tiempo esperado.

## Pruebas de las decisiones

No dejamos estas reglas solamente documentadas. Las pruebas unitarias comprueban
los patrones y los casos de uso, mientras que las pruebas integradas crean una
base SQLite temporal mediante Alembic y recorren el flujo real. También intentan
alterar directamente los estados y eventos para verificar que las restricciones
y los triggers rechacen esos cambios.

De esta forma podemos probar tanto el comportamiento normal de la API como la
protección que permanece activa aun cuando una operación no pasa por los
servicios.
