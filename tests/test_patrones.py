"""Pruebas unitarias de los patrones State y Singleton."""

from dataclasses import FrozenInstanceError

import pytest

from app.domain import (
    CicloVidaMuestra,
    CicloVidaRemito,
    EstadoMuestra,
    EstadoRemito,
    RegistroEstados,
    TransicionEstadoInvalida,
)


def test_registro_estados_es_singleton_y_entrega_estados_canonicos() -> None:
    primero = RegistroEstados()
    segundo = RegistroEstados.instancia()

    assert primero is segundo
    assert (
        primero.obtener_estado_muestra(EstadoMuestra.EXTRAIDA)
        is segundo.obtener_estado_muestra("extraida")
    )
    assert (
        primero.obtener_estado_remito(EstadoRemito.EN_TRANSITO)
        is segundo.obtener_estado_remito("en transito")
    )


def test_muestra_recorrido_completo_y_trazabilidad_inmutable() -> None:
    eventos_observados = []
    muestra = CicloVidaMuestra(observador=eventos_observados.append)

    muestra.empaquetar()
    muestra.iniciar_transito()
    muestra.registrar_recepcion(precinto_intacto=True)
    muestra.registrar_analisis()

    assert muestra.estado is EstadoMuestra.ANALIZADA
    assert tuple(evento.estado_nuevo for evento in muestra.historial) == (
        "empaquetada",
        "en_transito",
        "recibida",
        "analizada",
    )
    assert eventos_observados == list(muestra.historial)
    assert muestra.historial[0].ocurrida_en.tzinfo is not None

    with pytest.raises(FrozenInstanceError):
        muestra.historial[0].estado_nuevo = "ALTERADO"  # type: ignore[misc]


def test_precinto_roto_rechaza_muestra_e_impide_analizarla() -> None:
    muestra = CicloVidaMuestra()
    muestra.empaquetar()
    muestra.iniciar_transito()

    evento = muestra.registrar_recepcion(precinto_intacto=False)

    assert muestra.estado is EstadoMuestra.RECHAZADA
    assert evento.estado_anterior == "en_transito"
    assert evento.estado_nuevo == "rechazada"
    assert "precinto sanitario llegó roto" in (evento.detalle or "")

    with pytest.raises(TransicionEstadoInvalida) as error:
        muestra.registrar_analisis()

    assert error.value.estado_actual == "rechazada"
    assert muestra.estado is EstadoMuestra.RECHAZADA
    assert len(muestra.historial) == 3


def test_transicion_invalida_no_modifica_muestra_ni_historial() -> None:
    muestra = CicloVidaMuestra("EXTRAIDA")

    with pytest.raises(TransicionEstadoInvalida):
        muestra.iniciar_transito()

    assert muestra.estado is EstadoMuestra.EXTRAIDA
    assert muestra.historial == ()


@pytest.mark.parametrize(
    ("aceptado", "estado_final"),
    [
        (True, EstadoRemito.RECIBIDO),
        (False, EstadoRemito.RECHAZADO),
    ],
)
def test_remito_puede_ser_recibido_o_rechazado(
    aceptado: bool, estado_final: EstadoRemito
) -> None:
    remito = CicloVidaRemito()

    remito.emitir()
    remito.iniciar_transito()
    ultima = remito.registrar_recepcion(aceptado=aceptado)

    assert remito.estado is estado_final
    assert ultima.estado_nuevo == estado_final.value
    assert tuple(evento.estado_anterior for evento in remito.historial) == (
        "borrador",
        "emitido",
        "en_transito",
    )


def test_remito_no_puede_recibirse_antes_del_transporte() -> None:
    remito = CicloVidaRemito()
    remito.emitir()

    with pytest.raises(TransicionEstadoInvalida) as error:
        remito.registrar_recepcion(aceptado=True)

    assert error.value.estado_actual == "emitido"
    assert remito.estado is EstadoRemito.EMITIDO
    assert len(remito.historial) == 1


def test_estado_desconocido_falla_al_reconstruir_maquina() -> None:
    with pytest.raises(ValueError, match="desconocido"):
        CicloVidaMuestra("CONTAMINADA")
