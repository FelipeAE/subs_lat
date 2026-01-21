"""Proveedor de subtítulos TuSubtitulo - Español España y Latino."""
import re
import os
import requests
from bs4 import BeautifulSoup
from typing import List, Optional
from urllib.parse import urljoin, quote

from .base import SubtitleProvider, SubtitleResult, Language


class TuSubtituloProvider(SubtitleProvider):
    """Proveedor para tusubtitulo.com - Subtítulos en español."""
    
    name = "TuSubtitulo"
    supported_languages = [Language.SPANISH_SPAIN, Language.SPANISH_LATAM]
    BASE_URL = "https://www.tusubtitulo.com"
    
    def search(self, query: str, language: Optional[Language] = None) -> List[SubtitleResult]:
        """Busca subtítulos en TuSubtitulo."""
        results = []
        
        try:
            # Limpiar query - quitar S01E01, año, etc.
            clean_query = re.sub(r'S\d+E\d+', '', query).strip()
            clean_query = re.sub(r'\s+\d{4}\s*$', '', clean_query).strip()
            
            # TuSubtitulo usa búsqueda por serie
            search_url = f"{self.BASE_URL}/series.php"
            params = {'q': clean_query}
            
            response = requests.get(
                search_url,
                params=params,
                headers=self._get_headers(),
                timeout=15
            )
            
            soup = BeautifulSoup(response.text, 'lxml')
            
            # Buscar series que coincidan
            for item in soup.select('a[href*="/show/"]'):
                try:
                    title = item.get_text(strip=True)
                    href = item.get('href', '')
                    
                    if not title or not href:
                        continue
                    
                    # Si coincide con la búsqueda
                    if clean_query.lower() in title.lower():
                        show_url = urljoin(self.BASE_URL, href)
                        # Obtener subtítulos de esta serie
                        subs = self._get_subtitles_from_show(show_url, query)
                        results.extend(subs)
                        
                        if len(results) >= 15:
                            break
                            
                except Exception:
                    continue
            
            # Búsqueda alternativa directa
            if not results:
                results = self._search_direct(clean_query)
                    
        except Exception as e:
            print(f"Error buscando en TuSubtitulo: {e}")
        
        return results[:15]
    
    def _search_direct(self, query: str) -> List[SubtitleResult]:
        """Búsqueda directa en la página principal."""
        results = []
        
        try:
            response = requests.get(
                self.BASE_URL,
                headers=self._get_headers(),
                timeout=15
            )
            
            soup = BeautifulSoup(response.text, 'lxml')
            
            # Buscar en últimos subtítulos
            for item in soup.select('a[href*="capitulo"]'):
                title = item.get_text(strip=True)
                if query.lower() in title.lower():
                    result = SubtitleResult(
                        title=title,
                        language=Language.SPANISH_SPAIN,
                        provider=self.name,
                        download_url=urljoin(self.BASE_URL, item.get('href', '')),
                        description="",
                    )
                    results.append(result)
                    
        except Exception:
            pass
        
        return results
    
    def _get_subtitles_from_show(self, show_url: str, original_query: str) -> List[SubtitleResult]:
        """Obtiene subtítulos de una página de serie."""
        results = []
        
        try:
            response = requests.get(
                show_url,
                headers=self._get_headers(),
                timeout=15
            )
            
            soup = BeautifulSoup(response.text, 'lxml')
            
            # Extraer temporada y episodio de la query original
            se_match = re.search(r'S(\d+)E(\d+)', original_query, re.IGNORECASE)
            target_season = None
            target_episode = None
            if se_match:
                target_season = int(se_match.group(1))
                target_episode = int(se_match.group(2))
            
            # Buscar tabla de episodios
            for row in soup.select('tr'):
                try:
                    cells = row.find_all('td')
                    if len(cells) < 2:
                        continue
                    
                    # Buscar número de episodio
                    ep_text = cells[0].get_text(strip=True)
                    ep_match = re.search(r'(\d+)x(\d+)', ep_text)
                    
                    if ep_match:
                        season = int(ep_match.group(1))
                        episode = int(ep_match.group(2))
                        
                        # Filtrar por temporada/episodio si se especificó
                        if target_season and target_episode:
                            if season != target_season or episode != target_episode:
                                continue
                        
                        # Buscar link de descarga
                        link = row.find('a', href=True)
                        if link:
                            title = f"S{season:02d}E{episode:02d} - {link.get_text(strip=True)}"
                            
                            result = SubtitleResult(
                                title=title,
                                language=Language.SPANISH_SPAIN,
                                provider=self.name,
                                download_url=urljoin(self.BASE_URL, link.get('href', '')),
                                description="",
                            )
                            results.append(result)
                            
                except Exception:
                    continue
                    
        except Exception as e:
            print(f"Error obteniendo subs de TuSubtitulo: {e}")
        
        return results
    
    def download(self, subtitle: SubtitleResult, destination: str) -> Optional[str]:
        """Descarga un subtítulo de TuSubtitulo."""
        try:
            # Ir a la página del subtítulo
            response = requests.get(
                subtitle.download_url,
                headers=self._get_headers(),
                timeout=15
            )
            
            soup = BeautifulSoup(response.text, 'lxml')
            
            # Buscar link de descarga directa
            download_link = None
            for a in soup.find_all('a', href=True):
                href = a.get('href', '')
                text = a.get_text().lower()
                if 'descargar' in text or 'download' in text or '.srt' in href:
                    download_link = urljoin(self.BASE_URL, href)
                    break
            
            if not download_link:
                # Buscar por clase
                dl_btn = soup.select_one('a.bt-descarga, a.download, a[download]')
                if dl_btn:
                    download_link = urljoin(self.BASE_URL, dl_btn.get('href', ''))
            
            if not download_link:
                return None
            
            # Descargar
            dl_response = requests.get(
                download_link,
                headers=self._get_headers(),
                timeout=30,
                allow_redirects=True
            )
            
            # Determinar nombre
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
            print(f"Error descargando de TuSubtitulo: {e}")
            return None
