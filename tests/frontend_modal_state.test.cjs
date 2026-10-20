"use strict";

const assert = require("node:assert/strict");
const test = require("node:test");

const {
  crearControlEnvioModal,
} = require("../frontend/modal-state.js");

function crearEscenario() {
  const estado = { submitting: false };
  const boton = { disabled: true, textContent: "Estado anterior" };
  const control = crearControlEnvioModal(estado, () => boton);
  return { boton, control, estado };
}

test("restablece el botón entre tres formularios consecutivos", () => {
  const { boton, control, estado } = crearEscenario();

  for (const method of ["POST", "POST", "PATCH"]) {
    control.restablecer(method);
    assert.equal(estado.submitting, false);
    assert.equal(boton.disabled, false);
    assert.equal(
      boton.textContent,
      method === "PATCH" ? "Guardar cambios" : "Confirmar",
    );

    assert.equal(control.iniciar(method), true);
    assert.equal(estado.submitting, true);
    assert.equal(boton.disabled, true);
    assert.equal(boton.textContent, "Guardando…");

    control.restablecer(method);
  }
});

test("impide un envío duplicado mientras la petición está pendiente", () => {
  const { boton, control, estado } = crearEscenario();

  control.restablecer("POST");
  assert.equal(control.iniciar("POST"), true);
  assert.equal(control.iniciar("POST"), false);
  assert.equal(estado.submitting, true);
  assert.equal(boton.disabled, true);

  control.restablecer("POST");
  assert.equal(estado.submitting, false);
  assert.equal(boton.disabled, false);
  assert.equal(boton.textContent, "Confirmar");
});

test("recupera el estado correcto después de un error", () => {
  const { boton, control, estado } = crearEscenario();

  control.restablecer("PATCH");
  control.iniciar("PATCH");
  control.restablecer("PATCH");

  assert.equal(estado.submitting, false);
  assert.equal(boton.disabled, false);
  assert.equal(boton.textContent, "Guardar cambios");
});
