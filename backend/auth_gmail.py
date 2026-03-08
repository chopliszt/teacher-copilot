import os
import sys

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow

# Scopes definen qué permisos le pedimos a Google.
# gmail.modify nos permite leer, y también marcar como leído o mover a carpetas si lo necesitamos luego.
SCOPES = ["https://www.googleapis.com/auth/gmail.modify"]

CREDENTIALS_FILE = "credentials-google-connection.json"
TOKEN_FILE = "token.json"


def main():
    if not os.path.exists(CREDENTIALS_FILE):
        print(f"❌ Error: No se encontró el archivo '{CREDENTIALS_FILE}'.")
        print(
            "Asegúrate de haberlo descargado de Google Cloud y guardado en la carpeta 'backend/'."
        )
        sys.exit(1)

    creds = None

    # 1. Verificamos si ya existe un token.json
    if os.path.exists(TOKEN_FILE):
        print("🔄 Se encontró un token.json existente. Verificando validez...")
        creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)

    # 2. Si no hay token, o el token ya no es válido, hacemos el flujo de login
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            print("🔄 El token expiró. Intentando refrescarlo automáticamente...")
            try:
                creds.refresh(Request())
            except Exception as e:
                print(
                    f"⚠️ No se pudo refrescar el token ({e}). Vamos a pedir uno nuevo."
                )
                creds = None

        if not creds:
            print("🌐 Abriendo el navegador para autorizar la aplicación...")
            # Usar puerto 8080 fijo para que coincida con el Redirect URI de Google
            flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_FILE, SCOPES)
            creds = flow.run_local_server(port=8080)

        # 3. Guardamos el string del token para que Marimba lo use en el futuro sin molestarte
        with open(TOKEN_FILE, "w") as token:
            token.write(creds.to_json())
            print(f"✅ ¡Éxito! Tu acceso se ha guardado en '{TOKEN_FILE}'.")

    print("✨ Autenticación completada y válida. Marimba ya tiene su llave de Gmail.")


if __name__ == "__main__":
    main()
