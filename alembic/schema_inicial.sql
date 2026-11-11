CREATE TABLE clientes (
	nombre VARCHAR(100) NOT NULL, 
	apellido VARCHAR(100) NOT NULL, 
	tipo_documento VARCHAR(9) NOT NULL, 
	numero_documento VARCHAR(30) NOT NULL, 
	email VARCHAR(254) NOT NULL, 
	telefono VARCHAR(40) NOT NULL, 
	direccion VARCHAR(250), 
	activo BOOLEAN DEFAULT 'true' NOT NULL, 
	id CHAR(32) NOT NULL, 
	creado_en DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL, 
	actualizado_en DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL, 
	CONSTRAINT pk_clientes PRIMARY KEY (id), 
	CONSTRAINT uq_clientes_tipo_documento UNIQUE (tipo_documento, numero_documento), 
	CONSTRAINT ck_clientes_cliente_nombre_no_vacio CHECK (length(trim(nombre)) > 0), 
	CONSTRAINT ck_clientes_cliente_apellido_no_vacio CHECK (length(trim(apellido)) > 0), 
	CONSTRAINT ck_clientes_tipo_documento CHECK (tipo_documento IN ('dni', 'pasaporte', 'cuit')), 
	CONSTRAINT uq_clientes_email UNIQUE (email)
);

CREATE TABLE clinicas_veterinarias (
	nombre VARCHAR(160) NOT NULL, 
	codigo VARCHAR(30) NOT NULL, 
	cuit VARCHAR(20) NOT NULL, 
	direccion VARCHAR(250) NOT NULL, 
	telefono VARCHAR(40) NOT NULL, 
	email VARCHAR(254) NOT NULL, 
	activa BOOLEAN DEFAULT 'true' NOT NULL, 
	id CHAR(32) NOT NULL, 
	creado_en DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL, 
	actualizado_en DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL, 
	CONSTRAINT pk_clinicas_veterinarias PRIMARY KEY (id), 
	CONSTRAINT ck_clinicas_veterinarias_clinica_nombre_no_vacio CHECK (length(trim(nombre)) > 0), 
	CONSTRAINT uq_clinicas_veterinarias_cuit UNIQUE (cuit)
);

CREATE TABLE laboratorios_centrales (
	nombre VARCHAR(160) NOT NULL, 
	codigo VARCHAR(30) NOT NULL, 
	direccion VARCHAR(250) NOT NULL, 
	telefono VARCHAR(40) NOT NULL, 
	email VARCHAR(254) NOT NULL, 
	activo BOOLEAN DEFAULT 'true' NOT NULL, 
	clave_singleton INTEGER DEFAULT '1' NOT NULL, 
	id CHAR(32) NOT NULL, 
	creado_en DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL, 
	actualizado_en DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL, 
	CONSTRAINT pk_laboratorios_centrales PRIMARY KEY (id), 
	CONSTRAINT ck_laboratorios_centrales_laboratorio_unico_por_red CHECK (clave_singleton = 1), 
	CONSTRAINT uq_laboratorios_centrales_clave_singleton UNIQUE (clave_singleton)
);

CREATE TABLE contenedores (
	codigo VARCHAR(60) NOT NULL, 
	descripcion VARCHAR(250), 
	capacidad_muestras INTEGER NOT NULL, 
	temperatura_min_c NUMERIC(5, 2) NOT NULL, 
	temperatura_max_c NUMERIC(5, 2) NOT NULL, 
	estado VARCHAR(13) NOT NULL, 
	ultima_sanitizacion DATETIME, 
	id CHAR(32) NOT NULL, 
	creado_en DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL, 
	actualizado_en DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL, 
	CONSTRAINT pk_contenedores PRIMARY KEY (id), 
	CONSTRAINT ck_contenedores_contenedor_capacidad_positiva CHECK (capacidad_muestras > 0), 
	CONSTRAINT ck_contenedores_contenedor_rango_temperatura_valido CHECK (temperatura_min_c < temperatura_max_c), 
	CONSTRAINT ck_contenedores_estado_contenedor CHECK (estado IN ('disponible', 'en_uso', 'en_transito', 'mantenimiento', 'baja'))
);

CREATE TABLE precintos_sanitarios (
	codigo VARCHAR(80) NOT NULL, 
	estado VARCHAR(10) NOT NULL, 
	aplicado_en DATETIME, 
	verificado_en DATETIME, 
	observaciones TEXT, 
	id CHAR(32) NOT NULL, 
	creado_en DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL, 
	actualizado_en DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL, 
	CONSTRAINT pk_precintos_sanitarios PRIMARY KEY (id), 
	CONSTRAINT ck_precintos_sanitarios_estado_precinto CHECK (estado IN ('disponible', 'aplicado', 'intacto', 'roto', 'invalidado'))
);

