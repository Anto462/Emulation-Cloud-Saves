import sys
import os


def app_dir():
    """Next to .exe in bundle mode, project root in dev."""
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def resource_path(relative_path):
    """Resolve path for both development and PyInstaller compiled builds.
       It helps so we can access all the diferent def, assets and folders for the files we need
       
       If for some reason you move utils.py to a subfolder of core or to another folder is importanto to change the logic of os.path.dirname so it moves correctly to the root
    """
    try:
        base_path = sys._MEIPASS
    except AttributeError:
        # core/utils.py is one level deep — go up to project root - Se mueve un escalon por encima, sale de core y termina en la raiz del projecto donde tiene acceso a las demas carpetas
        base_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base_path, relative_path)
