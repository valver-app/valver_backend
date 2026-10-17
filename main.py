from fastapi import FastAPI, HTTPException, File, UploadFile, Header
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import os
import shutil
import json
import psycopg2
from urllib.parse import urlparse
import bcrypt

app = FastAPI(title="Valver Cloud API")

# Clave secreta obtenida desde las variables de Railway (con respaldo seguro)
API_KEY_SECRET = os.environ.get("VALVER_API_KEY", "ValverSecretKey_2026_Secure!")

# Credenciales maestras obtenidas desde variables de entorno
PASS_VALVER_MASTER = os.environ.get("MASTER_VALVER_PASS", "Vemeds237.")
PASS_PRUEBAS_MASTER = os.environ.get("MASTER_PRUEBAS_PASS", "Vemeds236.")

# Carpeta pública para alojar los informes escaneables
CARPETA_INFORMES = "informes_publicos"
os.makedirs(CARPETA_INFORMES, exist_ok=True)
app.mount("/informes", StaticFiles(directory=CARPETA_INFORMES), name="informes")

# Obtener la URL de PostgreSQL desde las variables de entorno de Railway
DATABASE_URL = os.environ.get("DATABASE_URL")

def obtener_conexion():
    if not DATABASE_URL:
        return None
    try:
        url = urlparse(DATABASE_URL)
        conn = psycopg2.connect(
            database=url.path[1:],
            user=url.username,
            password=url.password,
            host=url.hostname,
            port=url.port
        )
        return conn
    except Exception as e:
        print("Error conectando a PostgreSQL:", e)
        return None

# Inicializar tabla en PostgreSQL si está disponible
def inicializar_db():
    conn = obtener_conexion()
    if conn:
        try:
            cur = conn.cursor()
            cur.execute("""
                CREATE TABLE IF NOT EXISTS profesionales (
                    rif_cedula VARCHAR(50) PRIMARY KEY,
                    data JSONB
                )
            """)
            conn.commit()
            cur.close()
            conn.close()
            print("Base de datos PostgreSQL inicializada correctamente.")
        except Exception as e:
            print("Error al crear tabla en PostgreSQL:", e)

inicializar_db()

# Archivo de respaldo local por seguridad
DB_CLOUD_FILE = "servidor_nube.json"

def cargar_db():
    conn = obtener_conexion()
    if conn:
        try:
            cur = conn.cursor()
            cur.execute("SELECT rif_cedula, data FROM profesionales")
            rows = cur.fetchall()
            cur.close()
            conn.close()
            db = {}
            for rif_cedula, data in rows:
                db[rif_cedula] = data
            return db
        except Exception as e:
            print("Error leyendo de PostgreSQL, usando respaldo:", e)
    
    # Respaldo en archivo si no hay conexión SQL
    if os.path.exists(DB_CLOUD_FILE):
        try:
            with open(DB_CLOUD_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except:
            return {}
    return {}

def guardar_en_db(rif_cedula, datos_dict):
    conn = obtener_conexion()
    if conn:
        try:
            cur = conn.cursor()
            cur.execute("""
                INSERT INTO profesionales (rif_cedula, data) VALUES (%s, %s)
                ON CONFLICT (rif_cedula) DO UPDATE SET data = EXCLUDED.data
            """, (rif_cedula, json.dumps(datos_dict)))
            conn.commit()
            cur.close()
            conn.close()
            return True
        except Exception as e:
            print("Error guardando en PostgreSQL:", e)
    
    # Respaldo en archivo local
    db = {}
    if os.path.exists(DB_CLOUD_FILE):
        try:
            with open(DB_CLOUD_FILE, "r", encoding="utf-8") as f:
                db = json.load(f)
        except:
            pass
    db[rif_cedula] = datos_dict
    with open(DB_CLOUD_FILE, "w", encoding="utf-8") as f:
        json.dump(db, f, ensure_ascii=False, indent=4)
    return True

# Funciones de cifrado y verificación de contraseñas
def hashear_password(password: str) -> str:
    salt = bcrypt.gensalt(rounds=12)
    return bcrypt.hashpw(password.encode("utf-8"), salt).decode("utf-8")

def verificar_password(password_plana: str, password_almacenada: str) -> bool:
    try:
        # Si ya está hasheada con bcrypt (empieza por $2b$ o $2a$)
        if password_almacenada.startswith("$2b$") or password_almacenada.startswith("$2a$"):
            return bcrypt.checkpw(password_plana.encode("utf-8"), password_almacenada.encode("utf-8"))
        # Retrocompatibilidad con contraseñas que estaban en texto plano
        return password_plana == password_almacenada
    except Exception:
        return False

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

class EstadoModel(BaseModel):
    estado_suscripcion: str

@app.get("/")
def home():
    return {"estado": "¡El servidor de Farmacia Valver en la nube con PostgreSQL está activo y operando con éxito! 🚀"}

# Endpoint blindado para subida de informes
@app.post("/subir-informe")
async def subir_informe(
    archivo: UploadFile = File(...),
    x_valver_token: str = Header(None)
):
    # 1. Validar Token Secreto
    if x_valver_token != API_KEY_SECRET:
        raise HTTPException(status_code=401, detail="Acceso denegado: Token de autorización inválido.")

    # 2. Validar extensión permitida
    nombre_seguro = os.path.basename(archivo.filename)
    extension = os.path.splitext(nombre_seguro)[1].lower()
    if extension not in [".png", ".jpg", ".jpeg"]:
        raise HTTPException(status_code=400, detail="Formato no permitido. Solo imágenes PNG o JPG.")

    # 3. Validar tipo MIME
    if archivo.content_type not in ["image/png", "image/jpeg", "image/jpg"]:
        raise HTTPException(status_code=400, detail="Tipo de contenido no válido.")

    # 4. Validar tamaño máximo (5 MB)
    contenido = await archivo.read()
    if len(contenido) > 5 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="El archivo excede el límite de 5 MB.")

    # 5. Guardar archivo
    try:
        ruta_guardado = os.path.join(CARPETA_INFORMES, nombre_seguro)
        with open(ruta_guardado, "wb") as buffer:
            buffer.write(contenido)

        url_publica = f"https://valverbackend-production.up.railway.app/informes/{nombre_seguro}"
        return {"exito": True, "url": url_publica}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error interno guardando informe: {str(e)}")

