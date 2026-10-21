"use strict";

const assert = require("node:assert/strict");
const test = require("node:test");

const {
  fechaHoraLocal,
  validarIntervaloTurno,
  validarNumeroEnRango,
} = require("../frontend/form-rules.js");

test("genera el mínimo datetime-local sin convertirlo a UTC", () => {
  const fecha = new Date(2026, 9, 20, 14, 5, 31);
  assert.equal(fechaHoraLocal(fecha), "2026-10-20T14:05");
});

test("rechaza turnos pasados e intervalos invertidos", () => {
  const ahora = new Date(2026, 9, 20, 12, 0);
  assert.throws(
    () => validarIntervaloTurno("2026-10-19T12:00", "2026-10-19T12:30", ahora),
    /pasado/,
  );
  assert.throws(
    () => validarIntervaloTurno("2026-10-21T12:30", "2026-10-21T12:00", ahora),
    /posterior/,
  );
  assert.equal(
    validarIntervaloTurno("2026-10-21T12:00", "2026-10-21T12:30", ahora),
    true,
  );
});

test("valida peso positivo y temperatura entre 24 y 45", () => {
  assert.equal(validarNumeroEnRango("0.01", "0.01", undefined, "Peso"), 0.01);
  assert.throws(
    () => validarNumeroEnRango("-2", "0.01", undefined, "Peso"),
    /mayor o igual/,
  );
  assert.equal(validarNumeroEnRango("24", "24", "45", "Temperatura"), 24);
  assert.equal(validarNumeroEnRango("45", "24", "45", "Temperatura"), 45);
  assert.throws(
    () => validarNumeroEnRango("23.9", "24", "45", "Temperatura"),
    /mayor o igual/,
  );
  assert.throws(
    () => validarNumeroEnRango("45.1", "24", "45", "Temperatura"),
    /menor o igual/,
  );
});