CREATE TABLE vacunas (
	nombre VARCHAR(160) NOT NULL, 
	laboratorio_fabricante VARCHAR(160) NOT NULL, 
	especie_objetivo VARCHAR(80) NOT NULL, 
	dosis_ml NUMERIC(6, 2) NOT NULL, 
	edad_minima_dias INTEGER DEFAULT '0' NOT NULL, 
	intervalo_refuerzo_dias INTEGER, 
	obligatoria BOOLEAN DEFAULT 'false' NOT NULL, 
	activa BOOLEAN DEFAULT 'true' NOT NULL, 
	id CHAR(32) NOT NULL, 
	creado_en DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL, 
	actualizado_en DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL, 
	CONSTRAINT pk_vacunas PRIMARY KEY (id), 
	CONSTRAINT ck_vacunas_vacuna_dosis_positiva CHECK (dosis_ml > 0), 
	CONSTRAINT ck_vacunas_vacuna_edad_minima_valida CHECK (edad_minima_dias >= 0), 
	CONSTRAINT ck_vacunas_vacuna_intervalo_refuerzo_valido CHECK (intervalo_refuerzo_dias IS NULL OR intervalo_refuerzo_dias > 0)
);

CREATE TABLE mascotas (
	cliente_id CHAR(32) NOT NULL, 
	nombre VARCHAR(100) NOT NULL, 
	especie VARCHAR(80) NOT NULL, 
	raza VARCHAR(100), 
	fecha_nacimiento DATE, 
	sexo VARCHAR(15) NOT NULL, 
	peso_kg NUMERIC(6, 2), 
	microchip VARCHAR(80), 
	color VARCHAR(80), 
	activo BOOLEAN DEFAULT 'true' NOT NULL, 
	id CHAR(32) NOT NULL, 
	creado_en DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL, 
	actualizado_en DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL, 
	CONSTRAINT pk_mascotas PRIMARY KEY (id), 
	CONSTRAINT ck_mascotas_mascota_nombre_no_vacio CHECK (length(trim(nombre)) > 0), 
	CONSTRAINT ck_mascotas_mascota_peso_positivo CHECK (peso_kg IS NULL OR peso_kg > 0), 
	CONSTRAINT fk_mascotas_cliente_id_clientes FOREIGN KEY(cliente_id) REFERENCES clientes (id) ON DELETE RESTRICT, 
	CONSTRAINT ck_mascotas_sexo_mascota CHECK (sexo IN ('macho', 'hembra', 'no_especificado')), 
	CONSTRAINT uq_mascotas_microchip UNIQUE (microchip)
);

CREATE TABLE profesionales_veterinarios (
	clinica_id CHAR(32) NOT NULL, 
	nombre VARCHAR(100) NOT NULL, 
	apellido VARCHAR(100) NOT NULL, 
	matricula VARCHAR(50) NOT NULL, 
	email VARCHAR(254) NOT NULL, 
	telefono VARCHAR(40) NOT NULL, 
	especialidad VARCHAR(120), 
	activo BOOLEAN DEFAULT 'true' NOT NULL, 
	id CHAR(32) NOT NULL, 
	creado_en DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL, 
	actualizado_en DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL, 
	CONSTRAINT pk_profesionales_veterinarios PRIMARY KEY (id), 
	CONSTRAINT ck_profesionales_veterinarios_profesional_matricula_no_vacia CHECK (length(trim(matricula)) > 0), 
	CONSTRAINT fk_profesionales_veterinarios_clinica_id_clinicas_veterinarias FOREIGN KEY(clinica_id) REFERENCES clinicas_veterinarias (id) ON DELETE RESTRICT, 
	CONSTRAINT uq_profesionales_veterinarios_email UNIQUE (email)
);

CREATE TABLE analisis (
	laboratorio_id CHAR(32) NOT NULL, 
	codigo VARCHAR(40) NOT NULL, 
	nombre VARCHAR(160) NOT NULL, 
	descripcion TEXT, 
	tipo_muestra VARCHAR(13) NOT NULL, 
	precio NUMERIC(12, 2) NOT NULL, 
	tiempo_estimado_horas INTEGER NOT NULL, 
	requiere_ayuno BOOLEAN DEFAULT 'false' NOT NULL, 
	activo BOOLEAN DEFAULT 'true' NOT NULL, 
	id CHAR(32) NOT NULL, 
	creado_en DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL, 
	actualizado_en DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL, 
	CONSTRAINT pk_analisis PRIMARY KEY (id), 
	CONSTRAINT uq_analisis_laboratorio_id UNIQUE (laboratorio_id, codigo), 
	CONSTRAINT ck_analisis_analisis_precio_no_negativo CHECK (precio >= 0), 
	CONSTRAINT ck_analisis_analisis_tiempo_estimado_positivo CHECK (tiempo_estimado_horas > 0), 
	CONSTRAINT fk_analisis_laboratorio_id_laboratorios_centrales FOREIGN KEY(laboratorio_id) REFERENCES laboratorios_centrales (id) ON DELETE RESTRICT, 
	CONSTRAINT ck_analisis_tipo_muestra_analisis CHECK (tipo_muestra IN ('sangre', 'orina', 'materia_fecal', 'tejido', 'hisopado', 'otro'))
);

