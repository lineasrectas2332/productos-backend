from fastapi import FastAPI, HTTPException, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List
import shutil
import uuid
import os

app = FastAPI()

# Permitir acceso desde tu frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # En producción usá el dominio exacto
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class Producto(BaseModel):
    id: str
    nombre: str
    descripcion: str
    precio: float
    imagen: str  # Ruta a la imagen

productos: List[Producto] = []

@app.get("/productos")
def get_productos():
    return productos

@app.post("/productos")
def add_producto(nombre: str, descripcion: str, precio: float, imagen: UploadFile = File(...)):
    id_producto = str(uuid.uuid4())
    ruta = f"static/{id_producto}.jpg"
    with open(ruta, "wb") as buffer:
        shutil.copyfileobj(imagen.file, buffer)
    producto = Producto(id=id_producto, nombre=nombre, descripcion=descripcion, precio=precio, imagen=ruta)
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
