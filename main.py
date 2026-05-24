"""
main.py — comand to build the .exe

python -m PyInstaller main.py --onefile --noconsole --name "CloudSaveHub" --add-data "ui;ui" --add-data "data;data" --add-data "lang;lang" --add-data "assets;assets" --collect-all webview --hidden-import="webview.platforms.winforms" --hidden-import="clr" --hidden-import="google.auth.transport.requests" --hidden-import="google.oauth2.credentials" --hidden-import="google_auth_oauthlib.flow" --icon "Cloudemustorage.ico"

"""

import os
import re
import shutil
import ctypes
import ctypes.wintypes

import webview
from googleapiclient.discovery import build

from core.auth import authenticate
from core.drive_sync import (
    check_status, upload_file, upload_folder, download_files,
    list_saves_with_status, download_file_to_path,
)
from core.file_manager import load_config, save_config, load_lang
from core.utils import resource_path, app_dir


# ============================================================
# TÍTULO DE VENTANA 
# ============================================================

def _apply_dark_frame(*_):
    """
    Cambia el color de la barra de título a near-black y el borde
    a rojo usando la API DWM de Windows (disponible en Windows 11+).

    Se llama desde window.events.loaded para que el HWND ya exista.

    COLORREF format: 0x00BBGGRR (azul/verde/rojo en bytes)
      #0f0f0f → R=0x0f G=0x0f B=0x0f → COLORREF = 0x000f0f0f
      #cc0000 → R=0xcc G=0x00 B=0x00 → COLORREF = 0x000000cc
    """
    try:
        FindWindowW = ctypes.windll.user32.FindWindowW
        FindWindowW.restype = ctypes.wintypes.HWND
        hwnd = FindWindowW(None, 'Cloud Save Hub')
        if not hwnd:
            return

        DWMWA_BORDER_COLOR  = 34   # color del borde exterior de la ventana
        DWMWA_CAPTION_COLOR = 35   # color de fondo de la barra de título

        # Barra de título: negro profundo para que no rompa la paleta
        caption = ctypes.c_uint32(0x000f0f0f)
        ctypes.windll.dwmapi.DwmSetWindowAttribute(
            hwnd, DWMWA_CAPTION_COLOR,
            ctypes.byref(caption), ctypes.sizeof(caption)
        )
        # Borde: rojo acento igual que las barras verticales de las tarjetas
        border = ctypes.c_uint32(0x000000cc)
        ctypes.windll.dwmapi.DwmSetWindowAttribute(
            hwnd, DWMWA_BORDER_COLOR,
            ctypes.byref(border), ctypes.sizeof(border)
        )
    except Exception:
        pass  # Windows 10 u otros OS — ignorar silenciosamente


# ============================================================
# API
# ============================================================