CREATE TABLE remitos_biologicos (
	numero VARCHAR(60) NOT NULL, 
	contenedor_id CHAR(32) NOT NULL, 
	precinto_id CHAR(32) NOT NULL, 
	clinica_origen_id CHAR(32) NOT NULL, 
	laboratorio_destino_id CHAR(32) NOT NULL, 
	fecha_emision DATETIME NOT NULL, 
	fecha_despacho DATETIME, 
	estado VARCHAR(11) NOT NULL, 
	observaciones TEXT, 
	id CHAR(32) NOT NULL, 
	creado_en DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL, 
	actualizado_en DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL, 
	CONSTRAINT pk_remitos_biologicos PRIMARY KEY (id), 
	CONSTRAINT ck_remitos_biologicos_remito_despacho_posterior_emision CHECK (fecha_despacho IS NULL OR fecha_despacho >= fecha_emision), 
	CONSTRAINT fk_remitos_biologicos_contenedor_id_contenedores FOREIGN KEY(contenedor_id) REFERENCES contenedores (id) ON DELETE RESTRICT, 
	CONSTRAINT uq_remitos_biologicos_precinto_id UNIQUE (precinto_id), 
	CONSTRAINT fk_remitos_biologicos_precinto_id_precintos_sanitarios FOREIGN KEY(precinto_id) REFERENCES precintos_sanitarios (id) ON DELETE RESTRICT, 
	CONSTRAINT fk_remitos_biologicos_clinica_origen_id_clinicas_veterinarias FOREIGN KEY(clinica_origen_id) REFERENCES clinicas_veterinarias (id) ON DELETE RESTRICT, 
	CONSTRAINT fk_remitos_biologicos_laboratorio_destino_id_laboratorios_centrales FOREIGN KEY(laboratorio_destino_id) REFERENCES laboratorios_centrales (id) ON DELETE RESTRICT, 
	CONSTRAINT ck_remitos_biologicos_estado_remito CHECK (estado IN ('borrador', 'emitido', 'en_transito', 'recibido', 'rechazado'))
);

CREATE TABLE historias_clinicas (
	mascota_id CHAR(32) NOT NULL, 
	fecha_apertura DATETIME NOT NULL, 
	antecedentes TEXT, 
	alergias TEXT, 
	observaciones TEXT, 
	id CHAR(32) NOT NULL, 
	creado_en DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL, 
	actualizado_en DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL, 
	CONSTRAINT pk_historias_clinicas PRIMARY KEY (id), 
	CONSTRAINT uq_historias_clinicas_mascota_id UNIQUE (mascota_id), 
	CONSTRAINT fk_historias_clinicas_mascota_id_mascotas FOREIGN KEY(mascota_id) REFERENCES mascotas (id) ON DELETE RESTRICT
);

CREATE TABLE envios (
	remito_id CHAR(32) NOT NULL, 
	codigo_seguimiento VARCHAR(80) NOT NULL, 
	transportista VARCHAR(160) NOT NULL, 
	conductor VARCHAR(160) NOT NULL, 
	vehiculo VARCHAR(100) NOT NULL, 
	fecha_salida DATETIME, 
	fecha_entrega DATETIME, 
	estado VARCHAR(14) NOT NULL, 
	temperatura_min_registrada_c NUMERIC(5, 2), 
	temperatura_max_registrada_c NUMERIC(5, 2), 
	observaciones TEXT, 
	id CHAR(32) NOT NULL, 
	creado_en DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL, 
	actualizado_en DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL, 
	CONSTRAINT pk_envios PRIMARY KEY (id), 
	CONSTRAINT ck_envios_envio_entrega_posterior_salida CHECK (fecha_entrega IS NULL OR fecha_salida IS NULL OR fecha_entrega >= fecha_salida), 
	CONSTRAINT ck_envios_envio_rango_temperatura_valido CHECK (temperatura_min_registrada_c IS NULL OR temperatura_max_registrada_c IS NULL OR temperatura_min_registrada_c <= temperatura_max_registrada_c), 
	CONSTRAINT uq_envios_remito_id UNIQUE (remito_id), 
	CONSTRAINT fk_envios_remito_id_remitos_biologicos FOREIGN KEY(remito_id) REFERENCES remitos_biologicos (id) ON DELETE RESTRICT, 
	CONSTRAINT ck_envios_estado_envio CHECK (estado IN ('preparado', 'en_transito', 'entregado', 'con_incidencia'))
);

CREATE TABLE eventos_remito (
	remito_id CHAR(32) NOT NULL, 
	secuencia INTEGER NOT NULL, 
	tipo_evento VARCHAR(9) NOT NULL, 
	estado_anterior VARCHAR(11), 
	estado_nuevo VARCHAR(11) NOT NULL, 
	ocurrido_en DATETIME NOT NULL, 
	actor VARCHAR(160) NOT NULL, 
	observaciones TEXT, 
	id CHAR(32) NOT NULL, 
	CONSTRAINT pk_eventos_remito PRIMARY KEY (id), 
	CONSTRAINT uq_eventos_remito_remito_id UNIQUE (remito_id, secuencia), 
	CONSTRAINT ck_eventos_remito_evento_remito_secuencia_positiva CHECK (secuencia > 0), 
	CONSTRAINT ck_eventos_remito_evento_remito_cambio_real CHECK (estado_anterior IS NULL OR estado_anterior <> estado_nuevo), 
	CONSTRAINT fk_eventos_remito_remito_id_remitos_biologicos FOREIGN KEY(remito_id) REFERENCES remitos_biologicos (id) ON DELETE RESTRICT, 
	CONSTRAINT ck_eventos_remito_tipo_evento_remito CHECK (tipo_evento IN ('creacion', 'emision', 'despacho', 'recepcion', 'rechazo')), 
	CONSTRAINT ck_eventos_remito_estado_remito_anterior CHECK (estado_anterior IN ('borrador', 'emitido', 'en_transito', 'recibido', 'rechazado')), 
	CONSTRAINT ck_eventos_remito_estado_remito_nuevo CHECK (estado_nuevo IN ('borrador', 'emitido', 'en_transito', 'recibido', 'rechazado'))
);

