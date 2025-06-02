from fastapi import FastAPI, HTTPException, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from enum import Enum
from typing import List
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

# Enumeración de categorías
class Categoria(str, Enum):
    LIVING = "living"
    DORMITORIO = "dormitorio"
    COMEDOR = "comedor"

# Modelo de Producto
class Producto(BaseModel):
    id: str
    nombre: str
    descripcion: str
    precio: float
    imagen: str
    categoria: Categoria  # Nuevo campo

# Base de datos en memoria
productos: List[Producto] = []

@app.get("/")
def home():
    return {"message": "API funcionando"}

@app.get("/productos")
def get_productos(categoria: str = None):
    if categoria:
        return [p for p in productos if p.categoria == categoria]
    return productos

@app.post("/productos")
async def add_producto(
    nombre: str = Form(...),
    descripcion: str = Form(...),
    precio: float = Form(...),
    categoria: Categoria = Form(...),  # Nuevo campo
    imagen: UploadFile = File(...)
):
    try:
        # Generar ID único
        id_producto = str(uuid.uuid4())
        
        # Guardar imagen
        file_extension = os.path.splitext(imagen.filename)[1]
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
            categoria=categoria
        )
        
        productos.append(producto)
        return producto
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.put("/productos/{producto_id}")
def update_producto(producto_id: str, producto_editado: Producto):
    for i, p in enumerate(productos):
        if p.id == producto_id:
            # Mantener la misma imagen si no se proporciona una nueva
            if not producto_editado.imagen:
                producto_editado.imagen = p.imagen
            productos[i] = producto_editado
            return producto_editado
    raise HTTPException(status_code=404, detail="Producto no encontrado")

@app.delete("/productos/{producto_id}")
def delete_producto(producto_id: str):
    global productos
    productos = [p for p in productos if p.id != producto_id]
    return {"mensaje": "Producto eliminado"}