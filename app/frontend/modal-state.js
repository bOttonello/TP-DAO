"use strict";

(function registrarControlEnvioModal(scope) {
  function etiquetaParaMetodo(method) {
    return method === "PATCH" ? "Guardar cambios" : "Confirmar";
  }

  function crearControlEnvioModal(estado, obtenerBoton) {
    if (!estado || typeof obtenerBoton !== "function") {
      throw new TypeError("El control del modal requiere un estado y un botón.");
    }

    function boton() {
      const elemento = obtenerBoton();
      if (!elemento) throw new Error("No se encontró el botón de envío del modal.");
      return elemento;
    }

    function restablecer(method = "POST") {
      const elemento = boton();
      estado.submitting = false;
      elemento.disabled = false;
      elemento.textContent = etiquetaParaMetodo(method);
    }

    function iniciar(method = "POST") {
      if (estado.submitting) return false;
      const elemento = boton();
      estado.submitting = true;
      elemento.disabled = true;
      elemento.textContent = "Guardando…";
      return true;
    }

    return Object.freeze({
      estaEnviando: () => estado.submitting,
      iniciar,
      restablecer,
    });
  }

  scope.crearControlEnvioModal = crearControlEnvioModal;
  if (typeof module !== "undefined" && module.exports) {
    module.exports = { crearControlEnvioModal };
  }
})(typeof globalThis !== "undefined" ? globalThis : this);
