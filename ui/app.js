/* ============================================================
   app.js
   ============================================================ */

'use strict';  // Modo estricto: JS avisa de errores comunes


/* ============================================================
   ESTADO GLOBAL DE LA APLICACIÓN
   Un objeto centralizado que guarda los datos que comparten
   todas las funciones de este archivo.
   ============================================================ */
const state = {
    config:   null,   // Contenido completo de data/config.json (cargado de Python)
    t:        null,   // Diccionario del idioma activo (es.json o en.json)
    statuses: {},     // Cache: { "ps2": {status, local_mtime, drive_mtime}, ... }
    icons:    {},     // Cache: { "ps2": "data:image/png;base64,..." } — cargado vía Python
    connected: false, // true después de autenticar con Google Drive

    // Datos temporales del onboarding (cuál emulador se está configurando)
    onboardingKey:      null,
    onboardingCallback: null,
};


/* ============================================================
   MAPAS VISUALES DE ESTADO
   Convierten un status_key (string) en el símbolo y clase CSS correctos.
   ============================================================ */

// Símbolo que aparece junto al texto de estado en la tarjeta
const STATUS_DOTS = {
    not_configured:   '○',   // vacío
    checking:         '◌',   // animación de búsqueda
    not_in_cloud:     '◉',   // círculo parcial = hay local pero no nube
    up_to_date:       '●',   // círculo lleno = sincronizado
    upload_pending:   '↑',   // flecha arriba = hay nuevo progreso local
    download_pending: '↓',   // flecha abajo = hay nueva versión en la nube
    error:            '✗',
};

// Clases CSS que aplican el color de estado (definidas en styles.css)
const STATUS_CLASSES = {
    not_configured:   's-not_configured',
    checking:         's-checking',
    not_in_cloud:     's-not_in_cloud',
    up_to_date:       's-up_to_date',
    upload_pending:   's-upload_pending',
    download_pending: 's-download_pending',
    error:            's-error',
};

// Iconos por emulador. Se muestran en las tarjetas.
// Cuando el usuario tenga imágenes PNG reales en assets/icons/,
// se puede cambiar esto para usar <img> en lugar de emoji.
const EMU_ICONS = {
    ps2:   '🎮',
    ds:    '🎮',
    '3ds': '🎮',
    psp:   '🎮',
};


/* ============================================================
   NOTIFICACIONES TOAST
   Reemplaza alert() del sistema. Tipo: 'success' | 'error' | 'warning'
   ============================================================ */
function notify(message, type = 'success') {
    const container = document.getElementById('notify-container');
    if (!container) return;

    const prefixes = { success: '✓', error: '✗', warning: '!' };
    const toast = document.createElement('div');
    toast.className = `notify-toast${type === 'error' || type === 'warning' ? ' ' + type : ''}`;
    toast.textContent = `${prefixes[type] || '◆'}  ${message}`;
    container.appendChild(toast);

    // Animar salida a los 3.5s y borrar después del fade
    const SHOW_MS = 3500;
    setTimeout(() => {
        toast.classList.add('out');
        setTimeout(() => toast.remove(), 200);
    }, SHOW_MS);
}


/* ============================================================
   READOUT DE SISTEMA — SYS: label dinámico durante operaciones
   Muestra el estado actual de la operación en el header.
   resetAfterMs > 0 vuelve al estado base tras esa cantidad de ms.
   ============================================================ */
let _sysResetTimer = null;

function setSysStatus(label, resetAfterMs = 0) {
    const labelEl = document.getElementById('conn-label');
    if (!labelEl) return;
    clearTimeout(_sysResetTimer);
    labelEl.textContent = label;
    if (resetAfterMs > 0) {
        _sysResetTimer = setTimeout(() => {
            if (state.connected) labelEl.textContent = 'DRIVE ● ONLINE';
        }, resetAfterMs);
    }
}


/* ============================================================
   PUNTO DE ENTRADA
   'pywebviewready' se dispara cuando PyWebView terminó de inyectar
   window.pywebview.api en la página. Antes de este evento, intentar
   llamar a window.pywebview.api lanzaría un error.
   ============================================================ */
window.addEventListener('pywebviewready', async () => {

    // 1. Pedir datos iniciales a Python (operaciones rápidas, sin red)
    state.config = await window.pywebview.api.get_config();
    state.t      = await window.pywebview.api.get_lang();

    // 1b. Precargar iconos como base64 — evita restricciones del servidor
    //     virtual de WebView con rutas locales.
    state.icons = await window.pywebview.api.get_all_icons();

    // 2. Aplicar el idioma a todos los elementos con atributo data-t en el HTML
    applyTranslations();

    // 3. Generar las tarjetas de emuladores a partir del config
    renderCards();

    // 4. Generar los campos del modal de configuración
    renderSettingsFields();

    // 5. Autenticar con Google Drive (puede abrir el navegador para OAuth)
    setConnStatus('connecting');
    const authResult = await window.pywebview.api.authenticate();

    if (authResult.success) {
        setConnStatus('connected');
        // 6. Verificar el estado de cada emulador contra Drive
        refreshAllStatuses();
    } else {
        setConnStatus('error');
        notify(state.t.error_auth, 'error');
    }
});


