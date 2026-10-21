"use strict";

(function registrarReglasFormulario(scope) {
  function fechaHoraLocal(fecha = new Date()) {
    const dosDigitos = (valor) => String(valor).padStart(2, "0");
    return [
      fecha.getFullYear(),
      dosDigitos(fecha.getMonth() + 1),
      dosDigitos(fecha.getDate()),
    ].join("-") + `T${dosDigitos(fecha.getHours())}:${dosDigitos(fecha.getMinutes())}`;
  }

  function validarNumeroEnRango(valor, minimo, maximo, etiqueta) {
    const numero = Number(valor);
    if (!Number.isFinite(numero)) {
      throw new Error(`${etiqueta} debe ser un número válido.`);
    }
    if (minimo !== undefined && minimo !== null && numero < Number(minimo)) {
      throw new Error(`${etiqueta} debe ser mayor o igual a ${minimo}.`);
    }
    if (maximo !== undefined && maximo !== null && numero > Number(maximo)) {
      throw new Error(`${etiqueta} debe ser menor o igual a ${maximo}.`);
    }
    return numero;
  }

  function validarIntervaloTurno(inicio, fin, ahora = new Date()) {
    const fechaInicio = new Date(inicio);
    const fechaFin = new Date(fin);
    if (Number.isNaN(fechaInicio.getTime()) || Number.isNaN(fechaFin.getTime())) {
      throw new Error("Indicá un día y horario válidos para la atención.");
    }
    if (fechaInicio < ahora) {
      throw new Error("No se puede agendar una atención en el pasado.");
    }
    if (fechaFin <= fechaInicio) {
      throw new Error("El horario de finalización debe ser posterior al inicio.");
    }
    return true;
  }

  const reglas = Object.freeze({
    fechaHoraLocal,
    validarIntervaloTurno,
    validarNumeroEnRango,
  });

  scope.reglasFormulario = reglas;
  if (typeof module !== "undefined" && module.exports) {
    module.exports = reglas;
  }
})(typeof globalThis !== "undefined" ? globalThis : this);
