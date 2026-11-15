"use strict";

(function registrarUsabilidad(scope) {
  const esTurnoOcupado = (turno) => !["cancelado", "ausente"].includes(turno.estado);

  // SQLite devuelve horarios de agenda sin zona: se interpretan como hora local.
  function turnosDelDia(turnos, profesionalId, dia) {
    if (!profesionalId || !/^\d{4}-\d{2}-\d{2}$/.test(dia)) return [];
    const desde = new Date(dia + "T00:00");
    const hasta = new Date(desde);
    hasta.setDate(hasta.getDate() + 1);
    return turnos.filter((turno) => turno.profesional_id === profesionalId
      && esTurnoOcupado(turno)
      && new Date(turno.inicio) < hasta && new Date(turno.fin) > desde)
      .sort((a, b) => new Date(a.inicio) - new Date(b.inicio));
  }

  function buscarConflictos(turnos, profesionalId, inicio, fin) {
    const desde = new Date(inicio);
    const hasta = new Date(fin);
    return turnos.filter((turno) => turno.profesional_id === profesionalId
      && esTurnoOcupado(turno)
      && new Date(turno.inicio) < hasta && new Date(turno.fin) > desde);
  }

  function sugerirHorarios(turnos, profesionalId, dia, duracion = 30, ahora = new Date()) {
    if (!profesionalId || !/^\d{4}-\d{2}-\d{2}$/.test(dia)
      || !Number.isFinite(duracion) || duracion <= 0) return [];
    const limite = new Date(dia + "T20:00");
    const sugerencias = [];
    for (let inicio = new Date(dia + "T08:00"); inicio < limite;
      inicio = new Date(inicio.getTime() + 30 * 60000)) {
      const fin = new Date(inicio.getTime() + duracion * 60000);
      if (inicio > ahora && fin <= limite
        && !buscarConflictos(turnos, profesionalId, inicio, fin).length) {
        sugerencias.push({ inicio, fin });
      }
    }
    return sugerencias;
  }

  function modeloReporte(clave, filas) {
    const sumar = (campo) => filas.reduce((total, fila) => total + Number(fila[campo] || 0), 0);
    if (clave === "atenciones-derivaciones") return {
      titulo: "Actividad por clínica y tipo de atención", unidad: "cantidad",
      metricas: [["Atenciones", sumar("atenciones")], ["Derivaciones", sumar("derivaciones")]],
      series: ["Atenciones", "Derivaciones"],
      barras: filas.map((fila) => ({
        etiqueta: fila.clinica + " · " + fila.tipo_atencion,
        valores: [Number(fila.atenciones), Number(fila.derivaciones)],
      })),
    };
    if (clave === "muestras-rechazadas") {
      // La cantidad enviada se repite por motivo: no se debe sumar por fila.
      const enviadas = new Map();
      filas.forEach((fila) => enviadas.set(fila.clinica_id || fila.clinica,
        Number(fila.muestras_enviadas || 0)));
      return {
        titulo: "Muestras rechazadas por motivo", unidad: "cantidad",
        metricas: [["Muestras enviadas", [...enviadas.values()].reduce((a, b) => a + b, 0)],
          ["Rechazadas", sumar("muestras_rechazadas")]],
        series: ["Rechazadas"],
        barras: filas.map((fila) => ({
          etiqueta: fila.clinica + " · " + (fila.motivo_rechazo || "Sin rechazos"),
          valores: [Number(fila.muestras_rechazadas)],
        })),
      };
    }
    if (clave === "facturacion") return {
      titulo: "Facturación neta por clínica y concepto", unidad: "ARS",
      metricas: [["Importe bruto", sumar("importe_bruto")],
        ["Descuentos", sumar("descuentos_prorrateados")], ["Importe neto", sumar("importe_neto")]],
      series: ["Neto"],
      barras: filas.map((fila) => ({
        etiqueta: fila.clinica + " · " + fila.tipo_componente,
        valores: [Number(fila.importe_neto)],
      })),
    };
    if (clave === "tratamientos-vacunas") return {
      titulo: "Vacunas pendientes por paciente", unidad: "cantidad",
      metricas: [["Pacientes", filas.length], ["Vacunas pendientes", sumar("cantidad_vacunas_pendientes")],
        ["Tratamientos registrados", sumar("cantidad_tratamientos")]],
      series: ["Vacunas pendientes"],
      barras: filas.map((fila) => ({
        etiqueta: fila.mascota + " · " + fila.responsable,
        valores: [Number(fila.cantidad_vacunas_pendientes)],
      })),
    };
    return {
      titulo: "Tiempos promedio por clínica", unidad: "horas",
      metricas: [
        ["Envíos completados", filas.reduce((s, f) => s + Number(f.transito?.envios_completados || 0), 0)],
        ["Muestras analizadas", filas.reduce((s, f) => s + Number(f.procesamiento?.muestras_analizadas || 0), 0)],
      ],
      series: ["Tránsito", "Procesamiento"],
      barras: filas.map((fila) => ({
        etiqueta: fila.clinica,
        valores: [fila.transito?.promedio_horas ?? null, fila.procesamiento?.promedio_horas ?? null],
      })),
    };
  }

  function valoresDesdeFilas(filas) {
    const valores = {};
    for (const { nombre, valor } of filas) {
      const clave = nombre.trim();
      if (!clave || !valor.trim()) throw new Error("Completá el parámetro y su valor en cada fila.");
      if (Object.hasOwn(valores, clave)) throw new Error("No repitas el mismo parámetro.");
      Object.defineProperty(valores, clave, {
        value: valor.trim(), enumerable: true, configurable: true, writable: true,
      });
    }
    if (!filas.length) throw new Error("Agregá al menos un parámetro al resultado.");
    return valores;
  }

  const utilidades = Object.freeze({
    esTurnoOcupado, turnosDelDia, buscarConflictos, sugerirHorarios, modeloReporte, valoresDesdeFilas,
  });
  scope.usabilidad = utilidades;
  if (typeof module !== "undefined" && module.exports) module.exports = utilidades;
})(typeof globalThis !== "undefined" ? globalThis : this);
