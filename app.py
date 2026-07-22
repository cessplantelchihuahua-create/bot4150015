import os
import sys
import json
import sqlite3
from datetime import datetime, timezone
from flask import Flask, request, jsonify
import requests
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()  # Lee el archivo .env (si existe) y carga sus variables al entorno

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
# ⚠️ Las credenciales se leen de variables de entorno. Configúralas antes de correr el script.
API_VERSION = "v25.0"
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
META_TOKEN = os.environ.get("META_TOKEN")
PHONE_NUMBER_ID = os.environ.get("PHONE_NUMBER_ID")
VERIFY_TOKEN = os.environ.get("VERIFY_TOKEN", "vibecode")
NUMERO_ASESOR = os.environ.get("NUMERO_ASESOR")

# Validar que las variables de entorno estén configuradas
if not all([OPENAI_API_KEY, META_TOKEN, PHONE_NUMBER_ID, NUMERO_ASESOR]):
    print("⚠️ ADVERTENCIA: Faltan variables de entorno requeridas. Configúralas en Render.", flush=True)

client = OpenAI(api_key=OPENAI_API_KEY) if OPENAI_API_KEY else None

# ==========================================
# 📁 CONFIGURACIÓN DE BASE DE DATOS Y ARCHIVOS (Compatible con Render)
# ==========================================
# Para Render: usar volumen persistente o variables de entorno
RENDER_DISK_PATH = os.environ.get("RENDER_DISK_PATH", "/var/data")  # Render ofrece volúmenes persistentes
DATA_DIR = os.environ.get("DATA_DIR", RENDER_DISK_PATH)

# Crear directorio si no existe
os.makedirs(DATA_DIR, exist_ok=True)

# Ventana: cuántos mensajes pasados (usuario + bot) se mandan como contexto por llamada.
VENTANA_HISTORIAL = int(os.environ.get("VENTANA_HISTORIAL", "10"))
# Cuántos mensajes por número se conservan en disco (limpieza; no afecta lo que se manda a OpenAI).
MAX_GUARDADOS_POR_NUMERO = 30

DB_PATH = os.path.join(DATA_DIR, "historial_cess.db")
DATOS_FILE_PATH = os.path.join(DATA_DIR, "datosCESS.txt")

print(f"📁 Usando directorio de datos: {DATA_DIR}", flush=True)
print(f"🗄️ Base de datos SQLite: {DB_PATH}", flush=True)


def inicializar_db():
    """Inicializa la base de datos SQLite con tabla de historial."""
    try:
        con = sqlite3.connect(DB_PATH)
        con.execute("""
            CREATE TABLE IF NOT EXISTS historial (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                numero TEXT NOT NULL,
                rol TEXT NOT NULL,
                contenido TEXT NOT NULL,
                creado_en TEXT NOT NULL
            )
        """)
        con.execute("CREATE INDEX IF NOT EXISTS idx_historial_numero ON historial(numero)")
        con.commit()
        con.close()
        print(f"✅ Base de datos inicializada en {DB_PATH}", flush=True)
    except Exception as e:
        print(f"❌ Error inicializando la base de datos: {e}", flush=True)


def guardar_mensaje(numero: str, rol: str, contenido: str):
    """Guarda un mensaje en la base de datos."""
    try:
        con = sqlite3.connect(DB_PATH)
        con.execute(
            "INSERT INTO historial (numero, rol, contenido, creado_en) VALUES (?, ?, ?, ?)",
            (numero, rol, contenido, datetime.now(timezone.utc).isoformat()),
        )
        con.commit()
        con.close()
    except Exception as e:
        print(f"❌ Error guardando mensaje: {e}", flush=True)


def obtener_historial(numero: str, limite: int = None):
    """Devuelve los últimos `limite` mensajes de ese número, en orden cronológico,
    listos para pasarse como `input` a la Responses API."""
    if limite is None:
        limite = VENTANA_HISTORIAL
    try:
        con = sqlite3.connect(DB_PATH)
        filas = con.execute(
            "SELECT rol, contenido FROM historial WHERE numero = ? ORDER BY id DESC LIMIT ?",
            (numero, limite),
        ).fetchall()
        con.close()
        filas.reverse()  # de más viejo a más nuevo
        return [{"role": rol, "content": contenido} for rol, contenido in filas]
    except Exception as e:
        print(f"❌ Error obteniendo historial: {e}", flush=True)
        return []


def limpiar_historial_antiguo(numero: str):
    """Evita que la tabla crezca sin límite: conserva solo los últimos
    MAX_GUARDADOS_POR_NUMERO registros de ese número."""
    try:
        con = sqlite3.connect(DB_PATH)
        con.execute(
            """
            DELETE FROM historial
            WHERE numero = ? AND id NOT IN (
                SELECT id FROM historial WHERE numero = ? ORDER BY id DESC LIMIT ?
            )
            """,
            (numero, numero, MAX_GUARDADOS_POR_NUMERO),
        )
        con.commit()
        con.close()
    except Exception as e:
        print(f"❌ Error limpiando historial: {e}", flush=True)


