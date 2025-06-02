from fastapi import FastAPI, HTTPException, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
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

# Modelo Pydantic
class Producto(BaseModel):
    id: str
    nombre: str
    descripcion: str
    precio: float
    imagen: str

# Base de datos en memoria
productos: List[Producto] = []

# Crear directorio static si no existe
os.makedirs("static", exist_ok=True)

# Ruta raíz
@app.get("/")
def home():
    return {"message": "API funcionando"}

# Obtener todos los productos
@app.get("/productos")
def get_productos():
    return productos

# Añadir nuevo producto
@app.post("/productos")
async def add_producto(
    nombre: str = Form(...),
    descripcion: str = Form(...),
    precio: float = Form(...),
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
            imagen=ruta_imagen
        )
        
        productos.append(producto)
        return producto
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# Actualizar producto
@app.put("/productos/{producto_id}")
def update_producto(producto_id: str, producto_editado: Producto):
    for i, p in enumerate(productos):
        if p.id == producto_id:
            productos[i] = producto_editado
            return producto_editado
    raise HTTPException(status_code=404, detail="Producto no encontrado")

# Eliminar producto
@app.delete("/productos/{producto_id}")
def delete_producto(producto_id: str):
    global productos
    productos = [p for p in productos if p.id != producto_id]
    return {"mensaje": "Producto eliminado"}