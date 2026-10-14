"""Esquema inicial SQLite de la red veterinaria y su trazabilidad.

Revision ID: 20261013_0001
Revises:
Create Date: 2026-10-13
"""

from collections.abc import Sequence

import app.models  # noqa: F401
from alembic import op
from app.core.database import Base

revision: str = "20261013_0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


TRIGGERS = (
    "tr_turnos_sin_superposicion_insert",
    "tr_turnos_sin_superposicion_update",
    "tr_eventos_custodia_inmutable_update",
    "tr_eventos_custodia_inmutable_delete",
    "tr_eventos_remito_inmutable_update",
    "tr_eventos_remito_inmutable_delete",
    "tr_eventos_custodia_validar_insert",
    "tr_eventos_custodia_sincronizar_insert",
    "tr_eventos_remito_validar_insert",
    "tr_eventos_remito_sincronizar_insert",
    "tr_ordenes_analisis_muestra_insert",
    "tr_ordenes_analisis_muestra_update",
    "tr_muestras_remito_coherente_insert",
    "tr_muestras_remito_coherente_update",
    "tr_muestras_remito_inmutable_update",
    "tr_remitos_estructura_inmutable_update",
    "tr_envios_remito_inmutable_update",
    "tr_recepciones_coherencia_insert",
    "tr_recepciones_inmutable_update",
    "tr_recepciones_inmutable_delete",
    "tr_resultados_muestra_viable_insert",
    "tr_resultados_muestra_viable_update",
)