# Inicializar base de datos al arrancar
inicializar_db()

# ==========================================
# 📋 CARGAR CONTEXTO PRIVADO
# ==========================================
contexto_privado = ""
try:
    # Intentar leer del archivo en el directorio de datos
    if os.path.exists(DATOS_FILE_PATH):
        with open(DATOS_FILE_PATH, "r", encoding="utf-8") as f:
            contexto_privado = f.read()
        print(f"✅ Contexto cargado desde {DATOS_FILE_PATH}", flush=True)
    else:
        # Si no existe, intentar leer de una variable de entorno (alternativa para Render)
        contexto_privado = os.environ.get("CONTEXTO_DATOS_CESS", "")
        if contexto_privado:
            print("✅ Contexto cargado desde variable de entorno CONTEXTO_DATOS_CESS", flush=True)
        else:
            print("⚠️ No se encontró archivo datosCESS.txt ni variable CONTEXTO_DATOS_CESS. Las respuestas de la IA podrían fallar.", flush=True)
except Exception as e:
    print(f"⚠️ Error cargando contexto: {e}", flush=True)

# ==========================================
# 🔧 DEFINICIÓN DE LA FUNCIÓN DE TRASPASO (Responses API)
# ==========================================
tools_traspaso = [
    {
        "type": "function",
        "name": "notificar_traspaso",
        "description": (
            "Notifica a un asesor humano que un prospecto está siendo transferido. "
            "Llámala junto con tu respuesta normal al cliente, nunca en lugar de ella."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "tipo": {
                    "type": "string",
                    "enum": ["listo_para_inscribir", "duda_sin_resolver", "tramite_administrativo"],
                    "description": "Motivo del traspaso.",
                },
                "programa": {
                    "type": "string",
                    "description": "Programa de interés del prospecto, si se conoce.",
                },
                "resumen": {
                    "type": "string",
                    "description": "1 línea de contexto para el asesor.",
                },
            },
            "required": ["tipo", "resumen"],
        },
    }
]

MENSAJES_RESPALDO = {
    "listo_para_inscribir": "¡Perfecto! Para continuar con tu inscripción, comunícate al número 6144150015 con el mensaje \"estoy listo para la inscripcion\" o haz clic en el siguiente enlace: https://wa.me/526144150015?text=estoy%20listo%20para%20la%20inscripcion",
    "duda_sin_resolver": "En un momento te atiende un asesor para resolver tu duda 🙂",
    "tramite_administrativo": "En un momento te atiende un asesor para ayudarte con ese trámite 🙂",
}
MENSAJE_RESPALDO_GENERICO = "En un momento te atiende un asesor 🙂"


@app.route('/', methods=['GET'])
def inicio():
    return "¡Servidor de WhatsApp e IA activo correctamente! 🚀", 200


@app.route('/health', methods=['GET'])
def health_check():
    """Health check para Render."""
    return jsonify({"status": "healthy"}), 200


@app.route('/webhook', methods=['GET'])
def verificar_webhook():
    """Verifica el webhook con Meta (WhatsApp)."""
    mode = request.args.get('hub.mode')
    token = request.args.get('hub.verify_token')
    challenge = request.args.get('hub.challenge')

    if mode and token:
        if mode == 'subscribe' and token == VERIFY_TOKEN:
            print(f"✅ Webhook verificado exitosamente", flush=True)
            return challenge, 200
        print(f"❌ Validación de webhook fallida. Token recibido: {token}", flush=True)
        return 'Validación fallida', 403
    print(f"❌ Webhook verificación con formato incorrecto", flush=True)
    return 'Mal formato', 400