CREATE TABLE atenciones_veterinarias (
	historia_clinica_id CHAR(32) NOT NULL, 
	turno_id CHAR(32), 
	clinica_id CHAR(32) NOT NULL, 
	profesional_id CHAR(32) NOT NULL, 
	fecha DATETIME NOT NULL, 
	tipo VARCHAR(8) NOT NULL, 
	motivo VARCHAR(300) NOT NULL, 
	diagnostico TEXT, 
	tratamiento TEXT, 
	peso_kg NUMERIC(6, 2), 
	temperatura_c NUMERIC(4, 1), 
	observaciones TEXT, 
	esquema_vacunacion_al_dia BOOLEAN DEFAULT 'false' NOT NULL, 
	vacunas_pendientes JSON NOT NULL, 
	id CHAR(32) NOT NULL, 
	creado_en DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL, 
	actualizado_en DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL, 
	CONSTRAINT pk_atenciones_veterinarias PRIMARY KEY (id), 
	CONSTRAINT ck_atenciones_veterinarias_atencion_peso_positivo CHECK (peso_kg IS NULL OR peso_kg > 0), 
	CONSTRAINT fk_atenciones_veterinarias_historia_clinica_id_historias_clinicas FOREIGN KEY(historia_clinica_id) REFERENCES historias_clinicas (id) ON DELETE RESTRICT, 
	CONSTRAINT uq_atenciones_veterinarias_turno_id UNIQUE (turno_id), 
	CONSTRAINT fk_atenciones_veterinarias_turno_id_turnos FOREIGN KEY(turno_id) REFERENCES turnos (id) ON DELETE RESTRICT, 
	CONSTRAINT fk_atenciones_veterinarias_clinica_id_clinicas_veterinarias FOREIGN KEY(clinica_id) REFERENCES clinicas_veterinarias (id) ON DELETE RESTRICT, 
	CONSTRAINT fk_atenciones_veterinarias_profesional_id_profesionales_veterinarios FOREIGN KEY(profesional_id) REFERENCES profesionales_veterinarios (id) ON DELETE RESTRICT, 
	CONSTRAINT ck_atenciones_veterinarias_tipo_atencion CHECK (tipo IN ('consulta', 'control', 'urgencia'))
);

CREATE TABLE recepciones_laboratorio (
	remito_id CHAR(32) NOT NULL, 
	envio_id CHAR(32) NOT NULL, 
	laboratorio_id CHAR(32) NOT NULL, 
	recibido_en DATETIME NOT NULL, 
	receptor_nombre VARCHAR(160) NOT NULL, 
	estado_precinto VARCHAR(10) NOT NULL, 
	temperatura_recepcion_c NUMERIC(5, 2) NOT NULL, 
	muestra_viable BOOLEAN NOT NULL, 
	observaciones TEXT, 
	id CHAR(32) NOT NULL, 
	CONSTRAINT pk_recepciones_laboratorio PRIMARY KEY (id), 
	CONSTRAINT ck_recepciones_laboratorio_recepcion_precinto_roto_no_viable CHECK (estado_precinto <> 'roto' OR muestra_viable = false), 
	CONSTRAINT uq_recepciones_laboratorio_remito_id UNIQUE (remito_id), 
	CONSTRAINT fk_recepciones_laboratorio_remito_id_remitos_biologicos FOREIGN KEY(remito_id) REFERENCES remitos_biologicos (id) ON DELETE RESTRICT, 
	CONSTRAINT uq_recepciones_laboratorio_envio_id UNIQUE (envio_id), 
	CONSTRAINT fk_recepciones_laboratorio_envio_id_envios FOREIGN KEY(envio_id) REFERENCES envios (id) ON DELETE RESTRICT, 
	CONSTRAINT fk_recepciones_laboratorio_laboratorio_id_laboratorios_centrales FOREIGN KEY(laboratorio_id) REFERENCES laboratorios_centrales (id) ON DELETE RESTRICT, 
	CONSTRAINT ck_recepciones_laboratorio_estado_precinto_recepcion CHECK (estado_precinto IN ('disponible', 'aplicado', 'intacto', 'roto', 'invalidado'))
);

CREATE TABLE ordenes_derivacion (
	numero VARCHAR(50) NOT NULL, 
	atencion_id CHAR(32) NOT NULL, 
	laboratorio_id CHAR(32) NOT NULL, 
	profesional_solicitante_id CHAR(32) NOT NULL, 
	fecha_emision DATETIME NOT NULL, 
	estado VARCHAR(22) NOT NULL, 
	prioridad VARCHAR(7) DEFAULT 'normal' NOT NULL, 
	diagnostico_presuntivo TEXT, 
	indicaciones TEXT, 
	id CHAR(32) NOT NULL, 
	creado_en DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL, 
	actualizado_en DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL, 
	CONSTRAINT pk_ordenes_derivacion PRIMARY KEY (id), 
	CONSTRAINT fk_ordenes_derivacion_atencion_id_atenciones_veterinarias FOREIGN KEY(atencion_id) REFERENCES atenciones_veterinarias (id) ON DELETE RESTRICT, 
	CONSTRAINT fk_ordenes_derivacion_laboratorio_id_laboratorios_centrales FOREIGN KEY(laboratorio_id) REFERENCES laboratorios_centrales (id) ON DELETE RESTRICT, 
	CONSTRAINT fk_ordenes_derivacion_profesional_solicitante_id_profesionales_veterinarios FOREIGN KEY(profesional_solicitante_id) REFERENCES profesionales_veterinarios (id) ON DELETE RESTRICT, 
	CONSTRAINT ck_ordenes_derivacion_estado_orden CHECK (estado IN ('emitida', 'muestra_extraida', 'despachada', 'recibida', 'requiere_nueva_muestra', 'completada', 'cancelada')), 
	CONSTRAINT ck_ordenes_derivacion_prioridad_orden CHECK (prioridad IN ('normal', 'urgente'))
);

