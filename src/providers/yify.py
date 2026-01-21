"""Proveedor de subtítulos YIFY - Fácil acceso, multi-idioma."""
import re
import os
import requests
from bs4 import BeautifulSoup
from typing import List, Optional
from urllib.parse import urljoin, quote
import zipfile
import io

from .base import SubtitleProvider, SubtitleResult, Language


class YifyProvider(SubtitleProvider):
    """Proveedor para yifysubtitles.ch - Funciona bien sin bloqueos."""
    
    name = "YIFY"
    supported_languages = [Language.SPANISH_SPAIN, Language.SPANISH_LATAM, Language.ENGLISH]
    BASE_URL = "https://yifysubtitles.ch"
    
    LANG_MAP = {
        Language.SPANISH_SPAIN: 'spanish',
        Language.SPANISH_LATAM: 'spanish',
        Language.ENGLISH: 'english',
    }
    
    def search(self, query: str, language: Optional[Language] = None) -> List[SubtitleResult]:
        """Busca subtítulos en YIFY."""
        results = []
        
        try:
            # Limpiar query
            clean_query = re.sub(r'S\d+E\d+', '', query).strip()
            clean_query = re.sub(r'\d{4}$', '', clean_query).strip()
            
            search_url = f"{self.BASE_URL}/search"
            params = {'q': clean_query}
            
            response = requests.get(
                search_url,
                params=params,
                headers=self._get_headers(),
                timeout=15
            )
            
            soup = BeautifulSoup(response.text, 'lxml')
            
            # Encontrar películas
            for item in soup.select('div.media-body, li.media'):
                try:
                    link = item.find('a', href=True)
                    if not link:
                        continue
                    
                    href = link.get('href', '')
                    if '/movie-imdb/' not in href and '/subtitles/' not in href:
                        continue
                    
                    title = link.get_text(strip=True)
                    movie_url = urljoin(self.BASE_URL, href)
                    
                    # Obtener subtítulos de esta película
                    subs = self._get_subtitles_for_movie(movie_url, language)
                    results.extend(subs)
                    
                    if len(results) >= 15:
                        break
                        
                except Exception:
                    continue
                    
        except Exception as e:
            print(f"Error buscando en YIFY: {e}")
        
        return results[:15]
    
    def _get_subtitles_for_movie(self, movie_url: str, language: Optional[Language] = None) -> List[SubtitleResult]:
        """Obtiene los subtítulos de una página de película."""
        results = []
        
        try:
            response = requests.get(
                movie_url,
                headers=self._get_headers(),
                timeout=15
            )
            
            soup = BeautifulSoup(response.text, 'lxml')
            
            # Obtener título de la película
            title_elem = soup.find('h1') or soup.find('h2')
            movie_title = title_elem.get_text(strip=True) if title_elem else "Película"
            
            # Filtrar por idioma
            target_langs = []
            if language:
                target_langs = [self.LANG_MAP[language]]
            else:
                target_langs = ['spanish', 'english']
            
            # Buscar filas de subtítulos
            for row in soup.select('table tbody tr'):
                try:
                    # Rating
                    rating_cell = row.select_one('td.rating-cell')
                    rating = 0
                    if rating_cell:
                        rating_span = rating_cell.select_one('span.label')
                        if rating_span:
                            try:
                                rating = int(rating_span.get_text(strip=True))
                            except:
                                pass
                    
                    # Idioma
                    lang_cell = row.select_one('td.flag-cell')
                    if lang_cell:
                        lang_span = lang_cell.find('span', class_=re.compile(r'flag'))
                        if lang_span:
                            lang_class = ' '.join(lang_span.get('class', []))
                            
                            # Verificar idioma
                            lang_ok = False
                            for tl in target_langs:
                                if tl in lang_class.lower():
                                    lang_ok = True
                                    break
                            
                            if not lang_ok:
                                continue
                    
                    # Link de descarga
                    link = row.find('a', href=True)
                    if not link:
                        continue
                    
                    href = link.get('href', '')
                    sub_title = link.get_text(strip=True)
                    
                    if not sub_title:
                        sub_title = movie_title
                    
                    download_url = urljoin(self.BASE_URL, href)
                    
                    # Determinar idioma
                    lang_enum = Language.ENGLISH
                    if lang_cell:
                        lang_text = str(lang_cell)
                        if 'spanish' in lang_text.lower() or 'spain' in lang_text.lower():
                            lang_enum = Language.SPANISH_SPAIN
                    
                    result = SubtitleResult(
                        title=f"{movie_title} - {sub_title}",
                        language=lang_enum,
                        provider=self.name,
                        download_url=download_url,
                        description="",
                        rating=float(rating),
                    )
                    results.append(result)
                    
                except Exception:
                    continue
                    
        except Exception as e:
            print(f"Error obteniendo subs de película YIFY: {e}")
        
        return results
    
    def download(self, subtitle: SubtitleResult, destination: str) -> Optional[str]:
        """Descarga un subtítulo de YIFY."""
        try:
            # Ir a la página del subtítulo
            response = requests.get(
                subtitle.download_url,
                headers=self._get_headers(),
                timeout=15
            )
            
            soup = BeautifulSoup(response.text, 'lxml')
            
            # Buscar botón de descarga
            download_btn = soup.select_one('a.download-subtitle, a[href*="subtitle/download"]')
            if not download_btn:
                # Buscar cualquier link de descarga
                for a in soup.find_all('a', href=True):
                    href = a.get('href', '')
                    if 'download' in href.lower() and 'subtitle' in href.lower():
                        download_btn = a
                        break
            
            if not download_btn:
                # Intentar construir URL de descarga
                sub_id = re.search(r'/subtitle/([^/]+)', subtitle.download_url)
                if sub_id:
                    download_url = f"{self.BASE_URL}/subtitle/{sub_id.group(1)}.zip"
                else:
                    return None
            else:
                download_url = urljoin(self.BASE_URL, download_btn.get('href', ''))
            
            # Descargar
            dl_response = requests.get(
                download_url,
                headers=self._get_headers(),
                timeout=30,
                allow_redirects=True
            )
            
            # Determinar nombre
            filename = "subtitle.zip"
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
            print(f"Error descargando de YIFY: {e}")
            return None
