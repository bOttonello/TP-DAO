"use strict";

const API = "/api";

const state = {
  view: "dashboard",
  cache: {},
  loading: false,
  reportKey: "atenciones-derivaciones",
  reportData: null,
  reportFilters: {},
  reportRequest: 0,
  reportLoading: false,
  modal: null,
  submitting: false,
  formRequest: 0,
};

const viewMeta = {
  dashboard: ["Panel general", "Resumen operativo"],
  pacientes: ["Pacientes y responsables", "Núcleo clínico"],
  atencion: ["Atención clínica", "Agenda, consultas y vacunación"],
  laboratorio: ["Laboratorio", "Derivaciones, muestras y resultados"],
  custodia: ["Custodia y envíos", "Transporte sanitario y trazabilidad"],
  facturacion: ["Facturación", "Comprobantes y componentes"],
  reportes: ["Reportes", "Indicadores clínicos y logísticos"],
  configuracion: ["Configuración", "Red, profesionales y catálogos"],
};

const $ = (selector, root = document) => root.querySelector(selector);
const $$ = (selector, root = document) => [...root.querySelectorAll(selector)];

const root = $("#view-root");
const modalBackdrop = $("#modal-backdrop");
const modalForm = $("#modal-form");
const modalFields = $("#modal-fields");
const drawer = $("#detail-drawer");
const controlEnvioModal = window.crearControlEnvioModal(state, () => $("#modal-submit"));
const {
  fechaHoraLocal,
  validarIntervaloTurno,
  validarNumeroEnRango,
} = window.reglasFormulario;
const { turnosDelDia, buscarConflictos, sugerirHorarios, modeloReporte, valoresDesdeFilas } = window.usabilidad;

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function titleCase(value) {
  return String(value ?? "")
    .replaceAll("_", " ")
    .replace(/\b\w/g, (letter) => letter.toUpperCase());
}

function shortId(value) {
  return value ? String(value).slice(0, 8) : "—";
}

function formatDate(value, withTime = true) {
  if (!value) return "—";
  const date = new Date(/^\d{4}-\d{2}-\d{2}$/.test(String(value)) ? value + "T12:00" : value);
  if (Number.isNaN(date.getTime())) return escapeHtml(value);
  return new Intl.DateTimeFormat("es-AR", {
    day: "2-digit",
    month: "short",
    year: "numeric",
    ...(withTime ? { hour: "2-digit", minute: "2-digit" } : {}),
  }).format(date);
}

function formatMoney(value) {
  const number = Number(value ?? 0);
  return new Intl.NumberFormat("es-AR", {
    style: "currency",
    currency: "ARS",
    maximumFractionDigits: 2,
  }).format(Number.isFinite(number) ? number : 0);
}

function displayValue(value) {
  if (value === null || value === undefined || value === "") return "—";
  if (typeof value === "boolean") return value ? "Sí" : "No";
  if (Array.isArray(value)) return value.length ? value.map(displayValue).join(", ") : "—";
  if (typeof value === "object") return Object.entries(value).map(([key, item]) => `${titleCase(key)}: ${displayValue(item)}`).join(" · ");
  return String(value);
}

function badge(value) {
  const normalized = String(value ?? "").toLowerCase();
  let tone = "info";
  if (["activo", "activa", "disponible", "completada", "completado", "analizada", "recibida", "recibido", "emitida"].includes(normalized)) tone = "success";
  if (["pendiente", "programado", "confirmado", "borrador", "emitido", "extraida", "empaquetada"].includes(normalized)) tone = "warning";
  if (["rechazada", "rechazado", "anulada", "cancelado", "inactivo", "inactiva"].includes(normalized)) tone = "danger";
  return `<span class="badge badge-${tone}">${escapeHtml(titleCase(value))}</span>`;
}

function toast(message, type = "success", title = type === "error" ? "No se pudo completar" : "Operación realizada") {
  const node = document.createElement("div");
  node.className = `toast ${type === "error" ? "is-error" : ""}`;
  node.innerHTML = `
    <span class="toast-mark">${type === "error" ? "!" : "✓"}</span>
    <div><strong>${escapeHtml(title)}</strong><span>${escapeHtml(message)}</span></div>`;
  $("#toast-region").append(node);
  window.setTimeout(() => node.remove(), 4800);
}

async function api(path, options = {}) {
  const request = { ...options, headers: { ...(options.headers || {}) } };
  if (request.body && !(request.body instanceof FormData)) {
    request.headers["Content-Type"] = "application/json";
    request.body = JSON.stringify(request.body);
  }
  const response = await fetch(`${API}${path}`, request);
  const contentType = response.headers.get("content-type") || "";
  const payload = contentType.includes("application/json") ? await response.json() : await response.text();
  if (!response.ok) {
    const validation = Array.isArray(payload?.detail)
      ? payload.detail.map((item) => `${titleCase(item.loc?.slice(1).join(" · ") || "Datos")}: ${item.msg}`).join(". ")
      : null;
    throw new Error(payload?.detalle || validation || payload?.detail || `Error HTTP ${response.status}`);
  }
  return payload;
}

async function fetchCached(key, path, force = false) {
  if (!force && Object.hasOwn(state.cache, key)) return state.cache[key];
  state.cache[key] = await api(path);
  return state.cache[key];
}

async function safeCached(key, path, fallback = null, force = false) {
  try {
    return await fetchCached(key, path, force);
  } catch (error) {
    state.cache[key] = fallback;
    return fallback;
  }
}

async function loadCatalogs(force = false) {
  await Promise.all([
    fetchCached("clientes", "/clientes", force),
    fetchCached("mascotas", "/mascotas", force),
    fetchCached("clinicas", "/clinicas", force),
    safeCached("laboratorio", "/laboratorio", null, force),
    fetchCached("profesionales", "/profesionales", force),
    fetchCached("analisis", "/analisis", force),
    fetchCached("vacunas", "/vacunas", force),
    fetchCached("contenedores", "/contenedores", force),
    fetchCached("turnos", "/turnos", force),
    fetchCached("atenciones", "/atenciones", force),
    fetchCached("aplicaciones", "/vacunas/aplicaciones", force),
    fetchCached("ordenes", "/ordenes-derivacion", force),
    fetchCached("muestras", "/muestras", force),
    fetchCached("remitos", "/remitos", force),
    fetchCached("envios", "/envios", force),
    fetchCached("resultados", "/resultados", force),
    fetchCached("facturas", "/facturas", force),
  ]);
}

function itemLabel(source, item) {
  if (!item) return "Sin datos";
  const labels = {
    clientes: `${item.apellido}, ${item.nombre} · ${item.numero_documento}`,
    mascotas: `${item.nombre} · ${item.especie}`,
    clinicas: `${item.nombre} · ${item.codigo}`,
    profesionales: `${item.apellido}, ${item.nombre} · ${item.matricula}`,
    analisis: `${item.nombre} · ${item.codigo}`,
    vacunas: `${item.nombre} · ${item.especie_objetivo}`,
    contenedores: `${item.codigo} · ${titleCase(item.estado)}`,
    turnos: `${titleCase(item.tipo)} · ${formatDate(item.inicio)}`,
    atenciones: `${findById("mascotas", item.mascota_id)?.nombre || "Paciente"} · ${titleCase(item.tipo)} · ${formatDate(item.fecha)}`,
    ordenes: `${item.numero} · ${titleCase(item.estado)}`,
    muestras: `${item.codigo} · ${titleCase(item.estado_actual)}`,
    remitos: `${item.numero} · ${titleCase(item.estado)}`,
    envios: `${item.transportista} · ${titleCase(item.estado)}`,
  };
  return labels[source] || item.nombre || item.codigo || item.numero || shortId(item.id);
}

function optionsFor(source, selected = null) {
  let items = state.cache[source];
  if (source === "laboratorio") items = items ? [items] : [];
  if (!Array.isArray(items)) items = [];
  return items.map((item) => {
    const value = item.id;
    const isSelected = Array.isArray(selected) ? selected.includes(value) : selected === value;
    return `<option value="${escapeHtml(value)}" ${isSelected ? "selected" : ""}>${escapeHtml(itemLabel(source, item))}</option>`;
  }).join("");
}

function choiceOptions(choices, selected = null) {
  return choices.map((choice) => {
    const value = typeof choice === "string" ? choice : choice[0];
    const label = typeof choice === "string" ? titleCase(choice) : choice[1];
    return `<option value="${escapeHtml(value)}" ${selected === value ? "selected" : ""}>${escapeHtml(label)}</option>`;
  }).join("");
}

function renderField(field, values) {
  const value = values[field.name] ?? field.value ?? "";
  const required = field.required ? "required" : "";
  const full = field.full || ["textarea", "values", "repeat"].includes(field.type) ? "field-full" : "";
  const help = field.help ? `<p class="field-help">${escapeHtml(field.help)}</p>` : "";

  if (field.type === "checkbox") {
    const checked = value === true || value === "true" || (value === "" && field.checked);
    return `<div class="field ${full}"><div class="check-field"><input id="field-${field.name}" type="checkbox" name="${field.name}" ${checked ? "checked" : ""}><label for="field-${field.name}">${escapeHtml(field.label)}</label></div>${help}</div>`;
  }

  if (field.type === "repeat") {
    return `<div class="field ${full}"><span>${escapeHtml(field.label)}</span><div class="repeat-list" id="component-list"></div><button type="button" class="button button-secondary button-small repeat-add" data-modal-action="add-component">+ Agregar componente</button>${help}</div>`;
  }
  if (field.type === "values") {
    return `<div class="field field-full"><span>${escapeHtml(field.label)}</span><div id="result-values" class="repeat-list"></div><button type="button" class="button button-secondary button-small repeat-add" data-modal-action="add-value">+ Agregar parámetro</button>${help}</div>`;
  }

  if (field.type === "select" || field.type === "multiselect") {
    const multiple = field.type === "multiselect" ? "multiple" : "";
    const options = field.source ? optionsFor(field.source, value) : choiceOptions(field.choices || [], value);
    const placeholder = options
      ? (field.type === "multiselect" ? "Seleccione una o más opciones" : "Seleccione…")
      : "No hay opciones disponibles";
    return `<div class="field ${full}"><label for="field-${field.name}">${escapeHtml(field.label)}</label><select id="field-${field.name}" name="${field.name}" ${multiple} ${required}><option value="">${placeholder}</option>${options}</select>${help}</div>`;
  }

  if (field.type === "textarea" || field.type === "json") {
    const content = field.type === "json" && typeof value === "object" ? JSON.stringify(value, null, 2) : value;
    return `<div class="field ${full}"><label for="field-${field.name}">${escapeHtml(field.label)}</label><textarea id="field-${field.name}" name="${field.name}" placeholder="${escapeHtml(field.placeholder || "")}" ${required}>${escapeHtml(content)}</textarea>${help}</div>`;
  }

  return `<div class="field ${full}"><label for="field-${field.name}">${escapeHtml(field.label)}</label><input id="field-${field.name}" name="${field.name}" type="${escapeHtml(field.type || "text")}" value="${escapeHtml(value)}" placeholder="${escapeHtml(field.placeholder || "")}" ${field.step ? `step="${field.step}"` : ""} ${field.min !== undefined ? `min="${field.min}"` : ""} ${field.max !== undefined ? `max="${field.max}"` : ""} ${required}>${help}</div>`;
}

function addValueRow(values = {}) {
  const row = document.createElement("div");
  row.className = "value-item";
  row.innerHTML = `<label>Parámetro<input name="result_name" value="${escapeHtml(values.nombre || "")}" placeholder="Ej.: hematocrito" required></label><label>Valor y unidad<input name="result_value" value="${escapeHtml(values.valor || "")}" placeholder="Ej.: 42 %" required></label><button type="button" class="icon-button" data-modal-action="remove-value" aria-label="Quitar parámetro">×</button>`;
  $("#result-values").append(row);
}