CREATE TABLE aplicaciones_vacunas (
	vacuna_id CHAR(32) NOT NULL, 
	mascota_id CHAR(32) NOT NULL, 
	atencion_id CHAR(32) NOT NULL, 
	profesional_id CHAR(32) NOT NULL, 
	fecha_aplicacion DATETIME NOT NULL, 
	dosis_ml NUMERIC(6, 2) NOT NULL, 
	lote VARCHAR(80) NOT NULL, 
	fecha_vencimiento_lote DATE, 
	proxima_aplicacion DATE, 
	observaciones TEXT, 
	id CHAR(32) NOT NULL, 
	creado_en DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL, 
	actualizado_en DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL, 
	CONSTRAINT pk_aplicaciones_vacunas PRIMARY KEY (id), 
	CONSTRAINT ck_aplicaciones_vacunas_aplicacion_dosis_positiva CHECK (dosis_ml > 0), 
	CONSTRAINT ck_aplicaciones_vacunas_aplicacion_lote_vigente CHECK (fecha_vencimiento_lote IS NULL OR fecha_vencimiento_lote >= CAST(fecha_aplicacion AS DATE)), 
	CONSTRAINT fk_aplicaciones_vacunas_vacuna_id_vacunas FOREIGN KEY(vacuna_id) REFERENCES vacunas (id) ON DELETE RESTRICT, 
	CONSTRAINT fk_aplicaciones_vacunas_mascota_id_mascotas FOREIGN KEY(mascota_id) REFERENCES mascotas (id) ON DELETE RESTRICT, 
	CONSTRAINT fk_aplicaciones_vacunas_atencion_id_atenciones_veterinarias FOREIGN KEY(atencion_id) REFERENCES atenciones_veterinarias (id) ON DELETE RESTRICT, 
	CONSTRAINT fk_aplicaciones_vacunas_profesional_id_profesionales_veterinarios FOREIGN KEY(profesional_id) REFERENCES profesionales_veterinarios (id) ON DELETE RESTRICT
);

CREATE TABLE facturas (
	numero VARCHAR(60) NOT NULL, 
	cliente_id CHAR(32) NOT NULL, 
	clinica_id CHAR(32) NOT NULL, 
	atencion_id CHAR(32), 
	orden_derivacion_id CHAR(32), 
	fecha_emision DATE NOT NULL, 
	fecha_vencimiento DATE, 
	estado VARCHAR(8) NOT NULL, 
	subtotal NUMERIC(12, 2) NOT NULL, 
	descuento NUMERIC(12, 2) NOT NULL, 
	total NUMERIC(12, 2) NOT NULL, 
	emitida_en DATETIME, 
	observaciones TEXT, 
	id CHAR(32) NOT NULL, 
	creado_en DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL, 
	actualizado_en DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL, 
	CONSTRAINT pk_facturas PRIMARY KEY (id), 
	CONSTRAINT ck_facturas_factura_subtotal_no_negativo CHECK (subtotal >= 0), 
	CONSTRAINT ck_facturas_factura_descuento_no_negativo CHECK (descuento >= 0), 
	CONSTRAINT ck_facturas_factura_descuento_valido CHECK (descuento <= subtotal), 
	CONSTRAINT ck_facturas_factura_total_consistente CHECK (total = subtotal - descuento), 
	CONSTRAINT ck_facturas_factura_vencimiento_valido CHECK (fecha_vencimiento IS NULL OR fecha_vencimiento >= fecha_emision), 
	CONSTRAINT fk_facturas_cliente_id_clientes FOREIGN KEY(cliente_id) REFERENCES clientes (id) ON DELETE RESTRICT, 
	CONSTRAINT fk_facturas_clinica_id_clinicas_veterinarias FOREIGN KEY(clinica_id) REFERENCES clinicas_veterinarias (id) ON DELETE RESTRICT, 
	CONSTRAINT uq_facturas_atencion_id UNIQUE (atencion_id), 
	CONSTRAINT fk_facturas_atencion_id_atenciones_veterinarias FOREIGN KEY(atencion_id) REFERENCES atenciones_veterinarias (id) ON DELETE RESTRICT, 
	CONSTRAINT fk_facturas_orden_derivacion_id_ordenes_derivacion FOREIGN KEY(orden_derivacion_id) REFERENCES ordenes_derivacion (id) ON DELETE RESTRICT, 
	CONSTRAINT ck_facturas_estado_factura CHECK (estado IN ('borrador', 'emitida', 'pagada', 'anulada', 'vencida'))
);