@app.route('/webhook', methods=['POST'])
def recibir_mensaje():
    """Recibe y procesa mensajes de WhatsApp."""
    data = request.get_json()

    try:
        entries = data.get('entry', [])
        for entry in entries:
            changes = entry.get('changes', [])
            for change in changes:
                value = change.get('value', {})

                if change.get('field') != 'messages' or value.get('messaging_product') != 'whatsapp':
                    continue

                contacts = value.get('contacts', [])
                nombre_usuario = "Usuario"
                if contacts:
                    nombre_usuario = contacts[0].get('profile', {}).get('name', 'Usuario')

                metadata = value.get('metadata', {})
                phone_number_id = metadata.get('phone_number_id')

                messages = value.get('messages', [])
                for message in messages:
                    numero_usuario = message.get('from')

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
                        ad_context = f"\n[El usuario hizo clic en el anuncio de Facebook: '{headline}' - '{body}' (ID: {source_id})]"
                        if not texto_usuario:
                            texto_usuario = f"Hola, me interesa el anuncio: {headline}"

                    if texto_usuario:
                        print(f"📩 {nombre_usuario} ({numero_usuario}) dijo: {texto_usuario}", flush=True)

                        instrucciones_sistema = (
                            "Eres un asistente de servicio al cliente automatizado y amable.\n"
                            "Usa ÚNICAMENTE el siguiente contexto para responder la pregunta del usuario.\n"
                            "REGLA CRÍTICA: Si la respuesta no se encuentra explícitamente en el contexto, "
                            "sigue las reglas de escalamiento definidas en el contexto (mensaje de escalación + "
                            "llamada a la función notificar_traspaso). No inventes ni asumas información.\n\n"
                            f"Contexto:\n{contexto_privado}"
                        )

                        if ad_context:
                            instrucciones_sistema += (
                                f"\n\nContexto de origen del anuncio:\n{ad_context}\n"
                                "IMPORTANTE: Saluda amigablemente haciendo alusión al anuncio de forma natural "
                                "y prioriza la información del contexto privado relacionada con el tema del anuncio."
                            )

                        # --- Historial: últimos N turnos de este número + mensaje actual ---
                        historial_previo = obtener_historial(numero_usuario)
                        entrada_modelo = historial_previo + [{"role": "user", "content": texto_usuario}]

                        if not client:
                            print(f"❌ Cliente OpenAI no disponible. OPENAI_API_KEY no configurada.", flush=True)
                            enviar_whatsapp(numero_usuario, MENSAJE_RESPALDO_GENERICO, phone_number_id)
                            continue

                        response = client.responses.create(
                            model="gpt-4o-mini",
                            instructions=instrucciones_sistema,
                            input=entrada_modelo,
                            temperature=0,
                            max_output_tokens=2048,
                            store=True,
                            tools=tools_traspaso,
                        )

                        respuesta_final = response.output_text or ""

                        tipo_traspaso_detectado = None
                        for item in response.output:
                            if getattr(item, "type", None) == "function_call" and item.name == "notificar_traspaso":
                                try:
                                    datos = json.loads(item.arguments)
                                except json.JSONDecodeError:
                                    datos = {}

                                tipo_traspaso_detectado = datos.get("tipo")
                                etiqueta = {
                                    "listo_para_inscribir": "🔥 LISTO PARA INSCRIBIR",
                                    "duda_sin_resolver": "❓ DUDA SIN RESOLVER",
                                    "tramite_administrativo": "🗂 TRÁMITE ADMINISTRATIVO",
                                }.get(tipo_traspaso_detectado, tipo_traspaso_detectado or "TRASPASO")

                                aviso = (
                                    f"{etiqueta}\n"
                                    f"Programa: {datos.get('programa', 'N/A')}\n"
                                    f"Cliente: {nombre_usuario} ({numero_usuario})\n"
                                    f"Nota: {datos.get('resumen', 'Sin detalle')}"
                                )
                                enviar_whatsapp(NUMERO_ASESOR, aviso, phone_number_id)

                        if not respuesta_final:
                            respuesta_final = MENSAJES_RESPALDO.get(
                                tipo_traspaso_detectado, MENSAJE_RESPALDO_GENERICO
                            )
                        elif tipo_traspaso_detectado == "listo_para_inscribir":
                            # Asegurar que se le envíe la información de contacto para la inscripción
                            instruccion_inscripcion = (
                                "Para continuar con tu inscripción, comunícate al número 6144150015 con el mensaje "
                                "\"estoy listo para la inscripcion\" o haz clic en este enlace: "
                                "https://wa.me/526144150015?text=estoy%20listo%20para%20la%20inscripcion"
                            )
                            if "6144150015" not in respuesta_final and "614 415 0015" not in respuesta_final:
                                respuesta_final = respuesta_final.strip() + "\n\n" + instruccion_inscripcion

                        enviar_whatsapp(numero_usuario, respuesta_final, phone_number_id)
                        print(f"🤖 Chatbot respondió: {respuesta_final}", flush=True)

                        # --- Guardar el turno en el historial (usuario + respuesta del bot) ---
                        guardar_mensaje(numero_usuario, "user", texto_usuario)
                        guardar_mensaje(numero_usuario, "assistant", respuesta_final)
                        limpiar_historial_antiguo(numero_usuario)

    except Exception as e:
        print(f"❌ Error interno procesando el flujo de Meta: {e}", flush=True)
        import traceback
        traceback.print_exc()

    return jsonify({"status": "success"}), 200


def enviar_whatsapp(number, text, phone_number_id=None):
    """Envía un mensaje de texto por WhatsApp."""
    if not phone_number_id:
        phone_number_id = PHONE_NUMBER_ID
    
    if not all([META_TOKEN, phone_number_id]):
        print(f"❌ Error: META_TOKEN o PHONE_NUMBER_ID no configurados", flush=True)
        return
    
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
    try:
        res = requests.post(url, json=payload, headers=headers)
        if res.status_code != 200:
            print(f"⚠️ Error enviando mensaje a {number}: {res.status_code} - {res.text}", flush=True)
        else:
            print(f"✅ Mensaje enviado a {number}", flush=True)
    except Exception as e:
        print(f"❌ Error en enviar_whatsapp: {e}", flush=True)


if __name__ == '__main__':
    # Render asigna dinámicamente el puerto mediante la variable PORT
    port = int(os.environ.get("PORT", 5000))
    print(f"🚀 Iniciando servidor en puerto {port}", flush=True)
    
    from waitress import serve
    serve(app, host='0.0.0.0', port=port)