function addComponentRow(values = {}) {
  const list = $("#component-list");
  if (!list) return;
  const row = document.createElement("div");
  row.className = "repeat-item";
  row.innerHTML = `
    <label>Descripción<input name="component_descripcion" placeholder="Concepto facturado" value="${escapeHtml(values.descripcion || "")}" required></label>
    <label>Tipo<select name="component_tipo" aria-label="Tipo de componente" required>${choiceOptions(["atencion", "laboratorio", "vacuna", "insumo", "otro"], values.tipo || "otro")}</select></label>
    <label>Cantidad<input name="component_cantidad" type="number" step="0.01" min="0.01" value="${escapeHtml(values.cantidad || "1")}" required></label>
    <label>Precio unitario<input name="component_precio" type="number" step="0.01" min="0" value="${escapeHtml(values.precio_unitario ?? "")}" required></label>
    <label>Análisis asociado<select name="component_analisis" aria-label="Análisis asociado"><option value="">Sin vincular</option></select></label>
    <output class="component-subtotal" aria-label="Subtotal del componente"></output>
    <button type="button" class="icon-button" data-modal-action="remove-component" aria-label="Quitar">×</button>`;
  list.append(row);
  actualizarAnalisisFactura();
  actualizarTotalFactura();
}

function formConfig(name, context = {}) {
  const minimoTurno = fechaHoraLocal();
  const configs = {
    cliente: {
      title: context.id ? "Editar responsable" : "Nuevo responsable",
      eyebrow: "Clientes",
      endpoint: context.id ? `/clientes/${context.id}` : "/clientes",
      method: context.id ? "PATCH" : "POST",
      values: context.values || {},
      fields: [
        { name: "nombre", label: "Nombre", required: true },
        { name: "apellido", label: "Apellido", required: true },
        ...(!context.id ? [
          { name: "tipo_documento", label: "Tipo de documento", type: "select", choices: ["dni", "pasaporte", "cuit"], value: "dni", required: true },
          { name: "numero_documento", label: "Número de documento", required: true },
        ] : []),
        { name: "email", label: "Correo electrónico", type: "email", required: true },
        { name: "telefono", label: "Teléfono", type: "tel", required: true },
        { name: "direccion", label: "Dirección", full: true },
      ],
    },
    mascota: {
      title: context.id ? "Editar paciente" : "Nuevo paciente",
      eyebrow: "Mascotas",
      endpoint: context.id ? `/mascotas/${context.id}` : "/mascotas",
      method: context.id ? "PATCH" : "POST",
      values: context.values || {},
      fields: [
        ...(!context.id ? [{ name: "cliente_id", label: "Responsable", type: "select", source: "clientes", required: true }] : []),
        { name: "nombre", label: "Nombre", required: true },
        { name: "especie", label: "Especie", required: true, placeholder: "Perro, gato…" },
        { name: "raza", label: "Raza" },
        { name: "sexo", label: "Sexo", type: "select", choices: [["macho", "Macho"], ["hembra", "Hembra"], ["no_especificado", "No especificado"]], value: "no_especificado", required: true },
        { name: "fecha_nacimiento", label: "Fecha de nacimiento", type: "date" },
        { name: "color", label: "Color" },
        { name: "microchip", label: "Microchip" },
        { name: "peso_kg", label: "Peso (kg)", type: "number", step: "0.01", min: "0.01" },
        ...(context.id ? [{ name: "activo", label: "Paciente activo", type: "checkbox" }] : []),
      ],
    },
    historia: {
      title: "Actualizar historia clínica",
      eyebrow: context.petName || "Paciente",
      endpoint: `/mascotas/${context.id}/historia-clinica`,
      method: "PATCH",
      values: context.values || {},
      fields: [
        { name: "antecedentes", label: "Antecedentes", type: "textarea" },
        { name: "alergias", label: "Alergias", type: "textarea" },
        { name: "observaciones", label: "Observaciones", type: "textarea" },
      ],
    },
    clinica: {
      title: "Nueva clínica", eyebrow: "Configuración", endpoint: "/clinicas", method: "POST", fields: [
        { name: "nombre", label: "Nombre", required: true }, { name: "codigo", label: "Código", required: true },
        { name: "cuit", label: "CUIT", required: true }, { name: "telefono", label: "Teléfono", required: true },
        { name: "email", label: "Correo electrónico", type: "email", required: true }, { name: "direccion", label: "Dirección", full: true, required: true },
      ],
    },
    laboratorio: {
      title: "Configurar laboratorio central", eyebrow: "Configuración", endpoint: "/laboratorio", method: "POST", fields: [
        { name: "nombre", label: "Nombre", required: true }, { name: "codigo", label: "Código", required: true },
        { name: "telefono", label: "Teléfono", required: true }, { name: "email", label: "Correo electrónico", type: "email", required: true },
        { name: "direccion", label: "Dirección", full: true, required: true },
      ],
    },
    profesional: {
      title: "Nuevo profesional", eyebrow: "Equipo clínico", endpoint: "/profesionales", method: "POST", fields: [
        { name: "clinica_id", label: "Clínica", type: "select", source: "clinicas", required: true }, { name: "matricula", label: "Matrícula", required: true },
        { name: "nombre", label: "Nombre", required: true }, { name: "apellido", label: "Apellido", required: true },
        { name: "especialidad", label: "Especialidad" }, { name: "telefono", label: "Teléfono", required: true },
        { name: "email", label: "Correo electrónico", type: "email", full: true, required: true },
      ],
    },
    analisis: {
      title: "Nuevo análisis", eyebrow: "Catálogo de laboratorio", endpoint: "/analisis", method: "POST", fields: [
        { name: "laboratorio_id", label: "Laboratorio", type: "select", source: "laboratorio", required: true }, { name: "codigo", label: "Código", required: true },
        { name: "nombre", label: "Nombre", required: true }, { name: "tipo_muestra", label: "Tipo de muestra", type: "select", choices: ["sangre", "orina", "materia_fecal", "tejido", "hisopado", "otro"], required: true },
        { name: "precio", label: "Precio", type: "number", min: "0", step: "0.01", required: true }, { name: "tiempo_estimado_horas", label: "Tiempo estimado (horas)", type: "number", min: "1", required: true },
        { name: "requiere_ayuno", label: "Requiere ayuno", type: "checkbox" }, { name: "descripcion", label: "Descripción", type: "textarea", full: true },
      ],
    },
    vacuna: {
      title: "Nueva vacuna", eyebrow: "Catálogo sanitario", endpoint: "/vacunas", method: "POST", fields: [
        { name: "nombre", label: "Nombre", required: true }, { name: "laboratorio_fabricante", label: "Laboratorio fabricante", required: true },
        { name: "especie_objetivo", label: "Especie objetivo", required: true }, { name: "dosis_ml", label: "Dosis (ml)", type: "number", step: "0.01", min: "0.01", required: true },
        { name: "edad_minima_dias", label: "Edad mínima (días)", type: "number", min: "0", value: "0", required: true }, { name: "intervalo_refuerzo_dias", label: "Refuerzo (días)", type: "number", min: "1" },
        { name: "obligatoria", label: "Vacuna obligatoria", type: "checkbox", checked: true },
      ],
    },
    contenedor: {
      title: "Nuevo contenedor", eyebrow: "Conservadoras isotérmicas", endpoint: "/contenedores", method: "POST", fields: [
        { name: "codigo", label: "Código", required: true }, { name: "capacidad_muestras", label: "Capacidad de muestras", type: "number", min: "1", required: true },
        { name: "temperatura_min_c", label: "Temperatura mínima (°C)", type: "number", step: "0.1", required: true }, { name: "temperatura_max_c", label: "Temperatura máxima (°C)", type: "number", step: "0.1", required: true },
        { name: "descripcion", label: "Descripción", full: true },
      ],
    },
    turno: {
      title: "Agendar atención", eyebrow: "Agenda médica", endpoint: "/turnos", method: "POST", fields: [
        { name: "tipo", label: "Tipo de atención", type: "select", choices: ["consulta", "control", "urgencia"], value: "consulta", required: true },
        { name: "clinica_id", label: "Clínica", type: "select", source: "clinicas", required: true }, { name: "profesional_id", label: "Profesional", type: "select", source: "profesionales", required: true },
        { name: "mascota_id", label: "Paciente", type: "select", source: "mascotas", required: true }, { name: "motivo", label: "Motivo", required: true },
        { name: "inicio", label: "Día y horario", type: "datetime-local", min: minimoTurno, required: true }, { name: "fin", label: "Finalización", type: "datetime-local", min: minimoTurno, required: true },
        { name: "observaciones", label: "Observaciones", type: "textarea", full: true },
      ],
    },
    atencion: {
      title: "Registrar atención", eyebrow: "Atención clínica", endpoint: "/atenciones", method: "POST", fields: [
        { name: "mascota_id", label: "Paciente", type: "select", source: "mascotas", required: true }, { name: "clinica_id", label: "Clínica", type: "select", source: "clinicas", required: true },
        { name: "profesional_id", label: "Profesional", type: "select", source: "profesionales", required: true }, { name: "turno_id", label: "Turno asociado", type: "select", source: "turnos" },
        { name: "tipo", label: "Tipo", type: "select", choices: ["consulta", "control", "urgencia"], required: true }, { name: "motivo", label: "Motivo", required: true },
        { name: "peso_kg", label: "Peso (kg)", type: "number", step: "0.01", min: "0.01" }, { name: "temperatura_c", label: "Temperatura (°C)", type: "number", step: "0.1", min: "24", max: "45" },
      ],
    },
    aplicacionVacuna: {
      title: "Registrar vacuna aplicada", eyebrow: "Vacunación", endpoint: "/vacunas/aplicaciones", method: "POST", fields: [
        { name: "mascota_id", label: "Paciente", type: "select", source: "mascotas", required: true }, { name: "vacuna_id", label: "Vacuna", type: "select", source: "vacunas", required: true },
        { name: "profesional_id", label: "Profesional", type: "select", source: "profesionales", required: true }, { name: "atencion_id", label: "Atención", type: "select", source: "atenciones", required: true },
        { name: "aplicada_en", label: "Fecha y hora", type: "datetime-local", required: true }, { name: "dosis_ml", label: "Dosis (ml)", type: "number", step: "0.01", min: "0.01" },
        { name: "lote", label: "Lote", required: true }, { name: "fecha_vencimiento_lote", label: "Vencimiento del lote", type: "date" },
        { name: "proxima_dosis", label: "Próxima dosis", type: "date" }, { name: "observaciones", label: "Observaciones", type: "textarea" },
      ],
    },
    orden: {
      title: "Nueva orden de derivación", eyebrow: "Laboratorio", endpoint: "/ordenes-derivacion", method: "POST", fields: [
        { name: "atencion_id", label: "Atención", type: "select", source: "atenciones", required: true }, { name: "laboratorio_id", label: "Laboratorio", type: "select", source: "laboratorio", required: true },
        { name: "profesional_solicitante_id", label: "Profesional solicitante", type: "select", source: "profesionales", required: true }, { name: "prioridad", label: "Prioridad", type: "select", choices: ["normal", "urgente"], value: "normal", required: true },
        { name: "analisis_ids", label: "Análisis solicitados", type: "multiselect", source: "analisis", required: true, full: true, help: "Use Ctrl o Cmd para seleccionar más de uno." },
        { name: "indicaciones", label: "Indicaciones", type: "textarea", full: true },
      ],
    },
    muestra: {
      title: "Registrar extracción", eyebrow: "Muestra biológica", endpoint: "/muestras", method: "POST", fields: [
        { name: "orden_id", label: "Orden de derivación", type: "select", source: "ordenes", required: true }, { name: "tipo", label: "Tipo de muestra", type: "select", choices: ["sangre", "orina", "materia_fecal", "tejido", "hisopado", "otro"], required: true },
        { name: "volumen_ml", label: "Volumen (ml)", type: "number", step: "0.01", min: "0.01", required: true }, { name: "extraida_por", label: "Extraída por", required: true },
        { name: "temperatura_min_c", label: "Temperatura mínima (°C)", type: "number", step: "0.1", required: true }, { name: "temperatura_max_c", label: "Temperatura máxima (°C)", type: "number", step: "0.1", required: true },
        { name: "sitio_extraccion", label: "Sitio de extracción" }, { name: "observaciones", label: "Observaciones", type: "textarea" },
      ],
    },
    empaquetado: {
      title: "Empaquetar muestras", eyebrow: "Remito biológico", endpoint: "/muestras/empaquetar", method: "POST", fields: [
        { name: "muestra_ids", label: "Muestras extraídas", type: "multiselect", source: "muestras", required: true, full: true, help: "Seleccione muestras compatibles del mismo origen y destino." },
        { name: "contenedor_id", label: "Contenedor", type: "select", source: "contenedores", required: true }, { name: "codigo_precinto", label: "Código de precinto", required: true },
        { name: "clinica_origen_id", label: "Clínica de origen", type: "select", source: "clinicas", required: true }, { name: "laboratorio_destino_id", label: "Laboratorio de destino", type: "select", source: "laboratorio", required: true },
        { name: "temperatura_salida_c", label: "Temperatura de salida (°C)", type: "number", step: "0.1", required: true }, { name: "preparado_por", label: "Preparado por", required: true },
      ],
    },
    despacho: {
      title: `Despachar remito ${context.number || ""}`, eyebrow: "Inicio de transporte", endpoint: `/remitos/${context.id}/despachar`, method: "POST", fields: [
        { name: "transportista", label: "Transportista", required: true }, { name: "conductor", label: "Conductor", required: true },
        { name: "vehiculo", label: "Vehículo", required: true }, { name: "temperatura_salida_c", label: "Temperatura de salida (°C)", type: "number", step: "0.1", required: true },
      ],
    },
    transferencia: {
      title: "Registrar evento de custodia", eyebrow: "Envío en tránsito", endpoint: `/envios/${context.id}/eventos-custodia`, method: "POST", values: { tipo_evento: "transferencia" }, fields: [
        { name: "tipo_evento", label: "Tipo", type: "select", choices: ["transferencia"], required: true }, { name: "actor", label: "Responsable", required: true },
        { name: "ubicacion", label: "Ubicación", required: true }, { name: "temperatura_c", label: "Temperatura (°C)", type: "number", step: "0.1" },
        { name: "observaciones", label: "Observaciones", type: "textarea", full: true },
      ],
    },
    recepcion: {
      title: `Recibir remito ${context.number || ""}`, eyebrow: "Laboratorio central", endpoint: `/remitos/${context.id}/recibir`, method: "POST", fields: [
        { name: "precinto_intacto", label: "Precinto intacto", type: "checkbox", checked: true }, { name: "receptor", label: "Recibido por", required: true },
        { name: "temperatura_recepcion_c", label: "Temperatura de recepción (°C)", type: "number", step: "0.1", required: true },
        { name: "observaciones", label: "Observaciones o motivo de rechazo", type: "textarea", full: true, help: "Si el precinto está roto, detalle el motivo para rechazar la muestra." },
      ],
    },
    resultado: {
      title: "Registrar resultado", eyebrow: "Análisis de laboratorio", endpoint: "/resultados", method: "POST", fields: [
        { name: "orden_analisis_id", label: "Análisis listo para informar", type: "select", source: "solicitudesListas", required: true, value: context.solicitudId || "", help: "Solo se muestran análisis sin resultado de muestras recibidas y viables." },
        { name: "validado_por", label: "Validado por", required: true },
        { name: "valores", label: "Parámetros del análisis", type: "values", full: true, required: true, help: "Ingresá un parámetro por fila con su valor y unidad. No necesitás escribir JSON." },
        { name: "conclusion", label: "Conclusión", type: "textarea", required: true }, { name: "observaciones", label: "Observaciones", type: "textarea" },
      ],
    },
    factura: {
      title: "Emitir factura", eyebrow: "Facturación", endpoint: "/facturas", method: "POST", fields: [
        { name: "cliente_id", label: "Cliente", type: "select", source: "clientes", required: true }, { name: "clinica_id", label: "Clínica", type: "select", source: "clinicas", required: true },
        { name: "atencion_id", label: "Atención", type: "select", source: "atenciones" }, { name: "orden_derivacion_id", label: "Orden de derivación", type: "select", source: "ordenes" },
        { name: "componentes", label: "Conceptos a facturar", type: "repeat", full: true, help: "El importe mostrado es una vista previa. El backend recalcula el total al emitir." },
      ],
    },
  };
  const config = configs[name];
  if (!config) throw new Error(`Formulario desconocido: ${name}`);
  return {
    fields: [],
    ...config,
    values: { ...(config.values || {}), ...(context.values || {}) },
    key: name,
  };
}