CREATE TABLE muestras_biologicas (
	codigo VARCHAR(60) NOT NULL, 
	orden_id CHAR(32) NOT NULL, 
	remito_id CHAR(32), 
	tipo VARCHAR(13) NOT NULL, 
	estado_actual VARCHAR(11) NOT NULL, 
	fecha_extraccion DATETIME NOT NULL, 
	fecha_recepcion DATETIME, 
	fecha_analisis DATETIME, 
	volumen_ml NUMERIC(8, 2) NOT NULL, 
	temperatura_min_c NUMERIC(5, 2) NOT NULL, 
	temperatura_max_c NUMERIC(5, 2) NOT NULL, 
	sitio_extraccion VARCHAR(160), 
	observaciones TEXT, 
	motivo_rechazo TEXT, 
	id CHAR(32) NOT NULL, 
	creado_en DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL, 
	actualizado_en DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL, 
	CONSTRAINT pk_muestras_biologicas PRIMARY KEY (id), 
	CONSTRAINT ck_muestras_biologicas_muestra_volumen_positivo CHECK (volumen_ml > 0), 
	CONSTRAINT ck_muestras_biologicas_muestra_rango_temperatura_valido CHECK (temperatura_min_c <= temperatura_max_c), 
	CONSTRAINT ck_muestras_biologicas_muestra_rechazada_con_motivo CHECK (estado_actual <> 'rechazada' OR motivo_rechazo IS NOT NULL), 
	CONSTRAINT fk_muestras_biologicas_orden_id_ordenes_derivacion FOREIGN KEY(orden_id) REFERENCES ordenes_derivacion (id) ON DELETE RESTRICT, 
	CONSTRAINT fk_muestras_biologicas_remito_id_remitos_biologicos FOREIGN KEY(remito_id) REFERENCES remitos_biologicos (id) ON DELETE RESTRICT, 
	CONSTRAINT ck_muestras_biologicas_tipo_muestra CHECK (tipo IN ('sangre', 'orina', 'materia_fecal', 'tejido', 'hisopado', 'otro')), 
	CONSTRAINT ck_muestras_biologicas_estado_muestra CHECK (estado_actual IN ('extraida', 'empaquetada', 'en_transito', 'recibida', 'analizada', 'rechazada'))
);

CREATE TABLE ordenes_analisis (
	orden_id CHAR(32) NOT NULL, 
	analisis_id CHAR(32) NOT NULL, 
	muestra_id CHAR(32), 
	estado VARCHAR(10) NOT NULL, 
	id CHAR(32) NOT NULL, 
	creado_en DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL, 
	actualizado_en DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL, 
	CONSTRAINT pk_ordenes_analisis PRIMARY KEY (id), 
	CONSTRAINT uq_ordenes_analisis_orden_id UNIQUE (orden_id, analisis_id), 
	CONSTRAINT fk_ordenes_analisis_orden_id_ordenes_derivacion FOREIGN KEY(orden_id) REFERENCES ordenes_derivacion (id) ON DELETE RESTRICT, 
	CONSTRAINT fk_ordenes_analisis_analisis_id_analisis FOREIGN KEY(analisis_id) REFERENCES analisis (id) ON DELETE RESTRICT, 
	CONSTRAINT fk_ordenes_analisis_muestra_id_muestras_biologicas FOREIGN KEY(muestra_id) REFERENCES muestras_biologicas (id) ON DELETE RESTRICT, 
	CONSTRAINT ck_ordenes_analisis_estado_solicitud_analisis CHECK (estado IN ('pendiente', 'en_proceso', 'completada', 'cancelada'))
);

CREATE TABLE cadenas_custodia (
	muestra_id CHAR(32) NOT NULL, 
	abierta_en DATETIME NOT NULL, 
	cerrada_en DATETIME, 
	id CHAR(32) NOT NULL, 
	CONSTRAINT pk_cadenas_custodia PRIMARY KEY (id), 
	CONSTRAINT uq_cadenas_custodia_muestra_id UNIQUE (muestra_id), 
	CONSTRAINT fk_cadenas_custodia_muestra_id_muestras_biologicas FOREIGN KEY(muestra_id) REFERENCES muestras_biologicas (id) ON DELETE RESTRICT
);

CREATE TABLE componentes_atencion (
	factura_id CHAR(32) NOT NULL, 
	atencion_id CHAR(32), 
	orden_analisis_id CHAR(32), 
	tipo VARCHAR(11) NOT NULL, 
	descripcion VARCHAR(250) NOT NULL, 
	cantidad NUMERIC(10, 2) NOT NULL, 
	precio_unitario NUMERIC(12, 2) NOT NULL, 
	subtotal NUMERIC(12, 2) NOT NULL, 
	id CHAR(32) NOT NULL, 
	creado_en DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL, 
	actualizado_en DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL, 
	CONSTRAINT pk_componentes_atencion PRIMARY KEY (id), 
	CONSTRAINT ck_componentes_atencion_componente_cantidad_positiva CHECK (cantidad > 0), 
	CONSTRAINT ck_componentes_atencion_componente_precio_no_negativo CHECK (precio_unitario >= 0), 
	CONSTRAINT ck_componentes_atencion_componente_subtotal_consistente CHECK (subtotal = round(cantidad * precio_unitario, 2)), 
	CONSTRAINT fk_componentes_atencion_factura_id_facturas FOREIGN KEY(factura_id) REFERENCES facturas (id) ON DELETE RESTRICT, 
	CONSTRAINT fk_componentes_atencion_atencion_id_atenciones_veterinarias FOREIGN KEY(atencion_id) REFERENCES atenciones_veterinarias (id) ON DELETE RESTRICT, 
	CONSTRAINT fk_componentes_atencion_orden_analisis_id_ordenes_analisis FOREIGN KEY(orden_analisis_id) REFERENCES ordenes_analisis (id) ON DELETE RESTRICT, 
	CONSTRAINT ck_componentes_atencion_tipo_componente_atencion CHECK (tipo IN ('atencion', 'laboratorio', 'vacuna', 'insumo', 'otro'))
);

