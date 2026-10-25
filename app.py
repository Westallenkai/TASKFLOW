"""
📝 TaskFlow - App de gestión de tareas
Flask + SQLite, sin dependencias extra.
Ejecutar: python app.py  ->  http://127.0.0.1:5000
"""
import os
import re
import sqlite3
from datetime import date, datetime
from pathlib import Path
from urllib.parse import quote

from flask import Flask, g, render_template, request

BASE_DIR = Path(__file__).resolve().parent
# La BD va por defecto junto a app.py; la variable TASKFLOW_DB la desplaza
# (p. ej. a /data/tasks.db en Docker) para que los datos vivan en un volumen.
DB_PATH = Path(os.environ.get("TASKFLOW_DB") or str(BASE_DIR / "tasks.db"))

app = Flask(__name__)
app.secret_key = "taskflow-dev-key-cambia-en-prod"


# ---------------------------------------------------------------------------
# BD (SQLite)
# ---------------------------------------------------------------------------
def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(DB_PATH, check_same_thread=False)
        g.db.row_factory = sqlite3.Row
    return g.db


@app.teardown_appcontext
def close_db(_exc):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def _columns(conn, table):
    return {r[1] for r in conn.execute(f"PRAGMA table_info({table})")}


def init_db():
    db = sqlite3.connect(DB_PATH, check_same_thread=False)
    db.execute(
        """
        CREATE TABLE IF NOT EXISTS projects (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            name        TEXT NOT NULL,
            color       TEXT NOT NULL DEFAULT '#6c7bff',
            created_at  TEXT NOT NULL
        )
        """
    )
    db.execute(
        """
        CREATE TABLE IF NOT EXISTS tasks (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            title       TEXT NOT NULL,
            completed   INTEGER NOT NULL DEFAULT 0,
            priority    TEXT NOT NULL DEFAULT 'media' CHECK (priority IN ('baja','media','alta')),
            due_date    TEXT,
            project_id  INTEGER REFERENCES projects(id) ON DELETE SET NULL,
            pos         REAL NOT NULL DEFAULT 0,
            created_at  TEXT NOT NULL
        )
        """
    )
    # Migración idempotente para BDs creadas con la versión anterior
    cols = _columns(db, "tasks")
    for col, decl in (
        ("due_date", "TEXT"),
        ("project_id", "INTEGER REFERENCES projects(id) ON DELETE SET NULL"),
        ("pos", "REAL NOT NULL DEFAULT 0"),
    ):
        if col not in cols:
            db.execute(f'ALTER TABLE tasks ADD COLUMN "{col}" {decl}')
    db.commit()
    db.close()


init_db()


def query(sql, params=()):
    return get_db().execute(sql, params).fetchall()


def execute(sql, params=()):
    db = get_db()
    db.execute(sql, params)
    db.commit()


# ---------------------------------------------------------------------------
# Rutas
# ---------------------------------------------------------------------------
FILTERS = {
    "todas":  ("", "Todas"),
    "pend":   ("completed = 0", "Pendientes"),
    "hechas": ("completed = 1", "Completadas"),
}

ORDERS = {
    "manual":    'COALESCE("pos", 0) ASC, id ASC',
    "fecha":     '(due_date IS NULL) ASC, due_date ASC, COALESCE("pos", 0) ASC',
    "prioridad": 'CASE priority WHEN "alta" THEN 0 WHEN "media" THEN 1 ELSE 2 END, '
                 'COALESCE("pos", 0) ASC, id ASC',
}

PRIORITIES = ("baja", "media", "alta")


def escape_like(term):
    """Escapa los comodines de LIKE (\\, %, _) para que la búsqueda sea literal."""
    return term.replace("\\", "\\\\").replace("%", r"\%").replace("_", r"\_")


def valid_date(value):
    """Devuelve la fecha normalizada YYYY-MM-DD o None (vacía o inválida)."""
    value = (value or "").strip()
    if not value:
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%d").strftime("%Y-%m-%d")
    except ValueError:
        return None


def due_state(due_date):
    """'vencida' / 'hoy' / 'pronto' según la fecha; None si no hay fecha."""
    if not due_date:
        return None
    try:
        d = datetime.strptime(due_date, "%Y-%m-%d").date()
    except ValueError:
        return None
    today = date.today()
    if d < today:
        return "vencida"
    if d == today:
        return "hoy"
    return "pronto"


def valid_color(value):
    value = (value or "").strip()
    return value if re.fullmatch(r"#[0-9a-fA-F]{6}", value) else None