function opcionesFiltradas(nombre, origen, items, vacio = "Seleccione…", autoseleccionar = true) {
  const select = modalForm.elements[nombre];
  if (!select) return;
  const anterior = select.value;
  select.innerHTML = `<option value="">${items.length ? vacio : "No hay opciones compatibles"}</option>`
    + items.map((item) => `<option value="${escapeHtml(item.id)}">${escapeHtml(itemLabel(origen, item))}</option>`).join("");
  select.value = items.some((item) => item.id === anterior) ? anterior : "";
  if (autoseleccionar && !select.value && items.length === 1) select.value = items[0].id;
}

function sincronizarProfesionales() {
  const clinica = modalForm.elements.clinica_id?.value;
  opcionesFiltradas("profesional_id", "profesionales",
    (state.cache.profesionales || []).filter((p) => p.activo && p.clinica_id === clinica),
    "Seleccione profesional");
}

function sincronizarTurnoAtencion() {
  if (state.modal?.key !== "atencion") return;
  const campos = modalForm.elements;
  opcionesFiltradas("turno_id", "turnos", (state.cache.turnos || []).filter((t) =>
    ["programado", "confirmado"].includes(t.estado) && new Date(t.inicio) <= new Date()
    && (!campos.mascota_id.value || t.mascota_id === campos.mascota_id.value)
    && (!campos.clinica_id.value || t.clinica_id === campos.clinica_id.value)
    && (!campos.profesional_id.value || t.profesional_id === campos.profesional_id.value)),
  "Sin turno asociado", false);
}

function actualizarAgenda() {
  const contenedor = $("#agenda-content");
  if (!contenedor || state.modal?.key !== "turno") return;
  const profesional = modalForm.elements.profesional_id.value;
  const dia = $("#agenda-day").value;
  const inicio = modalForm.elements.inicio;
  const fin = modalForm.elements.fin;
  inicio.setCustomValidity("");
  if (!profesional) {
    contenedor.innerHTML = '<p class="inline-note">Elegí una clínica y un profesional para consultar los horarios ocupados.</p>';
    return;
  }
  const ocupados = turnosDelDia(state.cache.turnos || [], profesional, dia);
  const conflictos = buscarConflictos(state.cache.turnos || [], profesional, inicio.value, fin.value);
  if (conflictos.length) inicio.setCustomValidity("El horario se superpone con un turno del profesional.");
  const duracion = (new Date(fin.value) - new Date(inicio.value)) / 60000;
  const sugerencias = sugerirHorarios(state.cache.turnos || [], profesional, dia,
    duracion > 0 ? duracion : 30);
  contenedor.innerHTML = `
    ${conflictos.length ? '<p class="inline-note is-danger" role="alert">El intervalo elegido se superpone con un turno. Elegí otro horario.</p>' : ""}
    <h4>Horarios ocupados</h4>
    ${ocupados.length ? table(ocupados, [
      { label: "Inicio", value: (t) => formatDate(t.inicio) },
      { label: "Fin", value: (t) => formatDate(t.fin) },
      { label: "Paciente", value: (t) => relatedLabel("mascotas", t.mascota_id) },
      { label: "Estado", html: true, value: (t) => badge(t.estado) },
    ]) : '<p class="inline-note">No hay turnos ocupados registrados para este día.</p>'}
    <h4>Horarios sin superposición · ${duracion > 0 ? duracion : 30} minutos</h4>
    <p class="field-help">Sugerencias entre las 08:00 y las 20:00; no representan el horario laboral del profesional. También podés indicar otro intervalo manualmente. La disponibilidad se confirma al guardar.</p>
    <div class="slot-list">${sugerencias.map((slot) => `<button type="button" class="button button-secondary button-small" data-modal-action="choose-slot" data-start="${fechaHoraLocal(slot.inicio)}" data-end="${fechaHoraLocal(slot.fin)}">${slot.inicio.toLocaleTimeString("es-AR", { hour: "2-digit", minute: "2-digit" })}</button>`).join("") || '<p class="inline-note">No quedan sugerencias para este día y duración.</p>'}</div>`;
}

function actualizarAnalisisFactura() {
  const ordenId = modalForm.elements.orden_derivacion_id?.value;
  const detalle = (state.cache.detalleOrdenes || []).find((d) => d.orden.id === ordenId);
  for (const row of $$(".repeat-item", modalFields)) {
    const select = $('[name="component_analisis"]', row);
    const anterior = select.value;
    const laboratorio = $('[name="component_tipo"]', row).value === "laboratorio";
    select.innerHTML = '<option value="">Sin vincular</option>' + (detalle?.analisis_solicitados || [])
      .map((a) => `<option value="${escapeHtml(a.id)}">${escapeHtml(a.analisis.nombre)}</option>`).join("");
    select.value = laboratorio && [...select.options].some((o) => o.value === anterior) ? anterior : "";
    select.disabled = !laboratorio || !detalle;
  }
}

function actualizarTotalFactura() {
  const resumen = $("#invoice-preview");
  let total = 0;
  for (const row of $$(".repeat-item", modalFields)) {
    const cantidad = Number($('[name="component_cantidad"]', row).value);
    const precio = Number($('[name="component_precio"]', row).value);
    const subtotal = Number.isFinite(cantidad * precio) && cantidad > 0 && precio >= 0
      ? Math.round((cantidad * precio + Number.EPSILON) * 100) / 100 : 0;
    total += subtotal;
    $(".component-subtotal", row).textContent = formatMoney(subtotal);
  }
  if (resumen) resumen.textContent = `Total estimado: ${formatMoney(total)}`;
}

function sincronizarFactura() {
  const cliente = modalForm.elements.cliente_id.value;
  const clinica = modalForm.elements.clinica_id.value;
  const facturadas = new Set((state.cache.facturas || []).map((f) => f.atencion_id));
  opcionesFiltradas("atencion_id", "atenciones", (state.cache.atenciones || []).filter((a) =>
    !facturadas.has(a.id) && a.clinica_id === clinica
    && findById("mascotas", a.mascota_id)?.cliente_id === cliente), "Sin atención asociada");
  const atencion = modalForm.elements.atencion_id.value;
  opcionesFiltradas("orden_derivacion_id", "ordenes", (state.cache.ordenes || []).filter((o) => {
    const a = findById("atenciones", o.atencion_id);
    return a?.clinica_id === clinica
      && findById("mascotas", a.mascota_id)?.cliente_id === cliente
      && (!atencion || o.atencion_id === atencion);
  }), "Sin orden asociada");
  actualizarAnalisisFactura();
}

