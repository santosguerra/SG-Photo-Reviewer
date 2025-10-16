# Photo Reviewer

Aplicación web Flask para revisar y descartar fotos de sesiones fotográficas en servidor Linux.

## Características

- **Navegador de carpetas** para explorar puntos de montaje (discos Samba, etc.)
- **Vista de grilla** responsive con lazy loading de miniaturas
- **Vista de carrusel** con navegación por teclado y preload de imágenes
- **Detección de archivos RAW huérfanos** (RAW sin JPG pareado) con generación de miniaturas
- **Badges visuales** que muestran formato (JPG+RAW, Solo JPG, Solo RAW) y marca de cámara
- **Tooltips informativos** con nombre, tamaño y estado de cada foto
- **Marcado de fotos** para revisión posterior con contadores en tiempo real
- **Movimiento automático** de JPG y archivos RAW pareados a carpeta de revisión
- **Sistema de restauración** para devolver fotos desde carpeta de revisión a carpeta original
- **Sistema de eliminación** con confirmación segura (requiere escribir "ELIMINAR")
- **Gestión de configuración** persistente con opción para habilitar/deshabilitar eliminación
- **Diagnóstico de permisos** para troubleshooting
- **Pestaña de Ayuda** con documentación integrada

## Instalación

### 1. Instalar dependencias del sistema

```bash
# Instalar Python 3 y pip
sudo apt update
sudo apt install python3 python3-pip python3-venv

# Instalar librerías necesarias para rawpy
sudo apt install libjpeg-dev zlib1g-dev
```

### 2. Crear entorno virtual e instalar paquetes Python

```bash
cd /home/santosg/photo-reviewer
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 3. Configurar servicio systemd

```bash
# Copiar archivo de servicio
sudo cp photo-reviewer.service /etc/systemd/system/

# Recargar systemd
sudo systemctl daemon-reload

# Habilitar el servicio para que inicie automáticamente
sudo systemctl enable photo-reviewer

# Iniciar el servicio
sudo systemctl start photo-reviewer

# Verificar estado
sudo systemctl status photo-reviewer
```

## Uso

### Acceder a la aplicación

Abre tu navegador y ve a:

```
http://IP-SERVIDOR:5500
```

O si estás en el mismo servidor:

```
http://localhost:5500
```

### Flujo de trabajo

1. **Configuración**
   - Agrega tus puntos de montaje (ej: `/mnt/nvme`, `/data1`)
   - Define el nombre de la carpeta destino (por defecto: `para-revision`)
   - Opcionalmente, habilita el botón de eliminar (por seguridad está desactivado por defecto)
   - Guarda la configuración
   - Revisa el diagnóstico de permisos

2. **Navegador**
   - Navega por tus carpetas usando los breadcrumbs
   - Haz clic en las carpetas para explorar
   - Cuando estés en la carpeta con las fotos, haz clic en "Cargar Sesión"

3. **Revisor**
   - **Vista Grilla**: Visualiza todas las miniaturas con badges de formato y cámara
     - Badges verdes: JPG+RAW
     - Badges naranjas: Solo JPG
     - Badges azules: Solo RAW
     - Badge gris debajo: Marca de cámara (Canon, Sony, Nikon, etc.)
     - Pasa el mouse sobre una foto para ver detalles (nombre, tamaño, estado RAW)
   - **Vista Carrusel**: Usa las flechas o el teclado para revisar foto por foto
     - La siguiente imagen se precarga automáticamente para navegación fluida
     - Los badges se muestran en la esquina superior izquierda

   **Atajos de teclado en carrusel:**
   - `←` `→`: Navegar entre fotos
   - `Espacio`: Marcar/desmarcar foto actual
   - `G` o `Esc`: Volver a vista grilla

4. **Gestión de fotos**

   **Si estás en una carpeta normal:**
   - Haz clic en "Mover X fotos a revisión"
   - Las fotos JPG y sus archivos RAW pareados se moverán a la subcarpeta configurada

   **Si estás en la carpeta de revisión:**
   - Haz clic en "Restaurar X fotos" para devolverlas a la carpeta padre
   - Si habilitaste la eliminación en Configuración, verás "Eliminar X fotos definitivamente"
     - Al hacer clic, aparecerá un modal de confirmación
     - Debes escribir exactamente "ELIMINAR" para confirmar
     - Esta acción es irreversible y eliminará tanto JPG como RAW

5. **Archivos RAW huérfanos**
   - La aplicación detecta automáticamente archivos RAW sin JPG pareado
   - Genera miniaturas de estos RAW usando rawpy
   - Los muestra con badge azul "Solo RAW"
   - Puedes marcarlos, moverlos y eliminarlos igual que JPG

## Gestión del servicio

```bash
# Iniciar servicio
sudo systemctl start photo-reviewer

