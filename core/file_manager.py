import json
import os
import shutil
import sys
import tempfile
from pathlib import Path

from core.utils import resource_path, app_dir


# ----------------------------------------------------------------
# Rutas de config.json
#
# En modo bundle (.exe):
#   - Lectura/escritura → app_dir()/data/config.json  (escribible, junto al .exe)
#   - Primera ejecución → copia automática desde el bundle (sys._MEIPASS)
#
# En modo desarrollo:
#   - Lectura/escritura → resource_path('data/config.json')  (raíz del proyecto)
# ----------------------------------------------------------------

def _config_path() -> str:
    """Devuelve la ruta escribible de config.json según el entorno."""
    if getattr(sys, 'frozen', False):
        user_path = Path(app_dir()) / 'data' / 'config.json'
        if not user_path.exists():
            # Primera ejecución del .exe: copiar el config por defecto del bundle
            user_path.parent.mkdir(parents=True, exist_ok=True)
            bundled = Path(resource_path('data/config.json'))
            shutil.copy2(bundled, user_path)
        return str(user_path)
    return resource_path('data/config.json')


def load_config():
    with open(_config_path(), 'r', encoding='utf-8') as f:
        return json.load(f)


def save_config(config):
    with open(_config_path(), 'w', encoding='utf-8') as f:
        json.dump(config, f, ensure_ascii=False, indent=2)


def load_lang(lang_code):
    # Los archivos de idioma son assets de solo lectura — siempre desde resource_path
    lang_path = resource_path(f'lang/{lang_code}.json')
    with open(lang_path, 'r', encoding='utf-8') as f:
        return json.load(f)


def get_local_mtime(local_path, save_type):
    """Return the most recent modification timestamp for saves on the local path, or None."""
    path = Path(local_path)
    if not path.exists():
        return None

    if save_type == 'folder':
        mtimes = [f.stat().st_mtime for f in path.rglob('*') if f.is_file()]
    else:
        if path.is_dir():
            mtimes = [f.stat().st_mtime for f in path.iterdir() if f.is_file()]
        else:
            return path.stat().st_mtime

    return max(mtimes) if mtimes else None


def compress_folder(folder_path):
    """Compress folder contents into a temp ZIP. Returns the ZIP file path."""
    temp_dir = tempfile.mkdtemp()
    zip_base = os.path.join(temp_dir, 'saves')
    zip_path = shutil.make_archive(zip_base, 'zip', folder_path)
    return zip_path


def extract_zip(zip_path, dest_path):
    """Extract ZIP contents directly into dest_path."""
    os.makedirs(dest_path, exist_ok=True)
    shutil.unpack_archive(zip_path, dest_path, 'zip')
