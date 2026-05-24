# Cloud Save Hub - Cloud Emu Hub

---

Este programa permite **subir y descargar archivos de guardado de distintos emuladores** directamente desde Google Drive para mantener **backups seguros de tus partidas**.

---

This program allows you to **upload and download save files from diferent emulators** directly from Google Drive to keep **safe backups of your save files**.

---

# Why?

### English

I had a small but annoying problem. When I bought my **ROG Ally**, I wanted to continue my PS2 games between it and my desktop PC. However, constantly trying to figure out which save file was the most recent and sending memory cards to myself over and over again quickly became tedious.

That makes me create a frist program that managed the memory cards using drive. Then I remember "Bro I play more stuff" so that makes me create a full hub that manage my files.

### Español

Tenía un pequeño pero molesto problema. Cuando compré mi **ROG Ally**, quería poder continuar mis partidas de PS2 entre esta y mi PC de escritorio. Pero estar tratando de sincronizar qué archivo guardado era el más reciente y enviarme a mí mismo las memory cards una y otra vez se volvió realmente tedioso.

Ese pensamiento me hizo pensar en crear mi primer programa para manejar las memory cards de ps2. Luego recorde que realmente juego mas cosas, eso me llevo a evolucionarlo a un Hub completo con diversos emuladores.

---

# Features

### English

- Upload your save files to Google Drive  
- Download saves from the cloud  
- Automatic overwrite if the save already exists  
- Simple graphical interface (Tkinter)  
- Uses Google Drive API  
- Designed for quick backup and restore across multiple devices  

### Español

- Subir los archivos de guardado a Google Drive  
- Descargar partidas desde la nube  
- Sobrescribe automáticamente archivos existentes  
- Interfaz gráfica simple (Tkinter)  
- Utiliza la API de Google Drive  
- Diseñado para respaldos rápidos de partidas en distintos dispositivos  

---

# Preview

<img width="946" height="593" alt="Main - online" src="https://github.com/user-attachments/assets/4af2edc8-c9cf-4846-ae9e-9e38b278a0aa" />


---

# Requirements

- Python **3.9+**
- google-api-python-client
- google-auth
- google-auth-oauthlib
- google-auth-httplib2
- A Google account with access to Drive  
- Una cuenta de Google con acceso a Drive

---

# Google Drive Setup | Configuración de Google Drive

Before running the program you must configure **Google Drive API and OAuth2 credentials**.

Antes de ejecutar el programa debes configurar **Google Drive API y las credenciales OAuth2**.

---

# Create OAuth Credentials | Crear credenciales OAuth

https://console.cloud.google.com

### Steps

- Open **APIs & Services** | Abre **APIs y Servicios**

<img width="886" height="486" src="https://github.com/user-attachments/assets/49e13288-afcc-443c-94e1-7aa8ecc056e2">

- Go to **Credentials** | Ve a **Credenciales**

<img width="868" height="216" src="https://github.com/user-attachments/assets/8db0fb38-e037-4a51-ae10-f0ee8b096e1c">

- Click **Create Credentials** | Dale click a **Crear credenciales**

<img width="886" height="325" src="https://github.com/user-attachments/assets/41971c99-e26b-4013-b856-2b62667ab1e5">

- Select **OAuth Client ID** | Elige **Cliente ID OAuth**

<img width="824" height="530" src="https://github.com/user-attachments/assets/8ab4040b-2957-4100-9433-5088dc8fc11c">

- Application type: **Desktop App** | **Aplicación de escritorio**

<img width="878" height="667" src="https://github.com/user-attachments/assets/1f6dacfe-6bf3-4338-ab60-162e89af7864">

<img width="886" height="660" src="https://github.com/user-attachments/assets/39ab8674-d8bd-43b1-a004-f2b3f19f6115">

- Download the credentials JSON and rename it to **credentials.json**  
- Descarga el archivo JSON y renómbralo como **credentials.json**

---

# Important | Importante

You must give access to the account that will be used as storage.  
Debes darle acceso a la cuenta que se utilizará como almacenamiento.

- Open **APIs & Services**

<img width="405" height="475" src="https://github.com/user-attachments/assets/a019e1e0-5f1a-4dce-80b6-d2009b4aadd9">

- Go to **Audience / Public**

<img width="389" height="405" src="https://github.com/user-attachments/assets/7e6c3b53-db16-4e36-a952-ae43f14dca9a">

- Add the user emails that will have access to the save files  
- Agrega los correos de los usuarios que podrán acceder a los archivos

<img width="872" height="947" src="https://github.com/user-attachments/assets/50bd36e2-bec9-469b-ae9c-f9830e8b6624">

<img width="886" height="338" src="https://github.com/user-attachments/assets/c6bb3fb4-a14b-426e-a89d-1ecd1a11684d">

---

# Enable Drive API | Activar Drive API

### Steps

- Search **Drive** in Google Cloud Console  
- Busca **Drive** en la barra de búsqueda

<img width="886" height="292" src="https://github.com/user-attachments/assets/a8829264-7f04-49d0-981c-ba2f9b75a694">

- Enable **Google Drive API**

<img width="886" height="351" src="https://github.com/user-attachments/assets/45c120cd-7ea6-4f5c-a4a0-3b1166513a3a">

---

# Important | Importante

Remember to change the **Drive Folder ID** in the code.

Recuerda cambiar el **ID del folder de Drive** dentro del código.

---

# License

Free to use and modify for personal use.
