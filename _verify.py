"""Verificacion de las funciones (usa el test client de Flask, sin dependencias).

Cubre: busqueda literal, filtros, CRUD, fechas de vencimiento, proyectos,
edicion de titulo, reordenacion (pos + /reordenar) y limpieza de hechas.
Al terminar deja la base de datos vacia.
"""
import sqlite3
import sys
from datetime import date, timedelta
from pathlib import Path
from urllib.parse import quote

sys.path.insert(0, str(Path(__file__).parent))
import app as a  # noqa: E402

c = a.app.test_client()
fails = []


def check(name, cond, extra=""):
    print(("PASS " if cond else "FAIL ") + name + (f"  [{extra}]" if extra and not cond else ""))
    if not cond:
        fails.append(name)


def tasks_by_id():
    with a.app.app_context():
        return [dict(x) for x in a.query("SELECT * FROM tasks ORDER BY id")]


def tasks_db():
    with a.app.app_context():
        return [dict(x) for x in a.query('SELECT * FROM tasks ORDER BY "pos" ASC, id ASC')]


def projs_db():
    with a.app.app_context():
        return [dict(x) for x in a.query("SELECT * FROM projects ORDER BY id")]


def titles():
    return [t["title"] for t in tasks_by_id()]


TODAY = date.today().strftime("%Y-%m-%d")
YESTERDAY = (date.today() - timedelta(days=1)).strftime("%Y-%m-%d")
TOMORROW = (date.today() + timedelta(days=1)).strftime("%Y-%m-%d")

# --- 1. Vistas basicas (regresion del bug de 500 en busqueda) ---
check("GET / -> 200", c.get("/").status_code == 200)
check("GET /?q=foo -> 200", c.get("/?q=foo").status_code == 200)
check("GET /?filtro=pend&q=foo -> 200", c.get("/?filtro=pend&q=foo").status_code == 200)
check("GET /?filtro=hechas&q=foo -> 200", c.get("/?filtro=hechas&q=foo").status_code == 200)

# --- 2. Busqueda literal con comodines (regresion) ---
c.post("/api/tareas", json={"title": "hacer el 100% de la tarea", "priority": "alta"})
c.post("/api/tareas", json={"title": "test a_b con guion bajo", "priority": "baja"})
# (se comprueban titulos completos: substrings como '100%' tambien aparecen en el CSS)
html = c.get("/?q=100%").get_data(as_text=True)
check("busqueda literal '100%' solo coincide la tarea con %",
      "hacer el 100% de la tarea" in html and "test a_b con guion bajo" not in html)
html = c.get("/?q=a_b").get_data(as_text=True)
check("busqueda literal 'a_b' no coincide por comodin _",
      "test a_b con guion bajo" in html and "hacer el 100% de la tarea" not in html)

# --- 3. Proyectos: crear, duplicado, validaciones ---
r = c.post("/api/proyectos", json={"name": "Trabajo", "color": "#ff0000"})
check("POST /api/proyectos -> 201", r.status_code == 201, str(r.status_code))
check("proyecto duplicado (case-insensitive) -> 409",
      c.post("/api/proyectos", json={"name": "trabajo"}).status_code == 409)
check("proyecto sin nombre -> 400",
      c.post("/api/proyectos", json={"name": ""}).status_code == 400)
c.post("/api/proyectos", json={"name": "Estudio", "color": "color-invalido"})
check("color invalido se normaliza",
      next(p["color"] for p in projs_db() if p["name"] == "Estudio") == "#6c7bff")
check("GET /api/proyectos lista ambos",
      {p["name"] for p in c.get("/api/proyectos").get_json()} == {"Trabajo", "Estudio"})
pids = {p["name"]: p["id"] for p in projs_db()}

# --- 4. Tareas con vencimiento y proyecto ---
c.post("/api/tareas", json={"title": "reunion con el equipo",
                             "due_date": YESTERDAY, "project_id": pids["Trabajo"]})
c.post("/api/tareas", json={"title": "pagar la luz",
                             "due_date": TODAY, "project_id": pids["Trabajo"]})
c.post("/api/tareas", json={"title": "planificar sprint", "due_date": TOMORROW})
c.post("/api/tareas", json={"title": "fecha invalida x", "due_date": "no-fecha", "priority": "alta"})
check("due_date invalida -> NULL", tasks_by_id()[-1]["due_date"] is None)
check("tarea conserva su proyecto",
      next(t for t in tasks_by_id() if t["title"] == "reunion con el equipo")["project_id"]
      == pids["Trabajo"])
check("POST con proyecto inexistente -> 400",
      c.post("/api/tareas", json={"title": "x", "project_id": 999999}).status_code == 400)
check("pos crece en la creacion",
      all(tasks_by_id()[i]["pos"] <= tasks_by_id()[i + 1]["pos"]
          for i in range(len(tasks_by_id()) - 1)))

# --- 5. Estados de vencimiento en la vista ---
html = c.get("/?filtro=pend").get_data(as_text=True)
check("badge 'vencida' visible con fecha", "due vencida" in html and YESTERDAY in html)
check("badge 'hoy' visible", "due hoy" in html)
check("badge 'pronto' visible con fecha", "due pronto" in html and TOMORROW in html)