async function openForm(name, context = {}) {
  if (controlEnvioModal.estaEnviando()) return;
  const formRequest = ++state.formRequest;
  closeDrawer();
  const config = formConfig(name, context);
  controlEnvioModal.restablecer(config.method);
  await loadCatalogs();
  if (name === "factura") {
    await fetchCached("atenciones", "/atenciones", true);
  }
  if (name === "turno") await fetchCached("turnos", "/turnos", true);
  if (["resultado", "factura"].includes(name)) {
    state.cache.detalleOrdenes = await Promise.all((state.cache.ordenes || [])
      .map((o) => api(`/ordenes-derivacion/${o.id}`)));
    state.cache.solicitudesListas = state.cache.detalleOrdenes.flatMap((detalle) =>
      detalle.analisis_solicitados.filter((s) => !s.resultado
        && ["recibida", "analizada"].includes(findById("muestras", s.muestra_id)?.estado_actual))
        .map((s) => ({ ...s, nombre: `${s.analisis.nombre} · ${detalle.orden.numero}` })));
  }
  if (formRequest !== state.formRequest) return;
  state.modal = config;
  state.modalTrigger = document.activeElement;
  $("#modal-title").textContent = config.title;
  $("#modal-eyebrow").textContent = config.eyebrow;
  modalFields.innerHTML = `<div class="form-grid">${config.fields.map((field) => renderField(field, config.values || {})).join("")}</div>`;
  if (config.fields.some((field) => field.type === "repeat")) addComponentRow();
  if (name === "resultado") addValueRow();
  if (name === "resultado" && !state.cache.solicitudesListas.length)
    modalFields.insertAdjacentHTML("afterbegin", '<p class="inline-note">No hay análisis listos para informar. Primero recibí una muestra viable desde Custodia y envíos.</p>');
  if (name === "empaquetado") {
    opcionesFiltradas("contenedor_id", "contenedores", (state.cache.contenedores || []).filter((c) => c.estado === "disponible"));
    opcionesFiltradas("muestra_ids", "muestras", (state.cache.muestras || []).filter((m) => m.estado_actual === "extraida"));
  }
  if (["turno", "atencion"].includes(name)) sincronizarProfesionales();
  if (name === "atencion") sincronizarTurnoAtencion();
  if (name === "factura") {
    modalFields.insertAdjacentHTML("beforeend", '<output id="invoice-preview" class="invoice-preview" aria-live="polite"></output>');
    sincronizarFactura();
    actualizarTotalFactura();
  }
  if (name === "turno") {
    const inicio = $("#field-inicio", modalFields);
    const fin = $("#field-fin", modalFields);
    modalFields.insertAdjacentHTML("beforeend", `<section class="agenda-preview" aria-labelledby="agenda-title"><div class="agenda-heading"><h3 id="agenda-title">Agenda del profesional</h3><label>Día a consultar<input type="date" id="agenda-day" value="${fechaHoraLocal().slice(0, 10)}" min="${fechaHoraLocal().slice(0, 10)}"></label><button type="button" class="button button-secondary button-small" data-modal-action="refresh-agenda">Actualizar agenda</button></div><div id="agenda-content" aria-live="polite"></div></section>`);
    inicio.addEventListener("input", () => {
      fin.min = inicio.value || fechaHoraLocal();
      if (inicio.value) {
        $("#agenda-day").value = inicio.value.slice(0, 10);
        if (!fin.value || new Date(fin.value) <= new Date(inicio.value))
          fin.value = fechaHoraLocal(new Date(new Date(inicio.value).getTime() + 30 * 60000));
      }
      actualizarAgenda();
    });
    actualizarAgenda();
  }
  modalBackdrop.hidden = false;
  document.body.style.overflow = "hidden";
  window.setTimeout(() => $("input, select, textarea", modalFields)?.focus(), 20);
}

function closeModal() {
  if (controlEnvioModal.estaEnviando()) return false;
  ++state.formRequest;
  const method = state.modal?.method || "POST";
  modalBackdrop.hidden = true;
  document.body.style.overflow = "";
  modalForm.reset();
  modalForm.removeAttribute("aria-busy");
  controlEnvioModal.restablecer(method);
  state.modal = null;
  state.modalTrigger?.focus();
  return true;
}

function serializeForm(config) {
  const data = {};
  for (const field of config.fields) {
    if (["repeat", "values"].includes(field.type)) continue;
    const element = modalForm.elements[field.name];
    if (!element) continue;
    let value;
    if (field.type === "checkbox") value = element.checked;
    else if (field.type === "multiselect") value = [...element.selectedOptions].map((option) => option.value).filter(Boolean);
    else value = element.value.trim();

    if (value === "" && !field.required) continue;
    if (field.type === "number" && value !== "") {
      value = validarNumeroEnRango(value, field.min, field.max, field.label);
    }
    if (field.type === "json") {
      try { value = JSON.parse(value); }
      catch { throw new Error(`El campo ${field.label} no contiene JSON válido.`); }
    }
    data[field.name] = value;
  }

  if (config.key === "turno") {
    validarIntervaloTurno(data.inicio, data.fin);
    if (buscarConflictos(state.cache.turnos || [], data.profesional_id, data.inicio, data.fin).length)
      throw new Error("El profesional ya tiene un turno en ese intervalo. Elegí otro horario.");
  }
  if (config.key === "resultado") data.valores = valoresDesdeFilas($$(".value-item", modalFields)
    .map((row) => ({ nombre: $('[name="result_name"]', row).value, valor: $('[name="result_value"]', row).value })));

  if (config.key === "factura") {
    const rows = $$(".repeat-item", modalFields);
    data.componentes = rows.map((row) => {
      const component = {
        descripcion: $('[name="component_descripcion"]', row).value.trim(),
        tipo: $('[name="component_tipo"]', row).value,
        cantidad: Number($('[name="component_cantidad"]', row).value),
        precio_unitario: Number($('[name="component_precio"]', row).value),
      };
      const analysisId = $('[name="component_analisis"]', row).value.trim();
      if (analysisId) component.orden_analisis_id = analysisId;
      return component;
    });
    if (!data.componentes.length) throw new Error("La factura requiere al menos un componente.");
  }
  return data;
}

async function submitModal(event) {
  event.preventDefault();
  const config = state.modal;
  if (!config) return;
  if (!modalForm.reportValidity()) return;
  let body;
  try {
    body = serializeForm(config);
  } catch (error) {
    toast(error.message, "error");
    return;
  }
  if (!controlEnvioModal.iniciar(config.method)) return;
  modalForm.setAttribute("aria-busy", "true");
  let guardado = false;
  try {
    await api(config.endpoint, { method: config.method, body });
    guardado = true;
  } catch (error) {
    toast(error.message, "error");
  } finally {
    modalForm.removeAttribute("aria-busy");
    controlEnvioModal.restablecer(config.method);
  }
  if (!guardado) return;
  closeModal();
  state.cache = {};
  toast("Los datos se guardaron correctamente.");
  await renderCurrentView();
}

function openDrawer(title, data, eyebrow = "Detalle") {
  drawer.inert = false;
  $("#drawer-title").textContent = title;
  $("#drawer-eyebrow").textContent = eyebrow;
  $("#drawer-content").innerHTML = renderDetail(data);
  drawer.classList.add("is-open");
  drawer.setAttribute("aria-hidden", "false");
}

function closeDrawer() {
  drawer.inert = true;
  drawer.classList.remove("is-open");
  drawer.setAttribute("aria-hidden", "true");
}

function renderDetail(data) {
  if (data === null || data === undefined) return `<div class="empty-state"><span class="empty-mark">i</span><strong>Sin información</strong></div>`;
  if (Array.isArray(data)) return data.map((item, index) => `<h3>Registro ${index + 1}</h3>${renderDetail(item)}`).join("");
  if (typeof data !== "object") return `<p>${escapeHtml(displayValue(data))}</p>`;
  const relaciones = { cliente_id: "clientes", mascota_id: "mascotas", clinica_id: "clinicas",
    clinica_origen_id: "clinicas", laboratorio_id: "laboratorio", laboratorio_destino_id: "laboratorio",
    profesional_id: "profesionales", profesional_solicitante_id: "profesionales", atencion_id: "atenciones",
    orden_id: "ordenes", orden_derivacion_id: "ordenes", muestra_id: "muestras", contenedor_id: "contenedores",
    remito_id: "remitos", envio_id: "envios", vacuna_id: "vacunas", analisis_id: "analisis" };
  return `<dl class="detail-list">${Object.entries(data).filter(([key]) =>
    !["id", "creado_en", "actualizado_en", "clave_singleton", "historia_clinica_id", "cadena_custodia_id"].includes(key))
    .map(([key, value]) => {
      let rendered;
      if (typeof value === "object" && value !== null) rendered = `<div class="nested-detail">${value instanceof Array && !value.length ? "Sin registros" : renderDetail(value)}</div>`;
      else if (relaciones[key] && value) rendered = escapeHtml(relatedLabel(relaciones[key], value));
      else if (value && /^\d{4}-\d{2}-\d{2}/.test(String(value))) rendered = escapeHtml(formatDate(value, String(value).length > 10));
      else if (["subtotal", "total", "precio", "precio_unitario", "descuento", "importe_neto", "importe_bruto"].includes(key)) rendered = escapeHtml(formatMoney(value));
      else rendered = escapeHtml(displayValue(value));
      return `<div class="detail-row"><dt>${escapeHtml(titleCase(key.replace(/_id$/, "")))}</dt><dd>${rendered}</dd></div>`;
    }).join("")}</dl>`;
}

function renderFacturaDetalle(detail) {
  const factura = detail.factura;
  const cliente = findById("clientes", factura.cliente_id);
  return `<article class="invoice-document">
    <div class="invoice-heading"><span class="eyebrow">Comprobante de atención</span><h3>${escapeHtml(factura.numero)}</h3>${badge(factura.estado)}</div>
    <dl class="history-grid"><div><dt>Responsable</dt><dd>${escapeHtml(relatedLabel("clientes", factura.cliente_id))}</dd></div>
    <div><dt>Clínica</dt><dd>${escapeHtml(relatedLabel("clinicas", factura.clinica_id))}</dd></div>
    <div><dt>Emisión</dt><dd>${formatDate(factura.fecha_emision, false)}</dd></div>
    <div><dt>Vencimiento</dt><dd>${formatDate(factura.fecha_vencimiento, false)}</dd></div></dl>
    ${cliente?.direccion ? `<p class="inline-note">${escapeHtml(cliente.direccion)}</p>` : ""}
    ${table(detail.componentes || [], [
      { label: "Concepto", value: "descripcion" },
      { label: "Tipo", value: (i) => titleCase(i.tipo) },
      { label: "Cantidad", value: "cantidad" },
      { label: "Precio unitario", value: (i) => formatMoney(i.precio_unitario) },
      { label: "Subtotal", value: (i) => formatMoney(i.subtotal) },
    ])}
    <dl class="invoice-totals"><div><dt>Subtotal</dt><dd>${formatMoney(factura.subtotal)}</dd></div>
    <div><dt>Descuento</dt><dd>${formatMoney(factura.descuento)}</dd></div>
    <div class="invoice-total"><dt>Total</dt><dd>${formatMoney(factura.total)}</dd></div></dl>
    ${factura.observaciones ? `<p>${escapeHtml(factura.observaciones)}</p>` : ""}
    </article>`;
}

function renderHistoriaClinica(detail) {
  const mascota = detail.mascota || {};
  const historia = detail.historia || {};
  const atenciones = [...(detail.atenciones || [])].sort((a, b) =>
    String(b.fecha || "").localeCompare(String(a.fecha || "")),
  );
  const resumen = [
    ["Especie", mascota.especie],
    ["Raza", mascota.raza],
    ["Sexo", titleCase(mascota.sexo)],
    ["Peso actual", mascota.peso_kg ? `${mascota.peso_kg} kg` : null],
    ["Nacimiento", formatDate(mascota.fecha_nacimiento, false)],
    ["Microchip", mascota.microchip],
  ];
  const antecedentes = [
    ["Antecedentes", historia.antecedentes],
    ["Alergias", historia.alergias],
    ["Observaciones", historia.observaciones],
  ];
  const grillaAtenciones = table(atenciones, [
    { label: "Fecha", value: (item) => formatDate(item.fecha) },
    { label: "Tipo", html: true, value: (item) => badge(item.tipo) },
    { label: "Profesional", value: (item) => relatedLabel("profesionales", item.profesional_id) },
    { label: "Motivo", value: "motivo" },
    { label: "Peso", value: (item) => item.peso_kg ? `${item.peso_kg} kg` : "—" },
    { label: "Temp.", value: (item) => item.temperatura_c ? `${item.temperatura_c} °C` : "—" },
  ], "Todavía no hay atenciones en esta historia");

  return `<div class="history-layout">
    <section class="history-section">
      <h3>Datos del paciente</h3>
      <dl class="history-grid">${resumen.map(([label, value]) => `<div><dt>${escapeHtml(label)}</dt><dd>${escapeHtml(displayValue(value))}</dd></div>`).join("")}</dl>
    </section>
    <section class="history-section">
      <h3>Antecedentes clínicos</h3>
      <div class="history-notes">${antecedentes.map(([label, value]) => `<article><strong>${escapeHtml(label)}</strong><p>${escapeHtml(displayValue(value))}</p></article>`).join("")}</div>
    </section>
    <section class="history-section history-section-wide"><h3>Atenciones registradas</h3>${grillaAtenciones}</section>
  </div>`;
}

function emptyState(title, copy = "Cree el primer registro para comenzar.") {
  return `<div class="empty-state"><span class="empty-mark">+</span><strong>${escapeHtml(title)}</strong><span>${escapeHtml(copy)}</span></div>`;
}