/* ============================================================
   SISTEMA DE TRADUCCIONES
   Todos los elementos HTML con atributo data-t="clave" reciben
   su texto del diccionario de idioma activo (state.t).
   Ejemplo: <span data-t="btn_upload"> → "Subir" o "Upload"
   ============================================================ */
function applyTranslations() {
    document.querySelectorAll('[data-t]').forEach(el => {
        const key = el.getAttribute('data-t');
        if (state.t[key]) el.textContent = state.t[key];
    });
}


/* ============================================================
   INDICADOR DE CONEXIÓN — readout estilo terminal en el header
   ============================================================ */
function setConnStatus(status) {
    const labelEl  = document.getElementById('conn-label');
    const cursorEl = document.getElementById('conn-cursor');
    const readout  = document.getElementById('conn-readout');

    /*
       Texto de cada estado. 'DRIVE ● ONLINE' usa ● como separador visual
       (no es el punto de estado anterior — es parte del texto del readout).
    */
    const labels = {
        connecting: (state.t.connecting || 'CONECTANDO') + '...',
        connected:  'DRIVE ● ONLINE',
        error:      'ERROR  AUTH',
    };

    if (labelEl) labelEl.textContent = labels[status] || 'INIT';

    // Quitar todas las clases de estado y aplicar la correcta
    readout?.classList.remove('conn-online', 'conn-error');
    if (status === 'connected') readout?.classList.add('conn-online');
    if (status === 'error')     readout?.classList.add('conn-error');

    // El cursor solo parpadea mientras conecta (conn-online lo oculta con CSS)
    if (cursorEl) {
        cursorEl.classList.toggle('blinking', status !== 'connected');
    }

    state.connected = (status === 'connected');
}


/* ============================================================
   TARJETAS DE EMULADORES
   Se generan dinámicamente a partir de state.config.emulators.
   Si el usuario añade un emulador al config.json, aparece
   automáticamente sin tocar este código.
   ============================================================ */
function renderCards() {
    const container = document.getElementById('cards-container');
    container.innerHTML = '';  // limpiar antes de re-renderizar

    let cardIndex = 0;
    for (const [key, emu] of Object.entries(state.config.emulators)) {
        const card = document.createElement('div');
        card.className = 'emulator-card';
        card.id        = `card-${key}`;
        /*
           Stagger: cada tarjeta espera un poco más que la anterior.
           90ms × índice → las tarjetas golpean la pantalla en cascada,
           no todas a la vez.
        */
        card.style.animationDelay = `${cardIndex * 90}ms`;

        /*
           Para emuladores multi_file (MelonDS) reemplazamos los botones
           individuales de subir/descargar por un único botón "VER PARTIDAS"
           que abre el modal de gestión por juego.
        */
        const isMultiFile = emu.save_type === 'multi_file';

        // Subtítulo opcional: nombre del software (PCSX2, MelonDS, etc.)
        const emulatorSubtitle = emu.emulator
            ? `<div class="card-emulator">${emu.emulator}</div>`
            : '';

        const actionButtons = isMultiFile
            ? `<button class="btn-games" id="games-btn-${key}"
                       onclick="showGamesModal('${key}')">
                   ◈&nbsp;${state.t.btn_games || 'VER PARTIDAS'}
               </button>`
            : `<button class="btn-upload" id="upload-btn-${key}"
                       onclick="handleUpload('${key}')">
                   ↑&nbsp;${state.t.btn_upload}
               </button>
               <button class="btn-download" id="download-btn-${key}"
                       onclick="handleDownload('${key}')">
                   ↓&nbsp;${state.t.btn_download}
               </button>`;

        card.innerHTML = `
            ${getCardIconHtml(key, emu)}
            <div class="card-name">${emu.name}</div>
            ${emulatorSubtitle}
            <div class="card-status s-not_configured" id="status-${key}">
                ○&nbsp;&nbsp;${state.t.status_not_configured}
            </div>
            <div class="card-buttons">
                ${actionButtons}
            </div>
        `;
        /*
           Una vez que la animación de entrada termina, quitamos el atributo
           animation del elemento. Sin esto, fill-mode:both "congela" el
           transform final de la animación y bloquea el hover del CSS.
        */
        card.addEventListener('animationend', () => {
            card.style.animation = 'none';
        }, { once: true });

        container.appendChild(card);
        cardIndex++;
    }
}

/* Actualiza el texto y color del indicador de estado de una tarjeta */
function setCardStatus(key, statusInfo) {
    const el = document.getElementById(`status-${key}`);
    if (!el) return;

    const status = statusInfo.status || 'not_configured';
    const dot    = STATUS_DOTS[status] || '○';
    const label  = state.t[`status_${status}`] || status;

    el.classList.remove('flickering');
    void el.offsetWidth;
    el.classList.add('flickering');

    setTimeout(() => {
        el.textContent = `${dot}  ${label}`;  //   = &nbsp;
        el.className = `card-status ${STATUS_CLASSES[status] || ''}`;
    }, 80);
}

