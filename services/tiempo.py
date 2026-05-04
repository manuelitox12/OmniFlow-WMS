"""
tiempo.py — Motor de cálculo de tiempo laboral
================================================
Calcula minutos regulares, extras y totales entre dos timestamps,
respetando horarios laborales configurados en la BD (tabla empresa).
"""
from datetime import datetime, date, time, timedelta
from flask import g


def _fmt_minutos(m):
    """Formatea minutos a texto legible: '2h 30min'"""
    if m <= 0:
        return "0min"
    h, mins = divmod(int(m), 60)
    if h > 0 and mins > 0:
        return f"{h}h {mins}min"
    if h > 0:
        return f"{h}h"
    return f"{mins}min"


def _get_dynamic_work_config():
    """Lee la configuración de horarios desde g.empresa (BD)."""
    try:
        emp = g.empresa
        if emp:
            def parse_time(s, default):
                try:
                    parts = s.split(":")
                    return time(int(parts[0]), int(parts[1]))
                except:
                    return default

            return {
                "work_start":       parse_time(emp.get("work_start", "07:00"), time(7, 0)),
                "work_end":         parse_time(emp.get("work_end", "16:30"), time(16, 30)),
                "lunch_start":      parse_time(emp.get("lunch_start", "12:00"), time(12, 0)),
                "lunch_end":        parse_time(emp.get("lunch_end", "12:30"), time(12, 30)),
                "work_days":        {0, 1, 2, 3, 4},
                "include_saturday": bool(emp.get("include_saturday", 0)),
                "saturday_is_regular": bool(emp.get("saturday_regular", 0)),
                "sunday_is_extra":  bool(emp.get("sunday_extra", 0)),
            }
    except:
        pass
    # Defaults
    return {
        "work_start": time(7, 0),
        "work_end": time(16, 30),
        "lunch_start": time(12, 0),
        "lunch_end": time(12, 30),
        "work_days": {0, 1, 2, 3, 4},
        "include_saturday": False,
        "saturday_is_regular": False,
        "sunday_is_extra": False,
    }


def _minutos_en_tramo_diario(dia, dt_ini, dt_fin, cfg):
    """Calcula minutos regulares y extras para un tramo dentro de un solo día."""
    weekday  = dia.weekday()
    dia_base = datetime.combine(dia, time(0, 0))
    ti = int((dt_ini - dia_base).total_seconds()) // 60
    if dt_fin.date() > dia:
        tf = 24 * 60
    else:
        tf = int((dt_fin - dia_base).total_seconds()) // 60
    total_tramo = tf - ti
    if total_tramo <= 0:
        return 0, 0

    ws_ = cfg["work_start"].hour * 60 + cfg["work_start"].minute
    we_ = cfg["work_end"].hour   * 60 + cfg["work_end"].minute
    ls  = cfg["lunch_start"].hour * 60 + cfg["lunch_start"].minute
    le  = cfg["lunch_end"].hour   * 60 + cfg["lunch_end"].minute

    def overlap(a, b, c, d):
        return max(0, min(b, d) - max(a, c))

    def split_regular_extra():
        en_horario = overlap(ti, tf, ws_, we_)
        almuerzo   = overlap(ti, tf, ls, le)
        regulares  = max(0, en_horario - almuerzo)
        extras     = total_tramo - en_horario
        return regulares, extras

    if weekday in cfg["work_days"]:
        return split_regular_extra()
    if weekday == 5:
        if cfg.get("include_saturday") and cfg.get("saturday_is_regular"):
            return split_regular_extra()
        return 0, total_tramo
    if weekday == 6:
        if cfg.get("sunday_is_extra"):
            return 0, total_tramo
        return 0, 0
    return 0, 0


def calcular_tiempo_laboral(inicio_str, fin_str, cfg=None):
    """Calcula tiempo laboral entre dos fechas/hora string."""
    if not inicio_str or not fin_str:
        return None
    if cfg is None:
        cfg = _get_dynamic_work_config()
    inicio = fin = None
    # Normalizar T por espacio para máxima compatibilidad
    inicio_str = inicio_str.replace("T", " ")
    fin_str    = fin_str.replace("T", " ")

    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d"):
        try:
            inicio = datetime.strptime(inicio_str, fmt)
            fin    = datetime.strptime(fin_str, fmt)
            break
        except ValueError:
            continue
    if inicio is None or fin is None or fin <= inicio:
        return None
    minutos_totales   = int((fin - inicio).total_seconds()) // 60
    minutos_regulares = 0
    minutos_extras    = 0
    cursor = inicio
    while cursor < fin:
        dia     = cursor.date()
        fin_dia = datetime.combine(dia + timedelta(days=1), time(0, 0))
        tramo_fin = min(fin, fin_dia)
        reg, ext = _minutos_en_tramo_diario(dia, cursor, tramo_fin, cfg)
        minutos_regulares += reg
        minutos_extras    += ext
        cursor = fin_dia
    return {
        "minutos_totales":   minutos_totales,
        "minutos_regulares": minutos_regulares,
        "minutos_extras":    minutos_extras,
        "texto_total":       _fmt_minutos(minutos_totales),
        "texto_regulares":   _fmt_minutos(minutos_regulares),
        "texto_extras":      _fmt_minutos(minutos_extras),
    }
