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
from datetime import datetime

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
DATABASE_URL = "postgresql://backend_lr_user:qZVL67YuNu7UAtN1wLRNRKRpfufXlSHn@dpg-d0vnht0dl3ps73ft1no0-a/backend_lr"

def get_db_connection():
    return psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)

# Crear tablas si no existen
def init_db():
    conn = None
    cur = None
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
        print(f"Error al inicializar la base de datos: {str(e)}")
        raise
    finally:
        if cur: cur.close()
        if conn: conn.close()

init_db()

# Static
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

# Rutas
@app.get("/")
def home():
    return {"message": "API funcionando"}

@app.get("/productos")
def get_productos(categoria: Optional[str] = None):
    conn = None
    cur = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        if categoria:
            cur.execute("SELECT * FROM productos WHERE LOWER(categoria) = LOWER(%s)", (categoria,))
        else:
            cur.execute("SELECT * FROM productos")
        return cur.fetchall()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al obtener productos: {str(e)}")
    finally:
        if cur: cur.close()
        if conn: conn.close()

@app.post("/productos")
async def add_producto(
    nombre: str = Form(...),
    descripcion: str = Form(...),
    precio: float = Form(...),
    categoria: str = Form(...),
    imagen: UploadFile = File(...)
):
    conn = None
    cur = None
    try:
        if not imagen.filename:
            raise HTTPException(status_code=400, detail="Se requiere una imagen")

        id_producto = str(uuid.uuid4())
        file_extension = os.path.splitext(imagen.filename)[1].lower()
        if file_extension not in ['.jpg', '.jpeg', '.png', '.webp']:
            raise HTTPException(status_code=400, detail="Formato de imagen no soportado")

        ruta_imagen = f"static/{id_producto}{file_extension}"
        with open(ruta_imagen, "wb") as buffer:
            shutil.copyfileobj(imagen.file, buffer)

        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO productos (id, nombre, descripcion, precio, imagen, categoria) VALUES (%s, %s, %s, %s, %s, %s) RETURNING *",
            (id_producto, nombre, descripcion, precio, f"/static/{id_producto}{file_extension}", categoria.lower())
        )
        producto = cur.fetchone()
        conn.commit()
        return producto
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al agregar producto: {str(e)}")
    finally:
        if cur: cur.close()
        if conn: conn.close()

@app.put("/productos/{producto_id}")
async def update_producto(
    producto_id: str,
    nombre: str = Form(None),
    descripcion: str = Form(None),
    precio: float = Form(None),
    categoria: str = Form(None),
    imagen: UploadFile = File(None)
):
    conn = None
    cur = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT * FROM productos WHERE id = %s", (producto_id,))
        producto_existente = cur.fetchone()
        if not producto_existente:
            raise HTTPException(status_code=404, detail="Producto no encontrado")

        nombre = nombre or producto_existente['nombre']
        descripcion = descripcion or producto_existente['descripcion']
        precio = precio if precio is not None else producto_existente['precio']
        categoria = categoria or producto_existente['categoria']
        imagen_url = producto_existente['imagen']

        if imagen and imagen.filename:
            anterior_path = imagen_url.replace("/static/", "static/")
            if os.path.exists(anterior_path):
                os.remove(anterior_path)
            ext = os.path.splitext(imagen.filename)[1].lower()
            if ext not in ['.jpg', '.jpeg', '.png', '.webp']:
                raise HTTPException(status_code=400, detail="Formato de imagen no soportado")
            nueva_ruta = f"static/{producto_id}{ext}"
            with open(nueva_ruta, "wb") as buffer:
                shutil.copyfileobj(imagen.file, buffer)
            imagen_url = f"/static/{producto_id}{ext}"

        cur.execute(
            "UPDATE productos SET nombre=%s, descripcion=%s, precio=%s, imagen=%s, categoria=%s WHERE id=%s RETURNING *",
            (nombre, descripcion, precio, imagen_url, categoria.lower(), producto_id)
        )
        producto_actualizado = cur.fetchone()
        conn.commit()
        return producto_actualizado
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al actualizar producto: {str(e)}")
    finally:
        if cur: cur.close()
        if conn: conn.close()

@app.delete("/productos/{producto_id}")
def delete_producto(producto_id: str):
    conn = None
    cur = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT * FROM productos WHERE id = %s", (producto_id,))
        producto = cur.fetchone()
        if not producto:
            raise HTTPException(status_code=404, detail="Producto no encontrado")
        img_path = producto['imagen'].replace("/static/", "static/")
        if os.path.exists(img_path):
            os.remove(img_path)
        cur.execute("DELETE FROM productos WHERE id = %s", (producto_id,))
        conn.commit()
        return {"mensaje": "Producto eliminado"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if cur: cur.close()
        if conn: conn.close()