/* Desactiva/activa los botones durante una operación en curso */
function setCardLoading(key, loading) {
    // Cubre tanto tarjetas normales (upload/download) como multi_file (games)
    ['upload', 'download', 'games'].forEach(action => {
        const btn = document.getElementById(`${action}-btn-${key}`);
        if (btn) btn.disabled = loading;
    });
    if (loading) setCardStatus(key, { status: 'checking' });
}


/* ============================================================
   VERIFICACIÓN DE ESTADOS
   Consulta el estado de TODOS los emuladores al iniciar y tras
   cada operación de sincronización exitosa.
   ============================================================ */
async function refreshAllStatuses() {
    for (const key of Object.keys(state.config.emulators)) {
        setCardStatus(key, { status: 'checking' });

        /*
           Cada llamada espera a la anterior (await en for...of).
           Esto evita saturar la API de Drive con llamadas simultáneas.
           Si quisieras paralelo: Promise.all() - pero Drive puede limitar.
        */
        const result = await window.pywebview.api.get_emulator_status(key);
        state.statuses[key] = result;
        setCardStatus(key, result);
    }
}


/* ============================================================
   FLUJO DE SUBIDA
   ============================================================ */
async function handleUpload(key) {
    const emu = state.config.emulators[key];

    // Guardia: si el emulador no tiene configuración, mostrar onboarding
    if (!emu.local_path || !emu.drive_id) {
        // El segundo argumento es la función a llamar DESPUÉS de configurar
        showOnboarding(key, () => handleUpload(key));
        return;
    }

    if (!state.connected) {
        notify(state.t.error_not_connected, 'warning');
        return;
    }

    const paths = await collectPaths(key, emu);
    if (!paths || paths.length === 0) return;

    const cached = state.statuses[key] || {};
    if (cached.status === 'download_pending' && cached.local_mtime && cached.drive_mtime) {
        const proceed = await showConflict(cached.local_mtime, cached.drive_mtime);
        if (!proceed) return;
    }

    setSysStatus(`UPLOADING  ${key.toUpperCase()}...`);
    setCardLoading(key, true);
    const result = await window.pywebview.api.upload(key, paths);
    setCardLoading(key, false);

    if (result.success) {
        setSysStatus(`${key.toUpperCase()}  SYNCED`, 3000);
        notify(state.t.upload_success, 'success');
        const status = await window.pywebview.api.get_emulator_status(key);
        state.statuses[key] = status;
        setCardStatus(key, status);
    } else {
        setSysStatus('SYNC  FAILED', 4000);
        notify(result.error ? `${state.t.upload_error}  —  ${result.error}` : state.t.upload_error, 'error');
    }
}

/*
   Obtiene automáticamente las rutas a subir desde local_path configurado.
   Python escanea la carpeta del emulador y devuelve la lista de archivos;
   no se abre ningún diálogo — el usuario ya indicó la ruta en la config.
*/
async function collectPaths(key, emu) {
    const result = await window.pywebview.api.get_upload_paths(key);

    if (!result.success) {
        const msgs = {
            no_files:      state.t.no_files_found || 'No se encontraron archivos para subir.',
            path_not_found: state.t.upload_error  || 'La ruta configurada no existe.',
            not_configured: state.t.upload_error  || 'Ruta no configurada.',
        };
        notify(msgs[result.error] || state.t.upload_error, 'warning');
        return null;
    }

    return result.paths;
}


/* ============================================================
   FLUJO DE DESCARGA
   ============================================================ */
async function handleDownload(key) {
    const emu = state.config.emulators[key];

    if (!emu.local_path || !emu.drive_id) {
        showOnboarding(key, () => handleDownload(key));
        return;
    }

    if (!state.connected) {
        notify(state.t.error_not_connected, 'warning');
        return;
    }

    const dest = emu.local_path;

    const cached = state.statuses[key] || {};
    if (cached.status === 'upload_pending' && cached.local_mtime && cached.drive_mtime) {
        const proceed = await showConflict(cached.local_mtime, cached.drive_mtime);
        if (!proceed) return;
    }

    setSysStatus(`DOWNLOADING  ${key.toUpperCase()}...`);
    setCardLoading(key, true);
    const result = await window.pywebview.api.download(key, dest);
    setCardLoading(key, false);

    if (result.success) {
        setSysStatus(`${key.toUpperCase()}  SYNCED`, 3000);
        notify(state.t.download_success, 'success');
        const status = await window.pywebview.api.get_emulator_status(key);
        state.statuses[key] = status;
        setCardStatus(key, status);
    } else {
        setSysStatus('SYNC  FAILED', 4000);
        notify(result.error ? `${state.t.download_error}  —  ${result.error}` : state.t.download_error, 'error');
    }
}


/* ============================================================
   MODAL: RESUMEN DE SINCRONIZACIÓN
   ============================================================ */
