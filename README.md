# HuellaVet

HuellaVet es el backend que desarrollé para administrar una red de clínicas
veterinarias y su laboratorio central. El foco del sistema no está solamente en
la atención de la mascota: también resuelve la derivación de estudios, el
transporte seguro de muestras y la trazabilidad completa desde la extracción
hasta la publicación del resultado.

Uso **SQLite** como base de datos, de acuerdo con los requisitos de la cátedra.
El sistema queda autocontenido en un único archivo, sin necesidad de instalar
un servidor, y conserva transacciones, claves foráneas, índices y triggers para
las reglas críticas. La API está desarrollada con FastAPI, SQLAlchemy 2 y Alembic.

La aplicación incluye una interfaz web responsive, servida por el mismo
backend, para trabajar con clientes, pacientes, turnos, atenciones,
derivaciones, muestras, remitos, envíos, resultados, facturas, reportes y
catálogos sin tener que operar directamente sobre Swagger.

## Qué resuelve

- Alta y administración de clientes, mascotas e historias clínicas.
- Agenda de profesionales sin superposición de turnos activos.
- Consultas, controles y urgencias dentro de una única atención veterinaria.
- Control del esquema obligatorio de vacunación al registrar una atención.
- Órdenes de derivación con uno o varios análisis de laboratorio.
- Extracción, empaquetado y traslado de muestras biológicas.
- Contenedores isotérmicos, precintos sanitarios y remitos biológicos.
- Cadena de custodia inmutable con actor, ubicación, fecha y secuencia.
- Recepción en el laboratorio con control de precinto y temperatura.
- Rechazo automático y definitivo de muestras no viables.
- Registro de resultados únicamente para muestras recibidas y viables.
- Facturas con componentes clínicos, de laboratorio e insumos.
- Cinco reportes clínicos, logísticos y contables.

## Modelo del flujo principal

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

## Patrones de diseño

### State

La muestra y el remito no cambian de estado mediante asignaciones libres. Los
objetos `CicloVidaMuestra` y `CicloVidaRemito` delegan cada operación en un
estado concreto, que conoce qué transición está permitida.

```text
EXTRAÍDA -> EMPAQUETADA -> EN TRÁNSITO -> RECIBIDA -> ANALIZADA
                                  |
                                  +-> RECHAZADA
```

`RECHAZADA` y `ANALIZADA` son estados terminales. Si el precinto llega roto o
la temperatura sale del rango admitido, la recepción rechaza todas las muestras
del remito y ya no permite cargar resultados.

El remito recorre `BORRADOR -> EMITIDO -> EN TRÁNSITO -> RECIBIDO`, con una
salida a `RECHAZADO` durante la recepción.

### Singleton

`RegistroEstados` es un Singleton thread-safe que contiene una sola instancia
de cada estado posible. Así centralicé el mapa de estados, evité duplicaciones y
puedo reconstruir la máquina de estados a partir del valor guardado en la base.

La regla de un único laboratorio central también está reforzada en SQLite
mediante una clave única.

## Validaciones importantes

- Toda mascota debe estar asociada a un cliente responsable.
- Cada mascota recibe automáticamente una historia clínica.
- El inicio de un turno debe ser anterior al final.
- Dos turnos activos del mismo profesional no se pueden superponer.
- Una atención guarda una foto del estado de las vacunas obligatorias en ese
  momento, incluso si el catálogo cambia después.
- Toda orden de derivación debe solicitar al menos un análisis.
- Una muestra sólo se puede incluir una vez y debe respetar el tipo solicitado.
- Un contenedor no puede superar su capacidad ni utilizarse en dos remitos
  activos.
- Un precinto roto produce el estado `RECHAZADA` de forma automática.
- Una muestra rechazada no puede volver a un estado viable ni recibir un
  resultado.
- Cada transición crea un evento nuevo; los eventos existentes no se editan ni
  eliminan.
- Los importes de la factura se recalculan en el servidor, sin confiar en un
  total enviado por el cliente.

Estas reglas se aplican en el servicio de dominio y, para las invariantes más
críticas, también en SQLite mediante restricciones, índices parciales y triggers.

## Reportes

La API expone cinco reportes no triviales, todos con filtros opcionales por
fecha y clínica:

| Reporte | Endpoint | Información |
|---|---|---|
| Atenciones y derivaciones | `GET /api/reportes/atenciones-derivaciones` | Totales por tipo, derivaciones y porcentaje derivado |
| Muestras rechazadas | `GET /api/reportes/muestras-rechazadas` | Motivos, cantidades y tasa sobre muestras enviadas |
| Tratamientos y vacunas | `GET /api/reportes/tratamientos-vacunas` | Tratamientos aplicados y vacunas obligatorias pendientes |
| Facturación | `GET /api/reportes/facturacion` | Importe bruto, descuentos prorrateados y neto por clínica/componente |
| Tiempos de muestras | `GET /api/reportes/tiempos-muestras` | Tránsito, procesamiento, demoras y excesos sobre el objetivo |

## Tecnologías

- Python 3.12 o superior
- FastAPI y Pydantic
- SQLAlchemy 2
- SQLite 3
- Alembic
- Pytest y Ruff
- Docker Compose

## Ejecución con Docker

1. Copiar la configuración de ejemplo:

   ```powershell
   Copy-Item .env.example .env
   ```

2. Crear el contenedor. La migración se aplica automáticamente y la base queda
   persistida en el volumen Docker `huellavet_data` (`/data/huellavet.db`
   dentro del contenedor):

   ```powershell
   docker compose up --build -d
   ```

La documentación interactiva queda disponible en
`http://localhost:8000/docs` y el control de salud en
`http://localhost:8000/api/salud`.

La interfaz principal queda disponible en `http://localhost:8000/`.

## Ejecución local

No hace falta instalar ningún motor de base de datos. Alembic crea
`huellavet.db` en la carpeta del proyecto:

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
alembic upgrade head
uvicorn app.main:app --reload
```

Luego se abre `http://localhost:8000/` en el navegador. El frontend no
necesita una instalación separada: utiliza HTML, CSS y JavaScript nativos y se
comunica con `/api` en el mismo origen.

## Pruebas y calidad

Las pruebas usan SQLite en memoria para ser rápidas y aisladas. Cubren los
patrones, las transiciones válidas e inválidas, el rechazo por precinto roto,
la agenda, la vacunación, la trazabilidad, el flujo exitoso y los cinco
reportes.

```powershell
pytest
ruff check .
```

La migración de Alembic agrega protecciones propias de SQLite: control de
superposición de turnos, contenedor activo único, secuencias de custodia,
bloqueo de resultados inviables y triggers que impiden alterar o borrar el
historial.

## Estructura

```text
TPDAO/
├── app/
│   ├── api/          # Endpoints HTTP
│   ├── core/         # Configuración, sesión y errores
│   ├── domain/       # State, Singleton y reglas de ciclo de vida
│   ├── frontend/     # Interfaz web responsive
│   ├── models/       # Modelo relacional SQLAlchemy
│   ├── services/     # Casos de uso y reportes
│   ├── main.py       # Aplicación FastAPI
│   └── schemas.py    # Contratos de entrada
├── alembic/          # Migraciones SQLite
├── docs/             # Decisiones de arquitectura
└── tests/            # Pruebas unitarias e integradas
```

En [decisiones-arquitectura.md](docs/decisiones-arquitectura.md) dejé un
resumen adicional de las decisiones de dominio y persistencia.
