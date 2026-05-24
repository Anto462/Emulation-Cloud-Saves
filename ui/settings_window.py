import customtkinter as ctk
from tkinter import filedialog

from core.file_manager import save_config

# Pestaña de ajustes - Settings window
class SettingsWindow(ctk.CTkToplevel):
    def __init__(self, parent, config, t, on_saved):
        super().__init__(parent)
        self.title(t['settings_title'])
        self.resizable(False, True)
        self.grab_set()
        self.transient(parent)
        self.after(100, self.lift)

        self._config = config
        self._t = t
        self._on_saved = on_saved
        self._path_vars: dict[str, ctk.StringVar] = {}
        self._drive_vars: dict[str, ctk.StringVar] = {}
        self._lang_var = ctk.StringVar(value=config['settings']['language']) # Usa el lengaje usado de acuerdo a los huardados en el folder de lang - Use te choosen one from the ones on lang folder

        self._build()

    def _build(self):
        t = self._t

        # Area scrolleable - Scrollable content area
        scroll = ctk.CTkScrollableFrame(self, width=480, height=420)
        scroll.pack(padx=16, pady=(16, 8), fill='both', expand=True)

        # Elegir idioma - Language section
        self._section_label(scroll, t['settings_language'])

        lang_row = ctk.CTkFrame(scroll, fg_color='transparent')
        lang_row.pack(fill='x', padx=10, pady=(4, 14))

        for code, label in [('es', 'Español'), ('en', 'English')]:
            ctk.CTkRadioButton(
                lang_row, text=label,
                variable=self._lang_var, value=code,
                font=ctk.CTkFont(size=12)
            ).pack(side='left', padx=12)

        # Emuladores - Emulators section
        self._section_label(scroll, t['settings_emulators'])

        for key, emu in self._config['emulators'].items():
            group = ctk.CTkFrame(scroll, corner_radius=8)
            group.pack(fill='x', padx=6, pady=6)

            ctk.CTkLabel(
                group, text=emu['name'],
                font=ctk.CTkFont(size=12, weight='bold'),
                anchor='w'
            ).pack(fill='x', padx=12, pady=(10, 4))

            # Ruta local - Local path
            local_row = ctk.CTkFrame(group, fg_color='transparent')
            local_row.pack(fill='x', padx=12, pady=3)
            ctk.CTkLabel(local_row, text=t['settings_local'],
                         width=50, anchor='w',
                         font=ctk.CTkFont(size=11)).pack(side='left')
            p_var = ctk.StringVar(value=emu.get('local_path', ''))
            self._path_vars[key] = p_var
            ctk.CTkEntry(local_row, textvariable=p_var, width=280,
                         font=ctk.CTkFont(size=11)).pack(side='left')
            ctk.CTkButton(
                local_row, text='…', width=32, height=28,
                command=lambda k=key: self._browse(k)
            ).pack(side='left', padx=(4, 0))

            # Id de Drive (Folder en Drive) - Drive ID (Drive folder)
            drive_row = ctk.CTkFrame(group, fg_color='transparent')
            drive_row.pack(fill='x', padx=12, pady=(3, 10))
            ctk.CTkLabel(drive_row, text=t['settings_drive'],
                         width=50, anchor='w',
                         font=ctk.CTkFont(size=11)).pack(side='left')
            d_var = ctk.StringVar(value=emu.get('drive_id', ''))
            self._drive_vars[key] = d_var
            ctk.CTkEntry(drive_row, textvariable=d_var, width=318,
                         font=ctk.CTkFont(size=11)).pack(side='left')

        # Salvar ajustes - Save settings (outside scroll)
        ctk.CTkButton(
            self, text=t['settings_save'],
            command=self._save,
            width=200, height=38,
            font=ctk.CTkFont(size=13)
        ).pack(pady=14)

    def _section_label(self, parent, text):
        ctk.CTkLabel(
            parent, text=text,
            font=ctk.CTkFont(size=13, weight='bold'),
            anchor='w'
        ).pack(fill='x', padx=10, pady=(10, 2))
        ctk.CTkFrame(parent, height=1, fg_color='gray40').pack(fill='x', padx=10, pady=(0, 4))

    def _browse(self, key):
        folder = filedialog.askdirectory()
        if folder:
            self._path_vars[key].set(folder)

    def _save(self):
        self._config['settings']['language'] = self._lang_var.get()
        for key in self._config['emulators']:
            self._config['emulators'][key]['local_path'] = self._path_vars[key].get().strip()
            self._config['emulators'][key]['drive_id'] = self._drive_vars[key].get().strip()
        save_config(self._config)
        self.destroy()
        self._on_saved()