function showSummary() {
    const tbody = document.getElementById('summary-tbody');
    tbody.innerHTML = '';

    // Mapa de status → acción recomendada (usando textos del idioma activo)
    const actions = {
        upload_pending:   state.t.summary_action_upload,
        download_pending: state.t.summary_action_download,
        up_to_date:       state.t.summary_action_uptodate,
        not_in_cloud:     state.t.summary_action_first,
        not_configured:   state.t.summary_action_configure,
    };

    for (const [key, emu] of Object.entries(state.config.emulators)) {
        const info    = state.statuses[key] || {};
        const status  = info.status || 'not_configured';
        const dot     = STATUS_DOTS[status] || '○';
        const label   = state.t[`status_${status}`] || status;
        const cssClass = STATUS_CLASSES[status] || '';

        const tr = document.createElement('tr');
        tr.innerHTML = `
            <td>${emu.name}</td>
            <td class="${cssClass}">${dot}&nbsp;&nbsp;${label}</td>
            <td>${formatDate(info.local_mtime)}</td>
            <td>${formatDate(info.drive_mtime)}</td>
            <td>${actions[status] || '—'}</td>
        `;
        tbody.appendChild(tr);
    }

    document.getElementById('summary-overlay').classList.remove('hidden');
}

async function refreshSummary() {
    closeSummary();
    await refreshAllStatuses();  // vuelve a consultar Drive
    showSummary();               // reabre con datos frescos
}

function closeSummary() {
    document.getElementById('summary-overlay').classList.add('hidden');
}


/* ============================================================
   MODAL: CONFIGURACIÓN (SETTINGS)
   Los campos se generan en JavaScript para que sean dinámicos:
   si el usuario añade un emulador al JSON, aparece solo aquí.
   ============================================================ */
function renderSettingsFields() {
    const body = document.getElementById('settings-body');
    body.innerHTML = '';  // limpiar si se regenera (cambio de idioma)

    // --- Sección: Credenciales Google API ---
    const credsDiv = document.createElement('div');
    credsDiv.innerHTML = `
        <div class="settings-section-title">${state.t.creds_section || 'CREDENCIALES GOOGLE API'}</div>
        <div class="creds-status creds-missing" id="creds-status-text">
            &#9676;  ${state.t.status_checking || 'VERIFICANDO...'}
        </div>
        <button class="btn-import-creds" onclick="importCredentials()">
            &#9654;  ${state.t.creds_import_btn || 'IMPORTAR CREDENTIALS.JSON'}
        </button>
    `;
    body.appendChild(credsDiv);
    loadCredsStatus();

    // --- Sección: Idioma ---
    const langDiv = document.createElement('div');
    langDiv.innerHTML = `
        <div class="settings-section-title" data-t="settings_language">IDIOMA</div>
        <div class="lang-options">
            <button class="lang-btn ${state.config.settings.language === 'es' ? 'active' : ''}"
                    data-lang="es" onclick="selectLang(this)">Espa&#241;ol</button>
            <button class="lang-btn ${state.config.settings.language === 'en' ? 'active' : ''}"
                    data-lang="en" onclick="selectLang(this)">English</button>
        </div>
    `;
    body.appendChild(langDiv);

    // --- Sección: Rutas de emuladores ---
    const emuTitle = document.createElement('div');
    emuTitle.className = 'settings-section-title';
    emuTitle.textContent = state.t.settings_emulators || 'EMULADORES';
    body.appendChild(emuTitle);

    for (const [key, emu] of Object.entries(state.config.emulators)) {
        const group = document.createElement('div');
        group.className = 'settings-emulator-group';
        const editBtn = emu.custom
            ? `<button class="btn btn-secondary small" style="float:right;margin-top:-2px"
                       onclick="showEmulatorModal('${key}')">
                   ${state.t.emu_edit_btn || 'EDITAR'}
               </button>`
            : '';
        group.innerHTML = `
            <div class="settings-emulator-name">${emu.name}${editBtn}</div>

            <div class="settings-field">
                <label data-t="settings_local">LOCAL</label>
                <div class="field-row">
                    <input type="text" id="s-local-${key}"
                           value="${emu.local_path || ''}"
                           placeholder="/ruta/a/tus/guardados" readonly>
                    <button class="btn btn-secondary small"
                            onclick="browseSettingsFolder('${key}')">&#8230;</button>
                </div>
            </div>

            <div class="settings-field">
                <label data-t="settings_drive">DRIVE ID</label>
                <input type="text" id="s-drive-${key}"
                       value="${emu.drive_id || ''}"
                       placeholder="1aBcDeFgHiJkLmNoPqRsTuV...">
            </div>
        `;
        body.appendChild(group);
    }

    // --- Sección: Emuladores personalizados ---
    const customTitle = document.createElement('div');
    customTitle.className = 'settings-section-title';
    customTitle.textContent = state.t.emu_manage_section || 'EMULADORES PERSONALIZADOS';
    body.appendChild(customTitle);

    const customList = document.createElement('ul');
    customList.className = 'custom-emu-list';

    for (const [key, emu] of Object.entries(state.config.emulators)) {
        if (!emu.custom) continue;
        const li = document.createElement('li');
        li.className = 'custom-emu-item';
        li.innerHTML = `
            <div>
                <div class="custom-emu-item-name">${emu.name}</div>
                <div class="custom-emu-item-sub">${emu.emulator || ''}  ${emu.save_type || ''}</div>
            </div>
            <div class="custom-emu-item-actions">
                <button class="btn btn-secondary small"
                        onclick="showEmulatorModal('${key}')">
                    ${state.t.emu_edit_btn || 'EDITAR'}
                </button>
                <button class="btn btn-danger small"
                        onclick="deleteEmulator('${key}')">
                    ${state.t.emu_delete_btn || 'ELIMINAR'}
                </button>
            </div>
        `;
        customList.appendChild(li);
    }
    body.appendChild(customList);

    const addBtn = document.createElement('button');
    addBtn.className = 'btn-add-emu';
    addBtn.textContent = '+  ' + (state.t.emu_add_btn || 'AGREGAR EMULADOR');
    addBtn.onclick = () => showEmulatorModal(null);
    body.appendChild(addBtn);
}