@app.context_processor
def _url_helpers():
    def tab_url(filtro):
        parts = [f"filtro={filtro}"]
        if request.args.get("q"):
            parts.append("q=" + quote(request.args.get("q"), safe=""))
        if request.args.get("proyecto"):
            parts.append("proyecto=" + quote(request.args.get("proyecto"), safe=""))
        if request.args.get("orden", "manual") != "manual":
            parts.append("orden=" + quote(request.args.get("orden"), safe=""))
        return "/" + "?" + "&".join(parts)

    def proj_url(filtro, search, orden, pid):
        parts = [f"filtro={filtro}"]
        if search:
            parts.append("q=" + quote(search, safe=""))
        if orden != "manual":
            parts.append("orden=" + quote(orden, safe=""))
        if pid:
            parts.append("proyecto=" + str(pid))
        return "/" + "?" + "&".join(parts)

    return {"tab_url": tab_url, "proj_url": proj_url}


@app.route("/")
def index():
    filtro = request.args.get("filtro", "todas")
    cond, filtro_label = FILTERS.get(filtro, FILTERS["todas"])
    search = request.args.get("q", "").strip()
    proyecto = request.args.get("proyecto", "").strip()
    orden = request.args.get("orden", "manual")
    if orden not in ORDERS:
        orden = "manual"
    if not proyecto.isdigit():
        proyecto = ""

    where = []
    params = []
    if cond:
        where.append(cond)
    if proyecto:
        where.append("project_id = ?")
        params.append(int(proyecto))
    if search:
        where.append("lower(title) LIKE ? ESCAPE '\\'")
        params.append(f"%{escape_like(search.lower())}%")

    sql = "SELECT * FROM tasks"
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY completed ASC, " + ORDERS[orden]

    tasks = []
    for r in query(sql, tuple(params)):
        t = dict(r)
        t["pos"] = t.get("pos") or 0
        t["due_state"] = None if t["completed"] else due_state(t.get("due_date"))
        tasks.append(t)

    proyectos = query(
        "SELECT p.id, p.name, p.color,"
        " (SELECT COUNT(*) FROM tasks t WHERE t.project_id = p.id) total,"
        " (SELECT COUNT(*) FROM tasks t WHERE t.project_id = p.id AND t.completed = 0) pend"
        " FROM projects p ORDER BY p.id"
    )
    proj_names = {p["id"]: p["name"] for p in proyectos}

    # Contadores globales para las estadísticas
    total = query("SELECT COUNT(*) c FROM tasks")[0]["c"]
    pendientes = query("SELECT COUNT(*) c FROM tasks WHERE completed = 0")[0]["c"]
    completadas = total - pendientes

    return render_template(
        "index.html",
        tasks=tasks,
        filtro=filtro,
        filtro_label=filtro_label,
        search=search,
        total=total,
        pendientes=pendientes,
        completadas=completadas,
        proyecto=proyecto,
        proyecto_name=proj_names.get(int(proyecto), "") if proyecto else "",
        orden=orden,
        proyectos=proyectos,
        proj_names=proj_names,
        proj_colors={p["id"]: p["color"] for p in proyectos},
    )


@app.route("/api/tareas", methods=["POST"])
def crear_tarea():
    data = request.get_json(silent=True) or {}
    title = (data.get("title") or "").strip()
    priority = data.get("priority") or "media"
    if not title:
        return {"error": "El título no puede estar vacío"}, 400
    if priority not in PRIORITIES:
        priority = "media"
    due = valid_date(data.get("due_date"))
    project_id = None
    pid = data.get("project_id")
    if pid not in (None, ""):
        if str(pid).isdigit() and query("SELECT id FROM projects WHERE id = ?", (int(pid),)):
            project_id = int(pid)
        else:
            return {"error": "Proyecto no válido"}, 400
    nxt = query('SELECT COALESCE(MAX("pos"), 0) + 1 AS p FROM tasks')[0]["p"]
    execute(
        'INSERT INTO tasks (title, priority, due_date, project_id, "pos", created_at) '
        "VALUES (?, ?, ?, ?, ?, ?)",
        (title[:140], priority, due, project_id, nxt,
         datetime.now().strftime("%Y-%m-%d %H:%M")),
    )
    return {"ok": True}, 201


@app.route("/api/tareas/<int:task_id>", methods=["PATCH"])
def actualizar_tarea(task_id):
    data = request.get_json(silent=True) or {}
    if not query("SELECT id FROM tasks WHERE id = ?", (task_id,)):
        return {"error": "Tarea no encontrada"}, 404
    if "completed" in data:
        done = 1 if str(data["completed"]).strip().lower() in ("1", "true") else 0
        execute("UPDATE tasks SET completed = ? WHERE id = ?", (done, task_id))
    if "title" in data:
        title = (data["title"] or "").strip()
        if title:  # un título vacío no se aplica
            execute("UPDATE tasks SET title = ? WHERE id = ?", (title[:140], task_id))
    if "priority" in data and data["priority"] in PRIORITIES:
        execute("UPDATE tasks SET priority = ? WHERE id = ?",
                (data["priority"], task_id))
    if "due_date" in data:
        execute("UPDATE tasks SET due_date = ? WHERE id = ?",
                (valid_date(data["due_date"]), task_id))
    if "project_id" in data:
        pid = data["project_id"]
        if pid in (None, ""):
            execute("UPDATE tasks SET project_id = NULL WHERE id = ?", (task_id,))
        elif str(pid).isdigit() and query("SELECT id FROM projects WHERE id = ?", (int(pid),)):
            execute("UPDATE tasks SET project_id = ? WHERE id = ?", (int(pid), task_id))
    if "position" in data:
        try:
            pos = float(data["position"])
        except (TypeError, ValueError):
            pos = None
        if pos is not None and pos == pos:  # descarta NaN
            execute('UPDATE tasks SET "pos" = ? WHERE id = ?', (pos, task_id))
    return {"ok": True}