@app.get("/profesionales/listar")
def listar_profesionales():
    try:
        db = cargar_db()
        return {"exito": True, "profesionales": db}
    except Exception as e:
        return {"exito": False, "profesionales": {}, "msg": str(e)}

@app.put("/profesionales/estado/{rif_cedula}")
def actualizar_estado(rif_cedula: str, datos: EstadoModel):
    db = cargar_db()
    if rif_cedula not in db:
        return {"exito": False, "msg": "Profesional no encontrado."}
    
    db[rif_cedula]["estado_suscripcion"] = datos.estado_suscripcion
    guardar_en_db(rif_cedula, db[rif_cedula])
    return {"exito": True, "msg": "Estado de suscripción actualizado correctamente."}

@app.post("/auth/login")
def login(datos: LoginModel):
    db = cargar_db()
    identificador = datos.identificador.strip().lower()
    
    # 1. Cuentas maestras protegidas con variables de entorno
    if identificador == "valver" and datos.password == PASS_VALVER_MASTER:
        return {"exito": True, "usuario": {"rol": "admin", "empresa": "Farmacia Valver (Master)", "rif_cedula": "MASTER_VALVER", "correo": "admin@valver.com"}, "msg": "Master Ok."}
    if identificador == "pruebas" and datos.password == PASS_PRUEBAS_MASTER:
        return {"exito": True, "usuario": {"rol": "pruebas", "empresa": "Laboratorio Valver", "rif_cedula": "PRUEBAS_VALVER", "correo": "pruebas@valver.com"}, "msg": "Pruebas Ok."}

    # 2. Cuentas de profesionales
    for doc_id, usuario in db.items():
        if doc_id.lower() == identificador or usuario.get("correo", "").lower() == identificador:
            pass_almacenada = usuario.get("password", "")
            if verificar_password(datos.password, pass_almacenada):
                if usuario.get("estado_suscripcion", "activo") != "activo":
                    return {"exito": False, "usuario": None, "msg": "Acceso suspendido por falta de pago."}
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
    
    nuevo_datos = datos.dict()
    # Guardar contraseña hasheada irreversiblemente
    nuevo_datos["password"] = hashear_password(datos.password)
    nuevo_datos["estado_suscripcion"] = "activo"
    guardar_en_db(doc_id, nuevo_datos)
    return {"exito": True, "msg": "Registro exitoso en la base de datos de la nube."}