/* Marca el botón de idioma seleccionado como activo */
function selectLang(btn) {
    document.querySelectorAll('.lang-btn').forEach(b => b.classList.remove('active'));
    btn.classList.add('active');
}

/* Abre el selector de carpeta nativo y rellena el campo del emulador */
async function browseSettingsFolder(key) {
    const path = await window.pywebview.api.select_folder();
    if (path) document.getElementById(`s-local-${key}`).value = path;
}

async function saveSettings() {
    // Leer el idioma seleccionado del botón activo
    const activeLang = document.querySelector('.lang-btn.active');
    if (activeLang) state.config.settings.language = activeLang.dataset.lang;

    // Leer las rutas de cada emulador desde los campos
    for (const key of Object.keys(state.config.emulators)) {
        const localEl = document.getElementById(`s-local-${key}`);
        const driveEl = document.getElementById(`s-drive-${key}`);
        if (localEl) state.config.emulators[key].local_path = localEl.value.trim();
        if (driveEl) state.config.emulators[key].drive_id   = driveEl.value.trim();
    }

    // Enviar el config actualizado a Python para que lo guarde en disco
    const result = await window.pywebview.api.save_settings(state.config);

    if (result.success) {
        closeSettings();
        // Recargar el diccionario de idioma (puede haber cambiado)
        state.t = await window.pywebview.api.get_lang();
        // Re-renderizar la UI completa con el nuevo idioma
        applyTranslations();
        renderCards();
        renderSettingsFields();
        // Re-aplicar los estados cacheados a las nuevas tarjetas
        for (const [key, status] of Object.entries(state.statuses)) {
            setCardStatus(key, status);
        }
    }
}

function showSettings()  { document.getElementById('settings-overlay').classList.remove('hidden'); }
function closeSettings() { document.getElementById('settings-overlay').classList.add('hidden'); }


/* ============================================================
   MODAL: ONBOARDING (Configuración just-in-time)
   Se activa cuando el usuario intenta sincronizar un emulador
   que no tiene local_path o drive_id configurados.
   Después de guardar, llama al callback para continuar la acción.
   ============================================================ */
function showOnboarding(key, callback) {
    state.onboardingKey      = key;
    state.onboardingCallback = callback;

    const emu = state.config.emulators[key];
    // Personalizar el encabezado con el nombre del emulador
    document.getElementById('ob-header').textContent =
        `${state.t.onboarding_title}: ${emu.name}`;

    // Pre-rellenar si ya hay valores parciales guardados
    document.getElementById('ob-local-path').value = emu.local_path || '';
    document.getElementById('ob-drive-id').value   = emu.drive_id   || '';

    document.getElementById('onboarding-overlay').classList.remove('hidden');
}

async function browseOnboardingFolder() {
    const path = await window.pywebview.api.select_folder(state.t.onboarding_local_path);
    if (path) document.getElementById('ob-local-path').value = path;
}

async function saveOnboarding() {
    const local = document.getElementById('ob-local-path').value.trim();
    const drive = document.getElementById('ob-drive-id').value.trim();

    // Validación visual: resaltar los campos vacíos con borde rojo
    const localEl = document.getElementById('ob-local-path');
    const driveEl = document.getElementById('ob-drive-id');
    localEl.classList.toggle('invalid', !local);
    driveEl.classList.toggle('invalid', !drive);
    if (!local || !drive) return;

    // Actualizar el objeto config en memoria
    state.config.emulators[state.onboardingKey].local_path = local;
    state.config.emulators[state.onboardingKey].drive_id   = drive;

    // Guardar en disco via Python
    await window.pywebview.api.save_settings(state.config);

    closeOnboarding();

    // Continuar con la acción que disparó el onboarding (upload o download)
    if (state.onboardingCallback) state.onboardingCallback();
}

function closeOnboarding() {
    document.getElementById('onboarding-overlay').classList.add('hidden');
    // Limpiar validaciones visuales
    document.getElementById('ob-local-path').classList.remove('invalid');
    document.getElementById('ob-drive-id').classList.remove('invalid');
    state.onboardingKey      = null;
    state.onboardingCallback = null;
}


