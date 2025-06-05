from fastapi import FastAPI, HTTPException, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import List, Optional
import shutil
import uuid
import os
import psycopg2
from psycopg2.extras import RealDictCursor

app = FastAPI()

# Configuración CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Base de datos
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://usuario:clave@host:puerto/db")

def get_db_connection():
    return psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)

@app.on_event("startup")
def startup():
    try:
        conn = get_db_connection()
        cur = conn.cursor()
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
        conn.commit()
    except Exception as e:
        print("Error al iniciar:", e)
    finally:
        cur.close()
        conn.close()

# Archivos estáticos
os.makedirs("static", exist_ok=True)
app.mount("/static", StaticFiles(directory="static"), name="static")

# Modelo
class Producto(BaseModel):
    id: str
    nombre: str
    descripcion: str
    precio: float
    imagen: str
    categoria: str

@app.get("/")
def home():
    return {"message": "API funcionando"}

@app.get("/productos")
def get_productos(categoria: Optional[str] = None):
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        if categoria:
            cur.execute("SELECT * FROM productos WHERE LOWER(categoria) = LOWER(%s)", (categoria,))
        else:
            cur.execute("SELECT * FROM productos")
        return cur.fetchall()
    finally:
        cur.close()
        conn.close()

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

    ruta_imagen = f"static/{id_producto}{ext}"
    with open(ruta_imagen, "wb") as buffer:
        shutil.copyfileobj(imagen.file, buffer)

    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute(
            "INSERT INTO productos (id, nombre, descripcion, precio, imagen, categoria) VALUES (%s, %s, %s, %s, %s, %s)",
            (id_producto, nombre, descripcion, precio, f"/static/{id_producto}{ext}", categoria.lower())
        )
        conn.commit()
        return {"mensaje": "Producto creado"}
    finally:
        cur.close()
        conn.close()
