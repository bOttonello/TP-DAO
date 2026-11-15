"use strict";

const assert = require("node:assert/strict");
const test = require("node:test");
const fs = require("node:fs");
const vm = require("node:vm");
const {
  turnosDelDia, buscarConflictos, sugerirHorarios, modeloReporte, valoresDesdeFilas,
} = require("../frontend/usability.js");

const turno = (inicio, fin, estado = "programado", profesional_id = "p1") =>
  ({ inicio, fin, estado, profesional_id });
const turnos = [
  turno("2027-01-10T09:00", "2027-01-10T10:00"),
  turno("2027-01-10T10:00", "2027-01-10T11:00", "cancelado"),
  turno("2027-01-10T11:00", "2027-01-10T12:00", "ausente"),
  turno("2027-01-10T12:00", "2027-01-10T13:00", "programado", "p2"),
  turno("2027-01-09T23:30", "2027-01-10T00:30"),
];

test("agenda filtra profesional, día, cancelados y turnos que cruzan medianoche", () => {
  assert.equal(turnosDelDia(turnos, "p1", "2027-01-10").length, 2);
  assert.deepEqual(turnosDelDia(turnos, "", "2027-01-10"), []);
  assert.deepEqual(turnosDelDia(turnos, "p1", ""), []);
});

test("detecta solapamientos parciales, completos y permite intervalos contiguos", () => {
  assert.equal(buscarConflictos(turnos, "p1", "2027-01-10T09:30", "2027-01-10T10:30").length, 1);
  assert.equal(buscarConflictos(turnos, "p1", "2027-01-10T08:00", "2027-01-10T10:00").length, 1);
  assert.equal(buscarConflictos(turnos, "p1", "2027-01-10T10:00", "2027-01-10T11:00").length, 0);
  assert.equal(buscarConflictos(turnos, "p2", "2027-01-10T09:00", "2027-01-10T10:00").length, 0);
});

test("sugiere horarios futuros sin conflictos y conserva la duración pedida", () => {
  const ahora = new Date("2027-01-10T08:15");
  const slots = sugerirHorarios(turnos, "p1", "2027-01-10", 60, ahora);
  assert.ok(slots.length);
  for (const slot of slots) {
    assert.ok(slot.inicio > ahora);
    assert.equal(slot.fin - slot.inicio, 3600000);
    assert.equal(buscarConflictos(turnos, "p1", slot.inicio, slot.fin).length, 0);
  }
  assert.deepEqual(sugerirHorarios(turnos, "p1", "2027-01-09", 30, ahora), []);
});

test("el reporte de rechazos no duplica las muestras enviadas por motivo", () => {
  const modelo = modeloReporte("muestras-rechazadas", [
    { clinica_id: "c1", clinica: "Centro", muestras_enviadas: 10, muestras_rechazadas: 2 },
    { clinica_id: "c1", clinica: "Centro", muestras_enviadas: 10, muestras_rechazadas: 1 },
  ]);
  assert.deepEqual(modelo.metricas, [["Muestras enviadas", 10], ["Rechazadas", 3]]);
});

test("los gráficos mantienen cero, sin datos y agregaciones monetarias correctas", () => {
  const tiempos = modeloReporte("tiempos-muestras", [
    { clinica: "Centro", transito: { promedio_horas: 0 }, procesamiento: { promedio_horas: null } },
  ]);
  assert.deepEqual(tiempos.barras[0].valores, [0, null]);
  const facturas = modeloReporte("facturacion", [
    { importe_bruto: 100, descuentos_prorrateados: 10, importe_neto: 90 },
    { importe_bruto: 20, descuentos_prorrateados: 0, importe_neto: 20 },
  ]);
  assert.equal(facturas.metricas[2][1], 110);
});