# --- 6. Filtro por proyecto ---
html = c.get(f"/?proyecto={pids['Trabajo']}").get_data(as_text=True)
check("proyecto muestra sus tareas", "reunion con el equipo" in html and "pagar la luz" in html)
check("proyecto excluye tareas de otros", "planificar sprint" not in html)
html = c.get(f"/?proyecto={pids['Estudio']}").get_data(as_text=True)
check("proyecto vacio -> estado vacio con su nombre", "No hay tareas en «Estudio»" in html)
check("proyecto inexistente -> lista vacia",
      "planificar sprint" not in c.get("/?proyecto=999").get_data(as_text=True))

# --- 7. Orden por fecha y prioridad ---
c.post("/api/tareas", json={"title": "sin fecha ninguna"})
html = c.get("/?orden=fecha").get_data(as_text=True)
i_v, i_h, i_p, i_s = (html.index(t) for t in (
    "reunion con el equipo", "pagar la luz", "planificar sprint", "sin fecha ninguna"))
check("orden=fecha: vencida < hoy < proxima < sin fecha", i_v < i_h < i_p < i_s)
html = c.get("/?orden=prioridad").get_data(as_text=True)
check("orden=prioridad: alta antes que media",
      html.index("fecha invalida x") < html.index("pagar la luz"))
check("orden=invalido -> 200 (cae en manual)", c.get("/?orden=raro").status_code == 200)

# --- 8. Edicion de titulo (PATCH) ---
t = next(x for x in tasks_by_id() if x["title"] == "planificar sprint")
check("PATCH title actualiza",
      c.patch(f"/api/tareas/{t['id']}", json={"title": "planificar sprint v2"}).status_code == 200
      and "planificar sprint v2" in titles())
c.patch(f"/api/tareas/{t['id']}", json={"title": "   "})
check("PATCH title vacio no lo borra", all(x["title"] for x in tasks_by_id()))
check("PATCH id inexistente -> 404",
      c.patch("/api/tareas/999999", json={"completed": True}).status_code == 404)

# --- 9. Posiciones: PATCH position y /reordenar ---
ts = tasks_by_id()
a1, b1, c1 = ts[0]["id"], ts[1]["id"], ts[2]["id"]
check("PATCH position guarda float",
      c.patch(f"/api/tareas/{a1}", json={"position": 0.5}).status_code == 200
      and next(x for x in tasks_by_id() if x["id"] == a1)["pos"] == 0.5)
check("reordenar -> 200",
      c.post("/api/tareas/reordenar", json={"ids": [c1, b1, a1]}).status_code == 200)
check("reordenar deja el orden pedido",
      [x["id"] for x in tasks_db() if x["id"] in (a1, b1, c1)] == [c1, b1, a1])
check("reordenar sin ids -> 400",
      c.post("/api/tareas/reordenar", json={"ids": []}).status_code == 400)

# --- 10. PATCH booleanos, DELETE y limpiar-hechas ---
t0 = tasks_by_id()[0]
c.patch(f"/api/tareas/{t0['id']}", json={"completed": "false"})
check('PATCH completed="false" (string) -> 0', tasks_by_id()[0]["completed"] == 0)
c.patch(f"/api/tareas/{t0['id']}", json={"completed": True})
check("PATCH completed=true (bool) -> 1", tasks_by_id()[0]["completed"] == 1)
c.patch(f"/api/tareas/{t0['id']}", json={"completed": "false"})
check("DELETE id inexistente -> 404", c.delete("/api/tareas/999999").status_code == 404)
check("DELETE existente -> 200",
      c.delete(f"/api/tareas/{tasks_by_id()[-1]['id']}").status_code == 200)
c.post("/api/tareas", json={"title": "para limpiar"})
last = tasks_by_id()[-1]
c.patch(f"/api/tareas/{last['id']}", json={"completed": "true"})
check("filtro pend descarta la completada",
      "para limpiar" not in c.get("/?filtro=pend").get_data(as_text=True))
check("filtro hechas muestra la completada",
      "para limpiar" in c.get("/?filtro=hechas").get_data(as_text=True))
check("POST /api/limpiar-hechas -> 200", c.post("/api/limpiar-hechas").status_code == 200)
check("limpiar borro solo las completadas",
      all(x["completed"] == 0 for x in tasks_by_id()))

# --- 11. Eliminar proyecto: sus tareas a 'Sin proyecto' ---
check("DELETE proyecto -> 200", c.delete(f"/api/proyectos/{pids['Trabajo']}").status_code == 200)
check("tareas del proyecto -> project_id NULL",
      all(x["project_id"] is None for x in tasks_by_id()
          if x["title"] in ("reunion con el equipo", "pagar la luz")))
check("DELETE proyecto inexistente -> 404", c.delete("/api/proyectos/999999").status_code == 404)

# --- 12. URLs: tabs y buscador conservan q / proyecto / orden ---
html = c.get("/?q=abc&proyecto=1&orden=fecha").get_data(as_text=True)
check("tabs conservan proyecto y orden",
      "q=abc" in html and "proyecto=1" in html and "orden=fecha" in html)
html = c.get("/?q=" + quote("a+b & c", safe="")).get_data(as_text=True)
check("tabs conservan q percent-encodeado", "q=a%2Bb%20%26%20c" in html)

# --- 13. Port del server ---
src = (a.BASE_DIR / "app.py").read_text(encoding="utf-8")
check("app.run usa puerto 5000 (coherente con README)",
      "port=5000" in src and "port=7500" not in src)

# --- Limpieza: dejar la BD vacia como estaba ---
db = sqlite3.connect(a.DB_PATH)
db.execute("DELETE FROM tasks")
db.execute("DELETE FROM projects")
db.commit()
db.close()

print()
print("FALLOS:", fails if fails else "ninguno - todos los checks OK")
sys.exit(1 if fails else 0)
