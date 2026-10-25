<div align="center">

# 📋 TaskFlow

### La app de gestión de tareas que no te pide nada

Crear, completar, buscar, filtrar, reordenar y eliminar tareas — con **proyectos**,
**fechas de vencimiento** y persistencia en SQLite. Sin dependencias extra (solo Flask).

[![Flask](https://img.shields.io/badge/Flask-3.x-092824?style=flat-square&logo=flask)](https://flask.palletsprojects.com/)
[![Python](https://img.shields.io/badge/Python-3.9+-117DDD?style=flat-square&logo=python&logoColor=white)](https://www.python.org/)
[![SQLite](https://img.shields.io/badge/SQLite-3.0-003B57?style=flat-square&logo=sqlite&logoColor=white)](https://www.sqlite.org/)
[![Docker](https://img.shields.io/badge/Docker-taskflow-2496ED?style=flat-square&logo=docker&logoColor=white)](https://docs.docker.com/)

**[🚀 Ejecutar](#-ejecutar)** · **[🐳 Docker](#-docker)** · **[✨ Funcionalidades](#-funcionalidades)** · **[🖱 Uso diario](#-uso-diario)** · **[🧠 Cómo funciona](#-cómo-funciona)** · **[📁 Estructura](#-estructura)** · **[🔌 API](#-api-json)**

</div>

---

## 🚀 Ejecutar

```bash
pip install flask   # si no lo tuvieras
python app.py
```

Abre [http://127.0.0.1:5000](http://127.0.0.1:5000).
La base `tasks.db` se crea (o migra sola, si venía de la versión anterior).

Verificar que todo funciona: `python _verify.py`

### 🐳 Docker (imagen autocontenida)

No hay que instalar nada en la máquina — la imagen trae Python + Flask:

```bash
docker build -t taskflow .
docker run -d -p 5000:5000 taskflow    # abre http://127.0.0.1:5000
```

- Los datos (`tasks.db`) viven en el volumen `/data`: sobreviven a la recreación
  del contenedor y se gestionan solos (o fíjalos a una carpeta de la máquina:
  `docker run -p 5000:5000 -v <ruta>/taskflow-data:/data taskflow`).
- La app corre con un usuario no-root, en un solo proceso y escuchando en
  `0.0.0.0` (sin el reloader de debug).
- Para parar: `docker stop <nombre-del-contenedor>`.

---

## ✨ Funcionalidades

|  |  |
|:---|:---|
| ➕ | Crear tarea con prioridad (🟢 baja / 🟡 media / 🔴 alta), proyecto y fecha de vencimiento |
| ✅ | Marcar / desmarcar completadas (con animación y contadores en vivo) |
| ✏️ | Editar el título en línea (doble clic o botón ✎ — Enter guarda, Esc cancela) |
| 🗂️ | Proyectos con color y contador de pendientes (borrar un proyecto deja sus tareas en «Sin proyecto») |
| 📅 | Vencimientos con badges: ⚠ vencida · hoy · 📅 próxima |
| ↕️ | Drag & drop para reordenar (orden manual, posiciones fraccionales) |
| 🔀 | Ordenar por: manual · fecha · prioridad |
| 🔍 | Búsqueda por texto (literal: `%` y `_` no actúan como comodines) |
| 🗂️ | Filtros Todas · Pendientes · Completadas, combinables con proyecto y búsqueda |
| 🗑️ | Eliminar una tarea o limpiar todas las completadas |
| 💾 | Persistencia en SQLite (`tasks.db`, con migración automática del esquema) |
| 🎨 | UI oscura moderna, responsive (sidebar de proyectos que se vuelve fila en móvil) |

---

## 🖱 Uso diario

| Quieres… | Así lo haces |
|:---|:---|
| Completar una tarea | Checkbox de la izquierda |
| Editar el título | Doble clic, o el botón ✎ |
| Mover una tarea | Arrástrala y suéltala (con orden «manual») |
| Borrar una tarea | 🗑 al final de la fila |
| Despachar el día | «Limpiar completadas» en el pie |

---

## 🧠 Cómo funciona

**Reordenar = un `UPDATE`.** Cada tarea tiene una columna `pos` (float). Al soltar
una tarea entre dos recibe el punto medio de sus posiciones; solo cuando el hueco
se agota (`< 1e-4`) el servidor renormaliza la lista completa en una transacción
(`POST /api/tareas/reordenar`).

**Vencimientos en el servidor.** El estado `vencida / hoy / próxima` se calcula
con la fecha local del servidor, no la del cliente: el badge es el mismo para
todos, da igual la zona horaria.

**Búsqueda literal con `ESCAPE`.** El patrón se escapa antes del `LIKE`
(`\%`, `\_`, `\\`): buscar `100%` solo coincide con `100%`.

---

## 📁 Estructura

```
.
├── app.py               # Flask + SQLite (rutas HTML y API)
├── Dockerfile           # imagen autocontenida (no-root, volumen /data)
├── tasks.db             # base de datos (autogenerada/migrada)
├── requirements.txt
├── _verify.py           # suite de verificación (test client, sin dependencias)
└── templates/
    └── index.html       # UI + JS (fetch a la API)
```

## 🔌 API (JSON)

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

> 📅 Fechas en formato `YYYY-MM-DD` · 🎨 colores en `#rrggbb`
> 💡 Los booleanos se aceptan como JSON (`true`) o texto (`"true"`, `"1"`, `"yes"`, …)

---

## 🧪 Verificación

```bash
python _verify.py
```

Suite de **45 checks** contra el test client — búsqueda, filtros, proyectos,
vencimientos, orden, reordenado, edición de título, booleanos y puerto.
Al terminar deja la base de datos vacía.

---

<div align="center">

Hecho con 🖤 — Flask, SQLite y cero frameworks.

</div>
