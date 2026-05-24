import customtkinter as ctk
from tkinter import filedialog
from datetime import datetime


def _fmt_ts(ts):
    if ts is None:
        return 'N/A'
    return datetime.fromtimestamp(ts).strftime('%Y-%m-%d  %H:%M:%S')


def show_conflict_dialog(root, t, local_mtime, drive_mtime) -> bool:
    """
    Modal warning about a timestamp conflict
    Returns True if user wants to proceed, False to cancel.
    """
    result = {'proceed': False}

    dialog = ctk.CTkToplevel(root)
    dialog.title(t['conflict_title'])
    dialog.resizable(False, False)
    dialog.grab_set()
    dialog.transient(root)
    dialog.after(100, dialog.lift)

    # Warning header band
    header = ctk.CTkFrame(dialog, fg_color='#856404', corner_radius=0)
    header.pack(fill='x')
    ctk.CTkLabel(
        header,
        text=f'⚠   {t["conflict_title"]}',
        font=ctk.CTkFont(size=13, weight='bold'),
        text_color='#fff3cd'
    ).pack(padx=20, pady=12)

    # Message
    ctk.CTkLabel(
        dialog,
        text=t['conflict_message'],
        wraplength=400, justify='center',
        font=ctk.CTkFont(size=11)
    ).pack(padx=24, pady=(14, 6))

    # Timestamps box
    box = ctk.CTkFrame(dialog, corner_radius=8)
    box.pack(padx=24, pady=6, fill='x')
    ctk.CTkLabel(
        box,
        text=f'{t["conflict_local_date"]}   {_fmt_ts(local_mtime)}',
        anchor='w', font=ctk.CTkFont(size=11)
    ).pack(fill='x', padx=14, pady=(10, 2))
    ctk.CTkLabel(
        box,
        text=f'{t["conflict_drive_date"]}   {_fmt_ts(drive_mtime)}',
        anchor='w', font=ctk.CTkFont(size=11)
    ).pack(fill='x', padx=14, pady=(2, 10))

    # Buttons
    btn_row = ctk.CTkFrame(dialog, fg_color='transparent')
    btn_row.pack(pady=16)

    def on_cancel():
        dialog.destroy()

    def on_proceed():
        result['proceed'] = True
        dialog.destroy()

    ctk.CTkButton(
        btn_row, text=t['conflict_cancel'],
        command=on_cancel, width=160,
        fg_color='gray40', hover_color='gray30'
    ).pack(side='left', padx=8)
    ctk.CTkButton(
        btn_row, text=t['conflict_confirm'],
        command=on_proceed, width=180,
        fg_color='#a71d2a', hover_color='#7b1020'
    ).pack(side='left', padx=8)

    dialog.wait_window()
    return result['proceed']


def show_onboarding(root, t, emulator_name, on_save):
    """
    Dialog for an unconfigured emulator
    Calls on_save(local_path, drive_id) when the user confirms.
    """
    dialog = ctk.CTkToplevel(root)
    dialog.title(t['onboarding_title'])
    dialog.resizable(False, False)
    dialog.grab_set()
    dialog.transient(root)
    dialog.after(100, dialog.lift)

    ctk.CTkLabel(
        dialog,
        text=f'{t["onboarding_title"]}\n{emulator_name}',
        font=ctk.CTkFont(size=14, weight='bold'),
        justify='center'
    ).pack(padx=28, pady=(20, 14))

    # Local path
    ctk.CTkLabel(
        dialog, text=t['onboarding_local_path'],
        anchor='w', font=ctk.CTkFont(size=11)
    ).pack(fill='x', padx=28)

    path_row = ctk.CTkFrame(dialog, fg_color='transparent')
    path_row.pack(fill='x', padx=28, pady=(2, 10))

    path_var = ctk.StringVar()
    path_entry = ctk.CTkEntry(path_row, textvariable=path_var, width=310,
                               font=ctk.CTkFont(size=11))
    path_entry.pack(side='left')

    def browse():
        folder = filedialog.askdirectory(title=t['onboarding_local_path'])
        if folder:
            path_var.set(folder)

    ctk.CTkButton(
        path_row, text=t['onboarding_browse'],
        command=browse, width=80, height=32
    ).pack(side='left', padx=(6, 0))

    # Drive ID
    ctk.CTkLabel(
        dialog, text=t['onboarding_drive_id'],
        anchor='w', font=ctk.CTkFont(size=11)
    ).pack(fill='x', padx=28)

    drive_var = ctk.StringVar()
    ctk.CTkEntry(
        dialog, textvariable=drive_var, width=400,
        font=ctk.CTkFont(size=11),
        placeholder_text='1aBcDeFgHiJkLmNoPqRsTuVwXyZ...'
    ).pack(padx=28, pady=(2, 14))

    # Buttons
    btn_row = ctk.CTkFrame(dialog, fg_color='transparent')
    btn_row.pack(pady=(4, 18))

    def on_confirm():
        local = path_var.get().strip()
        drive = drive_var.get().strip()
        if not local or not drive:
            return
        dialog.destroy()
        on_save(local, drive)

    ctk.CTkButton(
        btn_row, text=t['onboarding_cancel'],
        command=dialog.destroy, width=120,
        fg_color='gray40', hover_color='gray30'
    ).pack(side='left', padx=8)
    ctk.CTkButton(
        btn_row, text=t['onboarding_save'],
        command=on_confirm, width=180,
        fg_color='#1f8c3b', hover_color='#15632a'
    ).pack(side='left', padx=8)
