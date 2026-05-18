import sys
from pathlib import Path
from tkinter import Tk, Canvas, Button, PhotoImage, messagebox
import os
from pathlib import Path
from tkinter import filedialog
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
import io
from googleapiclient.http import MediaIoBaseDownload

def resource_path(relative_path):
    try:
        base_path = sys._MEIPASS
    except AttributeError:
        base_path = os.path.dirname(os.path.abspath(__file__))

    return os.path.join(base_path, relative_path)

# --- CONFIG ---
SCOPES = ['https://www.googleapis.com/auth/drive.file']
BASE_DIR = Path(__file__).resolve().parent
PARENT_FOLDER_ID = ""
EMULATOR_SELECTED = ""
EMULATOR_SAVE_TYPE = ""
OUTPUT_PATH = Path(__file__).parent
ASSETS_PATH = Path(resource_path("assets"))

# --- TKINTER ASSETS PATH ---
def relative_to_assets(path: str) -> Path:
    return ASSETS_PATH / Path(path)

# --- AUTHENTICATE ---
def authenticate():
    creds = None
    token_path = Path(resource_path("token.json"))
    creds_path = Path(resource_path("credentials.json"))

    if token_path.exists():
        creds = Credentials.from_authorized_user_file(str(token_path), SCOPES)
    
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(str(creds_path), SCOPES)
            creds = flow.run_local_server(port=0)
        
        with open(token_path, 'w') as token:
            token.write(creds.to_json())
    return creds

# --- SAVE THE FILES ---
def upload_save_file(paths):
    creds = authenticate()
    service = build('drive', 'v3', credentials=creds)

    for i, path in enumerate(paths, 1):
        if not path: continue
        filename = os.path.basename(path)
        
        # Search for an file with the same name - Busca si el archivo ya existe
        query = f"name = '{filename}' and '{PARENT_FOLDER_ID}' in parents and trashed = false"
        results = service.files().list(q=query, fields="files(id)").execute()
        files = results.get('files', [])

        media = MediaFileUpload(path, mimetype='application/octet-stream')

        if files:
            # If theres a file with that name - Si hay un archivo con ese nombre
            file_id = files[0]['id']
            file = service.files().update(
                fileId=file_id,
                media_body=media
            ).execute()
            status = "Actualizado"
        else:
            # If theres no file with that name - Si no hay archivos con ese nombre
            file_metadata = {'name': filename, 'parents': [PARENT_FOLDER_ID]}
            file = service.files().create(
                body=file_metadata,
                media_body=media,
                fields='id'
            ).execute()
            status = "Creado"
            
        messagebox.showinfo("¡Listo!",f"{filename} {status} con ID: {file.get('id')}")

# --- START SAVE PROCESS ---
def Save():
    if EMULATOR_SELECTED == "ps2":
        print("Selecciona tus Memory Cards...")
        mc1 = filedialog.askopenfilename(title="MC 1", filetypes=[("PS2 Save", "*.ps2")])
        mc2 = filedialog.askopenfilename(title="MC 2", filetypes=[("PS2 Save", "*.ps2")])
    
        if mc1 or mc2:
            upload_save_file([mc1, mc2])
            messagebox.showinfo("¡Listo!","Se han guardado tus partidas")
        else:
            messagebox.showinfo("¡Listo!","Cancelado.")
            #print("Cancelado.")
    else:
        print("Selecciona tus archivos de guardado...")
        save1 = filedialog.askopenfilename(title="SAVE 1", filetypes=[(EMULATOR_SELECTED + " save", EMULATOR_SAVE_TYPE)])               
        if save1:
            upload_save_file([save1])
            messagebox.showinfo("¡Listo!","Se han guardado tus partidas")
        else:
            messagebox.showinfo("¡Listo!","Cancelado.")
            #print("Cancelado.")

# --- DOWNLOAD THE FILES ---
def download_save_file():
    creds = authenticate()
    service = build('drive', 'v3', credentials=creds)

    # Ask for the save path - Pregunta donde se guardan los archivos
    folder_selected = filedialog.askdirectory(title="Selecciona donde guardaras tus partidas")
    if not folder_selected:
        return

    # Search if theres any file on the Drive folder - Busca si existen archivos en drive
    query = f"'{PARENT_FOLDER_ID}' in parents and trashed = false"
    results = service.files().list(q=query, fields="files(id, name)").execute()
    files = results.get('files', [])
    print(files)

    # If theres no files - Si no hay archivos
    if not files:
        messagebox.showwarning("-Error-", "No se encontraron partidas en la nube.")
        return
    # If theres files - Si hay archivos
    for f in files:
        file_id = f['id']
        file_name = f['name']
        request = service.files().get_media(fileId=file_id)
        
        dest_path = os.path.join(folder_selected, file_name)
        fh = io.FileIO(dest_path, 'wb')
        downloader = MediaIoBaseDownload(fh, request)
        
        done = False
        while done is False:
            status, done = downloader.next_chunk()
        
        messagebox.showinfo("¡Listo!", f"{file_name} descargado en {dest_path}")
    
    messagebox.showinfo("¡Listo!", "Partidas descargadas y listas para jugar.")
    
# --- SYSTEM EMULATOR SELECTION ---
def emulator_select():
    global PARENT_FOLDER_ID
    global EMULATOR_SELECTED
    global EMULATOR_SAVE_TYPE
    EMULATOR_SELECTED = input("Elige el emulador: ")
    
    # Separados por nombre de sistema y posteriormente directorio en drive
    emulators_dict = {"ps2": "", "ds": "", "3ds": "", "psp": "", "test": ""} #Reemplace here with your Drive folder ID - Remplazalo por el ID de tu Folder en Drive
    
    # Separados por nombre de sistema y posteriormente tipo de archivos de salvado * equivale a que se guarda una carpeta completa
    emulators_save_type = {"ps2": "*.ps2", "ds": "*.sav", "3ds": "*", "psp": "*", "test": "*"}
    
    # Acceso directo
    PARENT_FOLDER_ID = emulators_dict[EMULATOR_SELECTED.lower()]
    EMULATOR_SAVE_TYPE = emulators_save_type[EMULATOR_SELECTED.lower()]
    print(PARENT_FOLDER_ID)
    selection = input("Elige 1 para salvar partidas y 2 para descargar partidas: ")
    selection =int(selection)
    if selection == 1:
        Save()
    elif selection == 2:
         download_save_file()
    else:
        print("Elije una opcion valida")
        emulator_select()

emulator_select()