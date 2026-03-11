import cv2
import easyocr
import re
import numpy as np
import os

# ==========================================
# 1. FUNCIONES DE VISIÓN COMPUTACIONAL (NUEVAS)

def aislar_zona_datos(imagen_alineada):
    """
    Recorta únicamente la porción izquierda de la cédula (caja roja)
    basándose en porcentajes del documento ya aplanado.
    """
    h, w = imagen_alineada.shape[:2]
    
    # Coordenadas relativas (porcentajes de la imagen total)
    # Ajustado a la caja roja que dibujaste
    x_min = int(w * 0.10)  # 2% desde el borde izquierdo
    x_max = int(w * 0.65)  # 65% del ancho (corta antes de la foto y el director)
    y_min = int(h * 0.15)  # 15% desde arriba (corta el encabezado de "República")
    y_max = int(h * 1)  # 100% del alto (corta la huella y fechas de expedición/vencimiento)
    
    zona_segura = imagen_alineada[y_min:y_max, x_min:x_max]
    
    # Guardamos este recorte para que puedas verlo y verificar que el cuadro rojo está bien calculado
    cv2.imwrite("Recorte_Caja_Roja.jpg", zona_segura)
    
    return zona_segura

def parsear_datos(textos):
    datos = {
        "Cedula": None,
        "Nombres": None,
        "Apellidos": None,
        "Fecha_Nacimiento": None,
        "Estado_Civil": None,
        "Nacionalidad": None
    }
    
    for i, texto in enumerate(textos):
        texto_limpio = texto.upper().strip()
        
        # Buscar Cédula (Ej: 31.805.352 o 116 761.275)
        # Extraemos todos los números del bloque de texto
        numeros = re.sub(r'\D', '', texto_limpio)
        # Si tiene al menos 6 números y no hemos guardado la cédula
        if len(numeros) >= 6 and not datos["Cedula"]:
            caracteres_numericos = sum(c.isdigit() for c in texto_limpio)
            # Validar que gran parte del texto sean números
            if caracteres_numericos / len(texto_limpio) > 0.4:
                # El OCR de imágenes malas suele meter letras basura al inicio o al final.
                # Las cédulas venezolanas tienen típicamente hasta 8 dígitos.
                if len(numeros) > 8:
                    # Determinamos si la basura está al principio (ej: V17730261 -> 117730261) 
                    # o al final (ej: 17730261- -> 177302611).
                    # Las cédulas actuales empiezan por 1, 2 o 3. Si tenemos más de 8 números
                    # y los primeros números son lógicos (> 1000000), preferimos tomar los primeros 8.
                    if numeros.startswith(('1', '2', '3')):
                        numeros_limpios = numeros[:8] 
                    else:
                        numeros_limpios = numeros[-8:] # Si empieza por algo raro (ej: 8, 9), tomamos los últimos 8
                else:
                    numeros_limpios = numeros
                    
                # Limpiar ceros a la izquierda si los hay
                numeros_limpios = numeros_limpios.lstrip('0')
                
                datos["Cedula"] = f"{int(numeros_limpios):,}".replace(",", ".")
                
        LABELS_NOMBRES = ["NOMBRES", "NOMBRE", "NONBRES", "AOSRES", "AO;SRES", "NOSBRES", "NOM3RES", "NOMERES", '"OUPRES', 'OUPRES',"NOMIBRES"]
        LABELS_APELLIDOS = ["APELLIDOS", "APELLIDO", "AFELLIDOS", "APELUIDOS", "APELLID0S", "APELLID0", "APELLIDOS", "ACALLIOS", "KPELLDOS"]
        # Buscar Nombres (A veces OCR lo lee como 'NOMBAES')
        if any(label in texto_limpio for label in LABELS_NOMBRES) and i + 1 < len(textos):
            datos["Nombres"] = textos[i+1].upper()
            
        # Buscar Apellidos (A veces OCR lo lee como 'APElUIDOS')
        if any(label in texto_limpio for label in LABELS_APELLIDOS) and i + 1 < len(textos):
            datos["Apellidos"] = textos[i+1].upper()
            
        # Buscar Estado civil (buscar palabras clave en cualquier parte)
        if any(label in texto_limpio for label in LABELS_APELLIDOS) and i + 1 < len(textos):
            datos["Apellidos"] = textos[i+1].upper()
        if "SOLTERO" in texto_limpio or "SOLTERA" in texto_limpio:
            datos["Estado_Civil"] = "SOLTERO/A"
        elif "CASADO" in texto_limpio or "CASADA" in texto_limpio:
            datos["Estado_Civil"] = "CASADO/A"
        elif "DIVORCIADO" in texto_limpio or "DIVORCIADA" in texto_limpio:
            datos["Estado_Civil"] = "DIVORCIADO/A"
        elif "VIUDO" in texto_limpio or "VIUDA" in texto_limpio:
            datos["Estado_Civil"] = "VIUDO/A"
            
        # Buscar Nacionalidad
        if "VENEZOLANO" in texto_limpio or "VENEZOLANA" in texto_limpio or "VEN" in texto_limpio:
            datos["Nacionalidad"] = "Venezolano/a"
        elif "EXTRANJERO" in texto_limpio or "EXTRANJERA" in texto_limpio:
            datos["Nacionalidad"] = "Extranjero/a"
            
    # --- Lógica de Respaldo (Fallback Posicional) ---
    # Si la imagen es tan mala que no leyó "NOMBRES" ni "APELLIDOS", 
    # intentamos adivinar por posición. Generalmente, el Apellido y el Nombre
    # están justos después de la cédula y la firma del director.
    if datos["Nombres"] is None or datos["Apellidos"] is None:
        if datos["Cedula"]:
            # Buscamos en qué índice está la cédula
            indice_cedula = -1
            for i, txt in enumerate(textos):
                if datos["Cedula"].replace('.', '') in txt.replace('.', ''):
                    indice_cedula = i
                    break
            
            # Si encontramos la cédula, los apellidos y nombres suelen estar en los siguientes bloques de texto
            # Ignoramos "Director" o nombres de directores como "Gustavo Vizcaino"
            if indice_cedula != -1:
                candidatos = []
                for j in range(indice_cedula + 1, min(indice_cedula + 8, len(textos))):
                    txt_candidato = textos[j].upper().strip()
                    # Filtramos bloques cortos, fechas, palabras clave y al director
                    if len(txt_candidato) > 4 and not re.search(r'\d', txt_candidato) \
                       and txt_candidato not in ["DIRECTOR", "DIRECTON", "NOMBRES", "APELLIDOS", "GUSTAVO VIZCAINO", "CUSTAVO VIZCAIO", "CUSTAVO", "REPUBLICA", "NACIONALIDAD"]:
                        candidatos.append(txt_candidato)
                
                # Usualmente el primer candidato válido son los Apellidos y el segundo los Nombres
                if len(candidatos) >= 1 and not datos["Apellidos"]:
                    datos["Apellidos"] = candidatos[0]
                if len(candidatos) >= 2 and not datos["Nombres"]:
                    datos["Nombres"] = candidatos[1]
            
    # --- Búsqueda Global de Fecha de Nacimiento ---
    # Si la fecha estaba muy unida a otro texto y el bucle falló, buscamos en todo el texto unido
    if not datos["Fecha_Nacimiento"]:
        texto_completo = " ".join(textos).upper()
        # Buscamos DD[sep]MM[sep]AAAA donde sep puede ser casi cualquier cosa no numérica
        match_fecha = re.search(r'(\d{2})[^\d]{1,2}(\d{2})[^\d]{1,2}(\d{4})', texto_completo)
        if match_fecha:
            dia, mes, anio = match_fecha.groups()
            if int(mes) > 12:
                mes = "0" + mes[1] if len(mes) > 1 and mes[0] != '1' else "10"
            datos["Fecha_Nacimiento"] = f"{dia}/{mes}/{anio}"
                
    return datos

