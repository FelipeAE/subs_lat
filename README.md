# 🎬 Subtitle Downloader

Aplicación de escritorio para buscar y descargar subtítulos automáticamente.

## Características

- 📁 Escanea carpetas con archivos de video (.mkv, .mp4, .avi, etc.)
- 🔍 Busca subtítulos con sistema de fallback:
  - **OpenSubtitles** - Proveedor principal (la mayor base de datos)
  - **Subliminal** - Fallback con múltiples proveedores (gestdown, podnapisi, tvsubtitles)
- 🌍 Idiomas soportados:
  - Español
  - Inglés
- ⬇️ Descarga y renombra automáticamente los subtítulos
- 🎯 Modo automático: Arrastra una carpeta para descargar todo

## Requisitos

- Python 3.8+
- Windows / Linux / macOS

## Instalación

```bash
# Clonar o descargar el proyecto
cd subs_lat

# Instalar dependencias
pip install -r requirements.txt

# Configurar API key de OpenSubtitles
cp .env.example .env
# Editar .env y agregar tu API key
```

## Uso

```bash
python main.py
```

### Interfaz

1. **Arrastrar carpeta**: Arrastra una carpeta con videos para descarga automática
2. **Seleccionar carpeta**: O usa el botón "Examinar"
3. **Videos Encontrados**: Lista de archivos de video (✓ = ya tiene subtítulo)
4. **Buscar Subtítulos**: Busca para el video seleccionado
5. **Descargar Todos**: Descarga automáticamente para todos los videos sin subtítulo

### Sistema de Fallback

La app busca en orden de prioridad:
1. **OpenSubtitles** (por hash del archivo - más preciso)
2. **OpenSubtitles** (por nombre)
3. **Subliminal** (proveedores alternativos: gestdown, podnapisi, tvsubtitles)

## Configuración de OpenSubtitles

Para usar la aplicación necesitas una API key gratuita:

1. Registrarte en [opensubtitles.com](https://www.opensubtitles.com)
2. Obtener API key en [Consumer API](https://www.opensubtitles.com/consumers)
3. Copiar `.env.example` a `.env`:

```bash
cp .env.example .env
```

4. Editar `.env`:

```
OPENSUBTITLES_API_KEY=tu_api_key_aqui
```

## Estructura del Proyecto

```
subs_lat/
├── main.py                 # Aplicación principal (GUI)
├── requirements.txt        # Dependencias
├── .env.example            # Plantilla de configuración
├── README.md
└── src/
    ├── config.py           # Configuración (carga .env)
    └── utils/
        ├── file_utils.py   # Manejo de archivos
        └── parser.py       # Parser de nombres de video
```

## Licencia

MIT License