function table(records, columns, emptyTitle = "Todavía no hay registros") {
  if (!records?.length) return emptyState(emptyTitle);
  return `<div class="table-wrap"><table><thead><tr>${columns.map((column) => `<th>${escapeHtml(column.label)}</th>`).join("")}</tr></thead><tbody>${records.map((record, index) => {
    const searchText = columns.map((column) => typeof column.value === "function"
      ? column.value(record, index) : record[column.value])
      .map((value) => displayValue(value).replace(/<[^>]*>/g, " ")).join(" ")
      .normalize("NFD").replace(/[\u0300-\u036f]/g, "").toLowerCase();
    return `<tr data-search-row data-search-text="${escapeHtml(searchText)}">${columns.map((column) => {
      const value = typeof column.value === "function" ? column.value(record, index) : record[column.value];
      return `<td>${column.html ? value : escapeHtml(displayValue(value))}</td>`;
    }).join("")}</tr>`;
  }).join("")}</tbody></table></div>`;
}

function panel(title, subtitle, content, actions = "") {
  return `<section class="panel"><header class="panel-header"><div><h2>${escapeHtml(title)}</h2>${subtitle ? `<p>${escapeHtml(subtitle)}</p>` : ""}</div>${actions}</header>${content}</section>`;
}

function sectionIntro(title, copy, actions = "") {
  return `<div class="section-intro"><div><h2>${escapeHtml(title)}</h2><p>${escapeHtml(copy)}</p></div><div class="button-row">${actions}</div></div>`;
}

function searchField(placeholder = "Buscar…") {
  return `<input class="compact-field" type="search" data-table-search placeholder="${escapeHtml(placeholder)}" aria-label="${escapeHtml(placeholder)}">`;
}

function actionButton(form, label, primary = false, context = "") {
  return `<button class="button ${primary ? "button-primary" : "button-secondary"}" data-action="open-form" data-form="${form}" ${context}>${escapeHtml(label)}</button>`;
}

function rowActions(buttons) {
  return `<div class="table-actions">${buttons.join("")}</div>`;
}

function smallAction(action, label, attrs = "") {
  return `<button class="button button-secondary button-small" data-action="${action}" ${attrs}>${escapeHtml(label)}</button>`;
}

function findById(source, id) {
  const items = source === "laboratorio" ? [state.cache.laboratorio].filter(Boolean) : state.cache[source] || [];
  return items.find((item) => item.id === id);
}

function relatedLabel(source, id) {
  return id ? itemLabel(source, findById(source, id)) : "—";
}

function renderDashboard() {
  const clients = state.cache.clientes || [];
  const pets = state.cache.mascotas || [];
  const appointments = state.cache.turnos || [];
  const samples = state.cache.muestras || [];
  const orders = state.cache.ordenes || [];
  const remittances = state.cache.remitos || [];
  const today = new Date().toISOString().slice(0, 10);
  const todayAppointments = appointments.filter((item) => String(item.inicio || "").startsWith(today));
  const activeSamples = samples.filter((item) => !["analizada", "rechazada"].includes(item.estado_actual));
  const inTransit = remittances.filter((item) => item.estado === "en_transito");
  const recentOrders = [...orders].slice(0, 6);

  root.innerHTML = `<div class="view-enter">
    <section class="hero-panel">
      <div class="hero-copy">
        <span class="eyebrow">Cuidado conectado</span>
        <h2>Salud animal con trazabilidad en cada paso.</h2>
        <p>Administre la atención clínica, las derivaciones y la custodia de muestras desde un mismo espacio sereno y preciso.</p>
        <div class="button-row">
          ${actionButton("turno", "Agendar atención", true)}
          ${actionButton("orden", "Nueva derivación")}
        </div>
      </div>
      <div class="hero-signal"><span>Cadena de custodia</span><strong>${activeSamples.length}</strong><small>muestras activas con seguimiento disponible</small></div>
    </section>
    <section class="kpi-grid">
      <article class="kpi-card"><span class="kpi-label">Pacientes activos</span><strong class="kpi-value">${pets.filter((item) => item.activo !== false).length}</strong><span class="kpi-caption">${clients.filter((item) => item.activo !== false).length} responsables registrados</span></article>
      <article class="kpi-card"><span class="kpi-label">Turnos de hoy</span><strong class="kpi-value">${todayAppointments.length}</strong><span class="kpi-caption">agenda sin superposiciones</span></article>
      <article class="kpi-card"><span class="kpi-label">Derivaciones</span><strong class="kpi-value">${orders.length}</strong><span class="kpi-caption">${orders.filter((item) => item.estado !== "completada").length} en curso</span></article>
      <article class="kpi-card"><span class="kpi-label">Envíos en tránsito</span><strong class="kpi-value">${inTransit.length}</strong><span class="kpi-caption">control de precinto y temperatura</span></article>
    </section>
    <section class="dashboard-grid">
      ${panel("Derivaciones recientes", "Estado del trabajo de laboratorio", `<div class="panel-body">${table(recentOrders, [
        { label: "Orden", html: true, value: (item) => `<div class="primary-cell"><strong>${escapeHtml(item.numero)}</strong><span>${shortId(item.id)}</span></div>` },
        { label: "Emisión", value: (item) => formatDate(item.fecha_emision) },
        { label: "Prioridad", html: true, value: (item) => badge(item.prioridad) },
        { label: "Estado", html: true, value: (item) => badge(item.estado) },
        { label: "", html: true, value: (item) => smallAction("order-detail", "Ver", `data-id="${item.id}"`) },
      ], "No hay derivaciones registradas")}</div>`)}
      ${panel("Accesos rápidos", "Operaciones frecuentes", `<div class="panel-body quick-actions">
        <button class="quick-action" data-action="open-form" data-form="turno"><span class="quick-action-icon">+</span><span><strong>Agendar atención</strong><small>Tipo, profesional y horario</small></span></button>
        <button class="quick-action" data-action="open-form" data-form="muestra"><span class="quick-action-icon">△</span><span><strong>Extraer muestra</strong><small>Iniciar la trazabilidad</small></span></button>
        <button class="quick-action" data-action="open-form" data-form="empaquetado"><span class="quick-action-icon">□</span><span><strong>Preparar remito</strong><small>Contenedor y precinto</small></span></button>
        <button class="quick-action" data-action="open-form" data-form="factura"><span class="quick-action-icon">$</span><span><strong>Emitir factura</strong><small>Atención y laboratorio</small></span></button>
      </div>`)}
    </section>
  </div>`;
}

function renderPacientes() {
  const clients = state.cache.clientes || [];
  const pets = state.cache.mascotas || [];
  const clientsTable = table(clients, [
    { label: "Responsable", html: true, value: (item) => `<div class="primary-cell"><strong>${escapeHtml(item.apellido)}, ${escapeHtml(item.nombre)}</strong><span>${escapeHtml(item.tipo_documento?.toUpperCase())} ${escapeHtml(item.numero_documento)}</span></div>` },
    { label: "Contacto", html: true, value: (item) => `<div class="primary-cell"><strong>${escapeHtml(item.email)}</strong><span>${escapeHtml(item.telefono)}</span></div>` },
    { label: "Estado", html: true, value: (item) => badge(item.activo ? "activo" : "inactivo") },
    { label: "Acciones", html: true, value: (item) => rowActions([
      smallAction("client-detail", "Ver", `data-id="${item.id}"`),
      smallAction("client-edit", "Editar", `data-id="${item.id}"`),
      item.activo ? `<button class="button button-danger button-small" data-action="client-deactivate" data-id="${item.id}">Desactivar</button>` : "",
    ]) },
  ], "No hay responsables registrados");
  const petsTable = table(pets, [
    { label: "Paciente", html: true, value: (item) => `<div class="primary-cell"><strong>${escapeHtml(item.nombre)}</strong><span>${escapeHtml(item.especie)}${item.raza ? ` · ${escapeHtml(item.raza)}` : ""}</span></div>` },
    { label: "Responsable", value: (item) => relatedLabel("clientes", item.cliente_id) },
    { label: "Peso", value: (item) => item.peso_kg ? `${item.peso_kg} kg` : "—" },
    { label: "Estado", html: true, value: (item) => badge(item.activo ? "activo" : "inactivo") },
    { label: "Acciones", html: true, value: (item) => rowActions([
      smallAction("pet-history", "Historia", `data-id="${item.id}"`),
      smallAction("pet-edit", "Editar", `data-id="${item.id}"`),
    ]) },
  ], "No hay pacientes registrados");
  root.innerHTML = `<div class="view-enter">
    ${sectionIntro("Pacientes y responsables", "Cada mascota conserva un responsable y una historia clínica única, disponibles para toda la red.", `${actionButton("cliente", "+ Responsable")}${actionButton("mascota", "+ Paciente", true)}`)}
    <div class="dashboard-grid">
      ${panel("Pacientes", `${pets.length} registros`, petsTable, searchField("Buscar paciente"))}
      ${panel("Responsables", `${clients.length} registros`, clientsTable, searchField("Buscar responsable"))}
    </div>
  </div>`;
}

function renderAtencion() {
  const appointments = [...(state.cache.turnos || [])].sort((a, b) => new Date(a.inicio) - new Date(b.inicio));
  const attentions = state.cache.atenciones || [];
  const applications = state.cache.aplicaciones || [];
  const appointmentTable = table(appointments, [
    { label: "Horario", html: true, value: (item) => `<div class="primary-cell"><strong>${escapeHtml(formatDate(item.inicio))}</strong><span>hasta ${escapeHtml(formatDate(item.fin))}</span></div>` },
    { label: "Paciente", value: (item) => relatedLabel("mascotas", item.mascota_id) },
    { label: "Profesional", value: (item) => relatedLabel("profesionales", item.profesional_id) },
    { label: "Tipo", html: true, value: (item) => badge(item.tipo || "consulta") },
    { label: "Motivo", value: "motivo" },
    { label: "Estado", html: true, value: (item) => badge(item.estado) },
    { label: "Acción", html: true, value: (item) => item.estado === "atendido" ? "Registrada"
      : ["cancelado", "ausente"].includes(item.estado) ? "No disponible"
      : new Date(item.inicio) > new Date() ? "Pendiente de inicio"
      : smallAction("appointment-attend", "Registrar", `data-id="${item.id}"`) },
  ], "No hay turnos programados");
  const attentionTable = table(attentions, [
    { label: "Atención", html: true, value: (item) => `<div class="primary-cell"><strong>${escapeHtml(titleCase(item.tipo))}</strong><span>${escapeHtml(formatDate(item.fecha))}</span></div>` },
    { label: "Paciente", value: (item) => relatedLabel("mascotas", item.mascota_id) },
    { label: "Clínica", value: (item) => relatedLabel("clinicas", item.clinica_id) },
    { label: "Motivo", value: "motivo" },
    { label: "Detalle", html: true, value: (item) => smallAction("generic-detail", "Ver", `data-source="atenciones" data-id="${item.id}"`) },
  ], "No hay atenciones registradas");
  const applicationTable = table(applications, [
    { label: "Aplicación", html: true, value: (item) => `<div class="primary-cell"><strong>${escapeHtml(formatDate(item.fecha_aplicacion))}</strong><span>Lote ${escapeHtml(item.lote)}</span></div>` },
    { label: "Paciente", value: (item) => relatedLabel("mascotas", item.mascota_id) },
    { label: "Vacuna", value: (item) => relatedLabel("vacunas", item.vacuna_id) },
    { label: "Dosis", value: (item) => `${item.dosis_ml} ml` },
    { label: "Próxima", value: (item) => formatDate(item.proxima_aplicacion, false) },
  ], "No hay vacunas aplicadas");
  root.innerHTML = `<div class="view-enter">
    ${sectionIntro("Agenda y atención", "Agende consultas, controles o urgencias eligiendo profesional, día y horario desde una única acción.", actionButton("turno", "Agendar atención", true))}
    <div class="dashboard-grid">
      ${panel("Próximos turnos", `${appointments.length} registros`, appointmentTable, searchField("Buscar turno"))}
      ${panel("Atenciones recientes", `${attentions.length} registros`, attentionTable, searchField("Buscar atención"))}
    </div>
    <div style="margin-top:18px">${panel("Vacunas aplicadas", `${applications.length} registros`, applicationTable, `<div class="panel-actions">${searchField("Buscar aplicación")}${actionButton("aplicacionVacuna", "Aplicar vacuna")}</div>`)}</div>
  </div>`;
}

