from fastapi import FastAPI, HTTPException, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi_cache import FastAPICache
from fastapi_cache.backends.redis import RedisBackend
from fastapi_cache.decorator import cache
from pydantic import BaseModel
from typing import List, Optional
import shutil
import uuid
import os
import psycopg2
from psycopg2.extras import RealDictCursor
from PIL import Image  # Para optimización de imágenes
import io
from redis import asyncio as aioredis

app = FastAPI()

# Configuración CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configuración Redis para caché (usar Redis gratis en Render o Upstash)
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")

@app.on_event("startup")
async def startup():
    # Configurar caché Redis
    redis = aioredis.from_url(REDIS_URL)
    FastAPICache.init(RedisBackend(redis), prefix="fastapi-cache")
    
    # Configurar índices en la base de datos
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("""
            CREATE TABLE IF NOT EXISTS productos (
                id VARCHAR(36) PRIMARY KEY,
                nombre VARCHAR(100) NOT NULL,
                descripcion TEXT NOT NULL,
                precio DECIMAL(10, 2) NOT NULL,
                imagen VARCHAR(255) NOT NULL,
                categoria VARCHAR(20) NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        # Crear índices para mejorar consultas
        cur.execute("CREATE INDEX IF NOT EXISTS idx_productos_categoria ON productos(categoria)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_productos_created_at ON productos(created_at)")
        conn.commit()
    except Exception as e:
        print("Error al iniciar:", e)
    finally:
        cur.close()
        conn.close()

# Conexión a la base de datos con pool de conexiones
from psycopg2.pool import SimpleConnectionPool

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://usuario:clave@host:puerto/db")
connection_pool = SimpleConnectionPool(
    minconn=1,
    maxconn=10,
    dsn=DATABASE_URL,
    cursor_factory=RealDictCursor
)

def get_db_connection():
    return connection_pool.getconn()

def release_db_connection(conn):
    connection_pool.putconn(conn)

# Optimizar imágenes antes de guardar
async def optimize_image(file: UploadFile):
    # Leer imagen original
    image = Image.open(io.BytesIO(await file.read()))
    
    # Convertir a modo RGB si es RGBA
    if image.mode == 'RGBA':
        image = image.convert('RGB')
    
    # Redimensionar si es muy grande (máx 1200px en el lado más largo)
    max_size = 1200
    if max(image.size) > max_size:
        ratio = max_size / max(image.size)
        new_size = (int(image.size[0] * ratio), int(image.size[1] * ratio))
        image = image.resize(new_size, Image.Resampling.LANCZOS)
    
    # Optimizar calidad (80%)
    output = io.BytesIO()
    image.save(output, format='JPEG', quality=80, optimize=True)
    output.seek(0)
    
    return output

# Endpoints con caché
@app.get("/productos")
@cache(expire=30)  # Cachear por 30 segundos
def get_productos(categoria: Optional[str] = None):
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        if categoria:
            cur.execute("SELECT * FROM productos WHERE LOWER(categoria) = LOWER(%s) ORDER BY created_at DESC", (categoria,))
        else:
            cur.execute("SELECT * FROM productos ORDER BY created_at DESC")
        return cur.fetchall()
    finally:
        cur.close()
        release_db_connection(conn)

@app.post("/productos")
async def add_producto(
    nombre: str = Form(...),
    descripcion: str = Form(...),
    precio: float = Form(...),
    categoria: str = Form(...),
    imagen: UploadFile = File(...)
):
    if not imagen.filename:
        raise HTTPException(status_code=400, detail="Se requiere una imagen")

    id_producto = str(uuid.uuid4())
    ext = os.path.splitext(imagen.filename)[1].lower()
    if ext not in ['.jpg', '.jpeg', '.png', '.webp']:
        raise HTTPException(status_code=400, detail="Formato de imagen no soportado")

    # Optimizar imagen antes de guardar
    optimized_image = await optimize_image(imagen)
    ruta_imagen = f"static/{id_producto}.jpg"  # Siempre guardamos como JPG optimizado
    
    with open(ruta_imagen, "wb") as buffer:
        buffer.write(optimized_image.getvalue())

    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute(
            "INSERT INTO productos (id, nombre, descripcion, precio, imagen, categoria) VALUES (%s, %s, %s, %s, %s, %s)",
            (id_producto, nombre, descripcion, precio, f"/static/{id_producto}.jpg", categoria.lower())
        )
        conn.commit()
        
        # Invalidar caché después de agregar nuevo producto
        await FastAPICache.clear(namespace="productos")
        
        return {"mensaje": "Producto creado"}
    finally:
        cur.close()
        release_db_connection(conn)