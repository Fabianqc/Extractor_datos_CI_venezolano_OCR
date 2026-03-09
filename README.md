# 🇻🇪 OCR de Cédulas y Pasaportes Venezolanos (SAIME)

![Python](https://img.shields.io/badge/Python-3.8+-blue.svg)
![OpenCV](https://img.shields.io/badge/OpenCV-4.x-green.svg)
![EasyOCR](https://img.shields.io/badge/EasyOCR-Ready-orange.svg)
![FastAPI](https://img.shields.io/badge/API-Ready-brightgreen.svg)

Un pipeline de Visión Computacional e Inteligencia Artificial diseñado específicamente para extraer datos estructurados de Cédulas de Identidad y Pasaportes venezolanos a partir de fotografías tomadas por usuarios. 

Este sistema está optimizado para lidiar con los ruidos visuales típicos de los documentos del SAIME (marcas de agua, texturas de fondo, variaciones de impresión y firmas superpuestas) garantizando datos limpios y listos para bases de datos (KYC).

## ✨ Características Principales

* **Auto-Escáner (Warp Perspective):** Detecta automáticamente los bordes del documento en la fotografía y aplica una transformación de perspectiva geométrica para aplanarlo, emulando el efecto de aplicaciones como *CamScanner*.
* **Extracción por ROIs (Zonas Seguras):** Aísla matemáticamente la región izquierda de la cédula para evitar que el OCR intente leer la fotografía del titular, la huella dactilar o el código de estado, reduciendo el tiempo de procesamiento a la mitad.
* **Filtro "Anti-Directores":** Incluye una lista negra dinámica (`BLACKLIST_EXACT`) con los nombres de los directores históricos del SAIME (Dugarte, Vizcaíno, etc.) para evitar el falso positivo más común en OCRs genéricos.
* **Preprocesamiento en "Esteroides":** Aplica redimensionamiento cúbico (x2), conversión a escala de grises y un filtro *Unsharp Mask* (Nitidez) para resaltar el texto impreso frente al fondo de seguridad antes de pasarlo a la red neuronal.
* **Lógica de Fallback Posicional:** Si las etiquetas rojas ("NOMBRES", "APELLIDOS") son ilegibles, el sistema utiliza el número de cédula como ancla espacial para deducir los datos mediante índices de posición.
* **Validación Estricta (API-Ready):** Diseñado para funcionar como microservicio. Evalúa la completitud de los datos y levanta excepciones manejables (`HTTP 400 Bad Request`) si la imagen es demasiado deficiente, evitando inyección de datos nulos.

## 🛠️ Tecnologías Utilizadas

* **Python:** Lenguaje principal.
* **OpenCV (`cv2`):** Procesamiento de imágenes, detección de bordes (Canny), umbralización adaptativa (Adaptive Thresholding) y transformaciones geométricas.
* **EasyOCR:** Motor de Inteligencia Artificial (CRAFT + CRNN) para el reconocimiento óptico de caracteres, con soporte nativo para aceleración por GPU.
* **NumPy:** Cálculos matriciales para reordenar coordenadas espaciales.
* **Regex (`re`):** Limpieza estricta de cadenas de texto y formateo numérico.

## 🚀 Instalación

1. Clona este repositorio:
   ```bash
   git clone [https://github.com/tu-usuario/ocr-cedulas-venezuela.git](https://github.com/tu-usuario/ocr-cedulas-venezuela.git)
   cd ocr-cedulas-venezuela

 2.Crea un entorno virtual e instala las dependencias:
 
     python -m venv venv
    source venv/bin/activate  # En Windows: venv\Scripts\activate
    pip install opencv-python easyocr numpy

  Nota: Se recomienda instalar la versión de PyTorch compatible con CUDA si deseas aceleración por GPU para EasyOCR.

  💻 Uso Básico
El script puede ser llamado fácilmente pasándole la ruta de la imagen. Está diseñado para inyectar una instancia global de EasyOCR y así evitar recargar el modelo en cada petición si se usa en un servidor web.

import easyocr
from ocr_core import extraer_datos_cedula

# 1. Inicializar el lector una sola vez (ideal para APIs)
lector_ia = easyocr.Reader(['es', 'en'], gpu=True)

# 2. Extraer los datos
ruta_foto = "ruta/a/la/foto_cedula.jpg"

try:
    datos = extraer_datos_cedula(ruta_foto, lector_ia)
    print(datos)
except ValueError as e:
    print(f"Error de validación: {e}")
    
Ejemplo de Salida (JSON / Diccionario)

{
    "Cedula": "23.123.121",
    "Nombres": "FABIAN ABEL",
    "Apellidos": "QUIJADA CARRILLO",
    "Fecha_Nacimiento": "05/05/2004",
    "Estado_Civil": "SOLTERO/A",
    "Nacionalidad": "Venezolano/a"
}

🧠 Entendiendo el Pipeline (Bajo el capó)
1.Detección: La imagen original se procesa con Canny Edge Detection para encontrar los 4 vértices del plástico.

2.Aplanamiento: cv2.warpPerspective crea una vista cenital (vista de pájaro) perfecta.

3.Aislamiento: Se recorta un ROI del 2% al 65% del ancho, omitiendo datos irrelevantes.

4.Mejora: La imagen se escala x2 y se le aplica un suavizado gaussiano inverso para resaltar los bordes del texto.

5.Lectura Óptica: EasyOCR escanea con un filtro de confianza estricto (> 0.50).

6.Parseo Semántico: Expresiones regulares limpian los resultados, descartan firmas, remueven ceros a la izquierda en los códigos numéricos y emparejan los valores con sus claves.

🤝 Contribuciones
Las contribuciones son bienvenidas. Si tienes ideas para mejorar la extracción del pasaporte o refinar aún más el filtro de ruido, siéntete libre de abrir un Pull Request o un Issue.

👨‍💻 Autor
Fabián Quijada * Full-Stack Developer & Computer Science Student.
Co-fundador de koodev.net
Contacto: fabian.quijada@koodev.net | fabian05demayo@gmail.com