function renderLaboratorio() {
  const orders = state.cache.ordenes || [];
  const samples = state.cache.muestras || [];
  const results = state.cache.resultados || [];
  const orderTable = table(orders, [
    { label: "Orden", html: true, value: (item) => `<div class="primary-cell"><strong>${escapeHtml(item.numero)}</strong><span>${escapeHtml(formatDate(item.fecha_emision))}</span></div>` },
    { label: "Atención", value: (item) => relatedLabel("atenciones", item.atencion_id) },
    { label: "Prioridad", html: true, value: (item) => badge(item.prioridad) },
    { label: "Estado", html: true, value: (item) => badge(item.estado) },
    { label: "Acciones", html: true, value: (item) => rowActions([
      smallAction("order-detail", "Detalle", `data-id="${item.id}"`),
      ...(["emitida", "muestra_extraida", "requiere_nueva_muestra"].includes(item.estado)
        ? [smallAction("open-form", "Extraer", `data-form="muestra" data-order-id="${item.id}"`)] : []),
    ]) },
  ], "No hay órdenes de derivación");
  const sampleTable = table(samples, [
    { label: "Muestra", html: true, value: (item) => `<div class="primary-cell"><strong>${escapeHtml(item.codigo)}</strong><span>${escapeHtml(titleCase(item.tipo))} · ${escapeHtml(item.volumen_ml)} ml</span></div>` },
    { label: "Orden", value: (item) => relatedLabel("ordenes", item.orden_id) },
    { label: "Estado", html: true, value: (item) => badge(item.estado_actual) },
    { label: "Rango", value: (item) => `${item.temperatura_min_c} a ${item.temperatura_max_c} °C` },
    { label: "Acciones", html: true, value: (item) => smallAction("sample-trace", "Trazabilidad", `data-id="${item.id}"`) },
  ], "No hay muestras biológicas");
  const resultTable = table(results, [
    { label: "Resultado", html: true, value: (item) => `<div class="primary-cell"><strong>${escapeHtml(shortId(item.id))}</strong><span>${escapeHtml(formatDate(item.fecha_resultado))}</span></div>` },
    { label: "Análisis solicitado", value: (item) => shortId(item.orden_analisis_id) },
    { label: "Validado por", value: "validado_por" },
    { label: "Conclusión", value: "conclusion" },
    { label: "", html: true, value: (item) => smallAction("generic-detail", "Ver", `data-source="resultados" data-id="${item.id}"`) },
  ], "No hay resultados registrados");
  root.innerHTML = `<div class="view-enter">
    ${sectionIntro("Derivaciones y laboratorio", "Emita órdenes, registre la extracción y publique resultados solamente cuando la muestra haya sido recibida en condiciones.", `${actionButton("muestra", "+ Extracción")}${actionButton("resultado", "+ Resultado")}${actionButton("orden", "+ Orden", true)}`)}
    <div class="card-grid" style="margin-bottom:18px">
      <article class="action-card"><h3>Orden de derivación</h3><p>Solicite uno o varios estudios al laboratorio central.</p>${actionButton("orden", "Crear orden")}</article>
      <article class="action-card"><h3>Extracción</h3><p>Registre tipo, volumen, rango térmico y responsable.</p>${actionButton("muestra", "Registrar muestra")}</article>
      <article class="action-card"><h3>Resultado</h3><p>Informe valores y conclusión para una muestra viable.</p>${actionButton("resultado", "Cargar resultado")}</article>
    </div>
    <div class="dashboard-grid">
      ${panel("Órdenes de derivación", `${orders.length} registros`, orderTable, searchField("Buscar orden"))}
      ${panel("Muestras biológicas", `${samples.length} registros`, sampleTable, searchField("Buscar muestra"))}
    </div>
    <div style="margin-top:18px">${panel("Resultados", `${results.length} registros`, resultTable, searchField("Buscar resultado"))}</div>
  </div>`;
}

function renderCustodia() {
  const remittances = state.cache.remitos || [];
  const shipments = state.cache.envios || [];
  const containers = state.cache.contenedores || [];
  const samples = state.cache.muestras || [];
  const remittanceTable = table(remittances, [
    { label: "Remito", html: true, value: (item) => `<div class="primary-cell"><strong>${escapeHtml(item.numero)}</strong><span>${escapeHtml(formatDate(item.fecha_emision))}</span></div>` },
    { label: "Contenedor", value: (item) => relatedLabel("contenedores", item.contenedor_id) },
    { label: "Origen", value: (item) => relatedLabel("clinicas", item.clinica_origen_id) },
    { label: "Estado", html: true, value: (item) => badge(item.estado) },
    { label: "Acciones", html: true, value: (item) => {
      const actions = [smallAction("remittance-trace", "Trazabilidad", `data-id="${item.id}"`)];
      if (item.estado === "emitido") actions.push(smallAction("dispatch", "Despachar", `data-id="${item.id}" data-number="${escapeHtml(item.numero)}"`));
      if (item.estado === "en_transito") actions.push(smallAction("receive", "Recibir", `data-id="${item.id}" data-number="${escapeHtml(item.numero)}"`));
      return rowActions(actions);
    } },
  ], "No hay remitos biológicos");
  const shipmentTable = table(shipments, [
    { label: "Envío", html: true, value: (item) => `<div class="primary-cell"><strong>${escapeHtml(item.transportista)}</strong><span>${escapeHtml(item.vehiculo)} · ${shortId(item.id)}</span></div>` },
    { label: "Salida", value: (item) => formatDate(item.fecha_salida) },
    { label: "Conductor", value: "conductor" },
    { label: "Estado", html: true, value: (item) => badge(item.estado) },
    { label: "Acción", html: true, value: (item) => item.estado === "en_transito" ? smallAction("transfer", "Evento", `data-id="${item.id}"`) : "—" },
  ], "No hay envíos registrados");
  const containerTable = table(containers, [
    { label: "Contenedor", html: true, value: (item) => `<div class="primary-cell"><strong>${escapeHtml(item.codigo)}</strong><span>${escapeHtml(item.descripcion || "Sin descripción")}</span></div>` },
    { label: "Capacidad", value: (item) => `${item.capacidad_muestras} muestras` },
    { label: "Rango", value: (item) => `${item.temperatura_min_c} a ${item.temperatura_max_c} °C` },
    { label: "Estado", html: true, value: (item) => badge(item.estado) },
  ], "No hay contenedores");
  root.innerHTML = `<div class="view-enter">
    ${sectionIntro("Cadena de custodia", "Proteja la viabilidad de cada muestra con precinto, control térmico y eventos inmutables desde la clínica hasta el laboratorio.", `${actionButton("contenedor", "+ Contenedor")}${actionButton("empaquetado", "Empaquetar muestras", true)}`)}
    <section class="kpi-grid" style="margin-top:0;margin-bottom:18px">
      <article class="kpi-card"><span class="kpi-label">Muestras extraídas</span><strong class="kpi-value">${samples.filter((item) => item.estado_actual === "extraida").length}</strong><span class="kpi-caption">listas para empaquetar</span></article>
      <article class="kpi-card"><span class="kpi-label">Remitos emitidos</span><strong class="kpi-value">${remittances.filter((item) => item.estado === "emitido").length}</strong><span class="kpi-caption">pendientes de despacho</span></article>
      <article class="kpi-card"><span class="kpi-label">En tránsito</span><strong class="kpi-value">${shipments.filter((item) => item.estado === "en_transito").length}</strong><span class="kpi-caption">con cadena activa</span></article>
      <article class="kpi-card"><span class="kpi-label">Contenedores disponibles</span><strong class="kpi-value">${containers.filter((item) => item.estado === "disponible").length}</strong><span class="kpi-caption">de ${containers.length} registrados</span></article>
    </section>
    <div class="dashboard-grid">
      ${panel("Remitos biológicos", `${remittances.length} registros`, remittanceTable, searchField("Buscar remito"))}
      ${panel("Envíos", `${shipments.length} registros`, shipmentTable, searchField("Buscar envío"))}
    </div>
    <div style="margin-top:18px">${panel("Contenedores isotérmicos", `${containers.length} registros`, containerTable, searchField("Buscar contenedor"))}</div>
  </div>`;
}

function renderFacturacion() {
  const invoices = state.cache.facturas || [];
  const total = invoices.reduce((sum, item) => sum + Number(item.total || 0), 0);
  const invoiceTable = table(invoices, [
    { label: "Comprobante", html: true, value: (item) => `<div class="primary-cell"><strong>${escapeHtml(item.numero)}</strong><span>${escapeHtml(formatDate(item.fecha_emision, false))}</span></div>` },
    { label: "Cliente", value: (item) => relatedLabel("clientes", item.cliente_id) },
    { label: "Clínica", value: (item) => relatedLabel("clinicas", item.clinica_id) },
    { label: "Estado", html: true, value: (item) => badge(item.estado) },
    { label: "Total", html: true, value: (item) => `<strong>${escapeHtml(formatMoney(item.total))}</strong>` },
    { label: "", html: true, value: (item) => smallAction("invoice-detail", "Detalle", `data-id="${item.id}"`) },
  ], "No hay facturas emitidas");
  root.innerHTML = `<div class="view-enter">
    ${sectionIntro("Facturación", "Emita comprobantes con componentes clínicos, de laboratorio, vacunación e insumos.", actionButton("factura", "+ Emitir factura", true))}
    <section class="kpi-grid" style="margin-top:0;margin-bottom:18px">
      <article class="kpi-card"><span class="kpi-label">Facturas</span><strong class="kpi-value">${invoices.length}</strong><span class="kpi-caption">comprobantes registrados</span></article>
      <article class="kpi-card"><span class="kpi-label">Total emitido</span><strong class="kpi-value" style="font-size:24px">${escapeHtml(formatMoney(total))}</strong><span class="kpi-caption">antes de anulaciones</span></article>
      <article class="kpi-card"><span class="kpi-label">Clínicas con actividad</span><strong class="kpi-value">${new Set(invoices.map((item) => item.clinica_id)).size}</strong><span class="kpi-caption">facturación distribuida</span></article>
      <article class="kpi-card"><span class="kpi-label">SQLite</span><strong class="kpi-value" style="font-size:24px">Local</strong><span class="kpi-caption">datos persistidos en el equipo</span></article>
    </section>
    ${panel("Comprobantes", `${invoices.length} registros`, invoiceTable, searchField("Buscar factura"))}
  </div>`;
}