test("carga de parámetros produce el contrato de la API y rechaza datos incompletos", () => {
  assert.deepEqual(valoresDesdeFilas([{ nombre: "hematocrito", valor: "42 %" }]), { hematocrito: "42 %" });
  assert.throws(() => valoresDesdeFilas([]), /al menos/);
  assert.throws(() => valoresDesdeFilas([{ nombre: "x", valor: "" }]), /Completá/);
  assert.throws(() => valoresDesdeFilas([{ nombre: "x", valor: "1" }, { nombre: "x", valor: "2" }]), /repitas/);
});

// Ejecutamos los renderizadores reales de app.js, no comprobaciones de cadenas fuente.
function aplicacion() {
  const element = { querySelector: () => null, querySelectorAll: () => [] };
  const context = vm.createContext({
    console, Intl, URLSearchParams, Date,
    window: {
      crearControlEnvioModal: () => ({}),
      reglasFormulario: require("../frontend/form-rules.js"),
      usabilidad: require("../frontend/usability.js"),
    },
    document: { querySelector: () => element, querySelectorAll: () => [], addEventListener: () => {} },
  });
  vm.runInContext(fs.readFileSync(require.resolve("../frontend/app.js"), "utf8"), context);
  return (source) => vm.runInContext(source, context);
}

test("detalle de factura renderiza conceptos, importes y responsable sin JSON ni UUID", () => {
  const run = aplicacion();
  run('state.cache.clientes = [{id:"c1",nombre:"Ana",apellido:"Pérez",numero_documento:"12345678"}]; state.cache.clinicas=[{id:"cl1",nombre:"Centro",codigo:"C"}]');
  const html = run('renderFacturaDetalle({factura:{numero:"FAC-001",cliente_id:"c1",clinica_id:"cl1",estado:"emitida",subtotal:"100",descuento:"0",total:"100"},componentes:[{descripcion:"Consulta",tipo:"atencion",cantidad:"1",precio_unitario:"100",subtotal:"100"}]})');
  assert.match(html, /Ana/);
  assert.match(html, /Consulta/);
  assert.match(html, /invoice-total/);
  assert.doesNotMatch(html, /<pre|cliente_id|&quot;subtotal&quot;/);
});

test("detalle genérico convierte estructuras anidadas y escapa contenido HTML", () => {
  const html = aplicacion()('renderDetail({valores:{hematocrito:"42 %"},vacunas_pendientes:[{vacuna:"<script>"}]})');
  assert.match(html, /42 %/);
  assert.match(html, /&lt;script&gt;/);
  assert.doesNotMatch(html, /<pre|<script>/);
});

test("gráfico real es legible sin color y conserva la ausencia de datos", () => {
  const html = aplicacion()('renderGraficoReporte("tiempos-muestras",[{clinica:"Centro",transito:{promedio_horas:0},procesamiento:{promedio_horas:null}}])');
  assert.match(html, /Tránsito: 0 h/);
  assert.match(html, /Procesamiento: Sin datos/);
  assert.doesNotMatch(html, /NaN|Infinity/);
  const resumen = html.split("</section>")[0];
  assert.doesNotMatch(resumen, /0 h/);
});

test("una respuesta tardía no reemplaza el reporte seleccionado después", async () => {
  const run = aplicacion();
  run('let resolverReporte; api = () => new Promise(resolve => { resolverReporte = resolve; }); renderReportes = () => {}; state.view = "reportes";');
  const pendiente = run("runReport()");
  assert.equal(run("state.reportLoading"), true);
  await run('handleAction({dataset:{action:"select-report",key:"facturacion"}})');
  run('resolverReporte([{clinica:"Respuesta vieja"}])');
  await pendiente;
  assert.equal(run("state.reportKey"), "facturacion");
  assert.equal(run("state.reportData"), null);
  assert.equal(run("state.reportLoading"), false);
});

test("el reporte recupera el control de carga después de un error HTTP", async () => {
  const run = aplicacion();
  run('api = async () => { throw new Error("Sin conexión"); }; renderReportes = () => {}; state.view = "reportes";');
  await run("runReport()");
  assert.equal(run("state.reportLoading"), false);
  assert.equal(run("state.reportError"), "Sin conexión");
  assert.equal(run("state.reportData"), null);
});
