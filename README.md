## Despliegue en Render

Este proyecto está preparado para desplegarse en Render usando:

- `render.yaml` (Blueprint)
- `wsgi.py` (entrada WSGI)
- `requirements.txt` (dependencias)
- `DATABASE_URL` y `SECRET_KEY` por variables de entorno

### 1) Subir el repo a GitHub

Render despliega desde GitHub. Sube este proyecto a un repositorio.

### 2) Crear el Blueprint en Render

En Render:

- New -> **Blueprint**
- Selecciona tu repo
- Render detectará `render.yaml` y creará:
  - Un **Web Service** (`sistema-factura`)
  - Una **PostgreSQL DB** (`sistema-factura-db`)

### 3) Crear tablas (solo primera vez)

Este proyecto no incluye carpeta `migrations/`. Para el primer despliegue:

- En el Web Service, agrega temporalmente la env var:
  - `AUTO_CREATE_DB=1`
- Haz **Deploy** nuevamente.
- Cuando ya existan las tablas, puedes **quitar** `AUTO_CREATE_DB` (para evitar crear en cada arranque).

### 4) Crear/actualizar admin

En Render, abre la consola del servicio (Shell) y ejecuta:

```bash
python crear_admin.py
```

Variables opcionales:

- `ADMIN_USERNAME` (default: `admin`)
- `ADMIN_PASSWORD` (default: `12345`)

### 5) Notas importantes

- **Imágenes subidas**: Render no garantiza persistencia del filesystem entre deploys en plan free.
  - Si quieres persistencia real para `static/uploads`, lo ideal es usar un disco persistente o almacenamiento externo (S3, etc.).