function renderConfiguracion() {
  const clinics = state.cache.clinicas || [];
  const professionals = state.cache.profesionales || [];
  const analyses = state.cache.analisis || [];
  const vaccines = state.cache.vacunas || [];
  const lab = state.cache.laboratorio;
  const clinicTable = table(clinics, [
    { label: "Clínica", html: true, value: (item) => `<div class="primary-cell"><strong>${escapeHtml(item.nombre)}</strong><span>${escapeHtml(item.codigo)} · ${escapeHtml(item.cuit)}</span></div>` },
    { label: "Dirección", value: "direccion" }, { label: "Contacto", value: "telefono" }, { label: "Estado", html: true, value: (item) => badge(item.activa ? "activa" : "inactiva") },
  ], "No hay clínicas configuradas");
  const professionalTable = table(professionals, [
    { label: "Profesional", html: true, value: (item) => `<div class="primary-cell"><strong>${escapeHtml(item.apellido)}, ${escapeHtml(item.nombre)}</strong><span>${escapeHtml(item.matricula)}</span></div>` },
    { label: "Clínica", value: (item) => relatedLabel("clinicas", item.clinica_id) }, { label: "Especialidad", value: "especialidad" }, { label: "Estado", html: true, value: (item) => badge(item.activo ? "activo" : "inactivo") },
  ], "No hay profesionales");
  const analysisTable = table(analyses, [
    { label: "Análisis", html: true, value: (item) => `<div class="primary-cell"><strong>${escapeHtml(item.nombre)}</strong><span>${escapeHtml(item.codigo)}</span></div>` },
    { label: "Muestra", value: (item) => titleCase(item.tipo_muestra) }, { label: "Tiempo", value: (item) => `${item.tiempo_estimado_horas} h` }, { label: "Precio", value: (item) => formatMoney(item.precio) },
  ], "No hay análisis");
  const vaccineTable = table(vaccines, [
    { label: "Vacuna", html: true, value: (item) => `<div class="primary-cell"><strong>${escapeHtml(item.nombre)}</strong><span>${escapeHtml(item.laboratorio_fabricante)}</span></div>` },
    { label: "Especie", value: "especie_objetivo" }, { label: "Dosis", value: (item) => `${item.dosis_ml} ml` }, { label: "Obligatoria", html: true, value: (item) => badge(item.obligatoria ? "sí" : "no") },
  ], "No hay vacunas");
  root.innerHTML = `<div class="view-enter">
    ${sectionIntro("Configuración de la red", "Administre las entidades maestras que sostienen la operación clínica y de laboratorio.", `${!lab ? actionButton("laboratorio", "+ Laboratorio") : ""}${actionButton("clinica", "+ Clínica", true)}`)}
    <div class="card-grid" style="margin-bottom:18px">
      <article class="action-card"><h3>Laboratorio central</h3><p>${lab ? `${escapeHtml(lab.nombre)} · ${escapeHtml(lab.codigo)}` : "Todavía no fue configurado."}</p>${lab ? `<button class="button button-secondary" data-action="generic-detail" data-source="laboratorio">Ver configuración</button>` : actionButton("laboratorio", "Configurar")}</article>
      <article class="action-card"><h3>Equipo profesional</h3><p>${professionals.length} profesionales vinculados a las clínicas.</p>${actionButton("profesional", "Agregar profesional")}</article>
      <article class="action-card"><h3>Catálogos sanitarios</h3><p>Análisis, vacunas y contenedores disponibles.</p><div class="button-row">${actionButton("analisis", "+ Análisis")}${actionButton("vacuna", "+ Vacuna")}</div></article>
    </div>
    <div class="dashboard-grid">
      ${panel("Clínicas", `${clinics.length} registros`, clinicTable, searchField("Buscar clínica"))}
      ${panel("Profesionales", `${professionals.length} registros`, professionalTable, searchField("Buscar profesional"))}
    </div>
    <div class="dashboard-grid" style="margin-top:18px">
      ${panel("Análisis disponibles", `${analyses.length} registros`, analysisTable, searchField("Buscar análisis"))}
      ${panel("Vacunas", `${vaccines.length} registros`, vaccineTable, searchField("Buscar vacuna"))}
    </div>
  </div>`;
}

const reports = {
  "atenciones-derivaciones": { title: "Atenciones y derivaciones", copy: "Actividad clínica y tasa de derivación." },
  "muestras-rechazadas": { title: "Muestras rechazadas", copy: "Fallas de transporte y tasa de rechazo." },
  "tratamientos-vacunas": { title: "Tratamientos y vacunas", copy: "Seguimiento sanitario por paciente." },
  facturacion: { title: "Facturación", copy: "Importes por clínica y componente." },
  "tiempos-muestras": { title: "Tiempos logísticos", copy: "Tránsito, procesamiento y demoras." },
};

function renderReportResult() {
  const data = state.reportData;
  if (data === null) return emptyState("Seleccione filtros y genere el reporte", "Los resultados se calculan directamente sobre la base SQLite.");
  if (!data.length) return emptyState("Sin resultados para este rango", "Pruebe ampliando las fechas o quitando el filtro de clínica.");
  const key = state.reportKey;
  let columns;
  if (key === "atenciones-derivaciones") {
    columns = [
      { label: "Clínica", value: "clinica" }, { label: "Tipo", value: (item) => titleCase(item.tipo_atencion) },
      { label: "Atenciones", value: "atenciones" }, { label: "Derivaciones", value: "derivaciones" }, { label: "Tasa", value: (item) => `${item.tasa_derivacion_pct}%` },
    ];
  } else if (key === "muestras-rechazadas") {
    columns = [
      { label: "Clínica", value: "clinica" }, { label: "Motivo", value: "motivo_rechazo" }, { label: "Rechazadas", value: "muestras_rechazadas" },
      { label: "Enviadas", value: "muestras_enviadas" }, { label: "Tasa", value: (item) => `${item.tasa_rechazo_pct}%` },
    ];
  } else if (key === "tratamientos-vacunas") {
    columns = [
      { label: "Paciente", html: true, value: (item) => `<div class="primary-cell"><strong>${escapeHtml(item.mascota)}</strong><span>${escapeHtml(item.responsable)}</span></div>` },
      { label: "Especie", value: "especie" }, { label: "Tratamientos", value: "cantidad_tratamientos" }, { label: "Vacunas pendientes", value: "cantidad_vacunas_pendientes" },
      { label: "", html: true, value: (_item, index) => smallAction("report-detail", "Detalle", `data-index="${index}"`) },
    ];
  } else if (key === "facturacion") {
    columns = [
      { label: "Clínica", value: "clinica" }, { label: "Componente", value: (item) => titleCase(item.tipo_componente) }, { label: "Facturas", value: "facturas" },
      { label: "Bruto", value: (item) => formatMoney(item.importe_bruto) }, { label: "Descuentos", value: (item) => formatMoney(item.descuentos_prorrateados) }, { label: "Neto", html: true, value: (item) => `<strong>${escapeHtml(formatMoney(item.importe_neto))}</strong>` },
    ];
  } else {
    columns = [
      { label: "Clínica", value: "clinica" },
      { label: "Envíos", value: (item) => item.transito?.envios_completados },
      { label: "Tránsito promedio", value: (item) => item.transito?.promedio_horas === null ? "—" : `${item.transito.promedio_horas} h` },
      { label: "Demoras transporte", value: (item) => item.transito?.envios_demorados },
      { label: "Procesamiento promedio", value: (item) => item.procesamiento?.promedio_horas === null ? "—" : `${item.procesamiento.promedio_horas} h` },
      { label: "Demoras laboratorio", value: (item) => item.procesamiento?.muestras_demoradas },
      { label: "", html: true, value: (_item, index) => smallAction("report-detail", "Detalle", `data-index="${index}"`) },
    ];
  }
  return renderGraficoReporte(state.reportKey, data) + table(data, columns);
}

function renderGraficoReporte(key, data) {
  const modelo = modeloReporte(key, data);
  const formato = (valor) => valor === null ? "Sin datos"
    : modelo.unidad === "ARS" ? formatMoney(valor)
    : new Intl.NumberFormat("es-AR", { maximumFractionDigits: 2 }).format(valor)
      + (modelo.unidad === "horas" ? " h" : "");
  const maximo = Math.max(1, ...modelo.barras.flatMap((b) => b.valores)
    .filter((v) => v !== null && Number.isFinite(Number(v))).map(Number));
  const formatoMetrica = (valor) => modelo.unidad === "ARS" ? formatMoney(valor)
    : new Intl.NumberFormat("es-AR", { maximumFractionDigits: 2 }).format(valor);
  return `<section class="report-summary" aria-label="Indicadores del reporte">${modelo.metricas.map(([nombre, valor]) =>
    `<article class="metric-mini"><span>${escapeHtml(nombre)}</span><strong>${escapeHtml(formatoMetrica(valor))}</strong></article>`).join("")}</section>
    <figure class="report-chart"><figcaption>${escapeHtml(modelo.titulo)}</figcaption>
    <div class="chart-legend">${modelo.series.map((s, i) => `<span><i class="chart-color series-${i}" aria-hidden="true"></i>${escapeHtml(s)}</span>`).join("")}</div>
    <div class="chart-rows">${modelo.barras.map((b) => `<div class="chart-row"><strong>${escapeHtml(titleCase(b.etiqueta))}</strong><div>${b.valores.map((v, i) =>
      `<div class="chart-value"><span class="chart-track" aria-hidden="true"><span class="chart-bar series-${i}" style="width:${v === null ? 0 : Math.max(0, Math.min(100, Number(v) / maximo * 100))}%"></span></span><span>${escapeHtml(modelo.series[i])}: ${escapeHtml(formato(v))}</span></div>`).join("")}</div></div>`).join("")}</div>
    <p class="field-help">Las barras usan una escala común. Los valores exactos y el desglose completo están en la tabla.</p></figure>`;
}

function renderReportes() {
  const clinics = state.cache.clinicas || [];
  const current = reports[state.reportKey];
  const filters = state.reportFilters;
  root.innerHTML = `<div class="view-enter">
    ${sectionIntro("Indicadores de gestión", "Cinco reportes operativos para revisar la atención, la seguridad del transporte y el desempeño económico.")}
    <div class="report-nav">${Object.entries(reports).map(([key, report]) => `<button class="report-option ${key === state.reportKey ? "is-active" : ""}" data-action="select-report" data-key="${key}"><strong>${escapeHtml(report.title)}</strong>${escapeHtml(report.copy)}</button>`).join("")}</div>
    <section class="panel">
      <header class="panel-header"><div><h2>${escapeHtml(current.title)}</h2><p>${escapeHtml(current.copy)}</p></div></header>
      <div class="filter-row">
        <label>Desde<input class="compact-field" id="report-from" type="date" value="${escapeHtml(filters.desde || "")}" aria-label="Fecha desde"></label>
        <label>Hasta<input class="compact-field" id="report-to" type="date" value="${escapeHtml(filters.hasta || "")}" aria-label="Fecha hasta"></label>
        <label>Clínica<select class="compact-field" id="report-clinic" aria-label="Clínica"><option value="">Todas las clínicas</option>${optionsFor("clinicas", filters.clinica_id || null)}</select></label>
        ${state.reportKey === "tratamientos-vacunas" ? `<label>Fecha de referencia<input class="compact-field" id="report-reference" type="date" value="${escapeHtml(filters.fecha_referencia || "")}" aria-label="Fecha de referencia"></label>` : ""}
        ${state.reportKey === "tiempos-muestras" ? `<label>Demora de tránsito (horas)<input class="compact-field" id="report-threshold" type="number" min="0.1" step="0.1" value="${escapeHtml(filters.umbral_transito_horas || "24")}" aria-label="Umbral de tránsito"></label>` : ""}
        <button class="button button-primary" data-action="run-report" ${state.reportLoading ? "disabled" : ""}>${state.reportLoading ? "Generando…" : "Generar reporte"}</button>
      </div>
      <div class="panel-body">${state.reportError ? `<p class="inline-note is-danger" role="alert">${escapeHtml(state.reportError)}</p>` : state.reportLoading ? '<p class="inline-note" role="status">Consultando indicadores…</p>' : renderReportResult()}</div>
    </section>
  </div>`;
}

async function runReport() {
  if (state.reportLoading) return;
  const filters = {
    desde: $("#report-from")?.value || "",
    hasta: $("#report-to")?.value || "",
    clinica_id: $("#report-clinic")?.value || "",
    fecha_referencia: $("#report-reference")?.value || "",
    umbral_transito_horas: $("#report-threshold")?.value || "",
  };
  if (filters.desde && filters.hasta && filters.desde > filters.hasta) {
    toast("La fecha desde no puede ser posterior a la fecha hasta.", "error");
    return;
  }
  if (filters.umbral_transito_horas && !(Number(filters.umbral_transito_horas) > 0)) {
    toast("El umbral de tránsito debe ser mayor a cero.", "error");
    return;
  }
  state.reportFilters = filters;
  const requestId = ++state.reportRequest;
  const reportKey = state.reportKey;
  state.reportLoading = true;
  state.reportError = "";
  state.reportData = null;
  const params = new URLSearchParams();
  Object.entries(filters).forEach(([key, value]) => { if (value) params.set(key, value); });
  renderReportes();
  try {
    const result = await api(`/reportes/${reportKey}${params.size ? `?${params}` : ""}`);
    if (state.reportRequest === requestId) state.reportData = result;
  } catch (error) {
    if (state.reportRequest === requestId) state.reportError = error.message;
  } finally {
    if (state.reportRequest === requestId) {
      state.reportLoading = false;
      if (state.view === "reportes" && state.reportKey === reportKey) renderReportes();
    }
  }
}