def ordenar_puntos(pts):
    """
    Ordena las coordenadas de un rectángulo para la transformación de perspectiva.
    El orden será: arriba-izquierda, arriba-derecha, abajo-derecha, abajo-izquierda.
    """
    rect = np.zeros((4, 2), dtype="float32")
    
    # La suma de (x, y) será mínima en arriba-izquierda y máxima en abajo-derecha
    s = pts.sum(axis=1)
    rect[0] = pts[np.argmin(s)]
    rect[2] = pts[np.argmax(s)]
    
    # La diferencia (y - x) será mínima en arriba-derecha y máxima en abajo-izquierda
    diff = np.diff(pts, axis=1)
    rect[1] = pts[np.argmin(diff)]
    rect[3] = pts[np.argmax(diff)]
    
    return rect

def corregir_orientacion(imagen_plana, lector):
    """
    Verifica si el documento PLANO está de cabeza y lo endereza.
    Revisa la parte superior buscando "REPUBLICA". Si no la encuentra, 
    revisa la parte inferior. Si la encuentra abajo, rota 180.
    """
    if imagen_plana is None:
        return None

    h, w = imagen_plana.shape[:2]
    
    # 1. FORZAR HORIZONTAL (Apaisado)
    if h > w:
        print("[ORIENTACIÓN] Documento vertical detectado. Rotando 90 grados...")
        imagen_plana = cv2.rotate(imagen_plana, cv2.ROTATE_90_CLOCKWISE)
        h, w = imagen_plana.shape[:2]

    # 2. PRUEBA DE 180 GRADOS (De cabeza)
    # Recortamos el 35% de arriba (donde debe estar REPÚBLICA BOLIVARIANA)
    recorte_superior = imagen_plana[0:int(h * 0.35), 0:w]
    
    if len(imagen_plana.shape) == 3 and imagen_plana.shape[2] == 3:
        gris_superior = cv2.cvtColor(recorte_superior, cv2.COLOR_BGR2GRAY)
    else:
        gris_superior = recorte_superior.copy()
        
    # Aumentar contraste para lectura rápida
    gris_superior = cv2.adaptiveThreshold(gris_superior, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 11, 2)
    
    print("[ORIENTACIÓN] Verificando si el texto está de cabeza...")
    resultados_arriba = lector.readtext(gris_superior, detail=0)
    texto_arriba = " ".join(resultados_arriba).upper()
    
    palabras_clave = ["REPUBLICA", "BOLIVARIANA", "VENEZUELA", "CEDULA", "IDENTIDAD", "REP", "BLICA"]
    coincidencias_arriba = sum(1 for palabra in palabras_clave if palabra in texto_arriba)
    
    if coincidencias_arriba == 0:
        # Si no encontramos arriba, revisamos abajo para confirmar
        recorte_inferior = imagen_plana[int(h * 0.65):h, 0:w]
        
        if len(imagen_plana.shape) == 3 and imagen_plana.shape[2] == 3:
            gris_inferior = cv2.cvtColor(recorte_inferior, cv2.COLOR_BGR2GRAY)
        else:
            gris_inferior = recorte_inferior.copy()
        
        # Debemos rotar el pedazo de abajo 180 para que el OCR lo pueda leer si está invertido
        gris_inferior_rotado = cv2.rotate(gris_inferior, cv2.ROTATE_180)
        gris_inferior_rotado = cv2.adaptiveThreshold(gris_inferior_rotado, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 11, 2)
        
        resultados_abajo = lector.readtext(gris_inferior_rotado, detail=0)
        texto_abajo = " ".join(resultados_abajo).upper()
        
        coincidencias_abajo = sum(1 for palabra in palabras_clave if palabra in texto_abajo)
        
        if coincidencias_abajo > 0:
            print("[ORIENTACIÓN] Cabecera encontrada en la parte inferior. Rotando 180 grados...")
            return cv2.rotate(imagen_plana, cv2.ROTATE_180)
        else:
            print("[ORIENTACIÓN] No se pudo confirmar orientación, asumiendo correcta.")
    else:
        print("[ORIENTACIÓN] Imagen derecha confirmada.")

    return imagen_plana

