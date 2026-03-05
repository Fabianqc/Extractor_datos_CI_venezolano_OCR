import requests

url = "http://127.0.0.1:8000/procesar-documento"
# Especificar el tipo de contenido explícitamente para mayor robustez
files = {'file': ('cedula.jpg', open('cedula.jpg', 'rb'), 'image/jpeg')}

print("Enviando petición a la API...")
try:
    response = requests.post(url, files=files)
    print("Status Code:", response.status_code)
    if response.status_code == 200:
        print("Respuesta:", response.json())
    else:
        print("Error:", response.text)
except Exception as e:
    print("Error de conexión:", str(e))