CREATE TABLE resultados_analisis (
	orden_analisis_id CHAR(32) NOT NULL, 
	fecha_resultado DATETIME NOT NULL, 
	valores JSON NOT NULL, 
	conclusion TEXT, 
	observaciones TEXT, 
	validado_por VARCHAR(160) NOT NULL, 
	firmado_en DATETIME, 
	id CHAR(32) NOT NULL, 
	creado_en DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL, 
	actualizado_en DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL, 
	CONSTRAINT pk_resultados_analisis PRIMARY KEY (id), 
	CONSTRAINT uq_resultados_analisis_orden_analisis_id UNIQUE (orden_analisis_id), 
	CONSTRAINT fk_resultados_analisis_orden_analisis_id_ordenes_analisis FOREIGN KEY(orden_analisis_id) REFERENCES ordenes_analisis (id) ON DELETE RESTRICT
);

CREATE TABLE eventos_custodia (
	cadena_custodia_id CHAR(32) NOT NULL, 
	muestra_id CHAR(32) NOT NULL, 
	envio_id CHAR(32), 
	secuencia INTEGER NOT NULL, 
	tipo_evento VARCHAR(13) NOT NULL, 
	estado_anterior VARCHAR(11), 
	estado_nuevo VARCHAR(11) NOT NULL, 
	ocurrido_en DATETIME NOT NULL, 
	actor VARCHAR(160) NOT NULL, 
	ubicacion VARCHAR(250) NOT NULL, 
	temperatura_c NUMERIC(5, 2), 
	observaciones TEXT, 
	datos_adicionales JSON, 
	id CHAR(32) NOT NULL, 
	CONSTRAINT pk_eventos_custodia PRIMARY KEY (id), 
	CONSTRAINT uq_eventos_custodia_muestra_id UNIQUE (muestra_id, secuencia), 
	CONSTRAINT ck_eventos_custodia_evento_custodia_secuencia_positiva CHECK (secuencia > 0), 
	CONSTRAINT ck_eventos_custodia_evento_custodia_cambio_real CHECK (estado_anterior IS NULL OR estado_anterior <> estado_nuevo OR (tipo_evento = 'transferencia' AND estado_nuevo = 'en_transito')), 
	CONSTRAINT fk_eventos_custodia_cadena_custodia_id_cadenas_custodia FOREIGN KEY(cadena_custodia_id) REFERENCES cadenas_custodia (id) ON DELETE RESTRICT, 
	CONSTRAINT fk_eventos_custodia_muestra_id_muestras_biologicas FOREIGN KEY(muestra_id) REFERENCES muestras_biologicas (id) ON DELETE RESTRICT, 
	CONSTRAINT fk_eventos_custodia_envio_id_envios FOREIGN KEY(envio_id) REFERENCES envios (id) ON DELETE RESTRICT, 
	CONSTRAINT ck_eventos_custodia_tipo_evento_custodia CHECK (tipo_evento IN ('extraccion', 'empaquetado', 'despacho', 'transferencia', 'recepcion', 'rechazo', 'analisis')), 
	CONSTRAINT ck_eventos_custodia_estado_muestra_anterior CHECK (estado_anterior IN ('extraida', 'empaquetada', 'en_transito', 'recibida', 'analizada', 'rechazada')), 
	CONSTRAINT ck_eventos_custodia_estado_muestra_nuevo CHECK (estado_nuevo IN ('extraida', 'empaquetada', 'en_transito', 'recibida', 'analizada', 'rechazada'))
);

CREATE TABLE "turnos" (
	clinica_id CHAR(32) NOT NULL, 
	profesional_id CHAR(32) NOT NULL, 
	mascota_id CHAR(32) NOT NULL, 
	inicio DATETIME NOT NULL, 
	fin DATETIME NOT NULL, 
	estado VARCHAR(10) NOT NULL, 
	motivo VARCHAR(300) NOT NULL, 
	observaciones TEXT, 
	id CHAR(32) NOT NULL, 
	creado_en DATETIME DEFAULT (CURRENT_TIMESTAMP) NOT NULL, 
	actualizado_en DATETIME DEFAULT (CURRENT_TIMESTAMP) NOT NULL, 
	CONSTRAINT pk_turnos PRIMARY KEY (id), 
	CONSTRAINT ck_turnos_estado_turno CHECK (estado IN ('programado', 'confirmado', 'cancelado', 'atendido', 'ausente')), 
	CONSTRAINT fk_turnos_mascota_id_mascotas FOREIGN KEY(mascota_id) REFERENCES mascotas (id) ON DELETE RESTRICT, 
	CONSTRAINT fk_turnos_clinica_id_clinicas_veterinarias FOREIGN KEY(clinica_id) REFERENCES clinicas_veterinarias (id) ON DELETE RESTRICT, 
	CONSTRAINT ck_turnos_turno_intervalo_valido CHECK (fin > inicio), 
	CONSTRAINT fk_turnos_profesional_id_profesionales_veterinarios FOREIGN KEY(profesional_id) REFERENCES profesionales_veterinarios (id) ON DELETE RESTRICT
);

