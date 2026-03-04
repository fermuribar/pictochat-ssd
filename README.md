# PictoChat (Flask + JWT + API Key) — Docker-ready

Aplicación web/API para un “chat” sencillo con autenticación, control de permisos (admin), documentación Swagger y despliegue fácil con Docker. Incluye persistencia (SQLite) y logs en el host, además de un pack de tests de endpoints (pytest) para validar funcionamiento y casos límite.

---

## Tabla de contenidos

* [Características](#características)
* [Estructura del proyecto](#estructura-del-proyecto)
* [Requisitos](#requisitos)
* [Configuración con .env](#configuración-con-env)
* [Ejecutar con Docker (recomendado)](#ejecutar-con-docker-recomendado)
* [Ejecutar en local (sin Docker)](#ejecutar-en-local-sin-docker)
* [Endpoints y ejemplos](#endpoints-y-ejemplos)
* [Persistencia (DB) y logs en el host](#persistencia-db-y-logs-en-el-host)
* [Tests de endpoints (fuera de Docker)](#tests-de-endpoints-fuera-de-docker)
* [Troubleshooting](#troubleshooting)
* [Contribuir / Pull Request](#contribuir--pull-request)
* [Licencia](#licencia)

---

## Características

* API REST con Flask.
* Registro y login con **JWT** (`Authorization: Bearer <token>`).
* Generación y uso de **API Keys** para acceder a endpoints de chat (`X-API-KEY`).
* Rol **admin** con permisos para editar/borrar mensajes.
* UI simple con plantillas HTML (`/login.html`, `/register.html`, `/chat.html`).
* Documentación tipo Swagger disponible en `/swagger`.
* Dockerización completa con Docker y `docker compose`.
* Persistencia en host:

  * Base de datos SQLite en `./volumes/data`
  * Logs en `./volumes/logs`
* Tests de endpoints con `pytest` (fuera del contenedor).

---

## Estructura del proyecto

Ejemplo típico:

```text
.
├─ app.py
├─ requirements.txt
├─ Dockerfile
├─ docker-compose.yml
├─ .env                # NO se commitea
├─ .env.example        # plantilla (sí se commitea)
├─ templates/
│  ├─ login.html
│  ├─ register.html
│  └─ chat.html
├─ volumes/
│  ├─ data/            # sqlite
│  └─ logs/            # audit.log
└─ tests/
   ├─ requirements-dev.txt
   ├─ run_tests.sh
   └─ test_api_endpoints.py
```

---

## Requisitos

### Para Docker

* Docker + Docker Compose v2

### Para ejecución local (sin Docker)

* Python 3.9+ (recomendado 3.10+)
* pip / venv

---

## Configuración con .env

1. Copia `.env.example` a `.env`:

```bash
cp .env.example .env
```

2. Ajusta valores. Ejemplo:

```env
# --- Docker/Compose ---
HOST_HTTPS_PORT=443
CONTAINER_PORT=5000

# --- App ---
JWT_SECRET_KEY=pon-un-secret-largo-aqui
DATABASE_URL=sqlite:////app/data/pictochat.db
AUDIT_LOG_PATH=/app/logs/audit.log

PORT=5000
FLASK_DEBUG=0

# SSL:
# "adhoc" => HTTPS con certificado autogenerado (warning en navegador)
# "none" / "0" => HTTP sin TLS
SSL_CONTEXT=adhoc
```

### Notas importantes

* **No commitees `.env`** (contiene secretos).
* `JWT_SECRET_KEY` debe ser **fijo** para que los tokens no se invaliden tras reinicios.

---

## Ejecutar con Docker (recomendado)

1. Crear carpetas de volúmenes:

```bash
mkdir -p volumes/data volumes/logs
```

2. Levantar:

```bash
docker compose up -d --build
```

3. Abrir en navegador:

* `https://localhost/login.html`
* `https://localhost/register.html`
* `https://localhost/chat.html`
* Swagger: `https://localhost/swagger`

> Si usas HTTPS con `adhoc`, el navegador mostrará un warning de certificado (normal en dev).

### Parar

```bash
docker compose down
```

---

## Ejecutar en local (sin Docker)

1. Crear venv e instalar:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

2. Exporta variables de entorno (opcional, pero recomendado):

```bash
export JWT_SECRET_KEY="..."
export DATABASE_URL="sqlite:///pictochat.db"
export AUDIT_LOG_PATH="./audit.log"
export PORT=5000
export SSL_CONTEXT="adhoc"
```

3. Ejecutar:

```bash
python app.py
```

4. Abre:

* `https://localhost:5000/login.html` (si SSL_CONTEXT=adhoc)
* O `http://localhost:5000/login.html` (si SSL_CONTEXT=none)

---

## Endpoints y ejemplos

### Páginas HTML

* `GET /login.html`
* `GET /register.html`
* `GET /chat.html`

### API base

* Prefijo: `/api`
* Swagger: `/swagger`

---

### 1) Registro

**POST** `/api/register`

```bash
curl -k -X POST https://localhost/api/register \
  -H "Content-Type: application/json" \
  -d '{"username":"user1","password":"Passw0rd!"}'
```

---

### 2) Login (JWT)

**POST** `/api/login`

```bash
curl -k -X POST https://localhost/api/login \
  -H "Content-Type: application/json" \
  -d '{"username":"user1","password":"Passw0rd!"}'
```

Respuesta típica:

```json
{"access_token":"<JWT>"}
```

---

### 3) Generar API Key (requiere JWT)

**POST** `/api/api-key`

```bash
curl -k -X POST https://localhost/api/api-key \
  -H "Authorization: Bearer <JWT>"
```

Respuesta:

```json
{"api_key":"<API_KEY>"}
```

---

### 4) Chat (leer)

**GET** `/api/chat`

Autenticación posible por:

* `X-API-KEY: <API_KEY>` (recomendado para el cliente)
* o `Authorization: Bearer <JWT>`

Ejemplo:

```bash
curl -k https://localhost/api/chat \
  -H "X-API-KEY: <API_KEY>"
```

---

### 5) Chat (crear mensaje)

**POST** `/api/chat`

```bash
curl -k -X POST https://localhost/api/chat \
  -H "X-API-KEY: <API_KEY>" \
  -H "Content-Type: application/json" \
  -d '{"content":"hola"}'
```

---

### 6) Admin: editar/borrar mensaje

> Requiere usuario con rol `admin`.

**PUT** `/api/chat/<id>`

```bash
curl -k -X PUT https://localhost/api/chat/1 \
  -H "Authorization: Bearer <JWT_ADMIN>" \
  -H "Content-Type: application/json" \
  -d '{"content":"editado"}'
```

**DELETE** `/api/chat/<id>`

```bash
curl -k -X DELETE https://localhost/api/chat/1 \
  -H "Authorization: Bearer <JWT_ADMIN>"
```

---

## Persistencia (DB) y logs en el host

Con Docker Compose se montan:

* `./volumes/data` → `/app/data` (SQLite)
* `./volumes/logs` → `/app/logs` (audit log)

Archivos resultantes típicos:

* `./volumes/data/pictochat.db`
* `./volumes/logs/audit.log`

---

## Tests de endpoints (fuera de Docker)

### Requisitos de tests

En `tests/requirements-dev.txt`:

```txt
pytest==8.4.2
requests==2.32.3
urllib3==2.5.0
```

### Ejecutar tests

Asumiendo que **ya levantaste** el servicio (por ejemplo con `docker compose up -d`):

```bash
tests/run_tests.sh
```

Variables útiles:

* `BASE_URL` (por defecto `https://localhost`)
* `HTTP_TIMEOUT` (por defecto `5`)

Ejemplo:

```bash
BASE_URL=https://localhost HTTP_TIMEOUT=10 tests/run_tests.sh
```

### Qué validan los tests

* Registro y login (incluye duplicados y credenciales inválidas)
* Acceso a `/api/chat` sin auth (debe fallar)
* API Key generation y uso
* Caso límite de `Content-Type` JSON con `charset`
* Permisos admin en edición/borrado
* Borrado de ID inexistente (esperable 404)

---

## Troubleshooting

### 1) Error 415 con `Content-Type: application/json; charset=utf-8`

Tu backend puede estar comparando el header de forma estricta. Lo correcto es validar `request.mimetype == 'application/json'`.

### 2) DELETE de id inexistente devuelve 500 en vez de 404

Suele pasar si un `get_or_404()` queda atrapado por un `except Exception` genérico. Solución: comprobar `if not msg: return 404` antes del try/except o manejar esa excepción de forma explícita.

### 3) Puerto 443 no abre

* En Linux, puertos <1024 pueden requerir permisos especiales según tu configuración.
* Si te falla, cambia en `.env`:

  * `HOST_HTTPS_PORT=8443`
  * Accede con `https://localhost:8443`

### 4) Warning de urllib3 en macOS (LibreSSL)

Es un warning habitual (no necesariamente rompe tests). Si quieres eliminarlo, usa una instalación de Python enlazada a OpenSSL o fija `urllib3<2` en dev.

### 5) Certificado HTTPS “adhoc”

Es para desarrollo. En producción, usa un reverse proxy (ej. Nginx/Caddy) con certificado válido.

---

## Contribuir / Pull Request

Flujo típico:

```bash
git checkout -b fix/mi-cambio
git add .
git commit -m "Describe el cambio"
git push -u origin fix/mi-cambio
```

Luego abre un PR en GitHub (o tu plataforma). Si no tienes permisos, haz un fork y crea el PR desde tu fork.

Herramientas útiles para probar la API:

* Postman

---

## Licencia

Este proyecto se distribuye bajo los términos definidos en el archivo `LICENSE`.

---

Si quieres, te lo adapto a tu repo exacto pegando:

1. tu `docker-compose.yml` final y
2. el bloque actual de configuración/env en `app.py` (donde lees `JWT_SECRET_KEY`, `DATABASE_URL` y logs).