def upgrade() -> None:
    conexion = op.get_bind()
    if conexion.dialect.name != "sqlite":
        raise RuntimeError("HuellaVet usa exclusivamente SQLite")

    # Esta revisión nació junto con los modelos. Las garantías que exceden los
    # CHECK/FK declarativos se agregan debajo mediante SQL nativo de SQLite.
    Base.metadata.create_all(bind=conexion, checkfirst=True)

    # Una conservadora no puede estar comprometida en dos remitos activos.
    op.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS uq_remitos_contenedor_activo
        ON remitos_biologicos (contenedor_id)
        WHERE estado IN ('borrador', 'emitido', 'en_transito')
        """
    )

    # SQLite no ofrece EXCLUDE: se comprueba el intervalo en INSERT y UPDATE.
    op.execute(
        """
        CREATE TRIGGER tr_turnos_sin_superposicion_insert
        BEFORE INSERT ON turnos
        FOR EACH ROW
        BEGIN
            SELECT RAISE(ABORT, 'El profesional no pertenece a la clinica')
             WHERE NOT EXISTS (
                SELECT 1 FROM profesionales_veterinarios AS p
                 WHERE p.id = NEW.profesional_id AND p.clinica_id = NEW.clinica_id
             );
            SELECT RAISE(ABORT, 'El profesional ya tiene un turno superpuesto')
             WHERE NEW.estado IN ('programado', 'confirmado')
               AND EXISTS (
                SELECT 1 FROM turnos AS t
                 WHERE t.profesional_id = NEW.profesional_id
                   AND t.estado IN ('programado', 'confirmado')
                   AND t.inicio < NEW.fin
                   AND t.fin > NEW.inicio
             );
        END
        """
    )
    op.execute(
        """
        CREATE TRIGGER tr_turnos_sin_superposicion_update
        BEFORE UPDATE OF profesional_id, clinica_id, inicio, fin, estado ON turnos
        FOR EACH ROW
        BEGIN
            SELECT RAISE(ABORT, 'El profesional no pertenece a la clinica')
             WHERE NOT EXISTS (
                SELECT 1 FROM profesionales_veterinarios AS p
                 WHERE p.id = NEW.profesional_id AND p.clinica_id = NEW.clinica_id
             );
            SELECT RAISE(ABORT, 'El profesional ya tiene un turno superpuesto')
             WHERE NEW.estado IN ('programado', 'confirmado')
               AND EXISTS (
                SELECT 1 FROM turnos AS t
                 WHERE t.profesional_id = NEW.profesional_id
                   AND t.id <> NEW.id
                   AND t.estado IN ('programado', 'confirmado')
                   AND t.inicio < NEW.fin
                   AND t.fin > NEW.inicio
             );
        END
        """
    )

    # Los historiales son append-only incluso mediante SQL directo o bulk.
    for tabla in ("eventos_custodia", "eventos_remito"):
        op.execute(
            f"""
            CREATE TRIGGER tr_{tabla}_inmutable_update
            BEFORE UPDATE ON {tabla}
            FOR EACH ROW
            BEGIN
                SELECT RAISE(ABORT, 'El historial es inmutable; agregue un evento');
            END
            """
        )
        op.execute(
            f"""
            CREATE TRIGGER tr_{tabla}_inmutable_delete
            BEFORE DELETE ON {tabla}
            FOR EACH ROW
            BEGIN
                SELECT RAISE(ABORT, 'El historial es inmutable; no se puede eliminar');
            END
            """
        )

    # Pertenencia, cronología, secuencia y máquina de estados de la muestra.
    op.execute(
        """
        CREATE TRIGGER tr_eventos_custodia_validar_insert
        BEFORE INSERT ON eventos_custodia
        FOR EACH ROW
        BEGIN
            SELECT RAISE(ABORT, 'La cadena de custodia no pertenece a la muestra')
             WHERE NOT EXISTS (
                SELECT 1 FROM cadenas_custodia AS c
                 WHERE c.id = NEW.cadena_custodia_id
                   AND c.muestra_id = NEW.muestra_id
             );
            SELECT RAISE(ABORT, 'El envio no corresponde al remito de la muestra')
             WHERE NEW.envio_id IS NOT NULL
               AND NOT EXISTS (
                SELECT 1 FROM envios AS e
                JOIN muestras_biologicas AS m ON m.id = NEW.muestra_id
                 WHERE e.id = NEW.envio_id AND e.remito_id = m.remito_id
             );
            SELECT RAISE(ABORT, 'Secuencia de custodia invalida')
             WHERE NEW.secuencia <> COALESCE((
                SELECT MAX(e.secuencia) FROM eventos_custodia AS e
                 WHERE e.muestra_id = NEW.muestra_id
             ), 0) + 1;
            SELECT RAISE(ABORT, 'La cadena debe comenzar en EXTRAIDA')
             WHERE NOT EXISTS (
                SELECT 1 FROM eventos_custodia AS e
                 WHERE e.muestra_id = NEW.muestra_id
             )
               AND NOT (
                    NEW.secuencia = 1
                    AND NEW.estado_anterior IS NULL
                    AND NEW.estado_nuevo = 'extraida'
                    AND NEW.tipo_evento = 'extraccion'
               );
            SELECT RAISE(ABORT, 'El estado anterior no coincide con el ultimo evento')
             WHERE EXISTS (
                SELECT 1 FROM eventos_custodia AS e
                 WHERE e.muestra_id = NEW.muestra_id
             )
               AND NEW.estado_anterior IS NOT (
                SELECT e.estado_nuevo FROM eventos_custodia AS e
                 WHERE e.muestra_id = NEW.muestra_id
                 ORDER BY e.secuencia DESC LIMIT 1
             );
            SELECT RAISE(ABORT, 'Transicion de muestra invalida')
             WHERE EXISTS (
                SELECT 1 FROM eventos_custodia AS e
                 WHERE e.muestra_id = NEW.muestra_id
             )
               AND NOT (
                    (NEW.estado_anterior = 'extraida'
                        AND NEW.estado_nuevo = 'empaquetada'
                        AND NEW.tipo_evento = 'empaquetado')
                    OR (NEW.estado_anterior = 'empaquetada'
                        AND NEW.estado_nuevo = 'en_transito'
                        AND NEW.tipo_evento = 'despacho')
                    OR (NEW.estado_anterior = 'en_transito'
                        AND NEW.estado_nuevo = 'en_transito'
                        AND NEW.tipo_evento = 'transferencia')
                    OR (NEW.estado_anterior = 'en_transito'
                        AND NEW.estado_nuevo = 'recibida'
                        AND NEW.tipo_evento = 'recepcion')
                    OR (NEW.estado_anterior = 'en_transito'
                        AND NEW.estado_nuevo = 'rechazada'
                        AND NEW.tipo_evento = 'rechazo')
                    OR (NEW.estado_anterior = 'recibida'
                        AND NEW.estado_nuevo = 'analizada'
                        AND NEW.tipo_evento = 'analisis')
               );
            SELECT RAISE(ABORT, 'La fecha no puede ser anterior al ultimo evento')
             WHERE EXISTS (
                SELECT 1 FROM eventos_custodia AS e
                 WHERE e.muestra_id = NEW.muestra_id
                   AND e.ocurrido_en > NEW.ocurrido_en
             );
            SELECT RAISE(ABORT, 'Una muestra rechazada debe indicar el motivo')
             WHERE NEW.estado_nuevo = 'rechazada'
               AND NOT EXISTS (
                SELECT 1 FROM muestras_biologicas AS m
                 WHERE m.id = NEW.muestra_id
                   AND length(trim(COALESCE(m.motivo_rechazo, ''))) > 0
             );
        END
        """
    )
    op.execute(
        """
        CREATE TRIGGER tr_eventos_custodia_sincronizar_insert
        AFTER INSERT ON eventos_custodia
        FOR EACH ROW
        BEGIN
            UPDATE muestras_biologicas
               SET estado_actual = NEW.estado_nuevo,
                   fecha_recepcion = CASE
                       WHEN NEW.estado_nuevo IN ('recibida', 'rechazada')
                           THEN NEW.ocurrido_en
                       ELSE fecha_recepcion
                   END,
                   fecha_analisis = CASE
                       WHEN NEW.estado_nuevo = 'analizada' THEN NEW.ocurrido_en
                       ELSE fecha_analisis
                   END,
                   actualizado_en = CURRENT_TIMESTAMP
             WHERE id = NEW.muestra_id;
        END
        """
    )

    # Ciclo append-only y secuencial del remito biológico.
    op.execute(
        """
        CREATE TRIGGER tr_eventos_remito_validar_insert
        BEFORE INSERT ON eventos_remito
        FOR EACH ROW
        BEGIN
            SELECT RAISE(ABORT, 'Secuencia de remito invalida')
             WHERE NEW.secuencia <> COALESCE((
                SELECT MAX(e.secuencia) FROM eventos_remito AS e
                 WHERE e.remito_id = NEW.remito_id
             ), 0) + 1;
            SELECT RAISE(ABORT, 'El historial debe comenzar en BORRADOR')
             WHERE NOT EXISTS (
                SELECT 1 FROM eventos_remito AS e WHERE e.remito_id = NEW.remito_id
             )
               AND NOT (
                    NEW.secuencia = 1
                    AND NEW.estado_anterior IS NULL
                    AND NEW.estado_nuevo = 'borrador'
                    AND NEW.tipo_evento = 'creacion'
               );
            SELECT RAISE(ABORT, 'El estado anterior del remito no coincide')
             WHERE EXISTS (
                SELECT 1 FROM eventos_remito AS e WHERE e.remito_id = NEW.remito_id
             )
               AND NEW.estado_anterior IS NOT (
                SELECT e.estado_nuevo FROM eventos_remito AS e
                 WHERE e.remito_id = NEW.remito_id
                 ORDER BY e.secuencia DESC LIMIT 1
             );
            SELECT RAISE(ABORT, 'Transicion de remito invalida')
             WHERE EXISTS (
                SELECT 1 FROM eventos_remito AS e WHERE e.remito_id = NEW.remito_id
             )
               AND NOT (
                    (NEW.estado_anterior = 'borrador'
                        AND NEW.estado_nuevo = 'emitido'
                        AND NEW.tipo_evento = 'emision')
                    OR (NEW.estado_anterior = 'emitido'
                        AND NEW.estado_nuevo = 'en_transito'
                        AND NEW.tipo_evento = 'despacho')
                    OR (NEW.estado_anterior = 'en_transito'
                        AND NEW.estado_nuevo = 'recibido'
                        AND NEW.tipo_evento = 'recepcion')
                    OR (NEW.estado_anterior = 'en_transito'
                        AND NEW.estado_nuevo = 'rechazado'
                        AND NEW.tipo_evento = 'rechazo')
               );
            SELECT RAISE(ABORT, 'La fecha no puede ser anterior al ultimo evento')
             WHERE EXISTS (
                SELECT 1 FROM eventos_remito AS e
                 WHERE e.remito_id = NEW.remito_id
                   AND e.ocurrido_en > NEW.ocurrido_en
             );
        END
        """
    )
    op.execute(
        """
        CREATE TRIGGER tr_eventos_remito_sincronizar_insert
        AFTER INSERT ON eventos_remito
        FOR EACH ROW
        BEGIN
            UPDATE remitos_biologicos
               SET estado = NEW.estado_nuevo, actualizado_en = CURRENT_TIMESTAMP
             WHERE id = NEW.remito_id;
        END
        """
    )

    # Una solicitud sólo puede consumir una muestra de su misma orden.
    for operacion in ("INSERT", "UPDATE OF muestra_id, orden_id"):
        sufijo = "insert" if operacion == "INSERT" else "update"
        proteger_resultado = (
            """
                SELECT RAISE(ABORT, 'No se puede cambiar la muestra de un resultado')
                 WHERE EXISTS (
                    SELECT 1 FROM resultados_analisis AS r
                     WHERE r.orden_analisis_id = OLD.id
                 )
                   AND NEW.muestra_id IS NOT OLD.muestra_id;
            """
            if sufijo == "update"
            else ""
        )
        op.execute(
            f"""
            CREATE TRIGGER tr_ordenes_analisis_muestra_{sufijo}
            BEFORE {operacion} ON ordenes_analisis
            FOR EACH ROW
            BEGIN
                SELECT RAISE(ABORT, 'La muestra debe pertenecer a la misma orden')
                 WHERE NEW.muestra_id IS NOT NULL
                   AND NOT EXISTS (
                    SELECT 1 FROM muestras_biologicas AS m
                     WHERE m.id = NEW.muestra_id AND m.orden_id = NEW.orden_id
                 );
                {proteger_resultado}
            END
            """
        )

    # El remito debe respetar origen, destino, capacidad y rango térmico.
    for operacion in ("INSERT", "UPDATE OF remito_id, orden_id"):
        sufijo = "insert" if operacion == "INSERT" else "update"
        op.execute(
            f"""
            CREATE TRIGGER tr_muestras_remito_coherente_{sufijo}
            BEFORE {operacion} ON muestras_biologicas
            FOR EACH ROW
            WHEN NEW.remito_id IS NOT NULL
            BEGIN
                SELECT RAISE(ABORT, 'El remito no coincide con origen o destino')
                 WHERE NOT EXISTS (
                    SELECT 1 FROM remitos_biologicos AS r
                    JOIN ordenes_derivacion AS o ON o.id = NEW.orden_id
                    JOIN atenciones_veterinarias AS a ON a.id = o.atencion_id
                     WHERE r.id = NEW.remito_id
                       AND r.laboratorio_destino_id = o.laboratorio_id
                       AND r.clinica_origen_id = a.clinica_id
                 );
                SELECT RAISE(ABORT, 'El contenedor no admite el rango termico')
                 WHERE NOT EXISTS (
                    SELECT 1 FROM remitos_biologicos AS r
                    JOIN contenedores AS c ON c.id = r.contenedor_id
                     WHERE r.id = NEW.remito_id
                       AND c.temperatura_min_c <= NEW.temperatura_min_c
                       AND c.temperatura_max_c >= NEW.temperatura_max_c
                 );
                SELECT RAISE(ABORT, 'Se excede la capacidad del contenedor')
                 WHERE (
                    SELECT COUNT(*) FROM muestras_biologicas AS m
                     WHERE m.remito_id = NEW.remito_id AND m.id <> NEW.id
                 ) >= (
                    SELECT c.capacidad_muestras FROM remitos_biologicos AS r
                    JOIN contenedores AS c ON c.id = r.contenedor_id
                     WHERE r.id = NEW.remito_id
                 );
            END
            """
        )

    op.execute(
        """
        CREATE TRIGGER tr_muestras_remito_inmutable_update
        BEFORE UPDATE OF remito_id ON muestras_biologicas
        FOR EACH ROW
        WHEN OLD.remito_id IS NOT NULL AND NEW.remito_id IS NOT OLD.remito_id
        BEGIN
            SELECT RAISE(ABORT, 'Una muestra empaquetada no puede cambiar de remito');
        END
        """
    )
    op.execute(
        """
        CREATE TRIGGER tr_remitos_estructura_inmutable_update
        BEFORE UPDATE OF contenedor_id, precinto_id, clinica_origen_id,
            laboratorio_destino_id ON remitos_biologicos
        FOR EACH ROW
        WHEN OLD.estado <> 'borrador'
        BEGIN
            SELECT RAISE(ABORT, 'La estructura del remito emitido es inmutable');
        END
        """
    )
    op.execute(
        """
        CREATE TRIGGER tr_envios_remito_inmutable_update
        BEFORE UPDATE OF remito_id ON envios
        FOR EACH ROW
        WHEN EXISTS (
            SELECT 1 FROM recepciones_laboratorio AS r WHERE r.envio_id = OLD.id
        )
        BEGIN
            SELECT RAISE(ABORT, 'Un envio recibido no puede cambiar de remito');
        END
        """
    )

    # Acta de recepción coherente e inmutable.
    op.execute(
        """
        CREATE TRIGGER tr_recepciones_coherencia_insert
        BEFORE INSERT ON recepciones_laboratorio
        FOR EACH ROW
        BEGIN
            SELECT RAISE(ABORT, 'La recepcion no coincide con envio o laboratorio')
             WHERE NOT EXISTS (
                SELECT 1 FROM envios AS e
                JOIN remitos_biologicos AS r ON r.id = e.remito_id
                 WHERE e.id = NEW.envio_id
                   AND r.id = NEW.remito_id
                   AND r.laboratorio_destino_id = NEW.laboratorio_id
             );
            SELECT RAISE(ABORT, 'Una recepcion viable requiere precinto intacto')
             WHERE NEW.muestra_viable = 1 AND NEW.estado_precinto <> 'intacto';
            SELECT RAISE(ABORT, 'Una recepcion no viable requiere motivo')
             WHERE NEW.muestra_viable = 0
               AND length(trim(COALESCE(NEW.observaciones, ''))) = 0;
            SELECT RAISE(ABORT, 'La temperatura vuelve inviable la muestra')
             WHERE NEW.muestra_viable = 1
               AND EXISTS (
                SELECT 1 FROM muestras_biologicas AS m
                JOIN envios AS e ON e.id = NEW.envio_id
                 WHERE m.remito_id = NEW.remito_id
                   AND (
                        NEW.temperatura_recepcion_c < m.temperatura_min_c
                        OR NEW.temperatura_recepcion_c > m.temperatura_max_c
                        OR (e.temperatura_min_registrada_c IS NOT NULL
                            AND e.temperatura_min_registrada_c < m.temperatura_min_c)
                        OR (e.temperatura_max_registrada_c IS NOT NULL
                            AND e.temperatura_max_registrada_c > m.temperatura_max_c)
                   )
             );
        END
        """
    )
    op.execute(
        """
        CREATE TRIGGER tr_recepciones_inmutable_update
        BEFORE UPDATE ON recepciones_laboratorio
        FOR EACH ROW
        BEGIN
            SELECT RAISE(ABORT, 'El acta de recepcion es inmutable');
        END
        """
    )
    op.execute(
        """
        CREATE TRIGGER tr_recepciones_inmutable_delete
        BEFORE DELETE ON recepciones_laboratorio
        FOR EACH ROW
        BEGIN
            SELECT RAISE(ABORT, 'El acta de recepcion no se puede eliminar');
        END
        """
    )

    # Un resultado exige muestra recibida, recepción viable y precinto intacto.
    for operacion in ("INSERT", "UPDATE OF orden_analisis_id"):
        sufijo = "insert" if operacion == "INSERT" else "update"
        op.execute(
            f"""
            CREATE TRIGGER tr_resultados_muestra_viable_{sufijo}
            BEFORE {operacion} ON resultados_analisis
            FOR EACH ROW
            BEGIN
                SELECT RAISE(ABORT, 'No se puede procesar una muestra no viable')
                 WHERE NOT EXISTS (
                    SELECT 1 FROM ordenes_analisis AS oa
                    JOIN muestras_biologicas AS m ON m.id = oa.muestra_id
                    JOIN recepciones_laboratorio AS r ON r.remito_id = m.remito_id
                     WHERE oa.id = NEW.orden_analisis_id
                       AND m.estado_actual IN ('recibida', 'analizada')
                       AND r.muestra_viable = 1
                       AND r.estado_precinto = 'intacto'
                 );
            END
            """
        )


def downgrade() -> None:
    conexion = op.get_bind()
    if conexion.dialect.name != "sqlite":
        raise RuntimeError("HuellaVet usa exclusivamente SQLite")

    for trigger in TRIGGERS:
        op.execute(f"DROP TRIGGER IF EXISTS {trigger}")
    op.execute("DROP INDEX IF EXISTS uq_remitos_contenedor_activo")
    Base.metadata.drop_all(bind=conexion, checkfirst=True)