def escanear_documento(imagen):
    """
    Detecta el documento (Cédula/Pasaporte) buscando un contorno de 4 puntos,
    aplica 'Warp Perspective' para aplanarlo y un umbral para efecto CamScanner.
    """
    if imagen is None:
        return None

    imagen_original = imagen.copy()
    ratio = imagen.shape[0] / 800.0
    imagen_redimensionada = cv2.resize(imagen, (int(imagen.shape[1] / ratio), 800))
    
    # 1. Detección de bordes
    gray = cv2.cvtColor(imagen_redimensionada, cv2.COLOR_BGR2GRAY)
    blur = cv2.GaussianBlur(gray, (5, 5), 0)
    edged = cv2.Canny(blur, 75, 200)

    # 2. Búsqueda del contorno del documento
    contornos, _ = cv2.findContours(edged.copy(), cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
    contornos = sorted(contornos, key=cv2.contourArea, reverse=True)[:5]

    contorno_documento = None

    for c in contornos:
        perimetro = cv2.arcLength(c, True)
        aproximacion = cv2.approxPolyDP(c, 0.02 * perimetro, True)

        # Si el contorno tiene exactamente 4 puntos, asumimos que es el documento
        if len(aproximacion) == 4:
            contorno_documento = aproximacion
            break

    # Manejo de errores: Si no encuentra 4 puntos, retornamos la imagen original mejorada
    if contorno_documento is None:
        print("[WARNING] No se pudo detectar un contorno de 4 puntos. Aplicando mejora estándar.")
        imagen_final = cv2.cvtColor(imagen_original, cv2.COLOR_BGR2GRAY)
        imagen_final = cv2.adaptiveThreshold(imagen_final, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 21, 10)
        cv2.imwrite("Ultimo_recorte.jpg", imagen_final)
        return imagen_final

    # 3. Transformación de perspectiva (Warp Perspective)
    # Multiplicamos por el ratio para volver a las dimensiones originales de la imagen
    puntos_originales = contorno_documento.reshape(4, 2) * ratio
    rect = ordenar_puntos(puntos_originales)
    (tl, tr, br, bl) = rect

    # Calcular el ancho máximo y alto máximo del nuevo documento
    widthA = np.sqrt(((br[0] - bl[0]) ** 2) + ((br[1] - bl[1]) ** 2))
    widthB = np.sqrt(((tr[0] - tl[0]) ** 2) + ((tr[1] - tl[1]) ** 2))
    maxWidth = max(int(widthA), int(widthB))

    heightA = np.sqrt(((tr[0] - br[0]) ** 2) + ((tr[1] - br[1]) ** 2))
    heightB = np.sqrt(((tl[0] - bl[0]) ** 2) + ((tl[1] - bl[1]) ** 2))
    maxHeight = max(int(heightA), int(heightB))

    # Matriz de destino
    dst = np.array([
        [0, 0],
        [maxWidth - 1, 0],
        [maxWidth - 1, maxHeight - 1],
        [0, maxHeight - 1]], dtype="float32")

    M = cv2.getPerspectiveTransform(rect, dst)
    warped = cv2.warpPerspective(imagen_original, M, (maxWidth, maxHeight))

    # 4. Mejora de la imagen (Efecto Escáner digital)
    #warped_gray = cv2.cvtColor(warped, cv2.COLOR_BGR2GRAY)
    
    # Aplicar Adaptive Thresholding para fondo blanco y letras negras

    # Guardar el recorte solicitado
    cv2.imwrite("Ultimo_recorte.jpg", warped)
    print("[INFO] Documento escaneado y guardado como 'Ultimo_recorte.jpg'")

    return warped

# ==========================================
# 2. FUNCIONES DE EXTRACCIÓN (ACTUALIZADAS)
# ==========================================

def clasificar_documento(textos):
    texto_completo = " ".join(textos).upper()
    if any(k in texto_completo for k in ["PASAPORTE", "PASSPORT", "P<VEN", "<<<<"]):
        return "PASAPORTE"
    return "CEDULA"

def parsear_cedula(resultados):
    datos = {
        "Cedula": None, "Nombres": None, "Apellidos": None,
        "Fecha_Nacimiento": None, "Estado_Civil": None, 
        "Nacionalidad": None, "Tipo": "CEDULA"
    }
    
    textos = [res[1] for res in resultados]
    textos_up = [t.upper().strip() for t in textos]
    
    # ACTUALIZADO CON LOS ERRORES DEL OCR_TEST
    BLACKLIST_EXACT = [
        "JUAN CARLOS DUGARTE", "GUSTAVO VIZCAINO GIL", "ANABEL JIMENEZ", 
        "FABRICIO PEREZ MORON", "DANTE RIVAS", "GUSTAVO VIZCAINO",
        "JUAN DUGARTE", "JUAN DUGARIE", "JUAN DXGARRE", "ANABEL JIMÉNEZ", 
        "GUCTAVO VIRCAINO", "DIRECTORA", "DIRECTOR", "MINISTERIO",
        "REPUBLICA", "SAIME", "VENEZUELA", "BOLIVARIANA", "NOMIBRES","NOMBRES", "NOMBRE", "NONBRES", "AOSRES", "AO;SRES", "NOSBRES", "NOM3RES", "NOMERES", '"OUPRES', 'OUPRES',"APELLIDOS", "APELLIDO", "AFELLIDOS", "APELUIDOS", "APELLID0S", "APELLID0", "APELLIDOS", "ACALLIOS", "KPELLDOS"
    ]

    LABELS_NOMBRES = ["NOMBRES", "NOMBRE", "NONBRES", "AOSRES", "AO;SRES", "NOSBRES", "NOM3RES", "NOMERES", '"OUPRES', 'OUPRES',"NOMIBRES"]
    LABELS_APELLIDOS = ["APELLIDOS", "APELLIDO", "AFELLIDOS", "APELUIDOS", "APELLID0S", "APELLID0", "APELLIDOS", "ACALLIOS", "KPELLDOS"]
    
    def limpiar_valor(txt):
        if not txt: return None
        t = txt.upper().replace("@", "A").replace("0", "O")
        for kw in LABELS_NOMBRES + LABELS_APELLIDOS:
            t = t.replace(kw, "")
        t = re.sub(r'[^A-ZÁÉÍÓÚÑ ]', '', t)
        return t.strip()

    def es_valido_titular(txt):
        val = limpiar_valor(txt)
        if not val or len(val) < 3: return False 
        for b in BLACKLIST_EXACT:
            if b in val or val in b: return False
        return True

    # Búsqueda principal
    for i, texto_limpio in enumerate(textos_up):
        # Cédula
        numeros = re.sub(r'\D', '', texto_limpio)
        if len(numeros) >= 6 and not datos["Cedula"]:
            if sum(c.isdigit() for c in texto_limpio) / (len(texto_limpio) or 1) > 0.4:
                num_ref = numeros[:8] if numeros.startswith(('1', '2', '3')) else numeros[-8:]
                datos["Cedula"] = f"{int(num_ref):,}".replace(",", ".")

        # Nombres y Apellidos
        if any(kw in texto_limpio for kw in LABELS_NOMBRES):
            if i + 1 < len(textos) and es_valido_titular(textos[i+1]) and not datos["Nombres"]:
                datos["Nombres"] = limpiar_valor(textos[i+1])
        
        if any(kw in texto_limpio for kw in LABELS_APELLIDOS):
            if i + 1 < len(textos) and es_valido_titular(textos[i+1]) and not datos["Apellidos"]:
                datos["Apellidos"] = limpiar_valor(textos[i+1])

    # Fallback por ancla (si el OCR no leyó bien las etiquetas)
    if not datos["Nombres"] or not datos["Apellidos"]:
        id_idx = -1
        if datos["Cedula"]:
            nums_target = datos["Cedula"].replace(".", "")
            for idx, txt in enumerate(textos_up):
                if nums_target in txt.replace(".", ""):
                    id_idx = idx
                    break
        
        if id_idx != -1:
            cands = []
            for j in range(id_idx + 1, min(id_idx + 12, len(textos))):
                if es_valido_titular(textos[j]) and not any(lab in textos_up[j] for lab in LABELS_NOMBRES + LABELS_APELLIDOS):
                    cands.append(limpiar_valor(textos[j]))
            
            if len(cands) >= 1 and not datos["Apellidos"]: datos["Apellidos"] = cands[0]
            if len(cands) >= 2 and not datos["Nombres"]: datos["Nombres"] = cands[1]

    # Datos Globales
    t_full = " ".join(textos_up)
    if "SOLTER" in t_full: datos["Estado_Civil"] = "SOLTERO/A"
    elif "CASAD" in t_full: datos["Estado_Civil"] = "CASADO/A"
    if "VENEZOLAN" in t_full: datos["Nacionalidad"] = "Venezolano/a"
    
    match = re.search(r'(\d{2})[^\d]{1,2}(\d{2})[^\d]{1,2}(\d{4})', t_full)
    if match and not datos["Fecha_Nacimiento"]:
        datos["Fecha_Nacimiento"] = f"{match.group(1)}/{match.group(2)}/{match.group(3)}"

    return datos

# ==========================================
# 3. FLUJO PRINCIPAL
# ==========================================

def extraer_datos_cedula(ruta_imagen, lector):
    if lector is None:
        print(f"[{ruta_imagen}] Iniciando el motor de IA local...")
        lector = easyocr.Reader(['es', 'en'], gpu=True)
    
    imagen_raw = cv2.imread(ruta_imagen)
    
    if imagen_raw is None:
        raise FileNotFoundError(f"No se pudo cargar la imagen: {ruta_imagen}")

    print(f"[{ruta_imagen}] Aplicando escáner documental (recorte y perspectiva)...")
    
    # 1. Aplicar escáner documental ANTES de la orientación
    imagen_procesada_color = escanear_documento(imagen_raw)
    
    # 2. Corregir orientación en el documento ya aplanado
    imagen_procesada_color = corregir_orientacion(imagen_procesada_color, lector)
    
    imagen_original = imagen_procesada_color.copy()
    
    # Guardamos la foto bonita y natural para tus registros
    cv2.imwrite("Ultimo_recorte.jpg", imagen_procesada_color)
    print(f"[{ruta_imagen}] Documento a color guardado como 'Ultimo_recorte.jpg'")
    
    # --- PREPARACIÓN "MODO ESTEROIDES" SOLO PARA EL OCR ---
    print(f"[{ruta_imagen}] Optimizando imagen en memoria para el OCR...")
    
    imagen_zona_datos = aislar_zona_datos(imagen_procesada_color)
    # 2. Agrandamos la imagen al doble (EasyOCR lee MUCHO mejor las letras grandes)
    h, w = imagen_zona_datos.shape[:2]
    img_ocr = cv2.resize(imagen_zona_datos, (w*4, h*4), interpolation=cv2.INTER_CUBIC)
    cv2.imwrite("Ultimo_recorte_ocr.jpg", img_ocr)
    
    # 3. La pasamos a grises (elimina el ruido del color de fondo)
    if len(img_ocr.shape) == 3 and img_ocr.shape[2] == 3:
        img_ocr_gray = cv2.cvtColor(img_ocr, cv2.COLOR_BGR2GRAY)
    else:
        img_ocr_gray = img_ocr
    
    # 4. Aplicamos un "Unsharp Mask" (Filtro de nitidez)
    # Esto hace que los bordes de las letras negras resalten muchísimo contra el fondo
    gaussian = cv2.GaussianBlur(img_ocr_gray, (0, 0), 2.0)
    img_ocr_sharp = cv2.addWeighted(img_ocr_gray, 1.5, gaussian, -0.5, 0)
    # ------------------------------------------------------
    
    print(f"[{ruta_imagen}] Extrayendo texto OCR con parámetros avanzados...")
    
    # 5. Pasamos la imagen súper nítida al OCR con parámetros avanzados
    # mag_ratio=1.5: Aumenta internamente la imagen un 50% extra en el motor OCR.
    # contrast_ths y adjust_contrast: Obliga a la IA a forzar el contraste interno si hay sombras.
    resultados_crudos = lector.readtext(
        img_ocr_sharp, 
        detail=1, 
        mag_ratio=1.5, 
        contrast_ths=0.3, 
        adjust_contrast=0.7
    )
    
    umbral_confianza = 0.50
    resultados = []
    
    with open("OCR_Test.txt", "a", encoding="utf-8") as f:
        f.write(f"\n{'='*20} {ruta_imagen} (FILTRO > {umbral_confianza}) {'='*20}\n")
        
        for i, res in enumerate(resultados_crudos):
            texto = res[1]
            confianza = res[2]
            
            if confianza >= umbral_confianza:
                # Si pasa el filtro, lo guardamos para procesarlo
                resultados.append(res)
                f.write(f"{texto} (Conf: {confianza:.2f})\n")
            # else:
            #     # Si no pasa, lo registramos para saber qué perdimos
            #     f.write(f"[DESCARTADO] {texto} (Conf: {confianza:.2f})\n")

    # Extraer solo el texto para el primer parsing
    texto_solo = [res[1] for res in resultados]
    datos = parsear_datos(texto_solo)
    
   # --- RE-OCR DIRIGIDO PARA LA CÉDULA ---
    # Si detectamos una cédula, intentamos mejorar su precisión
    cedula_limpia_actual = re.sub(r'\D', '', datos.get("Cedula", "") or "")

    if datos["Cedula"] and len(cedula_limpia_actual) < 7:
        print(f"[{ruta_imagen}] Cédula incompleta detectada. Intentando Re-OCR...")
        id_bloque = -1
        if datos["Cedula"]:
            cedula_digits = re.sub(r'\D', '', datos["Cedula"])
            print(f"[{ruta_imagen}] Buscando caja delimitadora para cédula: {cedula_digits}")
            
            # Buscamos qué bloque contenía la mayoría de los dígitos de la cédula
            max_overlap = 0
            for i, res in enumerate(resultados):
                res_digits = re.sub(r'\D', '', res[1])
                if len(res_digits) >= 6:
                    matches = sum(1 for d in cedula_digits if d in res_digits)
                    if matches > max_overlap:
                        max_overlap = matches
                        id_bloque = i
                    
        if id_bloque != -1:
            print(f"[{ruta_imagen}] Bloque de cédula encontrado en índice {id_bloque}: '{resultados[id_bloque][1]}'")
            bbox = resultados[id_bloque][0]
            # bbox son 4 puntos: [[x1,y1], [x2,y2], [x3,y3], [x4,y4]]
            x_min = int(min(p[0] for p in bbox))
            x_max = int(max(p[0] for p in bbox))
            y_min = int(min(p[1] for p in bbox))
            y_max = int(max(p[1] for p in bbox))
            
            # Añadir un pequeño margen al recorte
            margen = 5
            
            # ¡CORRECCIÓN AQUÍ! Usamos la imagen que ya está en memoria (img_ocr_gray)
            # Sus dimensiones cuadran perfectamente con las coordenadas del bbox.
            h_ocr, w_ocr = img_ocr_gray.shape[:2]
            crop_id = img_ocr_gray[max(0, y_min-margen):min(h_ocr, y_max+margen), 
                                max(0, x_min-margen):min(w_ocr, x_max+margen)]
            
            if crop_id.size > 0:
                # Como la imagen ya viene agrandada x2 de pasos anteriores, 
                # no hace falta hacerle cv2.resize otra vez. Directamente aplicamos threshold.
                crop_bin = cv2.adaptiveThreshold(crop_id, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, 
                                                cv2.THRESH_BINARY, 11, 2)
                
                # Segundo pass: Solo números
                print(f"[{ruta_imagen}] Re-escaneando zona de cédula con alta resolución...")
                resultado_refinado = lector.readtext(crop_bin, detail=0, allowlist='0123456789')
                
                if resultado_refinado:
                    texto_refinado = "".join(resultado_refinado)
                    print(f"[{ruta_imagen}] Texto detectado en recorte: {texto_refinado}")
                    nums_refinados = re.sub(r'\D', '', texto_refinado)
                    
                    # Si el resultado refinado tiene un largo lógico (7 u 8 dígitos), lo usamos
                    if 7 <= len(nums_refinados) <= 8:
                        datos["Cedula"] = f"{int(nums_refinados):,}".replace(",", ".")
                    elif len(nums_refinados) > 8:
                        if nums_refinados.startswith(('1', '2', '3')):
                            datos["Cedula"] = f"{int(nums_refinados[:8]):,}".replace(",", ".")
                        else:
                            datos["Cedula"] = f"{int(nums_refinados[-8:]):,}".replace(",", ".")
    elif datos["Cedula"]:
        print(f"[{ruta_imagen}] Cédula leída perfectamente ({datos['Cedula']}). Omitiendo Re-OCR.")

    campos_faltantes = [clave for clave, valor in datos.items() if not valor]
    
    if campos_faltantes:
        mensaje_error = f"Documento ilegible o incompleto. Faltan los campos: {', '.join(campos_faltantes)}"
        print(f"[ERROR 400] {mensaje_error}")
        
        # Levantamos un ValueError genérico. 
        # Tu framework de API debe atrapar esto y devolver el HTTP 400.
        raise ValueError(mensaje_error)
        
    print("\n--- Datos Estructurados ---")
    for clave, valor in datos.items():
        print(f"{clave}: {valor}")
        
    return datos