CREATE UNIQUE INDEX ix_clinicas_veterinarias_codigo ON clinicas_veterinarias (codigo);

CREATE UNIQUE INDEX ix_laboratorios_centrales_codigo ON laboratorios_centrales (codigo);

CREATE INDEX ix_contenedores_estado ON contenedores (estado);

CREATE UNIQUE INDEX ix_contenedores_codigo ON contenedores (codigo);

CREATE INDEX ix_precintos_sanitarios_estado ON precintos_sanitarios (estado);

CREATE UNIQUE INDEX ix_precintos_sanitarios_codigo ON precintos_sanitarios (codigo);

CREATE INDEX ix_vacunas_especie_objetivo ON vacunas (especie_objetivo);

CREATE INDEX ix_mascotas_cliente_id ON mascotas (cliente_id);

CREATE INDEX ix_mascotas_cliente_nombre ON mascotas (cliente_id, nombre);

CREATE INDEX ix_mascotas_especie ON mascotas (especie);

CREATE INDEX ix_profesionales_veterinarios_clinica_id ON profesionales_veterinarios (clinica_id);

CREATE UNIQUE INDEX ix_profesionales_veterinarios_matricula ON profesionales_veterinarios (matricula);

CREATE INDEX ix_remitos_biologicos_estado ON remitos_biologicos (estado);

CREATE INDEX ix_remitos_origen_emision ON remitos_biologicos (clinica_origen_id, fecha_emision);

CREATE UNIQUE INDEX ix_remitos_biologicos_numero ON remitos_biologicos (numero);

CREATE UNIQUE INDEX uq_remitos_contenedor_activo ON remitos_biologicos (contenedor_id) WHERE estado IN ('borrador', 'emitido', 'en_transito');

CREATE INDEX ix_remitos_estado_emision ON remitos_biologicos (estado, fecha_emision);

CREATE INDEX ix_envios_estado_salida ON envios (estado, fecha_salida);

CREATE UNIQUE INDEX ix_envios_codigo_seguimiento ON envios (codigo_seguimiento);

CREATE INDEX ix_envios_estado ON envios (estado);

CREATE INDEX ix_eventos_remito_remito_ocurrido ON eventos_remito (remito_id, ocurrido_en);

CREATE INDEX ix_atenciones_clinica_fecha ON atenciones_veterinarias (clinica_id, fecha);

CREATE INDEX ix_atenciones_historia_fecha ON atenciones_veterinarias (historia_clinica_id, fecha);

CREATE INDEX ix_atenciones_veterinarias_esquema_vacunacion_al_dia ON atenciones_veterinarias (esquema_vacunacion_al_dia);

CREATE INDEX ix_recepciones_laboratorio_recibido_en ON recepciones_laboratorio (recibido_en);

CREATE INDEX ix_ordenes_derivacion_prioridad ON ordenes_derivacion (prioridad);

CREATE UNIQUE INDEX ix_ordenes_derivacion_numero ON ordenes_derivacion (numero);

CREATE INDEX ix_ordenes_derivacion_estado ON ordenes_derivacion (estado);

CREATE INDEX ix_ordenes_derivacion_atencion_id ON ordenes_derivacion (atencion_id);

CREATE INDEX ix_ordenes_derivacion_estado_emision ON ordenes_derivacion (estado, fecha_emision);

CREATE INDEX ix_aplicaciones_vacunas_mascota_id ON aplicaciones_vacunas (mascota_id);

CREATE INDEX ix_facturas_clinica_emision ON facturas (clinica_id, fecha_emision);

CREATE INDEX ix_facturas_cliente_id ON facturas (cliente_id);

CREATE INDEX ix_facturas_estado_emision ON facturas (estado, fecha_emision);

CREATE INDEX ix_facturas_estado ON facturas (estado);

CREATE UNIQUE INDEX ix_facturas_numero ON facturas (numero);

CREATE INDEX ix_muestras_orden_estado ON muestras_biologicas (orden_id, estado_actual);

CREATE UNIQUE INDEX ix_muestras_biologicas_codigo ON muestras_biologicas (codigo);

CREATE INDEX ix_muestras_biologicas_estado_actual ON muestras_biologicas (estado_actual);

CREATE INDEX ix_muestras_biologicas_remito_id ON muestras_biologicas (remito_id);

CREATE INDEX ix_ordenes_analisis_muestra_id ON ordenes_analisis (muestra_id);

CREATE INDEX ix_ordenes_analisis_orden_id ON ordenes_analisis (orden_id);

CREATE INDEX ix_componentes_atencion_factura_id ON componentes_atencion (factura_id);

CREATE INDEX ix_eventos_custodia_muestra_ocurrido ON eventos_custodia (muestra_id, ocurrido_en);

CREATE INDEX ix_turnos_mascota_id ON turnos (mascota_id);

CREATE INDEX ix_turnos_clinica_inicio ON turnos (clinica_id, inicio);

CREATE INDEX ix_turnos_profesional_inicio ON turnos (profesional_id, inicio);

CREATE INDEX ix_turnos_estado ON turnos (estado);