class Api:
    """
    Cada método público de esta clase se vuelve accesible desde JavaScript.
    PyWebView lo expone automáticamente bajo: window.pywebview.api.nombre()

    Reglas importantes:
    - Los parámetros que llegan de JS son Python nativo (dict, list, str, int).
    - Los valores que retornas se convierten a JSON para JS.
    - Los métodos se ejecutan en hilos secundarios (no bloquean la UI).
    """

    def __init__(self):
        self._window  = None   # Se asigna después de crear la ventana (ver main())
        self._service = None   # Cliente autenticado de Google Drive API
        self._config  = load_config()
        self._t       = load_lang(self._config['settings']['language'])
        # Cache de estados: { "ps2": { status, local_mtime, drive_mtime }, ... }
        self._last_statuses: dict = {}

    # ----------------------------------------------------------------
    # Consultas rápidas (sin red)
    # ----------------------------------------------------------------

    def get_config(self):
        """Devuelve data/config.json completo. JS lo recibe como objeto."""
        return self._config

    def get_lang(self):
        """Devuelve el diccionario del idioma activo (es.json o en.json)."""
        return self._t

    def get_statuses(self):
        """Devuelve el caché de estados para todos los emuladores."""
        return self._last_statuses

    # ----------------------------------------------------------------
    # Autenticación con Google Drive
    # ----------------------------------------------------------------

    def authenticate(self):
        """
        Lanza el flujo OAuth 2.0 de Google.

        Si ya existe token.json válido, lo usa sin abrir el navegador.
        Si el token expiró, lo refresca automáticamente.
        Si no hay token, abre el navegador del sistema para autorizar la app
        (esto es independiente de la ventana de PyWebView).

        Devuelve: { success: bool, error?: str }
        """
        try:
            creds = authenticate()
            # build() crea el cliente de la API de Drive con las credenciales
            self._service = build('drive', 'v3', credentials=creds)
            return {'success': True}
        except Exception as e:
            return {'success': False, 'error': str(e)}

    # ----------------------------------------------------------------
    # Verificación de estado
    # ----------------------------------------------------------------

    def get_emulator_status(self, emulator_key):
        """
        Consulta la API de Drive y compara timestamps:
          - os.path.getmtime(local_path)  vs  modifiedTime de Drive
        Guarda el resultado en caché para el check de conflictos (evita
        una segunda llamada de red al momento de subir/bajar).

        Devuelve: { status: str, local_mtime: float|null, drive_mtime: float|null }
        Valores de status: not_configured | not_in_cloud | up_to_date |
                           upload_pending | download_pending | error
        """
        if not self._service:
            return {'status': 'not_configured'}

        emu_data = self._config['emulators'][emulator_key]
        try:
            result = check_status(self._service, emulator_key, emu_data)
            self._last_statuses[emulator_key] = result
            return result
        except Exception as e:
            return {'status': 'error', 'error': str(e)}

    # ----------------------------------------------------------------
    # Resolución automática de rutas de subida
    # ----------------------------------------------------------------

    def get_upload_paths(self, emulator_key):
        """
        Devuelve la lista de rutas a subir para un emulador, leyéndolas
        directamente de local_path — sin abrir ningún diálogo.

        - folder:     [local_path]  (Python lo comprimirá en ZIP)
        - dual_file / file: escanea local_path buscando archivos con
          la extensión del emulador (.ps2, .sav, etc.)

        Devuelve: { success: bool, paths: list, error?: str }
        """
        emu_data   = self._config['emulators'][emulator_key]
        local_path = emu_data.get('local_path', '')
        save_type  = emu_data.get('save_type', 'file')
        extension  = emu_data.get('extension', '')

        if not local_path:
            return {'success': False, 'error': 'not_configured', 'paths': []}

        if save_type == 'folder':
            if not os.path.isdir(local_path):
                return {'success': False, 'error': 'path_not_found', 'paths': []}
            return {'success': True, 'paths': [local_path]}

        # file / dual_file: escanear la carpeta buscando archivos con la extensión
        if os.path.isdir(local_path):
            files = sorted(
                os.path.join(local_path, f)
                for f in os.listdir(local_path)
                if f.endswith(extension)
            )
            if not files:
                return {'success': False, 'error': 'no_files', 'paths': []}
            return {'success': True, 'paths': files}

        # Fallback: local_path apunta directamente a un archivo
        if os.path.isfile(local_path):
            return {'success': True, 'paths': [local_path]}

        return {'success': False, 'error': 'path_not_found', 'paths': []}

    # ----------------------------------------------------------------
    # Diálogos nativos del sistema operativo
    # ----------------------------------------------------------------

    def select_file(self, title, extension):
        """
        Abre el explorador de archivos nativo de Windows para seleccionar
        un archivo de guardado.

        create_file_dialog() es un método de la ventana PyWebView que
        delega al diálogo del sistema operativo.

        Devuelve: str (ruta del archivo) o None si se canceló.
        """
        result = self._window.create_file_dialog(
            webview.OPEN_DIALOG,
            allow_multiple=False,
            file_types=(f'Save files (*{extension})', 'All files (*.*)')
        )
        # create_file_dialog devuelve una tupla de rutas, o None
        return result[0] if result else None

    def select_folder(self, title='', initial_dir=''):
        """
        Abre el explorador de carpetas nativo de Windows.
        initial_dir: carpeta que se mostrará al abrir el diálogo.
                     Si está vacío, el OS usa la última carpeta visitada.
        Devuelve: str (ruta de carpeta) o None si se canceló.
        """
        result = self._window.create_file_dialog(
            webview.FOLDER_DIALOG,
            directory=initial_dir or '',
        )
        return result[0] if result else None

    # ----------------------------------------------------------------
    # Operaciones de sincronización con Drive
    # PyWebView ejecuta estos métodos en hilos secundarios, la UI
    # permanece reactiva durante uploads/downloads largos.
    # ----------------------------------------------------------------

    def upload(self, emulator_key, paths):
        """
        Sube archivos de guardado a Google Drive.

        Parámetros:
          emulator_key: "ps2", "ds", "3ds", "psp", etc.
          paths: lista de rutas (archivos o una carpeta según save_type)

        Para save_type "folder" (3DS/PSP): comprime la carpeta como .zip,
        sube el zip, borra el temporal.
        Para "file" / "dual_file" (DS/PS2): sube cada archivo directamente.

        Si ya existe un archivo con el mismo nombre en Drive, lo actualiza
        (evita duplicados). Si no existe, lo crea.

        Devuelve: { success: bool, error?: str }
        """
        if not self._service:
            return {'success': False, 'error': 'not_connected'}

        emu_data  = self._config['emulators'][emulator_key]
        folder_id = emu_data['drive_id']
        save_type = emu_data['save_type']

        try:
            if save_type == 'folder':
                result = upload_folder(self._service, paths[0], folder_id, emulator_key)
            else:
                # Sube cada archivo y combina los resultados
                results = [upload_file(self._service, p, folder_id) for p in paths]
                result  = {'success': all(r['success'] for r in results)}

            # Refrescar el caché de estado tras la operación
            self._last_statuses[emulator_key] = self._check_status_silent(emulator_key)
            return result
        except Exception as e:
            return {'success': False, 'error': str(e)}

    def download(self, emulator_key, dest_dir):
        """
        Descarga archivos de guardado desde Google Drive al directorio destino.

        Para "folder": descarga el .zip y lo extrae en dest_dir.
        Para "file" / "dual_file": descarga cada archivo directamente.

        Devuelve: { success: bool, files?: list, error?: str }
        """
        if not self._service:
            return {'success': False, 'error': 'not_connected'}

        emu_data  = self._config['emulators'][emulator_key]
        folder_id = emu_data['drive_id']
        save_type = emu_data['save_type']

        try:
            result = download_files(
                self._service, folder_id, dest_dir, save_type, emulator_key
            )
            self._last_statuses[emulator_key] = self._check_status_silent(emulator_key)
            return result
        except Exception as e:
            return {'success': False, 'error': str(e)}

    # ----------------------------------------------------------------
    # Multi-file per-game management
    # ----------------------------------------------------------------

    def list_local_saves(self, emulator_key):
        """
        For multi_file emulators: scan local_path for .sav files and compare
        each one against Drive, returning a merged list with sync status.

        Devuelve: { success: bool, saves: list, error?: str }
        """
        if not self._service:
            return {'success': False, 'error': 'not_connected', 'saves': []}

        emu_data   = self._config['emulators'][emulator_key]
        local_path = emu_data.get('local_path', '')
        folder_id  = emu_data.get('drive_id', '')
        extension  = emu_data.get('extension', '.sav')

        if not local_path or not folder_id:
            return {'success': False, 'error': 'not_configured', 'saves': []}

        try:
            saves = list_saves_with_status(
                self._service, folder_id, local_path, extension
            )
            return {'success': True, 'saves': saves}
        except Exception as e:
            return {'success': False, 'error': str(e), 'saves': []}

    def upload_single_save(self, emulator_key, filepath):
        """
        Upload one save file for a multi_file emulator.
        filepath es la ruta absoluta al .sav local.

        Devuelve: { success: bool, error?: str }
        """
        if not self._service:
            return {'success': False, 'error': 'not_connected'}

        emu_data  = self._config['emulators'][emulator_key]
        folder_id = emu_data['drive_id']

        try:
            return upload_file(self._service, filepath, folder_id)
        except Exception as e:
            return {'success': False, 'error': str(e)}

    def download_single_save(self, emulator_key, filename):
        """
        Download one save file from Drive to local_path/filename.
        filename es el nombre del archivo (sin ruta).

        Devuelve: { success: bool, error?: str }
        """
        if not self._service:
            return {'success': False, 'error': 'not_connected'}

        emu_data   = self._config['emulators'][emulator_key]
        folder_id  = emu_data['drive_id']
        local_path = emu_data['local_path']
        dest_path  = os.path.join(local_path, filename)

        try:
            return download_file_to_path(
                self._service, filename, folder_id, dest_path
            )
        except Exception as e:
            return {'success': False, 'error': str(e)}

    def _check_status_silent(self, emulator_key):
        """Verifica el estado sin propagar excepciones (uso interno post-sync)."""
        try:
            return check_status(
                self._service, emulator_key,
                self._config['emulators'][emulator_key]
            )
        except Exception:
            return {'status': 'error'}

    # ----------------------------------------------------------------
    # Configuración
    # ----------------------------------------------------------------

    def save_settings(self, new_config):
        """
        Guarda la configuración actualizada en data/config.json.

        new_config llega como dict Python — PyWebView convierte el objeto
        JS a dict automáticamente al pasar por el bridge.

        También recarga el idioma si el usuario lo cambió.

        Devuelve: { success: bool, error?: str }
        """
        try:
            self._config = new_config
            save_config(new_config)
            # Recargar el diccionario de idioma si cambió la selección
            self._t = load_lang(new_config['settings']['language'])
            return {'success': True}
        except Exception as e:
            return {'success': False, 'error': str(e)}

    # ----------------------------------------------------------------
    # Credenciales Google API
    # ----------------------------------------------------------------

    def get_all_icons(self):
        """
        Lee cada icono de emulador y lo devuelve como data URL base64.
        Esto evita los problemas de acceso a archivos locales del servidor
        virtual de WebView (las rutas file:// o relativas no siempre funcionan).

        Devuelve: { emulator_key: "data:image/png;base64,..." }
        Solo incluye entradas donde el archivo existe y se pudo leer.
        """
        import base64
        import mimetypes

        icons = {}
        for key, emu in self._config['emulators'].items():
            icon_path = emu.get('icon', '')
            if not icon_path:
                continue

            # Resolver: rutas relativas (assets/...) → resource_path()
            #           rutas absolutas             → tal cual
            full_path = (
                resource_path(icon_path)
                if not os.path.isabs(icon_path)
                else icon_path
            )

            if not os.path.isfile(full_path):
                continue

            try:
                mime, _ = mimetypes.guess_type(full_path)
                mime = mime or 'image/png'
                with open(full_path, 'rb') as f:
                    b64 = base64.b64encode(f.read()).decode('utf-8')
                icons[key] = f'data:{mime};base64,{b64}'
            except Exception:
                pass  # archivo ilegible — la tarjeta usará el emoji fallback

        return icons

    def check_credentials(self):
        """
        Verifica si credentials.json está disponible.
        Prioridad: app_dir() (importado por el usuario) → resource_path() (bundleado).
        """
        user_path    = os.path.join(app_dir(), 'credentials.json')
        bundled_path = resource_path('credentials.json')

        if os.path.isfile(user_path):
            return {'exists': True, 'path': user_path, 'source': 'user'}
        if os.path.isfile(bundled_path):
            return {'exists': True, 'path': bundled_path, 'source': 'bundled'}
        return {'exists': False, 'path': user_path, 'source': None}

    def import_credentials(self):
        """
        Abre el explorador de archivos para seleccionar credentials.json
        y lo copia al directorio de la app (junto al .exe en modo empaquetado).

        Devuelve: { success: bool, cancelled?: bool, error?: str }
        """
        result = self._window.create_file_dialog(
            webview.OPEN_DIALOG,
            allow_multiple=False,
            file_types=('JSON files (*.json)', 'All files (*.*)')
        )
        if not result:
            return {'success': False, 'cancelled': True}
        src = result[0]
        dest = os.path.join(app_dir(), 'credentials.json')
        try:
            shutil.copy2(src, dest)
            return {'success': True}
        except Exception as e:
            return {'success': False, 'error': str(e)}

    # ----------------------------------------------------------------
    # Gestión de emuladores
    # ----------------------------------------------------------------

    def select_emulator_icon(self):
        """Abre el explorador para seleccionar una imagen como icono de emulador."""
        result = self._window.create_file_dialog(
            webview.OPEN_DIALOG,
            allow_multiple=False,
            file_types=('Image files (*.png;*.jpg;*.jpeg;*.ico;*.bmp)', 'All files (*.*)')
        )
        return result[0] if result else None

    def add_emulator(self, data):
        """
        Agrega un nuevo emulador personalizado a config.json.

        data: { key, name, emulator, extension, save_type, icon, local_path, drive_id }
        La clave (key) solo acepta letras minúsculas, números y guiones.

        Devuelve: { success: bool, error?: str }
        """
        key = str(data.get('key', '')).strip().lower()
        if not key or not re.match(r'^[a-z0-9_-]+$', key):
            return {'success': False, 'error': 'invalid_key'}
        if key in self._config['emulators']:
            return {'success': False, 'error': 'key_exists'}

        self._config['emulators'][key] = {
            'name':       data.get('name', ''),
            'emulator':   data.get('emulator', ''),
            'extension':  data.get('extension', ''),
            'save_type':  data.get('save_type', 'file'),
            'icon':       data.get('icon', ''),
            'local_path': data.get('local_path', ''),
            'drive_id':   data.get('drive_id', ''),
            'custom':     True,
        }
        try:
            save_config(self._config)
            return {'success': True}
        except Exception as e:
            return {'success': False, 'error': str(e)}

    def update_emulator(self, key, data):
        """
        Actualiza los campos de un emulador existente (tanto predeterminados
        como personalizados).  Solo se sobreescriben los campos presentes en data.

        Devuelve: { success: bool, error?: str }
        """
        if key not in self._config['emulators']:
            return {'success': False, 'error': 'not_found'}
        emu = self._config['emulators'][key]
        for field in ('name', 'emulator', 'extension', 'save_type', 'icon',
                      'local_path', 'drive_id'):
            if field in data:
                emu[field] = data[field]
        try:
            save_config(self._config)
            return {'success': True}
        except Exception as e:
            return {'success': False, 'error': str(e)}

    def delete_emulator(self, key):
        """
        Elimina un emulador personalizado. Los emuladores predeterminados
        (custom: false) no pueden eliminarse.

        Devuelve: { success: bool, error?: str }
        """
        emu = self._config['emulators'].get(key)
        if not emu:
            return {'success': False, 'error': 'not_found'}
        if not emu.get('custom', False):
            return {'success': False, 'error': 'cannot_delete_default'}
        del self._config['emulators'][key]
        try:
            save_config(self._config)
            return {'success': True}
        except Exception as e:
            return {'success': False, 'error': str(e)}


# ============================================================
# MAIN
# ============================================================

def main():
    api = Api()

    # create_window() prepara la ventana pero NO la muestra todavía.
    # Parámetros
    #   url      → ruta al HTML principal (resource_path maneja PyInstaller)
    #   js_api   → la instancia de Api que JS verá como window.pywebview.api
    #   text_select=False → evita que el usuario seleccione texto como en web
    window = webview.create_window(
        title='Cloud Save Hub',
        url=resource_path('ui/index.html'),
        js_api=api,
        width=960,
        height=600,
        min_size=(720, 480),
        background_color='#0d0d0d',
        text_select=False,
    )

    # Guardamos la referencia a la ventana en la Api.
    # Es necesaria para poder llamar a create_file_dialog() desde los métodos.
    api._window = window

    # Aplicar borde y título oscuro en cuanto cargue la página
    window.events.loaded += _apply_dark_frame

    # start() muestra la ventana y bloquea hasta que el usuario la cierra.
    # PyWebView elige el mejor motor disponible.
    # En Windows 10/11 usará Edge WebView2.
    # debug=True abre las DevTools del navegador — útil durante desarrollo.
    webview.start(debug=False)


if __name__ == '__main__':
    main()
