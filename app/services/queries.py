"""Las 5 queries Q1-Q5 en sintaxis Athena/Trino.

Portadas de `aeropuerto-data-science/athena/queries/*.sql` con los ajustes
que ese repo documentó como `-- ATHENA:` en cada .sql:

- `EXTRACT(EPOCH FROM (a - b)) / 60.0` → `date_diff('minute', b, a)`
- `x::numeric` → `CAST(x AS DECIMAL)` (o `DOUBLE`)
- `STDDEV_POP` → `stddev`
- `NOW()` → `current_timestamp`
- Las fechas ISO 8601 de los CSV quedan como VARCHAR en Glue: se convierten
  con `TRY(from_iso8601_timestamp(...))` antes de compararlas o restarlas.

Las tablas viven en el catálogo Glue `aeropuerto_lake`. El crawler de Data
Science (DS-09) crea una tabla por CSV con prefix `raw/msX/<tabla>/`, y
Athena las expone con el mismo nombre.

Parámetros:
- Usamos `.format(...)` con **valores validados en el router** (int para
  `dias`, whitelist para `tipo`). NUNCA con input del usuario sin validar.
"""

# Q1 — Recurso (manga/radar) con más incidencias en los últimos N días.
Q1_RECURSOS_MAS_FALLAS = """
WITH incidencias_tipadas AS (
    SELECT
        i.id             AS incidencia_id,
        i.gravedad,
        TRY(from_iso8601_timestamp(i.fecha_reporte)) AS fecha_reporte,
        TRY(from_iso8601_timestamp(i.fecha_cierre)) AS fecha_cierre,
        iar.id_recurso
    FROM incidencia i
    JOIN incidencia_afecta_recurso iar ON iar.id_incidencia = i.id
),
incidencias_ventana AS (
    SELECT * FROM incidencias_tipadas
    WHERE fecha_reporte > current_timestamp - INTERVAL '{dias}' DAY
)
SELECT
    r.id                         AS recurso_id,
    r.tipo,
    r.nombre_tecnico_locacion,
    COUNT(*)                     AS incidencias_total,
    SUM(CASE WHEN iv.gravedad = 'Critica'  THEN 4
             WHEN iv.gravedad = 'Alta'     THEN 3
             WHEN iv.gravedad = 'Moderada' THEN 2
             ELSE 1 END)         AS severidad_ponderada,
    SUM(CASE WHEN iv.gravedad = 'Critica' THEN 1 ELSE 0 END) AS incidencias_criticas,
    SUM(CASE WHEN iv.fecha_cierre IS NULL THEN 1 ELSE 0 END) AS incidencias_abiertas,
    ROUND(
        100.0 * SUM(CASE WHEN iv.fecha_cierre IS NULL THEN 1 ELSE 0 END) / COUNT(*),
        2
    )                            AS pct_abiertas,
    ROUND(
        AVG(
            CASE WHEN iv.fecha_cierre IS NOT NULL
                 THEN date_diff('minute', iv.fecha_reporte, iv.fecha_cierre)
            END
        ),
        1
    )                            AS tpr_minutos_promedio
FROM incidencias_ventana iv
JOIN recurso r ON r.id = iv.id_recurso
GROUP BY r.id, r.tipo, r.nombre_tecnico_locacion
ORDER BY severidad_ponderada DESC, incidencias_total DESC
LIMIT 10
""".strip()


# Q2 — Retraso promedio (min) de vuelos por tipo, con percentiles y franja horaria.
Q2_RETRASO_PROMEDIO = """
WITH vuelos_tipados AS (
    SELECT
        v.id,
        v.numero AS num_vuelo,
        v.aerolinea_ruc,
        TRY(from_iso8601_timestamp(v.hora_programada)) AS hora_programada,
        TRY(from_iso8601_timestamp(v.hora_real)) AS hora_real
    FROM vuelo v
    WHERE v.tipo = '{tipo}'
      AND v.estado IN ('Retrasado', 'Despegado', 'Aterrizado')
),
retrasos AS (
    SELECT
        id,
        num_vuelo,
        aerolinea_ruc,
        CAST(date_diff('minute', hora_programada, hora_real) AS DOUBLE) AS retraso_min,
        CASE CAST(EXTRACT(HOUR FROM hora_programada) AS INTEGER) / 6
             WHEN 0 THEN 'Madrugada (0-6)'
             WHEN 1 THEN 'Manana (6-12)'
             WHEN 2 THEN 'Tarde (12-18)'
             ELSE       'Noche (18-24)'
        END AS franja_horaria
    FROM vuelos_tipados
    WHERE hora_programada IS NOT NULL AND hora_real IS NOT NULL
)
SELECT
    'GLOBAL' AS grupo,
    'Todo el periodo' AS categoria,
    COUNT(*) AS vuelos,
    ROUND(AVG(retraso_min), 2) AS retraso_promedio_min,
    ROUND(stddev(retraso_min), 2) AS desv_estandar_min,
    ROUND(approx_percentile(retraso_min, 0.50), 2) AS p50,
    ROUND(approx_percentile(retraso_min, 0.90), 2) AS p90,
    ROUND(approx_percentile(retraso_min, 0.99), 2) AS p99
FROM retrasos

UNION ALL

SELECT
    'POR FRANJA' AS grupo,
    franja_horaria,
    COUNT(*),
    ROUND(AVG(retraso_min), 2),
    ROUND(stddev(retraso_min), 2),
    ROUND(approx_percentile(retraso_min, 0.50), 2),
    ROUND(approx_percentile(retraso_min, 0.90), 2),
    ROUND(approx_percentile(retraso_min, 0.99), 2)
FROM retrasos
GROUP BY franja_horaria
ORDER BY grupo, categoria
""".strip()