/* ============================================================
   MODAL: CONFLICTO DE TIMESTAMPS

   Usa el patrón "Promise envuelta en modal" para poder usarlo
   con await dentro del flujo de upload/download:

       const proceed = await showConflict(localTs, driveTs);
       if (!proceed) return;  // usuario canceló

   Los botones del modal "resuelven" la Promise cuando el usuario
   hace clic, lo que desbloquea el await en el flujo principal.
   ============================================================ */
function showConflict(localMtime, driveMtime) {
    // Inyectar las fechas formateadas en el modal
    document.getElementById('conflict-local-date').textContent = formatDate(localMtime);
    document.getElementById('conflict-drive-date').textContent = formatDate(driveMtime);

    document.getElementById('conflict-overlay').classList.remove('hidden');

    /*
       new Promise((resolve, reject) => {...}) crea una Promise.
       La función que pasamos se ejecuta inmediatamente.
       'resolve' es la función que "completa" la Promise con un valor.
       Cuando el usuario hace clic en un botón, se llama resolve(true/false)
       y el await en handleUpload/handleDownload recibe ese valor.
    */
    return new Promise((resolve) => {

        document.getElementById('conflict-proceed-btn').onclick = () => {
            document.getElementById('conflict-overlay').classList.add('hidden');
            resolve(true);   // usuario eligió continuar
        };

        document.getElementById('conflict-cancel-btn').onclick = () => {
            document.getElementById('conflict-overlay').classList.add('hidden');
            resolve(false);  // usuario canceló
        };
    });
}


/* ============================================================
   MODAL: JUEGOS (multi_file — MelonDS / DS)

   Flujo:
   1. showGamesModal(key)  — abre el modal y dispara la carga
   2. loadGames(key)       — llama a Python para obtener la lista de saves
   3. renderGamesList(key, saves) — construye las filas de la tabla
   4. uploadGameFromBtn(btn) / downloadGameFromBtn(btn) — acciones por fila
   ============================================================ */

// Guardamos la key activa para que los botones de las filas la conozcan
state.gamesKey = null;

async function showGamesModal(key) {
    const emu = state.config.emulators[key];

    // Si le falta configuración, lanzar onboarding antes de abrir el modal
    if (!emu.local_path || !emu.drive_id) {
        showOnboarding(key, () => showGamesModal(key));
        return;
    }

    if (!state.connected) {
        alert(state.t.error_not_connected);
        return;
    }

    state.gamesKey = key;

    // Actualizar el título del modal con el nombre del sistema
    document.getElementById('games-modal-title').textContent =
        `${state.t.games_title || 'PARTIDAS'} — ${emu.name}`;

    // Mostrar spinner, ocultar tabla y mensaje vacío
    document.getElementById('games-loading').classList.remove('hidden');
    document.getElementById('games-table').classList.add('hidden');
    document.getElementById('games-empty').classList.add('hidden');

    document.getElementById('games-overlay').classList.remove('hidden');

    await loadGames(key);
}

async function loadGames(key) {
    const result = await window.pywebview.api.list_local_saves(key);

    document.getElementById('games-loading').classList.add('hidden');

    if (!result.success) {
        document.getElementById('games-empty').textContent =
            result.error || state.t.games_no_saves;
        document.getElementById('games-empty').classList.remove('hidden');
        return;
    }

    if (!result.saves || result.saves.length === 0) {
        document.getElementById('games-empty').classList.remove('hidden');
        return;
    }

    renderGamesList(key, result.saves);
    document.getElementById('games-table').classList.remove('hidden');
}

function renderGamesList(key, saves) {
    const tbody = document.getElementById('games-tbody');
    tbody.innerHTML = '';

    for (const save of saves) {
        // Nombre legible: quitar la extensión del archivo
        const gameName = save.filename.replace(/\.[^.]+$/, '');
        const dot      = STATUS_DOTS[save.status]   || '○';
        const cssClass = STATUS_CLASSES[save.status] || '';
        const label    = state.t[`status_${save.status}`] || save.status;

        const tr = document.createElement('tr');
        tr.id = `game-row-${CSS.escape(save.filename)}`;

        /*
           Usamos data-* attributes en lugar de onclick inline con strings
           para evitar problemas si el nombre del archivo tiene comillas,
           barras invertidas u otros caracteres especiales.
        */
        tr.innerHTML = `
            <td class="game-name">${gameName}</td>
            <td class="${cssClass}">${dot}&nbsp;${label}</td>
            <td>${formatDate(save.local_mtime)}</td>
            <td>${formatDate(save.drive_mtime)}</td>
            <td>
                <div class="games-actions">
                    <button class="btn-game-action btn-game-up"
                            data-key="${key}"
                            data-filepath="${save.filepath || ''}"
                            data-filename="${save.filename}"
                            ${!save.filepath ? 'disabled title="No existe localmente"' : ''}
                            onclick="uploadGameFromBtn(this)">↑</button>
                    <button class="btn-game-action btn-game-down"
                            data-key="${key}"
                            data-filename="${save.filename}"
                            onclick="downloadGameFromBtn(this)">↓</button>
                </div>
            </td>
        `;
        tbody.appendChild(tr);
    }
}

