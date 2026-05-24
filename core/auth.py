from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow

from core.utils import resource_path, app_dir

# --- CONFIG ---
SCOPES = ['https://www.googleapis.com/auth/drive.file']


def _token_path():
    """
    token.json debe estar en un directorio escribible.
    - Bundle (.exe): junto al .exe (app_dir())
    - Dev:           raíz del proyecto (resource_path())
    """
    return Path(app_dir()) / 'token.json'


def _credentials_path():
    """
    credentials.json: primero busca uno importado manualmente por el usuario
    en app_dir() (tiene prioridad). Si no existe, cae al bundleado en el .exe.
    """
    user_path = Path(app_dir()) / 'credentials.json'
    if user_path.exists():
        return user_path
    return Path(resource_path('credentials.json'))


# --- AUTHENTICATE ---
def authenticate():
    creds = None
    token_path = _token_path()
    creds_path = _credentials_path()

    if token_path.exists():
        creds = Credentials.from_authorized_user_file(str(token_path), SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(str(creds_path), SCOPES)
            creds = flow.run_local_server(port=0)

        # Guardar el token en un directorio escribible
        token_path.parent.mkdir(parents=True, exist_ok=True)
        with open(token_path, 'w') as f:
            f.write(creds.to_json())

    return creds
