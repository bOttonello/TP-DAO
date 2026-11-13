# Patitas

Patitas es el sistema que desarrollamos para administrar una red de clínicas
veterinarias conectadas con un laboratorio central. Desde el comienzo decidimos
que el proyecto no se limitara a registrar clientes y atenciones: también
necesitábamos cubrir la derivación de estudios, el traslado seguro de las
muestras y su seguimiento desde la extracción hasta la carga del resultado.

Usamos **SQLite** porque es el motor solicitado por la cátedra y porque nos
permite tener una aplicación autocontenida, sin instalar un servidor de base de
datos. Sobre SQLite trabajamos con SQLAlchemy 2 para el mapeo de los objetos y
con Alembic para mantener la estructura de la base mediante migraciones. La API
está desarrollada con FastAPI y Pydantic.

También incorporamos una interfaz web responsive, servida por el mismo backend.
Desde ella podemos trabajar con clientes, pacientes, turnos, atenciones,
derivaciones, muestras, remitos, envíos, resultados, facturas, reportes y
catálogos sin depender de Swagger para las operaciones habituales.

## Funcionalidades que desarrollamos

- Administración de clientes, mascotas e historias clínicas.
- Agenda de profesionales con control de superposición de turnos activos.
- Registro de consultas, controles y urgencias como atenciones veterinarias.
- Control de las vacunas obligatorias pendientes al registrar una atención.
- Órdenes de derivación con uno o varios análisis de laboratorio.
- Extracción, empaquetado y traslado de muestras biológicas.
- Gestión de contenedores isotérmicos, precintos sanitarios y remitos biológicos.
- Cadena de custodia inmutable con actor, ubicación, fecha y número de secuencia.
- Recepción en el laboratorio con control del precinto y de la temperatura.
- Rechazo automático y definitivo de las muestras que dejan de ser viables.
- Registro de resultados solamente para muestras recibidas y viables.
- Facturación con componentes clínicos, de laboratorio e insumos.
- Cinco reportes clínicos, logísticos y contables.

## Recorrido principal de una muestra

El flujo comienza con la atención de una mascota. Si el profesional necesita
un estudio de laboratorio, emite una orden de derivación y se extrae la muestra
correspondiente. Luego la muestra se acondiciona en un contenedor isotérmico,
se coloca un precinto sanitario y se genera el remito biológico. Durante el
traslado registramos los eventos de custodia y, cuando el laboratorio recibe el
envío, controla que tanto el precinto como la temperatura sean correctos.

```text
Cliente -> Mascota -> Historia clínica -> Atención
                                      |
                                      v
                            Orden de derivación
                                      |
                                      v
                              Muestra extraída
                                      |
                                      v
       Contenedor + Precinto + Remito biológico
                                      |
                                      v
                  Envío y eventos de custodia
                                      |
                         +------------+------------+
                         |                         |
                         v                         v
                 Recepción viable          Muestra rechazada
                         |                 (fin del proceso)
                         v
                Resultado de análisis
```

Si el precinto llega roto o las temperaturas registradas quedan fuera del rango
admitido, rechazamos la muestra. Ese rechazo se conserva como parte de la
trazabilidad y no se puede volver atrás para cargar un resultado sobre una
muestra que ya no es viable.

## Patrones de diseño

### State

Aplicamos State al ciclo de vida de la muestra y del remito. En lugar de cambiar
sus estados mediante asignaciones libres, `CicloVidaMuestra` y
`CicloVidaRemito` delegan cada operación en un objeto que representa el estado
actual. Cada estado sabe qué acciones permite y cuáles debe rechazar.

```text
EXTRAÍDA -> EMPAQUETADA -> EN TRÁNSITO -> RECIBIDA -> ANALIZADA
                                  |
                                  +-> RECHAZADA
```

`ANALIZADA` y `RECHAZADA` son estados finales. Esto impide, por ejemplo, que
una muestra recién extraída se reciba en el laboratorio sin pasar antes por el
empaquetado y el transporte, o que una muestra rechazada vuelva a considerarse
viable.

El remito sigue un recorrido relacionado, pero independiente:
`BORRADOR -> EMITIDO -> EN TRÁNSITO -> RECIBIDO`, con una salida hacia
`RECHAZADO` durante la recepción.

### Singleton

Implementamos Singleton en `RegistroEstados`. Este registro mantiene una sola
instancia de cada objeto State y es seguro frente al acceso desde distintos
hilos. De esta manera concentramos el catálogo de estados en un único lugar y
podemos reconstruir el ciclo de vida a partir del valor almacenado en la base
sin crear estados duplicados.

La existencia de un único laboratorio central responde a otra regla: la
reforzamos en SQLite mediante una clave única. Aunque ambas ideas hablan de una
sola instancia, el patrón Singleton del proyecto es `RegistroEstados`.

## Reglas de negocio que consideramos importantes

- Toda mascota debe estar asociada a un cliente responsable.
- Al crear una mascota también creamos su historia clínica.
- En un turno, el horario de inicio debe ser anterior al horario de finalización.
- Un profesional no puede tener dos turnos activos superpuestos.
- Cuando una atención nace de un turno, hacemos coincidir la mascota, la
  clínica, el profesional y el tipo de atención. También comprobamos que el
  turno haya comenzado y que siga disponible.
