# 🚀 Guía de Despliegue en Render

## Configuración para Render

Este bot de WhatsApp está configurado para ejecutarse en **Render** (antes Heroku).

### 📋 Requisitos Previos

1. Cuenta en [render.com](https://render.com)
2. Variables de entorno de Meta (WhatsApp Business API)
3. API Key de OpenAI
4. Repositorio GitHub conectado

### 🔧 Variables de Entorno en Render

En la sección **Environment** de tu servicio en Render, configura estas variables:

```
OPENAI_API_KEY=tu_api_key_de_openai
META_TOKEN=tu_token_de_meta
PHONE_NUMBER_ID=tu_numero_de_telefono_id
VERIFY_TOKEN=tu_token_de_verificacion_personalizado
NUMERO_ASESOR=numero_whatsapp_del_asesor
VENTANA_HISTORIAL=10
CONTEXTO_DATOS_CESS=contenido_del_contexto_o_dejar_en_blanco
```

> **Nota:** Las variables se leen automáticamente. No incluyas valores sensibles en el código.

### 📁 Almacenamiento Persistente

Render ofrece un **volumen persistente** para guardar datos entre reinicios:

1. Ve a tu servicio en Render
2. Abre **Disk** en la configuración
3. Crea un volumen con:
   - **Name:** `data`
   - **Mount Path:** `/var/data`
4. El código automáticamente usará este directorio para:
   - Base de datos SQLite (`historial_cess.db`)
   - Archivo de contexto (`datosCESS.txt`)

### 🌐 Conectar WhatsApp Webhook

1. Obtén la URL de tu servicio Render: `https://tu-servicio.onrender.com`
2. En Meta App Dashboard → WhatsApp → Configuración:
   - **Webhook URL:** `https://tu-servicio.onrender.com/webhook`
   - **Verify Token:** El mismo que configuraste en `VERIFY_TOKEN`

### 🔄 Desplegar cambios

Solo necesitas hacer `git push`. Render se sincroniza automáticamente y redeploy.

### ✅ Health Check

El servicio incluye un endpoint de salud:
```
GET https://tu-servicio.onrender.com/health
```

### 📊 Monitorar Logs

En el dashboard de Render puedes ver los logs en tiempo real.

### 🔒 Seguridad

- Los tokens están seguros en variables de entorno
- La base de datos está en el volumen persistente (no versionada)
- No incluyas `.env` en git (está en `.gitignore`)

### ⚡ Rendimiento

- **Plan Free:** Suficiente para bots de bajo volumen
- **Plan Starter:** Recomendado para producción
- El servidor Waitress maneja concurrencia automáticamente

### 🆘 Troubleshooting

#### El webhook no se verifica
- Verifica que `VERIFY_TOKEN` coincida en Render y en Meta
- Revisa los logs en Render dashboard

#### Base de datos no persiste
- Confirma que el volumen está montado en `/var/data`
- Reinicia el servicio

#### OpenAI API Key no funciona
- Valida la API key en https://platform.openai.com
- Verifica que la cuenta tenga saldo disponible

---

**¡Tu bot está listo para producción en Render! 🎉**
