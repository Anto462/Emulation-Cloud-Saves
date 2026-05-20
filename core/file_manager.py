import json
import os
import shutil
import tempfile
from pathlib import Path

from core.utils import resource_path


def load_config(): # Load the data from the json
    config_path = resource_path("data/config.json")
    with open(config_path, 'r', encoding='utf-8') as f:
        return json.load(f)


def save_config(config): # Save data on the json
    config_path = resource_path("data/config.json")
    with open(config_path, 'w', encoding='utf-8') as f:
        json.dump(config, f, ensure_ascii=False, indent=2)


def load_lang(lang_code): # This loads a lang json, I will probablly first add spanish and english - Este es un json que se usa como base para soportar disntintos idiomas, inicialmente busco soportar español e ingles
    lang_path = resource_path(f"lang/{lang_code}.json")
    with open(lang_path, 'r', encoding='utf-8') as f:
        return json.load(f)


def get_local_mtime(local_path, save_type):
    """Return the most recent modification timestamp for a saves on the local path, or None.
       Helps to compare the time with the drive time   
    """
    path = Path(local_path)
    if not path.exists():
        return None

    if save_type == "folder":
        mtimes = [f.stat().st_mtime for f in path.rglob('*') if f.is_file()]
    else:
        # dual_file / file: check all files directly inside the directory
        if path.is_dir():
            mtimes = [f.stat().st_mtime for f in path.iterdir() if f.is_file()]
        else:
            return path.stat().st_mtime

    return max(mtimes) if mtimes else None


def compress_folder(folder_path):
    """Compress folder contents into a temp ZIP. 
       Returns the ZIP file path.
       
       zip_base: The folder zip and the path to it
    """
    temp_dir = tempfile.mkdtemp()
    zip_base = os.path.join(temp_dir, "saves")
    # Archives contents of folder_path at root level (no top-level folder inside ZIP) - Crear el Zip con los archivos dentro de la carpeta selecionada, no comprime la cerpeta en si. Por ejemplo si la ruta es xxxx/xxxx/Saves/ el comprime todo lo que esta dentro de Saves pero no la carpeta Saves como tal
    zip_path = shutil.make_archive(zip_base, 'zip', folder_path)
    return zip_path


def extract_zip(zip_path, dest_path):
    """Extract ZIP contents directly into dest_path."""
    os.makedirs(dest_path, exist_ok=True)
    shutil.unpack_archive(zip_path, dest_path, 'zip')
