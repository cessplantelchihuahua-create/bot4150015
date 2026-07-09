import os
import sys
from flask import Flask, request, jsonify
import requests
from openai import OpenAI
# Configuración de codificación para evitar errores al imprimir emojis en Windows
if sys.platform.startswith('win'):
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='backslashreplace')
        sys.stderr.reconfigure(encoding='utf-8', errors='backslashreplace')
    except AttributeError:
        pass
app = Flask(__name__)
# ==========================================
# ⚙️ CONFIGURACIÓN DE CREDENCIALES
# ==========================================
# ⚠️ IMPORTANTE: Regenera estos tokens de inmediato en tus paneles de OpenAI y Meta, ya que quedaron expuestos.
API_VERSION="v25.0"
OPENAI_API_KEY = "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"
META_TOKEN = "EAATpKq7Ko8IBRgIi5YatoBwZAFXxQCLxq4YJTMRTiMK0FqOL9ZAjyYeYHKZARiQrvoUETZAwN5oIjgRU2xeJS6Auo9a7ZB8fQBqosJnZBADHXC5hltVWvL0IN06qJbcl7N95K2pqXYDEKgK5BCrApkHeoPI5U06bNwHtOZAsDJeWVuG4K4wblBgM6WfmicuKAZDZD"
PHONE_NUMBER_ID = "4821860974556462"
VERIFY_TOKEN = "vibecode"
client = OpenAI(api_key=OPENAI_API_KEY)
# Cargar el archivo de datos una sola vez al arrancar
try:
    with open("datosCESS.txt", "r", encoding="utf-8") as f:
        contexto_privado = f.read()
except FileNotFoundError:
    contexto_privado = ""
    print("⚠️ Archivo datosCESS.txt no encontrado. Las respuestas de la IA podrían fallar.")
@app.route('/', methods=['GET'])
def inicio():
    return "¡Servidor de WhatsApp e IA activo correctamente!", 200
@app.route('/webhook', methods=['GET'])
def verificar_webhook():
    mode = request.args.get('hub.mode')
    token = request.args.get('hub.verify_token')
    challenge = request.args.get('hub.challenge')
    
    if mode and token:
        if mode == 'subscribe' and token == VERIFY_TOKEN:
            return challenge, 200
        return 'Validación fallida', 403
    return 'Mal formato', 400
@app.route('/webhook', methods=['POST'])
def recibir_mensaje():
    data = request.get_json()
    
    # Imprime el JSON entrante para auditoría en tu consola
    print(f"📥 JSON recibido de Meta: {data}")
    
    try:
        # 1. Extraer la lista de entradas (entries)
        entries = data.get('entry', [])
        for entry in entries:
            changes = entry.get('changes', [])
            for change in changes:
                value = change.get('value', {})
                
                # 2. Validar que el webhook corresponda a un evento de mensajes de WhatsApp
                if change.get('field') != 'messages' or value.get('messaging_product') != 'whatsapp':
                    continue
                
                # 3. Extraer información del contacto y metadatos (Opcional, extraído de tu JSON de ejemplo)
                contacts = value.get('contacts', [])
                nombre_usuario = "Usuario"
                if contacts:
                    nombre_usuario = contacts[0].get('profile', {}).get('name', 'Usuario')
                
                metadata = value.get('metadata', {})
                phone_number_id = metadata.get('phone_number_id')
                # 4. Procesar la lista de mensajes entrantes
                messages = value.get('messages', [])
                for message in messages:
                    # Extrae el número del remitente ("from": "16315551181")
                    numero_usuario = message.get('from')
                    
                    # 5. Extraer texto y datos de referencia del anuncio (si existen)
                    texto_usuario = None
                    if message.get('type') == 'text':
                        texto_usuario = message.get('text', {}).get('body')
                    
                    referral = message.get('referral')
                    ad_context = ""
                    if referral:
                        headline = referral.get('headline', '')
                        body = referral.get('body', '')
                        source_id = referral.get('source_id', '')
                        source_type = referral.get('source_type', '')
                        print(f"📢 Usuario proviene de un anuncio de Facebook ({source_type}): ID={source_id}, Título='{headline}', Cuerpo='{body}'")
                        ad_context = f"\n[El usuario hizo clic en el anuncio de Facebook: '{headline}' - '{body}' (ID: {source_id})]"
                        # Si no hay texto (por ejemplo, primera interacción al dar clic en el anuncio)
                        if not texto_usuario:
                            texto_usuario = f"Hola, me interesa el anuncio: {headline}"
                    
                    # 6. Procesar si hay un mensaje o interacción válida
                    if texto_usuario:
                        print(f"📩 {nombre_usuario} ({numero_usuario}) dijo: {texto_usuario}")
                        
                        # Instrucciones para el modelo de OpenAI
                        instrucciones_sistema = (
                            "Eres un asistente de servicio al cliente automatizado y amable.\n"
                            "Usa ÚNICAMENTE el siguiente contexto para responder la pregunta del usuario.\n"
                            "REGLA CRÍTICA: Si la respuesta no se encuentra explícitamente en el contexto, "
                            "debes responder exactamente: 'Lo siento, no dispongo de esa información en este momento.' "
                            "No intentes inventar o asumir información bajo ninguna circunstancia.\n\n"
                            f"Contexto:\n{contexto_privado}"
                        )
                        
                        # Si proviene de un anuncio, enriquecemos las instrucciones de la IA
                        if ad_context:
                            instrucciones_sistema += (
                                f"\n\nContexto de origen del anuncio:\n{ad_context}\n"
                                "IMPORTANTE: Saluda amigablemente haciendo alusión al anuncio de forma natural "
                                "y prioriza la información del contexto privado relacionada con el tema del anuncio."
                            )
                        
                        # Llamada a la API de OpenAI
                        response = client.responses.create(
                            model="gpt-4o-mini",
                            instructions=instrucciones_sistema,
                            input=texto_usuario,
                            temperature=0,
                            max_output_tokens=2048,
                            store=True
                        )
                        
                        respuesta_final = response.output_text
                        print(f"🤖 IA responde a {nombre_usuario}: {respuesta_final}")
                        
                        # Enviar respuesta de vuelta al usuario
                        enviar_whatsapp(numero_usuario, respuesta_final, phone_number_id)
                        
    except Exception as e:
        print(f"❌ Error interno procesando el flujo de Meta: {e}")
        
    # Meta exige un estado 200 HTTP inmediato para no reenviar el mismo mensaje
    return jsonify({"status": "success"}), 200
def enviar_whatsapp(number, text, phone_number_id=None):
    if not phone_number_id:
        phone_number_id = PHONE_NUMBER_ID
    url = f"https://graph.facebook.com/{API_VERSION}/{phone_number_id}/messages"
    headers = {
        "Authorization": f"Bearer {META_TOKEN}",
        "Content-Type": "application/json"
    }
    payload = {
        "messaging_product": "whatsapp",
        "to": number,
        "type": "text",
        "text": {"body": text}
    }
    res = requests.post(url, json=payload, headers=headers)
    print(f"📤 Estado de envío a WhatsApp: {res.status_code} - Respuesta: {res.text}")
if __name__ == '__main__':
    from waitress import serve
    print("¡Servidor de producción Waitress encendido en el puerto 5000!")
    serve(app, host='0.0.0.0', port=5000)
