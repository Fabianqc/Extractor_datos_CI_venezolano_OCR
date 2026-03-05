from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import os
import shutil
import uuid
import easyocr
import identificadorCI

app = FastAPI(title="Document OCR API", description="API para extraer datos de Cédulas y Pasaportes venezolanos")

# Configurar CORS (ajustar según el origen de tu NestJS)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Cargar el modelo UNA SOLA VEZ al iniciar
print("[API] Cargando motor de IA en memoria...")
reader = easyocr.Reader(['es', 'en'], gpu=True)
print("[API] Motor listo.")

@app.get("/health")
def health_check():
    return {"status": "ok"}

@app.post("/procesar-documento")
async def procesar_documento_api(file: UploadFile = File(...)):
    # Validar que sea una imagen (manejar caso None)
    ctype = file.content_type or ""
    if not ctype.startswith("image/"):
        raise HTTPException(status_code=400, detail="El archivo enviado debe ser una imagen.")

    # Crear un nombre temporal para el archivo
    temp_filename = f"temp_{uuid.uuid4()}.jpg"
    temp_path = os.path.join("tmp", temp_filename)
    
    # Asegurar que la carpeta tmp exista
    os.makedirs("tmp", exist_ok=True)

    try:
        # Guardar el archivo subido
        with open(temp_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        
        # Procesar con nuestra lógica optimizada
        print(f"[API] Procesando archivo: {file.filename}")
        datos = identificadorCI.extraer_datos_cedula(temp_path, lector=reader)
        
        return {
            "success": True,
            "filename": file.filename,
            "data": datos
        }
    
    except Exception as e:
        print(f"[API] ERROR: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
    
    finally:
        # Limpiar el archivo temporal
        if os.path.exists(temp_path):
            os.remove(temp_path)

if __name__ == "__main__":
    import uvicorn
    # Correr el servidor
    uvicorn.run(app, host="0.0.0.0", port=8000)
