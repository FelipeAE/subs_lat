"""Proveedor de subtítulos Argenteam - Excelente para español latino."""
import re
import os
import requests
from bs4 import BeautifulSoup
from typing import List, Optional
from urllib.parse import urljoin, quote

from .base import SubtitleProvider, SubtitleResult, Language


class ArgenteamProvider(SubtitleProvider):
    """Proveedor para Argenteam.net - Muy bueno para español latino."""
    
    name = "Argenteam"
    supported_languages = [Language.SPANISH_LATAM]
    BASE_URL = "https://argenteam.net"
    
    def search(self, query: str, language: Optional[Language] = None) -> List[SubtitleResult]:
        """Busca subtítulos en Argenteam."""
        results = []
        
        try:
            search_url = f"{self.BASE_URL}/search"
            params = {'q': query}
            
            response = requests.get(
                search_url,
                params=params,
                headers=self._get_headers(),
                timeout=15
            )
            
            soup = BeautifulSoup(response.text, 'lxml')
            
            # Buscar resultados de películas/series
            for item in soup.select('div.result-item, div.movie-item, article'):
                try:
                    link = item.find('a', href=True)
                    if not link:
                        continue
                    
                    href = link.get('href', '')
                    if '/episode/' not in href and '/movie/' not in href and '/subtitles/' not in href:
                        continue
                    
                    title = link.get_text(strip=True)
                    if not title:
                        title_elem = item.find(['h2', 'h3', 'h4', 'span'])
                        title = title_elem.get_text(strip=True) if title_elem else "Sin título"
                    
                    detail_url = urljoin(self.BASE_URL, href)
                    
                    result = SubtitleResult(
                        title=title,
                        language=Language.SPANISH_LATAM,
                        provider=self.name,
                        download_url=detail_url,
                        description="",
                    )
                    results.append(result)
                    
                except Exception:
                    continue
            
            # Si no encontramos en búsqueda, intentar en API
            if not results:
                results = self._search_api(query)
                    
        except Exception as e:
            print(f"Error buscando en Argenteam: {e}")
        
        return results[:15]
    
    def _search_api(self, query: str) -> List[SubtitleResult]:
        """Búsqueda alternativa usando API."""
        results = []
        try:
            api_url = f"{self.BASE_URL}/api/v1/search"
            params = {'q': query}
            
            response = requests.get(
                api_url,
                params=params,
                headers=self._get_headers(),
                timeout=15
            )
            
            if response.status_code == 200:
                data = response.json()
                for item in data.get('results', []):
                    result = SubtitleResult(
                        title=item.get('title', 'Sin título'),
                        language=Language.SPANISH_LATAM,
                        provider=self.name,
                        download_url=item.get('url', ''),
                        description=item.get('description', ''),
                    )
                    results.append(result)
                    
        except Exception:
            pass
        
        return results
    
    def download(self, subtitle: SubtitleResult, destination: str) -> Optional[str]:
        """Descarga un subtítulo de Argenteam."""
        try:
            response = requests.get(
                subtitle.download_url,
                headers=self._get_headers(),
                timeout=15
            )
            
            soup = BeautifulSoup(response.text, 'lxml')
            
            # Buscar link de descarga
            download_link = None
            for a in soup.find_all('a', href=True):
                href = a.get('href', '')
                if 'download' in href.lower() or '.srt' in href or '.zip' in href:
                    download_link = urljoin(self.BASE_URL, href)
                    break
            
            if not download_link:
                btn = soup.select_one('a.download-btn, a.btn-download, a[href*="subtitles"]')
                if btn:
                    download_link = urljoin(self.BASE_URL, btn.get('href', ''))
            
            if not download_link:
                return None
            
            # Descargar
            dl_response = requests.get(
                download_link,
                headers=self._get_headers(),
                timeout=30,
                allow_redirects=True
            )
            
            filename = "subtitle.srt"
            content_disp = dl_response.headers.get('Content-Disposition', '')
            if 'filename=' in content_disp:
                match = re.search(r'filename="?([^";\n]+)"?', content_disp)
                if match:
                    filename = match.group(1)
            
            filepath = os.path.join(destination, filename)
            
            with open(filepath, 'wb') as f:
                f.write(dl_response.content)
            
            return filepath
            
        except Exception as e:
            print(f"Error descargando de Argenteam: {e}")
            return None