@app.route("/api/tareas/<int:task_id>", methods=["DELETE"])
def eliminar_tarea(task_id):
    if not query("SELECT id FROM tasks WHERE id = ?", (task_id,)):
        return {"error": "Tarea no encontrada"}, 404
    execute("DELETE FROM tasks WHERE id = ?", (task_id,))
    return {"ok": True}


@app.route("/api/tareas/reordenar", methods=["POST"])
def reordenar_tareas():
    """Recibe {ids: [...]} en el orden visible y renumera sus posiciones."""
    data = request.get_json(silent=True) or {}
    ids = data.get("ids")
    if not isinstance(ids, list):
        return {"error": "ids inválidos"}, 400
    clean = []
    for i in ids:
        try:
            i = int(i)
        except (TypeError, ValueError):
            continue
        if i not in clean:
            clean.append(i)
    if not clean:
        return {"error": "ids inválidos"}, 400
    db = get_db()
    for n, i in enumerate(clean, start=1):
        db.execute('UPDATE tasks SET "pos" = ? WHERE id = ?', (n, i))
    db.commit()
    return {"ok": True}


@app.route("/api/limpiar-hechas", methods=["POST"])
def limpiar_hechas():
    execute("DELETE FROM tasks WHERE completed = 1")
    return {"ok": True}


# ---------------------------------------------------------------------------
# API: proyectos
# ---------------------------------------------------------------------------
@app.route("/api/proyectos", methods=["GET"])
def listar_proyectos():
    rows = query(
        "SELECT p.id, p.name, p.color, p.created_at,"
        " (SELECT COUNT(*) FROM tasks t WHERE t.project_id = p.id) total,"
        " (SELECT COUNT(*) FROM tasks t WHERE t.project_id = p.id AND t.completed = 0) pendientes"
        " FROM projects p ORDER BY p.id"
    )
    return [dict(r) for r in rows]


@app.route("/api/proyectos", methods=["POST"])
def crear_proyecto():
    data = request.get_json(silent=True) or {}
    name = (data.get("name") or "").strip()
    color = valid_color(data.get("color")) or "#6c7bff"
    if not name:
        return {"error": "El nombre no puede estar vacío"}, 400
    name = name[:40]
    if query("SELECT id FROM projects WHERE lower(name) = lower(?)", (name,)):
        return {"error": "Ya existe un proyecto con ese nombre"}, 409
    execute(
        "INSERT INTO projects (name, color, created_at) VALUES (?, ?, ?)",
        (name, color, datetime.now().strftime("%Y-%m-%d")),
    )
    return {"ok": True}, 201


@app.route("/api/proyectos/<int:project_id>", methods=["PATCH"])
def actualizar_proyecto(project_id):
    data = request.get_json(silent=True) or {}
    if not query("SELECT id FROM projects WHERE id = ?", (project_id,)):
        return {"error": "Proyecto no encontrado"}, 404
    if "name" in data:
        name = (data["name"] or "").strip()
        if not name:
            return {"error": "El nombre no puede estar vacío"}, 400
        if query("SELECT id FROM projects WHERE id != ? AND lower(name) = lower(?)",
                 (project_id, name)):
            return {"error": "Ya existe un proyecto con ese nombre"}, 409
        execute("UPDATE projects SET name = ? WHERE id = ?", (name[:40], project_id))
    if "color" in data:
        color = valid_color(data["color"])
        if color:
            execute("UPDATE projects SET color = ? WHERE id = ?", (color, project_id))
    return {"ok": True}


@app.route("/api/proyectos/<int:project_id>", methods=["DELETE"])
def eliminar_proyecto(project_id):
    if not query("SELECT id FROM projects WHERE id = ?", (project_id,)):
        return {"error": "Proyecto no encontrado"}, 404
    # Las tareas del proyecto pasan a "Sin proyecto"
    execute("UPDATE tasks SET project_id = NULL WHERE project_id = ?", (project_id,))
    execute("DELETE FROM projects WHERE id = ?", (project_id,))
    return {"ok": True}


if __name__ == "__main__":
    app.run(debug=True, port=5000)