# Detener servicio
sudo systemctl stop photo-reviewer

# Reiniciar servicio
sudo systemctl restart photo-reviewer

# Ver logs
sudo journalctl -u photo-reviewer -f

# Ver estado
sudo systemctl status photo-reviewer
```

## Troubleshooting de permisos

### Problema: No puedo leer/escribir en un punto de montaje

```bash
# Corregir permisos de usuario
sudo chown -R santosg:santosg /ruta/problema
sudo chmod -R 755 /ruta/problema
```

### Problema: Montaje Samba sin permisos

```bash
# Remontar con permisos de usuario
sudo mount -o remount,uid=santosg,gid=santosg /punto/montaje

# O agregar a /etc/fstab para que sea permanente:
# //servidor/share /punto/montaje cifs credentials=/home/santosg/.smbcredentials,uid=santosg,gid=santosg 0 0
```

### Problema: Permiso denegado al crear thumbnails

```bash
# Asegurar permisos en directorio de aplicación
sudo chown -R santosg:santosg /home/santosg/photo-reviewer
sudo chmod -R 755 /home/santosg/photo-reviewer
```

### Problema: El servicio no inicia

```bash
# Ver logs detallados
sudo journalctl -u photo-reviewer -n 50

# Verificar que gunicorn está instalado
source /home/santosg/photo-reviewer/venv/bin/activate
which gunicorn

# Probar manualmente
cd /home/santosg/photo-reviewer
source venv/bin/activate
python3 app.py
```

## Formatos soportados

**JPG/JPEG**: Formato principal para visualización

**RAW soportados** (pareados automáticamente):
- `.CR2`, `.CR3` (Canon)
- `.ARW` (Sony)
- `.NEF` (Nikon)
- `.PEF` (Pentax)
- `.DNG` (Adobe)
- `.RAF` (Fujifilm)
- `.ORF` (Olympus)

## Configuración

La configuración se guarda en `config.json` con estos valores por defecto:

```json
{
  "mount_points": ["/mnt/nvme", "/data1"],
  "destination_folder": "para-revision",
  "enable_delete_button": false
}
```

### Opciones de configuración:

- **mount_points**: Lista de rutas absolutas a directorios montados que deseas explorar
- **destination_folder**: Nombre de la subcarpeta donde se moverán las fotos marcadas para revisión
- **enable_delete_button**: Boolean que controla si se muestra el botón de eliminación permanente en la carpeta de revisión (por defecto: false por seguridad)

## Estructura del proyecto

```
photo-reviewer/
├── app.py                      # Backend Flask
├── config.py                   # Gestión de configuración
├── requirements.txt            # Dependencias Python
├── photo-reviewer.service      # Servicio systemd
├── config.json                 # Configuración (generada automáticamente)
├── static/
│   ├── css/
│   │   └── style.css          # Estilos
│   ├── js/
│   │   └── app.js             # Lógica frontend
│   └── thumbnails/            # Cache de miniaturas (generado automáticamente)
└── templates/
    └── index.html             # Interfaz HTML
```

## Seguridad

- Solo se permite navegación dentro de puntos de montaje configurados
- Validación de path traversal para prevenir acceso a rutas no autorizadas
- Sin exposición de rutas del sistema
- Cache de miniaturas con hash para evitar colisiones
- Eliminación de archivos requiere confirmación explícita (escribir "ELIMINAR")
- El botón de eliminación está desactivado por defecto y debe habilitarse en configuración
- Solo se puede eliminar desde carpetas de revisión detectadas automáticamente

## API Endpoints

### Configuración
- `GET /api/config` - Obtener configuración actual
- `POST /api/config` - Guardar nueva configuración
- `GET /api/check-permissions?path=X` - Verificar permisos de lectura/escritura

### Navegación
- `GET /api/browse?path=X` - Listar carpetas en una ruta
- `GET /api/scan?path=X` - Escanear carpeta y devolver lista de fotos (JPG y RAW huérfanos)

### Imágenes
- `GET /api/thumbnail?path=X` - Obtener miniatura 300px (genera y cachea)
- `GET /api/image?path=X` - Obtener imagen completa (convierte RAW a JPG si es necesario)

### Operaciones de archivos
- `POST /api/move` - Mover JPG+RAW a carpeta de revisión
- `POST /api/restore` - Restaurar JPG+RAW desde carpeta de revisión a carpeta padre
- `POST /api/delete` - Eliminar JPG+RAW permanentemente

## Desarrollo

Para ejecutar en modo desarrollo:

```bash
cd /home/santosg/photo-reviewer
source venv/bin/activate
python3 app.py
```

La aplicación se ejecutará en `http://0.0.0.0:5500` con debug habilitado.

## Licencia

Uso libre para proyectos personales.