async function uploadGameFromBtn(btn) {
    const key      = btn.dataset.key;
    const filepath = btn.dataset.filepath;
    const filename = btn.dataset.filename;

    if (!filepath) return;

    // Verificar conflicto usando el status ya renderizado en la fila
    const row       = btn.closest('tr');
    const statusEl  = row ? row.querySelector('td:nth-child(2)') : null;
    const isConflict = statusEl && statusEl.className.includes('s-download_pending');
    if (isConflict) {
        // Leer tiempos de la fila para el modal de conflicto
        const saves = await window.pywebview.api.list_local_saves(key);
        const saveInfo = saves.saves?.find(s => s.filename === filename) || {};
        if (saveInfo.local_mtime && saveInfo.drive_mtime) {
            const proceed = await showConflict(saveInfo.local_mtime, saveInfo.drive_mtime);
            if (!proceed) return;
        }
    }

    // Deshabilitar todos los botones de la fila mientras se sube
    setRowLoading(row, true);
    const result = await window.pywebview.api.upload_single_save(key, filepath);
    setRowLoading(row, false);

    if (result.success) {
        setSysStatus('SAVE  UPLOADED', 3000);
        notify(state.t.games_upload_success, 'success');
        await loadGames(key);
    } else {
        setSysStatus('UPLOAD  FAILED', 4000);
        notify(result.error ? `${state.t.games_upload_error}  —  ${result.error}` : state.t.games_upload_error, 'error');
    }
}

async function downloadGameFromBtn(btn) {
    const key      = btn.dataset.key;
    const filename = btn.dataset.filename;

    const row      = btn.closest('tr');
    const statusEl = row ? row.querySelector('td:nth-child(2)') : null;
    const isConflict = statusEl && statusEl.className.includes('s-upload_pending');
    if (isConflict) {
        const saves = await window.pywebview.api.list_local_saves(key);
        const saveInfo = saves.saves?.find(s => s.filename === filename) || {};
        if (saveInfo.local_mtime && saveInfo.drive_mtime) {
            const proceed = await showConflict(saveInfo.local_mtime, saveInfo.drive_mtime);
            if (!proceed) return;
        }
    }

    setRowLoading(row, true);
    const result = await window.pywebview.api.download_single_save(key, filename);
    setRowLoading(row, false);

    if (result.success) {
        setSysStatus('SAVE  DOWNLOADED', 3000);
        notify(state.t.games_download_success, 'success');
        await loadGames(key);
    } else {
        setSysStatus('DOWNLOAD  FAILED', 4000);
        notify(result.error ? `${state.t.games_download_error}  —  ${result.error}` : state.t.games_download_error, 'error');
    }
}

/* Deshabilita/habilita los botones de acción de una fila de la tabla */
function setRowLoading(row, loading) {
    if (!row) return;
    row.querySelectorAll('.btn-game-action').forEach(b => {
        b.disabled = loading;
    });
}

function closeGamesModal() {
    document.getElementById('games-overlay').classList.add('hidden');
    state.gamesKey = null;
}


/* ============================================================
   UTILIDADES
   ============================================================ */

/*
   Convierte un Unix timestamp (segundos) a fecha legible.
   Python usa segundos desde epoch; JavaScript usa milisegundos,
   por eso multiplicamos por 1000 al crear el Date.
*/
function formatDate(ts) {
    if (!ts) return '—';
    const d = new Date(ts * 1000);
    return d.toLocaleDateString() + '  ' + d.toLocaleTimeString([], {
        hour:   '2-digit',
        minute: '2-digit',
    });
}

/*
   Construye el HTML del icono para una tarjeta.
   Usa el cache state.icons (data URLs base64 cargados por Python al inicio)
   para evitar restricciones del servidor virtual de WebView con rutas locales.
   Si no hay data URL disponible, usa el emoji fallback de EMU_ICONS.
*/
function getCardIconHtml(key, emu) {
    const dataUrl = state.icons && state.icons[key];
    if (dataUrl) {
        return `<img class="card-icon-img" src="${dataUrl}" alt="${emu.name}">`;
    }
    return `<span class="card-icon">${EMU_ICONS[key] || '&#127918;'}</span>`;
}


/* ============================================================
   CREDENCIALES GOOGLE API
   ============================================================ */

async function loadCredsStatus() {
    const el = document.getElementById('creds-status-text');
    if (!el) return;
    const result = await window.pywebview.api.check_credentials();
    if (result.exists) {
        el.className = 'creds-status creds-ok';
        el.textContent = '● ' + (state.t.creds_status_ok || 'credentials.json encontrado');
    } else {
        el.className = 'creds-status creds-missing';
        el.textContent = '○ ' + (state.t.creds_status_missing || 'No se encontró credentials.json');
    }
}

async function importCredentials() {
    const result = await window.pywebview.api.import_credentials();
    if (result.cancelled) return;
    if (result.success) {
        notify(state.t.creds_import_success || 'Credenciales importadas.', 'success');
        loadCredsStatus();
    } else {
        notify(state.t.creds_import_error || 'Error al importar credenciales.', 'error');
    }
}


