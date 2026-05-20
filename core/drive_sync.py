import io
import os
import shutil
import tempfile
from datetime import datetime

from googleapiclient.http import MediaFileUpload, MediaIoBaseDownload

from core.file_manager import get_local_mtime, compress_folder, extract_zip


def _find_file_in_folder(service, filename, folder_id):
    """Return Drive file metadata (id, name, modifiedTime) or None.
       - query: File with their file folder
       - results: List of the files on each folder of drive
       - files: Files list
    """
    query = f"name = '{filename}' and '{folder_id}' in parents and trashed = false"
    results = service.files().list(q=query, fields="files(id, name, modifiedTime)").execute()
    files = results.get('files', [])
    return files[0] if files else None


def _drive_time_to_timestamp(drive_time_str):
    """Convert Drive string to Unix timestamp."""
    dt = datetime.fromisoformat(drive_time_str.replace('Z', '+00:00'))
    return dt.timestamp()


def check_status(service, emulator_key, emulator_data):
    """
    Compare local vs Drive modification times.

    Returns:
        - dict with keys: status, local_mtime, drive_mtime
        - status values: not_configured | not_in_cloud | up_to_date |
                       upload_pending | download_pending
    """
    local_path = emulator_data.get('local_path', '')
    folder_id = emulator_data.get('drive_id', '')
    save_type = emulator_data.get('save_type', 'file')

    if not local_path or not folder_id:
        return {'status': 'not_configured', 'local_mtime': None, 'drive_mtime': None}

    local_mtime = get_local_mtime(local_path, save_type) # Get the time of the last modification from the local file - Obtiene el tiempo de la ultima modificacion en el archivo local

    if save_type == 'folder':
        zip_name = f"{emulator_key}_saves.zip"
        drive_file = _find_file_in_folder(service, zip_name, folder_id)
    else:
        # Get most recently modified file in the Drive folder - Obtiene la fecha de la ultima modificacion del archivo en el drive
        query = f"'{folder_id}' in parents and trashed = false"
        results = service.files().list(
            q=query,
            fields="files(id, name, modifiedTime)",
            orderBy="modifiedTime desc",
            pageSize=1
        ).execute()
        files = results.get('files', [])
        drive_file = files[0] if files else None

    if not drive_file: # If theres no data on the drive folder of the emulator saves  - Si no hay datos en el folder del drive
        return {'status': 'not_in_cloud', 'local_mtime': local_mtime, 'drive_mtime': None}

    drive_mtime = _drive_time_to_timestamp(drive_file['modifiedTime'])

    if local_mtime is None:
        return {'status': 'download_pending', 'local_mtime': None, 'drive_mtime': drive_mtime}

    # Within 60 seconds → treat as in sync (upload modifies the Drive timestamp slightly) - Syn, al subir un archivo siempre se modifica el timestap de drive de acuerdo a este nuevo registro de tiempo (Al final es no mas un refresh de la consulta lol)
    if abs(local_mtime - drive_mtime) < 60:
        status = 'up_to_date'
    elif local_mtime > drive_mtime:
        status = 'upload_pending'
    else:
        status = 'download_pending'

    return {'status': status, 'local_mtime': local_mtime, 'drive_mtime': drive_mtime}


def upload_file(service, filepath, folder_id):
    """Upload a single file, updating it if it already exists in Drive."""
    filename = os.path.basename(filepath) # Local file - Archivo local
    existing = _find_file_in_folder(service, filename, folder_id) # Search if the file exist on objective drive folder - Busca si existe el archivo en el folder objetivo de drive
    media = MediaFileUpload(filepath, mimetype='application/octet-stream', resumable=True) # Api stuff

    if existing: # If exist the old file is updated with the new file - Si existe actualiza la file vieja por la nueva
        service.files().update(fileId=existing['id'], media_body=media).execute()
        return {'success': True, 'action': 'updated', 'filename': filename}
    else:
        metadata = {'name': filename, 'parents': [folder_id]}
        service.files().create(body=metadata, media_body=media, fields='id').execute()
        return {'success': True, 'action': 'created', 'filename': filename}


