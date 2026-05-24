import tkinter as tk
import customtkinter as ctk

from core.utils import resource_path

_STATUS_COLORS = {
    'not_configured':   'gray',
    'checking':         '#ffc107',
    'not_in_cloud':     '#fd7e14',
    'up_to_date':       '#28a745',
    'upload_pending':   '#4da6ff',
    'download_pending': '#17a2b8',
    'error':            '#dc3545',
}

_STATUS_DOTS = {
    'not_configured':   '○',
    'checking':         '◌',
    'not_in_cloud':     '◉',
    'up_to_date':       '●',
    'upload_pending':   '↑',
    'download_pending': '↓',
    'error':            '✗',
}


class EmulatorCard(ctk.CTkFrame): # This creates a card for every emulator - Crea una card para cada emulador
    def __init__(self, parent, emulator_key, emulator_data, t,
                 on_upload, on_download):
        super().__init__(parent, corner_radius=12, border_width=1)
        self.emulator_key = emulator_key
        self.emulator_data = emulator_data
        self.t = t
        self._on_upload = on_upload
        self._on_download = on_download
        self._icon_ref = None

        self._build()

    def _build(self):
        # Intenta usar los iconos .png, de no encontrar usa 🎮 - try PNG file as icon, if fails use 🎮
        icon_path = resource_path(self.emulator_data.get('icon', ''))
        try:
            img = tk.PhotoImage(file=icon_path)
            self._icon_ref = img
            # tk.Label
            icon_lbl = tk.Label(self, image=img, bg='#2b2b2b', bd=0)
            icon_lbl.pack(pady=(14, 4))
        except Exception:
            ctk.CTkLabel(
                self, text='🎮',
                font=ctk.CTkFont(size=36)
            ).pack(pady=(14, 4))

        # Emulator name
        ctk.CTkLabel(
            self,
            text=self.emulator_data['name'],
            font=ctk.CTkFont(size=13, weight='bold')
        ).pack()

        # Status indicator
        self._status_label = ctk.CTkLabel(
            self, text='○  —',
            font=ctk.CTkFont(size=11),
            text_color='gray'
        )
        self._status_label.pack(pady=(3, 10))

        # Action buttons
        btn_row = ctk.CTkFrame(self, fg_color='transparent')
        btn_row.pack(padx=12, pady=(0, 14))

        self._upload_btn = ctk.CTkButton(
            btn_row,
            text=f'↑  {self.t["btn_upload"]}',
            command=lambda: self._on_upload(self.emulator_key),
            width=108, height=32,
            fg_color='#1f6aa5', hover_color='#144e7d',
            font=ctk.CTkFont(size=12)
        )
        self._upload_btn.pack(side='left', padx=4)

        self._download_btn = ctk.CTkButton(
            btn_row,
            text=f'↓  {self.t["btn_download"]}',
            command=lambda: self._on_download(self.emulator_key),
            width=108, height=32,
            fg_color='#117a8b', hover_color='#0c5460',
            font=ctk.CTkFont(size=12)
        )
        self._download_btn.pack(side='left', padx=4)

    def set_status(self, status_key: str, t: dict):
        dot = _STATUS_DOTS.get(status_key, '○')
        label = t.get(f'status_{status_key}', status_key)
        color = _STATUS_COLORS.get(status_key, 'gray')
        self._status_label.configure(
            text=f'{dot}  {label}',
            text_color=color
        )

    def set_loading(self, loading: bool):
        state = 'disabled' if loading else 'normal'
        self._upload_btn.configure(state=state)
        self._download_btn.configure(state=state)
