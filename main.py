from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import os
import json

app = FastAPI(title="Valver Cloud API")

# Archivo temporal de respaldo en la nube si aún no conectamos base de datos fija
DB_CLOUD_FILE = "servidor_nube.json"

def cargar_db():
    if os.path.exists(DB_CLOUD_FILE):
        try:
            with open(DB_CLOUD_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except:
            return {}
    return {}

def guardar_db(db):
    with open(DB_CLOUD_FILE, "w", encoding="utf-8") as f:
        json.dump(db, f, ensure_ascii=False, indent=4)

class ProfesionalModel(BaseModel):
    nombres: str
    apellidos: str
    empresa: str
    rif_cedula: str
    telefono1: str
    telefono2: str = ""
    correo: str
    direccion: str
    password: str
    logo: str = ""

class LoginModel(BaseModel):
    identificador: str
    password: str

@app.get("/")
def home():
    return {"estado": "¡El servidor de Farmacia Valver en la nube está activo y operando con éxito! 🚀"}

@app.post("/auth/login")
def login(datos: LoginModel):
    db = cargar_db()
    identificador = datos.identificador.strip().lower()
    
    # Cuentas maestras del sistema
    if identificador == "valver" and datos.password == "Vemeds237.":
        return {"exito": True, "usuario": {"rol": "admin", "empresa": "Farmacia Valver (Master)", "rif_cedula": "MASTER_VALVER", "correo": "admin@valver.com"}, "msg": "Master Ok."}
    if identificador == "pruebas" and datos.password == "Vemeds236.":
        return {"exito": True, "usuario": {"rol": "pruebas", "empresa": "Laboratorio Valver", "rif_cedula": "PRUEBAS_VALVER", "correo": "pruebas@valver.com"}, "msg": "Pruebas Ok."}

    for doc_id, usuario in db.items():
        if doc_id.lower() == identificador or usuario.get("correo", "").lower() == identificador:
            if usuario.get("password") == datos.password:
                if usuario.get("estado_suscripcion", "activo") != "activo":
                    return {"exito": False, "usuario": None, "msg": "Acceso suspendido."}
                usuario_resp = usuario.copy()
                usuario_resp["rol"] = "profesional"
                return {"exito": True, "usuario": usuario_resp, "msg": "Autenticación exitosa."}
            return {"exito": False, "usuario": None, "msg": "Contraseña incorrecta."}
    return {"exito": False, "usuario": None, "msg": "Usuario no existe."}

@app.post("/profesionales/registrar")
def registrar(datos: ProfesionalModel):
    db = cargar_db()
    doc_id = datos.rif_cedula.strip()
    if doc_id in db:
        return {"exito": False, "msg": "Cédula o RIF ya registrado."}
    
    db[doc_id] = datos.dict()
    db[doc_id]["estado_suscripcion"] = "activo"
    guardar_db(db)
    return {"exito": True, "msg": "Registro exitoso."}