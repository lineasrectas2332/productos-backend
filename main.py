from fastapi import FastAPI, HTTPException, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import List
import shutil
import uuid
import os

app = FastAPI()

# Configuración CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Mejor poner tu dominio frontend en producción
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Servir archivos estáticos
os.makedirs("static", exist_ok=True)
app.mount("/static", StaticFiles(directory="static"), name="static")

# Modelo
class Producto(BaseModel):
    id: str
    nombre: str
    descripcion: str
    precio: float
    imagen: str

productos: List[Producto] = []

@app.get("/")
def home():
    return {"message": "API funcionando"}

@app.get("/productos")
def get_productos():
    return productos

@app.post("/productos")
async def add_producto(
    nombre: str = Form(...),
    descripcion: str = Form(...),
    precio: float = Form(...),
    imagen: UploadFile = File(...)
):
    id_producto = str(uuid.uuid4())
    extension = os.path.splitext(imagen.filename)[1]
    ruta_archivo = f"static/{id_producto}{extension}"

    with open(ruta_archivo, "wb") as buffer:
        shutil.copyfileobj(imagen.file, buffer)

    producto = Producto(
        id=id_producto,
        nombre=nombre,
        descripcion=descripcion,
        precio=precio,
        imagen=f"/static/{id_producto}{extension}"
    )

    productos.append(producto)
    return producto

@app.put("/productos/{producto_id}")
def update_producto(producto_id: str, producto_editado: Producto):
    for i, p in enumerate(productos):
        if p.id == producto_id:
            productos[i] = producto_editado
            return producto_editado
    raise HTTPException(status_code=404, detail="Producto no encontrado")

@app.delete("/productos/{producto_id}")
def delete_producto(producto_id: str):
    global productos
    productos = [p for p in productos if p.id != producto_id]
    return {"mensaje": "Producto eliminado"}
