from pathlib import Path
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow

from core.utils import resource_path
# --- CONFIG ---
SCOPES = ['https://www.googleapis.com/auth/drive.file']

# --- AUTHENTICATE ---
def authenticate():
    creds = None
    token_path = Path(resource_path("token.json")) # Token creates when you login the first time - Se crea cuando inicias sesion por primera vez
    creds_path = Path(resource_path("credentials.json")) # Its the json you downloaded from google cloud console - Estas credenciales son las que descargas desde Google Cloud Console

    if token_path.exists():
        creds = Credentials.from_authorized_user_file(str(token_path), SCOPES) # If token exist it trys to use it - Si existe el archivo con el token intetna utlilziarlo para ahorrar el inicio de sesion

    if not creds or not creds.valid: # Check if cred stills valid  - Verifica si las credenciales aun son validas
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request()) # If token is expired it will try to get a new one without asking for login - Si esta vencido el token intentara obtenerlo sin solicitar un nuevo login
        else: # If theres no token it creates one when asking the user to login - Si no existe el token abrira el navegador y le pedira al user loguearse
            flow = InstalledAppFlow.from_client_secrets_file(str(creds_path), SCOPES) 
            creds = flow.run_local_server(port=0)

        with open(token_path, 'w') as token:
            token.write(creds.to_json())

    return creds
