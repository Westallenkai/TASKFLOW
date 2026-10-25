# TaskFlow — App de gestión de tareas (Python + Flask)

App web para crear, completar, buscar, filtrar, reordenar y eliminar tareas,
con proyectos, fechas de vencimiento y persistencia en SQLite.
Sin dependencias extra (solo Flask).

## Ejecutar

```bash
pip install flask   # si no lo tuvieras
python app.py
```

Abre [http://127.0.0.1:5000](http://127.0.0.1:5000).
La base `tasks.db` se crea (o migra sola, si venía de la versión anterior).

Verificar que todo funciona: `python _verify.py`

## Funcionalidades

- ➕ Crear tarea con prioridad (🟢 baja / 🟡 media / 🔴 alta), proyecto y fecha de vencimiento
- ✅ Marcar / desmarcar completadas (con animación y contadores en vivo)
- ✏️ Editar el título en línea (doble clic o botón ✎ — Enter guarda, Esc cancela)
- 🗂️ Proyectos con color y contador de pendientes (borrar un proyecto deja sus tareas en «Sin proyecto»)
- 📅 Vencimientos con badges: ⚠ vencida · hoy · 📅 próxima
- ↕️ Drag & drop para reordenar (orden manual, posiciones fraccionales)
- 🔀 Ordenar por: manual · fecha · prioridad
- 🔍 Búsqueda por texto (literal: `%` y `_` no actúan como comodines)
- 🗂️ Filtros Todas · Pendientes · Completadas, combinables con proyecto y búsqueda
- 🗑️ Eliminar una tarea o limpiar todas las completadas
- 💾 Persistencia en SQLite (`tasks.db`, con migración automática del esquema)
- 🎨 UI oscura moderna, responsive (sidebar de proyectos que se vuelve fila en móvil)

## Estructura

```
idk/
├── app.py               # Flask + SQLite (rutas HTML y API)
├── tasks.db             # base de datos (autogenerada/migrada)
├── requirements.txt
├── _verify.py           # suite de verificación (test client, sin dependencias)
└── templates/
    └── index.html       # UI + JS (fetch a la API)
```

## API (JSON)

| Método | Ruta                   | Cuerpo                                             | Descripción                        |
|--------|------------------------|----------------------------------------------------|------------------------------------|
| POST   | `/api/tareas`          | `{title, priority?, due_date?, project_id?}`       | crear tarea                         |
| PATCH  | `/api/tareas/<id>`     | `{title?, completed?, priority?, due_date?, project_id?, position?}` | actualizar |
| DELETE | `/api/tareas/<id>`     | —                                                  | eliminar                            |
| POST   | `/api/tareas/reordenar`| `{ids: [...]}` (en el orden visible)               | renumera las posiciones             |
| POST   | `/api/limpiar-hechas`  | —                                                  | borrar todas las completadas        |
| GET    | `/api/proyectos`       | —                                                  | lista con contadores                |
| POST   | `/api/proyectos`       | `{name, color?}`                                   | crear (409 si ya existe)            |
| PATCH  | `/api/proyectos/<id>`  | `{name?, color?}`                                  | actualizar                          |
| DELETE | `/api/proyectos/<id>`  | —                                                  | eliminar (tareas → sin proyecto)    |

Fechas en formato `YYYY-MM-DD`; colores en `#rrggbb`.
