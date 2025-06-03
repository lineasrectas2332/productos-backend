from fastapi import FastAPI, HTTPException, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import List, Optional
import shutil
import uuid
import os

app = FastAPI()

# Configuración CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

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
    categoria: str  # Cambiado de Enum a str para mayor flexibilidad

# Base de datos en memoria
productos: List[Producto] = []

@app.get("/")
def home():
    return {"message": "API funcionando"}

@app.get("/productos")
def get_productos(categoria: Optional[str] = None):
    if categoria:
        return [p for p in productos if p.categoria.lower() == categoria.lower()]
    return productos

@app.post("/productos")  # Corregido: era "/productos" no "/productos"
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

        # Crear producto
        producto = Producto(
            id=id_producto,
            nombre=nombre,
            descripcion=descripcion,
            precio=precio,
            imagen=f"/static/{id_producto}{file_extension}",
            categoria=categoria.lower()
        )
        
        productos.append(producto)
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
        producto_existente = next((p for p in productos if p.id == producto_id), None)
        if not producto_existente:
            raise HTTPException(status_code=404, detail="Producto no encontrado")

        # Mantener valores anteriores si no se proporcionan nuevos
        nombre = nombre if nombre is not None else producto_existente.nombre
        descripcion = descripcion if descripcion is not None else producto_existente.descripcion
        precio = precio if precio is not None else producto_existente.precio
        categoria = categoria if categoria is not None else producto_existente.categoria
        
        # Manejo de imagen
        imagen_url = producto_existente.imagen
        if imagen and imagen.filename:
            # Eliminar imagen anterior si existe
            imagen_path = producto_existente.imagen.replace("/static/", "static/")
            if os.path.exists(imagen_path):
                os.remove(imagen_path)
            
            # Guardar nueva imagen
            file_extension = os.path.splitext(imagen.filename)[1]
            nueva_ruta = f"static/{producto_id}{file_extension}"
            with open(nueva_ruta, "wb") as buffer:
                shutil.copyfileobj(imagen.file, buffer)
            imagen_url = f"/static/{producto_id}{file_extension}"

        # Actualizar producto
        producto_actualizado = Producto(
            id=producto_id,
            nombre=nombre,
            descripcion=descripcion,
            precio=precio,
            imagen=imagen_url,
            categoria=categoria.lower()
        )

        index = productos.index(producto_existente)
        productos[index] = producto_actualizado
        return producto_actualizado

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al actualizar producto: {str(e)}")

@app.delete("/productos/{producto_id}")
def delete_producto(producto_id: str):
    try:
        global productos
        producto = next((p for p in productos if p.id == producto_id), None)
        if not producto:
            raise HTTPException(status_code=404, detail="Producto no encontrado")
        
        # Eliminar imagen asociada
        if os.path.exists(producto.imagen.replace("/static/", "static/")):
            os.remove(producto.imagen.replace("/static/", "static/"))
        
        productos = [p for p in productos if p.id != producto_id]
        return {"mensaje": "Producto eliminado"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))