import requests
import json

url = "https://disorganizedly-interasteroidal-nathanial.ngrok-free.dev/webhook"
headers = {
    "Content-Type": "application/json"
}

payload = {
  "object": "whatsapp_business_account",
  "entry": [
    {
      "id": "102290129340398",
      "changes": [
        {
          "value": {
            "messaging_product": "whatsapp",
            "metadata": {
              "display_phone_number": "15550783881",
              "phone_number_id": "1204727649384372"
            },
            "contacts": [
              {
                "profile": {
                  "name": "Sheena Nelson"
                },
                "wa_id": "16505551234"
              }
            ],
            "messages": [
              {
                "referral": {
                  "source_url": "https://fb.me/3cr4Wqqkv",
                  "source_id": "120226305854810726",
                  "source_type": "ad",
                  "body": "Summer Succulents are here!",
                  "headline": "Chat with us",
                  "media_type": "image",
                  "image_url": "https://scontent.xx.fbcdn.net/v/t45.1...",
                  "ctwa_clid": "Aff-n8ZTODiE79d22KtAwQKj9e_mIEOOj27vDVwFjN80dp4_0NiNhEgpGo0AHemvuSoifXaytfTzcchptiErTKCqTrJ5nW1h7IHYeYymGb5K5J5iTROpBhWAGaIAeUzHL50",
                  "welcome_message": {
                    "text": "Hi there! Let us know how we can help!"
                  }
                },
                "from": "16505551234",
                "id": "wamid.HBgLMTY1MDM4Nzk0MzkVAgASGBQzQUQ0N0VFMDA2MTQ0RkJFNkNDNAA=",
                "timestamp": "1750275992",
                "text": {
                  "body": "Can I get more info about this?"
                },
                "type": "text"
              }
            ]
          },
          "field": "messages"
        }
      ]
    }
  ]
}

print("Enviando webhook simulado...")
try:
    response = requests.post(url, json=payload, headers=headers)
    print(f"Estado HTTP: {response.status_code}")
    print(f"Respuesta del servidor: {response.text}")
except Exception as e:
    print(f"Error al conectar con el servidor: {e}")