- Al registrar una atención calculamos las vacunas obligatorias pendientes y
  conservamos ese resultado como parte de la atención.
- No admitimos aplicaciones de vacunas en el futuro ni antes de la edad mínima.
  Para los refuerzos respetamos primero la próxima dosis indicada y, si no
  existe, usamos el intervalo general de la vacuna.
- Una orden de derivación debe incluir al menos un análisis.
- Una muestra debe respetar el tipo solicitado y no puede incorporarse dos
  veces al mismo proceso.
- Un contenedor no puede superar su capacidad ni formar parte de dos remitos
  activos al mismo tiempo.
- Si el precinto llega roto, la muestra pasa automáticamente a `RECHAZADA`.
- Una muestra rechazada no puede volver a un estado viable ni recibir resultados.
- Cada cambio de estado genera un evento nuevo. Los eventos anteriores no se
  editan ni se eliminan.
- El estado actual de la muestra o del remito debe coincidir con el último
  evento registrado en su historial.
- Calculamos en el backend el subtotal de cada componente y el total de la
  factura. El descuento está contemplado en el modelo y actualmente se emite en cero.

Las reglas principales viven en los servicios. Para las invariantes más
delicadas también agregamos restricciones, índices y triggers en SQLite. Así
evitamos que una modificación directa sobre la base deje datos incompatibles con
el comportamiento de la aplicación.

La trazabilidad puede consultarse desde estos endpoints:

- `GET /api/muestras/{muestra_id}/trazabilidad`
- `GET /api/remitos/{remito_id}/trazabilidad`

## Reportes

Desarrollamos cinco reportes no triviales. Todos permiten aplicar filtros por
fecha y, cuando corresponde, por clínica.

| Reporte | Endpoint | Información |
|---|---|---|
| Atenciones y derivaciones | `GET /api/reportes/atenciones-derivaciones` | Totales por tipo, derivaciones y porcentaje derivado |
| Muestras rechazadas | `GET /api/reportes/muestras-rechazadas` | Motivos, cantidades y tasa sobre muestras enviadas |
| Tratamientos y vacunas | `GET /api/reportes/tratamientos-vacunas` | Tratamientos aplicados y vacunas obligatorias pendientes |
| Facturación | `GET /api/reportes/facturacion` | Importe bruto, descuentos prorrateados y neto por clínica o componente |
| Tiempos de muestras | `GET /api/reportes/tiempos-muestras` | Tránsito, procesamiento, demoras y excesos sobre el objetivo |

## Tecnologías

- Python 3.12 o superior
- FastAPI y Pydantic
- SQLAlchemy 2
- SQLite 3
- Alembic
- Pytest y Ruff
- HTML, CSS y JavaScript nativos
- Docker Compose

## Ejecución local

No hace falta instalar un servidor de base de datos. Alembic crea y actualiza
`patitas.db` dentro de la carpeta del proyecto.

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
python -m alembic upgrade head
python -m uvicorn backend.main:app --reload
```

Después de iniciar la aplicación podemos acceder a:

- Interfaz principal: `http://localhost:8000/`
- Documentación interactiva: `http://localhost:8000/docs`
- Estado del servicio: `http://localhost:8000/api/salud`

El frontend no necesita una instalación separada porque utiliza HTML, CSS y
JavaScript nativos y se comunica con `/api` desde el mismo origen.

## Ejecución con Docker

Primero copiamos la configuración de ejemplo:

```powershell
Copy-Item .env.example .env
```

Luego construimos e iniciamos el contenedor:

```powershell
docker compose up --build -d
```

La migración se aplica al iniciar y la base queda persistida en el volumen
`patitas_data`, ubicado en `/data/patitas.db` dentro del contenedor.

## Pruebas y calidad

Las pruebas unitarias trabajan con SQLite en memoria para mantenerse rápidas y
aisladas. Además, las pruebas integradas crean bases temporales mediante Alembic
y comprueban las migraciones, los triggers, la agenda, la vacunación, la
trazabilidad, el flujo principal y los reportes sin alterar `patitas.db`.

```powershell
python -m pytest
python -m ruff check .
```

## Organización del proyecto

```text
TPDAO/
├── backend/          # API, dominio, persistencia y reglas de negocio
│   ├── api/          # Endpoints HTTP
│   ├── core/         # Configuración, sesión y manejo de errores
│   ├── domain/       # State, Singleton y ciclos de vida
│   ├── models/       # Entidades y relaciones de SQLAlchemy
│   ├── services/     # Casos de uso y reportes
│   ├── main.py       # Creación de la aplicación FastAPI
│   └── schemas.py    # Datos de entrada y validaciones básicas
├── frontend/         # Interfaz web responsive
├── alembic/          # Esquema inicial y migraciones de SQLite
├── docs/             # Documentación y decisiones de arquitectura
└── tests/            # Pruebas unitarias e integradas
```