def upload_folder(service, folder_path, folder_id, emulator_key):
    """Compress folder as ZIP and upload to Drive (Some emulator saves all the data on a folder so yeah this is the easiest work around. I mean we can still trying to load each save like we do on melon DS emulator but its more complex because they use more than 1 file as a save for every game and it doesn't have pretty intuitive names. Yeah.), replacing any existing ZIP."""
    zip_name = f"{emulator_key}_saves.zip" # The zip saves with the console name - El nombre del zip tiene el nombre de la consola
    raw_zip = compress_folder(folder_path)
    temp_dir = os.path.dirname(raw_zip) # We use the temp dir to dont consume real space - Usamos el directorio temporal para no consumir espacio real, luego se liberara al terminar el proceso
    named_zip = os.path.join(temp_dir, zip_name)

    try:
        os.rename(raw_zip, named_zip)
        existing = _find_file_in_folder(service, zip_name, folder_id)
        media = MediaFileUpload(named_zip, mimetype='application/zip', resumable=True)

        if existing: # Same logi of the other uploads - Misma logica de las demas subidas de archivos
            service.files().update(fileId=existing['id'], media_body=media).execute()
            action = 'updated'
        else:
            metadata = {'name': zip_name, 'parents': [folder_id]}
            service.files().create(body=metadata, media_body=media, fields='id').execute()
            action = 'created'

        return {'success': True, 'action': action, 'filename': zip_name}
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def download_files(service, folder_id, dest_dir, save_type, emulator_key):
    """
    Download saves from Drive to dest_dir.
    Its important to understand the type of files:
    - folder type: downloads ZIP on temp and extracts contents into dest_dir.
    - file/dual_file type: downloads all files directly into dest_dir.
    """
    if save_type == 'folder': # This is the workflow for the folders - Workflow para los salvados tipo carpeta
        zip_name = f"{emulator_key}_saves.zip"
        drive_file = _find_file_in_folder(service, zip_name, folder_id)
        if not drive_file:
            return {'success': False, 'error': 'no_files'}

        temp_dir = tempfile.mkdtemp() # path of the temp dir - path al directiorio temporal
        temp_zip = os.path.join(temp_dir, zip_name) # The temp dir and the zip name - Informacion del directorio temporal y el nombre del zip
        try:
            _download_to_path(service, drive_file['id'], temp_zip)
            extract_zip(temp_zip, dest_dir) # Extract the file from the zip on the temp dir to the dest dir - Extrae el archivo dentro del zip en el directorio temporal al directorio de destino
            return {'success': True, 'filename': zip_name}
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)
    else: # Workflow for the other files - Workflow para los demas archivos, no ocupan un trato especial ya que solo bajas lo que hay en la carpeta 
        query = f"'{folder_id}' in parents and trashed = false"
        results = service.files().list(q=query, fields="files(id, name)").execute()
        files = results.get('files', [])

        if not files:
            return {'success': False, 'error': 'no_files'}

        os.makedirs(dest_dir, exist_ok=True)
        downloaded = []
        for f in files:
            dest_path = os.path.join(dest_dir, f['name'])
            _download_to_path(service, f['id'], dest_path)
            downloaded.append(f['name'])

        return {'success': True, 'files': downloaded}


def _download_to_path(service, file_id, dest_path):
    """Download a Drive file by chunks to dest_path."""
    request = service.files().get_media(fileId=file_id) # Drive api stuff, is to avoid saturated the reuquest and to improve the download, but yeah just api stuff 
    with io.FileIO(dest_path, 'wb') as fh:
        downloader = MediaIoBaseDownload(fh, request)
        done = False
        while not done:
            _, done = downloader.next_chunk()


def list_saves_with_status(service, folder_id, local_path, extension):
    """
    Melon DS saves each save file as a .sav for every game played. 
    For multi_file emulators this def list every .sav file in both
    the local folder and Drive, merging them into one list with sync status. (In order to manage every sav as a indy item)

    Uses a single Drive API call to fetch all files in the folder at once,
    then does O(1) dict lookups per local file — no N-per-file requests.

    Returns a list of dicts:
        filename   – bare filename (e.g. "Mario.sav")
        filepath   – absolute local path, or None if only in Drive
        local_mtime – Unix timestamp or None
        drive_mtime – Unix timestamp or None
        status     – not_in_cloud | up_to_date | upload_pending | download_pending
    """
    # Fetch all Drive files(In the folder id) in one request - Todos los archivo del drive(de este folder id) se consultan
    query = f"'{folder_id}' in parents and trashed = false"
    results = service.files().list(
        q=query, fields="files(id, name, modifiedTime)"
    ).execute()
    # Build a dict keyed by filename; pop() removes matched entries - Drive files es un diccionario con la iformacion de los archivos dentro de la carpeta
    drive_files = {f['name']: f for f in results.get('files', [])}

    saves = []

    if os.path.isdir(local_path): # We assosiate the files that exist on both and declare a status from them - Asociamos aquellos archivos que existen en local y en drive y se les asigna un status
        for fname in sorted(os.listdir(local_path)):
            if not fname.endswith(extension):
                continue
            fpath = os.path.join(local_path, fname)
            local_mtime = os.path.getmtime(fpath)
            drive_file = drive_files.pop(fname, None)

            if drive_file:
                drive_mtime = _drive_time_to_timestamp(drive_file['modifiedTime'])
                if abs(local_mtime - drive_mtime) < 60:
                    status = 'up_to_date'
                elif local_mtime > drive_mtime:
                    status = 'upload_pending'
                else:
                    status = 'download_pending'
            else:
                drive_mtime = None
                status = 'not_in_cloud'

            saves.append({
                'filename':    fname,
                'filepath':    fpath,
                'local_mtime': local_mtime,
                'drive_mtime': drive_mtime,
                'status':      status,
            })

    # Remaining drive_files entries exist only in Drive - Los archivos restantes no tienen contraparte local solo en drive
    for fname, drive_file in sorted(drive_files.items()):
        saves.append({
            'filename':    fname,
            'filepath':    None,
            'local_mtime': None,
            'drive_mtime': _drive_time_to_timestamp(drive_file['modifiedTime']),
            'status':      'download_pending',
        })

    return saves


def download_file_to_path(service, filename, folder_id, dest_path):
    """Download a specific named file from a Drive folder to dest_path."""
    drive_file = _find_file_in_folder(service, filename, folder_id)
    if not drive_file:
        return {'success': False, 'error': 'not_found'}
    os.makedirs(os.path.dirname(dest_path), exist_ok=True)
    _download_to_path(service, drive_file['id'], dest_path)
    return {'success': True}
