"""Proveedor de subtítulos OpenSubtitles - API REST."""
import os
import re
import requests
from typing import List, Optional

from .base import SubtitleProvider, SubtitleResult, Language


class OpenSubtitlesProvider(SubtitleProvider):
    """Proveedor para OpenSubtitles.com usando la API REST."""
    
    name = "OpenSubtitles"
    supported_languages = [Language.SPANISH_SPAIN, Language.SPANISH_LATAM, Language.ENGLISH]
    API_URL = "https://api.opensubtitles.com/api/v1"
    
    # Mapeo de idiomas
    LANG_MAP = {
        Language.SPANISH_SPAIN: "es",
        Language.SPANISH_LATAM: "es",
        Language.ENGLISH: "en",
    }
    
    def __init__(self, api_key: str = "", username: str = "", password: str = ""):
        """
        Inicializa el proveedor.
        
        Args:
            api_key: API key de OpenSubtitles (obtener en opensubtitles.com)
            username: Usuario (opcional, para más descargas)
            password: Contraseña (opcional)
        """
        self.api_key = api_key
        self.username = username
        self.password = password
        self.token = None
    
    def _get_api_headers(self) -> dict:
        """Headers para la API."""
        headers = {
            'Api-Key': self.api_key,
            'Content-Type': 'application/json',
            'User-Agent': 'SubtitleDownloader v1.0',
        }
        if self.token:
            headers['Authorization'] = f'Bearer {self.token}'
        return headers
    
    def login(self) -> bool:
        """Autentica con la API para obtener un token."""
        if not self.api_key or not self.username or not self.password:
            return False
        
        try:
            response = requests.post(
                f"{self.API_URL}/login",
                json={
                    'username': self.username,
                    'password': self.password,
                },
                headers=self._get_api_headers(),
                timeout=15
            )
            
            if response.status_code == 200:
                data = response.json()
                self.token = data.get('token')
                return True
                
        except Exception as e:
            print(f"Error en login OpenSubtitles: {e}")
        
        return False
    
    def search(self, query: str, language: Optional[Language] = None) -> List[SubtitleResult]:
        """Busca subtítulos en OpenSubtitles."""
        results = []
        
        if not self.api_key:
            print("OpenSubtitles requiere API key. Obtener en: https://www.opensubtitles.com/consumers")
            return results
        
        try:
            params = {
                'query': query,
            }
            
            if language:
                params['languages'] = self.LANG_MAP.get(language, 'es')
            else:
                params['languages'] = 'es,en'
            
            response = requests.get(
                f"{self.API_URL}/subtitles",
                params=params,
                headers=self._get_api_headers(),
                timeout=15
            )
            
            if response.status_code != 200:
                print(f"Error OpenSubtitles API: {response.status_code}")
                return results
            
            data = response.json()
            
            for item in data.get('data', []):
                try:
                    attributes = item.get('attributes', {})
                    
                    # Determinar idioma
                    lang_code = attributes.get('language', 'es')
                    if lang_code == 'en':
                        lang = Language.ENGLISH
                    else:
                        lang = Language.SPANISH_LATAM
                    
                    # Obtener info del archivo
                    files = attributes.get('files', [])
                    if not files:
                        continue
                    
                    file_info = files[0]
                    
                    result = SubtitleResult(
                        title=attributes.get('release', 'Sin título'),
                        language=lang,
                        provider=self.name,
                        download_url=str(file_info.get('file_id', '')),
                        description=attributes.get('comments', ''),
                        downloads=attributes.get('download_count', 0),
                        rating=float(attributes.get('ratings', 0)),
                    )
                    results.append(result)
                    
                except Exception:
                    continue
                    
        except Exception as e:
            print(f"Error buscando en OpenSubtitles: {e}")
        
        return results[:15]
    
    def download(self, subtitle: SubtitleResult, destination: str) -> Optional[str]:
        """Descarga un subtítulo de OpenSubtitles."""
        if not self.api_key:
            return None
        
        try:
            # Solicitar link de descarga
            response = requests.post(
                f"{self.API_URL}/download",
                json={'file_id': int(subtitle.download_url)},
                headers=self._get_api_headers(),
                timeout=15
            )
            
            if response.status_code != 200:
                print(f"Error obteniendo link: {response.status_code}")
                return None
            
            data = response.json()
            download_link = data.get('link')
            
            if not download_link:
                return None
            
            # Descargar archivo
            dl_response = requests.get(download_link, timeout=30)
            
            filename = data.get('file_name', 'subtitle.srt')
            filepath = os.path.join(destination, filename)
            
            with open(filepath, 'wb') as f:
                f.write(dl_response.content)
            
            return filepath
            
        except Exception as e:
            print(f"Error descargando de OpenSubtitles: {e}")
            return None
