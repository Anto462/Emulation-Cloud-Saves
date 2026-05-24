import customtkinter as ctk
from datetime import datetime

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

# Pestaña de resumen, muestra el status de los emuladores agregados - Summary window, show the status of the added emulators
def _fmt(ts):
    if ts is None:
        return '—'
    return datetime.fromtimestamp(ts).strftime('%d %b  %H:%M')


class SummaryWindow(ctk.CTkToplevel):
    def __init__(self, parent, config, t, last_statuses, on_refresh):
        super().__init__(parent)
        self.title(t['summary_title'])
        self.resizable(False, False)
        self.grab_set()
        self.transient(parent)
        self.after(100, self.lift)

        self._config = config
        self._t = t
        self._last_statuses = last_statuses
        self._on_refresh = on_refresh

        self._build()

    def _build(self):
        t = self._t

        ctk.CTkLabel(
            self, text=t['summary_title'],
            font=ctk.CTkFont(size=15, weight='bold')
        ).pack(padx=28, pady=(20, 12))

        # Tabla de datos, Scrolleable - Scrollable table
        table = ctk.CTkScrollableFrame(self, width=640, height=220)
        table.pack(padx=16, pady=(0, 8), fill='both', expand=True)

        col_widths = [150, 160, 130, 130, 110]
        cols = [
            t['summary_col_system'],
            t['summary_col_status'],
            t['summary_col_local'],
            t['summary_col_cloud'],
            t['summary_col_action'],
        ]

        # Header row
        hrow = ctk.CTkFrame(table, fg_color='transparent')
        hrow.pack(fill='x', pady=(0, 4))
        for col, w in zip(cols, col_widths):
            ctk.CTkLabel(
                hrow, text=col, width=w, anchor='w',
                font=ctk.CTkFont(weight='bold')
            ).pack(side='left', padx=6)

        ctk.CTkFrame(table, height=1, fg_color='gray40').pack(fill='x', pady=4)

        # Informacion y status - Data and status
        _actions = {
            'upload_pending':   t['summary_action_upload'],
            'download_pending': t['summary_action_download'],
            'up_to_date':       t['summary_action_uptodate'],
            'not_in_cloud':     t['summary_action_first'],
            'not_configured':   t['summary_action_configure'],
        }

        for key, emu in self._config['emulators'].items():
            info = self._last_statuses.get(key, {})
            status = info.get('status', 'not_configured')

            dot = _STATUS_DOTS.get(status, '○')
            status_text = t.get(f'status_{status}', status)
            color = _STATUS_COLORS.get(status, 'gray')
            action = _actions.get(status, '—')

            row = ctk.CTkFrame(table, fg_color='transparent')
            row.pack(fill='x', pady=3)

            ctk.CTkLabel(row, text=emu['name'], width=col_widths[0],
                         anchor='w').pack(side='left', padx=6)
            ctk.CTkLabel(row, text=f'{dot}  {status_text}', width=col_widths[1],
                         anchor='w', text_color=color).pack(side='left', padx=6)
            ctk.CTkLabel(row, text=_fmt(info.get('local_mtime')), width=col_widths[2],
                         anchor='w').pack(side='left', padx=6)
            ctk.CTkLabel(row, text=_fmt(info.get('drive_mtime')), width=col_widths[3],
                         anchor='w').pack(side='left', padx=6)
            ctk.CTkLabel(row, text=action, width=col_widths[4],
                         anchor='w').pack(side='left', padx=6)

        # Botones - buttons
        btn_row = ctk.CTkFrame(self, fg_color='transparent')
        btn_row.pack(pady=14)

        ctk.CTkButton(
            btn_row, text=t['summary_btn_refresh'],
            command=self._refresh, width=140
        ).pack(side='left', padx=8)
        ctk.CTkButton(
            btn_row, text=t['summary_btn_close'],
            command=self.destroy, width=110,
            fg_color='gray40', hover_color='gray30'
        ).pack(side='left', padx=8)

    def _refresh(self):
        self._on_refresh()
        self.destroy()