/* ============================================================
   MODAL: GESTIÓN DE EMULADOR (Agregar / Editar)
   ============================================================ */

// null = modo agregar, string = modo editar con esa clave
state.emulatorModalKey = null;

function showEmulatorModal(key) {
    state.emulatorModalKey = key;
    const isEdit = key !== null;

    // Título del modal según el modo
    document.getElementById('emulator-modal-header').textContent =
        isEdit
            ? (state.t.emu_modal_edit_title || 'EDITAR EMULADOR')
            : (state.t.emu_modal_add_title  || 'AGREGAR EMULADOR');

    // El campo "Identificador" solo es relevante al agregar
    document.getElementById('em-key-field').style.display = isEdit ? 'none' : '';

    if (isEdit) {
        const emu = state.config.emulators[key];
        document.getElementById('em-name').value       = emu.name       || '';
        document.getElementById('em-emulator').value   = emu.emulator   || '';
        document.getElementById('em-key').value         = key;
        document.getElementById('em-extension').value  = emu.extension  || '';
        document.getElementById('em-icon').value        = emu.icon       || '';
        document.getElementById('em-local-path').value = emu.local_path  || '';
        document.getElementById('em-drive-id').value   = emu.drive_id   || '';
        selectSaveTypeByValue(emu.save_type || 'file');
    } else {
        ['em-name','em-emulator','em-key','em-extension','em-icon','em-local-path','em-drive-id']
            .forEach(id => { document.getElementById(id).value = ''; });
        selectSaveTypeByValue('file');
    }

    updateExtensionFieldVisibility();
    document.getElementById('emulator-modal-overlay').classList.remove('hidden');
}

function closeEmulatorModal() {
    document.getElementById('emulator-modal-overlay').classList.add('hidden');
    state.emulatorModalKey = null;
}

function selectSaveType(btn) {
    document.querySelectorAll('.save-type-btn').forEach(b => b.classList.remove('active'));
    btn.classList.add('active');
    updateExtensionFieldVisibility();
}

function selectSaveTypeByValue(type) {
    document.querySelectorAll('.save-type-btn').forEach(b => {
        b.classList.toggle('active', b.dataset.type === type);
    });
    updateExtensionFieldVisibility();
}

function updateExtensionFieldVisibility() {
    const active = document.querySelector('.save-type-btn.active');
    document.getElementById('em-extension-field').style.display =
        (active && active.dataset.type === 'folder') ? 'none' : '';
}

async function selectEmulatorIcon() {
    const path = await window.pywebview.api.select_emulator_icon();
    if (path) document.getElementById('em-icon').value = path;
}

async function browseEmulatorFolder() {
    const path = await window.pywebview.api.select_folder();
    if (path) document.getElementById('em-local-path').value = path;
}

async function saveEmulatorModal() {
    const isEdit   = state.emulatorModalKey !== null;
    const key      = isEdit
        ? state.emulatorModalKey
        : document.getElementById('em-key').value.trim().toLowerCase();
    const active   = document.querySelector('.save-type-btn.active');
    const saveType = active ? active.dataset.type : 'file';

    const data = {
        name:       document.getElementById('em-name').value.trim(),
        emulator:   document.getElementById('em-emulator').value.trim(),
        key,
        extension:  saveType === 'folder' ? 'folder' : document.getElementById('em-extension').value.trim(),
        save_type:  saveType,
        icon:       document.getElementById('em-icon').value.trim(),
        local_path: document.getElementById('em-local-path').value.trim(),
        drive_id:   document.getElementById('em-drive-id').value.trim(),
    };

    const result = isEdit
        ? await window.pywebview.api.update_emulator(key, data)
        : await window.pywebview.api.add_emulator(data);

    if (result.success) {
        notify(state.t.emu_saved_success || 'Emulador guardado.', 'success');
        state.config = await window.pywebview.api.get_config();
        state.icons  = await window.pywebview.api.get_all_icons();
        closeEmulatorModal();
        renderCards();
        renderSettingsFields();
        // Reaplicar estados cacheados a las nuevas tarjetas
        for (const [k, status] of Object.entries(state.statuses)) {
            setCardStatus(k, status);
        }
    } else {
        const msgs = {
            invalid_key: state.t.emu_key_invalid || 'Clave inválida.',
            key_exists:  state.t.emu_key_exists  || 'Ya existe un emulador con esa clave.',
        };
        notify(msgs[result.error] || result.error || 'Error.', 'error');
    }
}

async function deleteEmulator(key) {
    const result = await window.pywebview.api.delete_emulator(key);
    if (result.success) {
        notify(state.t.emu_deleted_success || 'Emulador eliminado.', 'success');
        state.config = await window.pywebview.api.get_config();
        // Limpiar estado cacheado del emulador eliminado
        delete state.statuses[key];
        renderCards();
        renderSettingsFields();
    } else {
        notify(result.error || 'Error.', 'error');
    }
}
