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

# Configuración de la base de datos PostgreSQL
DATABASE_URL = "postgresql://usuario:contraseña@host:5432/nombre_bd"  # Reemplaza con tus credenciales de Render

def get_db_connection():
    conn = psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)
    return conn

# Crear tablas si no existen
def init_db():
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
    cur.close()
    conn.close()

# Inicializar la base de datos al iniciar
init_db()

# Servir archivos estáticos
os.makedirs("static", exist_ok=True)
app.mount("/static", StaticFiles(directory="static"), name="static")

# Modelo de Producto
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
    
    if categoria:
        cur.execute("SELECT * FROM productos WHERE LOWER(categoria) = LOWER(%s)", (categoria,))
    else:
        cur.execute("SELECT * FROM productos")
    
    productos = cur.fetchall()
    cur.close()
    conn.close()
    
    return productos

@app.post("/productos")
async def add_producto(
    nombre: str = Form(...),
    descripcion: str = Form(...),
    precio: float = Form(...),
    categoria: str = Form(...),
    imagen: UploadFile = File(...)
):
    try:
        # Validaciones básicas
        if not imagen.filename:
            raise HTTPException(status_code=400, detail="Se requiere una imagen")
        
        # Generar ID único
        id_producto = str(uuid.uuid4())
        
        # Procesar imagen
        file_extension = os.path.splitext(imagen.filename)[1]
        if file_extension.lower() not in ['.jpg', '.jpeg', '.png', '.webp']:
            raise HTTPException(status_code=400, detail="Formato de imagen no soportado")
        
        ruta_imagen = f"static/{id_producto}{file_extension}"
        
        with open(ruta_imagen, "wb") as buffer:
            shutil.copyfileobj(imagen.file, buffer)

        # Guardar en PostgreSQL
        conn = get_db_connection()
        cur = conn.cursor()
        
        cur.execute(
            "INSERT INTO productos (id, nombre, descripcion, precio, imagen, categoria) VALUES (%s, %s, %s, %s, %s, %s) RETURNING *",
            (id_producto, nombre, descripcion, precio, f"/static/{id_producto}{file_extension}", categoria.lower())
        
        producto = cur.fetchone()
        conn.commit()
        cur.close()
        conn.close()
        
        return producto
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al agregar producto: {str(e)}")

@app.put("/productos/{producto_id}")
async def update_producto(
    producto_id: str,
    nombre: str = Form(None),
    descripcion: str = Form(None),
    precio: float = Form(None),
    categoria: str = Form(None),
    imagen: UploadFile = File(None)
):
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        # Obtener producto existente
        cur.execute("SELECT * FROM productos WHERE id = %s", (producto_id,))
        producto_existente = cur.fetchone()
        
        if not producto_existente:
            raise HTTPException(status_code=404, detail="Producto no encontrado")

        # Mantener valores anteriores si no se proporcionan nuevos
        nombre = nombre if nombre is not None else producto_existente['nombre']
        descripcion = descripcion if descripcion is not None else producto_existente['descripcion']
        precio = precio if precio is not None else producto_existente['precio']
        categoria = categoria if categoria is not None else producto_existente['categoria']
        
        # Manejo de imagen
        imagen_url = producto_existente['imagen']
        if imagen and imagen.filename:
            # Eliminar imagen anterior si existe
            imagen_path = producto_existente['imagen'].replace("/static/", "static/")
            if os.path.exists(imagen_path):
                os.remove(imagen_path)
            
            # Guardar nueva imagen
            file_extension = os.path.splitext(imagen.filename)[1]
            nueva_ruta = f"static/{producto_id}{file_extension}"
            with open(nueva_ruta, "wb") as buffer:
                shutil.copyfileobj(imagen.file, buffer)
            imagen_url = f"/static/{producto_id}{file_extension}"

        # Actualizar en la base de datos
        cur.execute(
            """UPDATE productos 
            SET nombre = %s, descripcion = %s, precio = %s, imagen = %s, categoria = %s 
            WHERE id = %s RETURNING *""",
            (nombre, descripcion, precio, imagen_url, categoria.lower(), producto_id)
        )
        
        producto_actualizado = cur.fetchone()
        conn.commit()
        cur.close()
        conn.close()
        
        return producto_actualizado

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al actualizar producto: {str(e)}")

@app.delete("/productos/{producto_id}")
def delete_producto(producto_id: str):
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        # Obtener producto para eliminar la imagen
        cur.execute("SELECT * FROM productos WHERE id = %s", (producto_id,))
        producto = cur.fetchone()
        
        if not producto:
            raise HTTPException(status_code=404, detail="Producto no encontrado")
        
        # Eliminar imagen asociada
        if os.path.exists(producto['imagen'].replace("/static/", "static/")):
            os.remove(producto['imagen'].replace("/static/", "static/"))
        
        # Eliminar de la base de datos
        cur.execute("DELETE FROM productos WHERE id = %s", (producto_id,))
        conn.commit()
        cur.close()
        conn.close()
        
        return {"mensaje": "Producto eliminado"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))