async function renderCurrentView(force = false) {
  if (state.loading) return;
  state.loading = true;
  root.innerHTML = `<section class="loading-state"><span class="spinner"></span><p>Actualizando información…</p></section>`;
  try {
    await loadCatalogs(force);
    const renderers = {
      dashboard: renderDashboard,
      pacientes: renderPacientes,
      atencion: renderAtencion,
      laboratorio: renderLaboratorio,
      custodia: renderCustodia,
      facturacion: renderFacturacion,
      reportes: renderReportes,
      configuracion: renderConfiguracion,
    };
    renderers[state.view]();
  } catch (error) {
    root.innerHTML = `<section class="error-state"><span class="empty-mark">!</span><strong>No pudimos cargar la información</strong><span>${escapeHtml(error.message)}</span><button class="button button-primary" data-action="retry">Reintentar</button></section>`;
  } finally {
    state.loading = false;
  }
}

async function changeView(view) {
  if (!viewMeta[view]) return;
  closeDrawer();
  state.view = view;
  const [title, eyebrow] = viewMeta[view];
  $("#page-title").textContent = title;
  $("#page-eyebrow").textContent = eyebrow;
  $$(".nav-item").forEach((button) => button.classList.toggle("is-active", button.dataset.view === view));
  $("#sidebar").classList.remove("is-open");
  $("#menu-button").setAttribute("aria-expanded", "false");
  await renderCurrentView();
}

async function handleAction(button) {
  const action = button.dataset.action;
  const id = button.dataset.id;
  if (action === "retry") return renderCurrentView(true);
  if (action === "open-form") {
    const context = {};
    if (button.dataset.orderId) context.values = { orden_id: button.dataset.orderId };
    return openForm(button.dataset.form, context);
  }
  if (action === "appointment-attend") {
    const turno = findById("turnos", id);
    if (!turno) return toast("No se encontró el turno seleccionado.", "error");
    return openForm("atencion", {
      values: {
        turno_id: turno.id,
        mascota_id: turno.mascota_id,
        clinica_id: turno.clinica_id,
        profesional_id: turno.profesional_id,
        tipo: turno.tipo || "consulta",
        motivo: turno.motivo,
      },
    });
  }
  if (action === "client-edit") return openForm("cliente", { id, values: findById("clientes", id) });
  if (action === "client-detail") {
    try {
      const detail = await api(`/clientes/${id}`);
      openDrawer(`${detail.apellido}, ${detail.nombre}`, detail, "Responsable");
    } catch (error) { toast(error.message, "error"); }
    return;
  }
  if (action === "pet-edit") return openForm("mascota", { id, values: findById("mascotas", id) });
  if (action === "client-deactivate") {
    if (!window.confirm("¿Desactivar este responsable? Sus datos se conservarán.")) return;
    try {
      await api(`/clientes/${id}`, { method: "DELETE" });
      state.cache = {};
      toast("El responsable fue desactivado.");
      return renderCurrentView();
    } catch (error) { return toast(error.message, "error"); }
  }
  if (action === "pet-history") {
    try {
      const detail = await api(`/mascotas/${id}/historia-clinica`);
      const actions = `<button class="button button-primary" data-action="history-edit" data-id="${id}">Editar historia</button>`;
      openDrawer(`Historia de ${detail.mascota.nombre}`, detail, "Historia clínica");
      $("#drawer-content").innerHTML = renderHistoriaClinica(detail);
      $("#drawer-content").insertAdjacentHTML("afterbegin", `<div class="button-row" style="margin-bottom:16px">${actions}</div>`);
    } catch (error) { toast(error.message, "error"); }
    return;
  }
  if (action === "history-edit") {
    try {
      const detail = await api(`/mascotas/${id}/historia-clinica`);
      closeDrawer();
      return openForm("historia", { id, petName: detail.mascota.nombre, values: detail.historia });
    } catch (error) { return toast(error.message, "error"); }
  }
  if (action === "order-detail") {
    try {
      const detail = await api(`/ordenes-derivacion/${id}`);
      openDrawer(detail.orden.numero, detail, "Orden de derivación");
      const pending = detail.analisis_solicitados.filter((item) => !item.resultado
        && ["recibida", "analizada"].includes(findById("muestras", item.muestra_id)?.estado_actual));
      if (pending.length) {
        $("#drawer-content").insertAdjacentHTML("afterbegin", `<div class="button-row" style="margin-bottom:16px">${pending.map((item) => `<button class="button button-primary button-small" data-action="result-for" data-request-id="${item.id}">Resultado · ${escapeHtml(item.analisis.nombre)}</button>`).join("")}</div>`);
      }
    } catch (error) { toast(error.message, "error"); }
    return;
  }
  if (action === "result-for") {
    closeDrawer();
    return openForm("resultado", { solicitudId: button.dataset.requestId });
  }
  if (action === "sample-trace") {
    try {
      const detail = await api(`/muestras/${id}/trazabilidad`);
      $("#drawer-title").textContent = detail.muestra.codigo;
      $("#drawer-eyebrow").textContent = "Trazabilidad inmutable";
      $("#drawer-content").innerHTML = `${renderDetail(detail.muestra)}<div class="timeline">${detail.eventos.map((event) => `<article class="timeline-item"><strong>${escapeHtml(titleCase(event.tipo_evento))} · ${escapeHtml(titleCase(event.estado_nuevo))}</strong><span>${escapeHtml(event.ubicacion)} · ${escapeHtml(event.actor)}</span><small>${escapeHtml(formatDate(event.ocurrido_en))}${event.temperatura_c !== null ? ` · ${escapeHtml(event.temperatura_c)} °C` : ""}</small></article>`).join("")}</div>`;
      drawer.classList.add("is-open");
      drawer.inert = false;
      drawer.setAttribute("aria-hidden", "false");
    } catch (error) { toast(error.message, "error"); }
    return;
  }
  if (action === "dispatch") return openForm("despacho", { id, number: button.dataset.number });
  if (action === "receive") return openForm("recepcion", { id, number: button.dataset.number });
  if (action === "transfer") return openForm("transferencia", { id });
  if (action === "invoice-detail") {
    try {
      const detail = await api(`/facturas/${id}`);
      openDrawer(detail.factura.numero, null, "Comprobante de atención");
      $("#drawer-content").innerHTML = renderFacturaDetalle(detail);
    }
    catch (error) { toast(error.message, "error"); }
    return;
  }
  if (action === "remittance-trace") {
    const detail = await api(`/remitos/${id}/trazabilidad`);
    openDrawer(detail.remito.numero, detail, "Trazabilidad del remito");
    return;
  }
  if (action === "generic-detail") {
    const source = button.dataset.source;
    const item = source === "laboratorio" ? state.cache.laboratorio : findById(source, id);
    return openDrawer(itemLabel(source, item), item, titleCase(source));
  }
  if (action === "select-report") {
    ++state.reportRequest;
    state.reportKey = button.dataset.key;
    state.reportData = null;
    state.reportLoading = false;
    state.reportError = "";
    return renderReportes();
  }
  if (action === "run-report") return runReport();
  if (action === "report-detail") return openDrawer(reports[state.reportKey].title, state.reportData[Number(button.dataset.index)], "Detalle del reporte");
}

async function checkHealth() {
  const dot = $("#api-dot");
  const text = $("#api-status");
  try {
    await api("/salud");
    dot.className = "status-dot is-online";
    text.textContent = "Sistema operativo";
  } catch {
    dot.className = "status-dot is-offline";
    text.textContent = "API sin conexión";
  }
}

function init() {
  $("#today").textContent = new Intl.DateTimeFormat("es-AR", { weekday: "long", day: "numeric", month: "long" }).format(new Date());
  $$(".nav-item").forEach((button) => button.addEventListener("click", () => changeView(button.dataset.view)));
  $("#refresh-button").addEventListener("click", () => { state.cache = {}; renderCurrentView(true); checkHealth(); });
  $("#menu-button").addEventListener("click", () => {
    const open = $("#sidebar").classList.toggle("is-open");
    $("#menu-button").setAttribute("aria-expanded", String(open));
  });
  $("#modal-close").addEventListener("click", closeModal);
  $("#modal-cancel").addEventListener("click", closeModal);
  modalBackdrop.addEventListener("click", (event) => { if (event.target === modalBackdrop) closeModal(); });
  modalForm.addEventListener("submit", submitModal);
  modalFields.addEventListener("click", (event) => {
    const button = event.target.closest("[data-modal-action]");
    if (!button) return;
    if (button.dataset.modalAction === "add-component") addComponentRow();
    if (button.dataset.modalAction === "remove-component") { button.closest(".repeat-item")?.remove(); actualizarTotalFactura(); }
    if (button.dataset.modalAction === "add-value") addValueRow();
    if (button.dataset.modalAction === "remove-value") button.closest(".value-item")?.remove();
    if (button.dataset.modalAction === "choose-slot") {
      modalForm.elements.inicio.value = button.dataset.start;
      modalForm.elements.fin.value = button.dataset.end;
      actualizarAgenda();
    }
    if (button.dataset.modalAction === "refresh-agenda") {
      button.disabled = true;
      fetchCached("turnos", "/turnos", true).then(actualizarAgenda)
        .catch((error) => toast("No se pudo actualizar la agenda: " + error.message, "error"))
        .finally(() => { button.disabled = false; });
    }
  });
  modalFields.addEventListener("change", (event) => {
    const nombre = event.target.name;
    if (["turno", "atencion"].includes(state.modal?.key) && nombre === "clinica_id") sincronizarProfesionales();
    if (state.modal?.key === "atencion") {
      if (nombre === "turno_id" && event.target.value) {
        const turno = findById("turnos", event.target.value);
        for (const campo of ["mascota_id", "clinica_id", "tipo", "motivo"])
          modalForm.elements[campo].value = turno[campo] || "";
        sincronizarProfesionales();
        modalForm.elements.profesional_id.value = turno.profesional_id;
      }
      if (["mascota_id", "clinica_id", "profesional_id", "turno_id"].includes(nombre)) sincronizarTurnoAtencion();
    }
    if (state.modal?.key === "turno") actualizarAgenda();
    if (state.modal?.key === "factura") {
      if (["cliente_id", "clinica_id", "atencion_id"].includes(nombre)) sincronizarFactura();
      if (["orden_derivacion_id", "component_tipo"].includes(nombre)) actualizarAnalisisFactura();
      if (nombre === "component_analisis" && event.target.value) {
        const row = event.target.closest(".repeat-item");
        const solicitud = (state.cache.detalleOrdenes || []).flatMap((d) => d.analisis_solicitados)
          .find((s) => s.id === event.target.value);
        if (solicitud) {
          $('[name="component_descripcion"]', row).value = solicitud.analisis.nombre;
          $('[name="component_precio"]', row).value = solicitud.analisis.precio;
        }
      }
      actualizarTotalFactura();
    }
  });
  modalFields.addEventListener("input", (event) => {
    if (state.modal?.key === "turno" && event.target.name === "fin") actualizarAgenda();
    if (state.modal?.key === "factura") actualizarTotalFactura();
  });
  $("#drawer-close").addEventListener("click", closeDrawer);
  document.addEventListener("keydown", (event) => {
    if (event.key === "Tab" && !modalBackdrop.hidden) {
      const controles = $$('button:not(:disabled), input:not(:disabled), select:not(:disabled), textarea:not(:disabled)', modalBackdrop);
      const primero = controles[0];
      const ultimo = controles.at(-1);
      if (event.shiftKey && document.activeElement === primero) { event.preventDefault(); ultimo?.focus(); }
      else if (!event.shiftKey && document.activeElement === ultimo) { event.preventDefault(); primero?.focus(); }
    }
    if (event.key === "Escape") { if (!modalBackdrop.hidden) closeModal(); else closeDrawer(); }
  });
  document.addEventListener("click", (event) => {
    const button = event.target.closest("[data-action]");
    if (button) handleAction(button).catch((error) => toast(error.message, "error"));
  });
  document.addEventListener("input", (event) => {
    if (!event.target.matches("[data-table-search]")) return;
    const panelNode = event.target.closest(".panel");
    const query = event.target.value.trim().normalize("NFD").replace(/[\u0300-\u036f]/g, "").toLowerCase();
    $$("[data-search-row]", panelNode).forEach((row) => { row.hidden = !row.dataset.searchText.includes(query); });
  });
  checkHealth();
  renderCurrentView();
}

document.addEventListener("DOMContentLoaded", init);