# Q3 — Ranking de aerolíneas por incidencias de Falta_Combustible.
Q3_INCIDENCIAS_COMBUSTIBLE = """
WITH vuelos_por_aerolinea AS (
    SELECT aerolinea_ruc, COUNT(*) AS total_vuelos
    FROM vuelo
    GROUP BY aerolinea_ruc
),
retrasos_combustible AS (
    SELECT
        v.aerolinea_ruc,
        COUNT(DISTINCT i.id) AS incidencias_combustible,
        COUNT(DISTINCT irv.id_vuelo) AS vuelos_afectados
    FROM incidencia i
    JOIN incidencia_retrasa_vuelo irv ON irv.id_incidencia = i.id
    JOIN vuelo v ON v.id = irv.id_vuelo
    WHERE i.tipo_incidencia = 'Falta_Combustible'
    GROUP BY v.aerolinea_ruc
)
SELECT
    a.ruc,
    a.nombre         AS aerolinea,
    a.alianza,
    v.total_vuelos,
    COALESCE(r.incidencias_combustible, 0) AS incidencias_combustible,
    COALESCE(r.vuelos_afectados, 0)        AS vuelos_afectados,
    ROUND(
        1000.0 * COALESCE(r.vuelos_afectados, 0) / v.total_vuelos,
        2
    ) AS tasa_por_1000_vuelos,
    ROUND(
        100.0 * COALESCE(r.vuelos_afectados, 0) / v.total_vuelos,
        2
    ) AS pct_vuelos_afectados
FROM aerolinea a
JOIN vuelos_por_aerolinea v ON v.aerolinea_ruc = a.ruc
LEFT JOIN retrasos_combustible r ON r.aerolinea_ruc = a.ruc
ORDER BY vuelos_afectados DESC, tasa_por_1000_vuelos DESC
""".strip()


# Q4 — Recaudación TUUA por categoría migratoria (solo pasajeros efectivos).
# En Hito 2 esto va contra la vista `vw_recaudacion_tuua` (DS-12).
Q4_RECAUDACION_TUUA = """
WITH pasajeros_efectivos AS (
    SELECT
        p.id_categoria,
        cm.nombre  AS categoria,
        cm.tarifa,
        COUNT(*)   AS pasajeros
    FROM ticket t
    JOIN pasajero p ON p.id_persona = t.id_persona
    JOIN categoria_migratoria cm ON cm.id = p.id_categoria
    JOIN vuelo v ON v.id = t.id_vuelo
    WHERE t.estado_boarding IN ('Check-in', 'Embarcado')
      AND v.estado <> 'Cancelado'
    GROUP BY p.id_categoria, cm.nombre, cm.tarifa
),
totales AS (
    SELECT SUM(pasajeros * tarifa) AS recaudacion_total FROM pasajeros_efectivos
)
SELECT
    pe.categoria,
    pe.tarifa                                                   AS tarifa_tuua_soles,
    pe.pasajeros,
    ROUND(pe.pasajeros * pe.tarifa, 2)                          AS recaudacion_soles,
    ROUND(
        100.0 * (pe.pasajeros * pe.tarifa) / t.recaudacion_total,
        2
    )                                                           AS share_pct
FROM pasajeros_efectivos pe
CROSS JOIN totales t
ORDER BY recaudacion_soles DESC
""".strip()


# Q5 — Porcentaje de vuelos en hora punta retrasados.
# En Hito 2 esto va contra la vista `vw_retrasos_hora_punta` (DS-12).
Q5_HORA_PUNTA = """
WITH vuelos_tipados AS (
    SELECT
        v.id,
        v.tipo,
        v.estado,
        TRY(from_iso8601_timestamp(v.hora_programada)) AS hora_programada,
        TRY(from_iso8601_timestamp(v.hora_real)) AS hora_real
    FROM vuelo v
    WHERE v.estado <> 'Cancelado'
),
clasificados AS (
    SELECT
        id,
        tipo,
        CAST(EXTRACT(HOUR FROM hora_programada) AS INTEGER) AS hora,
        CASE
            WHEN CAST(EXTRACT(HOUR FROM hora_programada) AS INTEGER) BETWEEN 6  AND 8  THEN 'HORA PUNTA (06-09h)'
            WHEN CAST(EXTRACT(HOUR FROM hora_programada) AS INTEGER) BETWEEN 18 AND 20 THEN 'HORA PUNTA (18-21h)'
            ELSE 'NO PUNTA'
        END AS franja,
        CASE
            WHEN estado = 'Retrasado' THEN 1
            WHEN hora_real IS NOT NULL
                 AND date_diff('minute', hora_programada, hora_real) > 15 THEN 1
            ELSE 0
        END AS es_retrasado,
        CASE
            WHEN hora_real IS NOT NULL
            THEN CAST(date_diff('minute', hora_programada, hora_real) AS DOUBLE)
        END AS retraso_min
    FROM vuelos_tipados
    WHERE hora_programada IS NOT NULL
)
SELECT
    franja,
    tipo,
    COUNT(*)                                    AS vuelos,
    SUM(es_retrasado)                           AS vuelos_retrasados,
    ROUND(100.0 * SUM(es_retrasado) / COUNT(*), 2) AS pct_retrasados,
    ROUND(AVG(retraso_min), 2)                  AS retraso_promedio_min,
    ROUND(approx_percentile(retraso_min, 0.90), 2) AS retraso_p90_min
FROM clasificados
GROUP BY franja, tipo
ORDER BY franja, tipo
""".strip()
