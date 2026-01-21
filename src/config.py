"""Configuración de la aplicación."""
import os
from pathlib import Path

# Cargar variables de entorno desde .env si existe
try:
    from dotenv import load_dotenv
    env_path = Path(__file__).parent.parent / '.env'
    load_dotenv(env_path)
except ImportError:
    pass

# OpenSubtitles API
OPENSUBTITLES_API_KEY = os.getenv('OPENSUBTITLES_API_KEY', '')
API_URL = "https://api.opensubtitles.com/api/v1"
