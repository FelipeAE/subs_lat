"""Proveedor de subtítulos Subdl - Acceso libre, multi-idioma."""
import re
import os
import requests
from bs4 import BeautifulSoup
from typing import List, Optional
from urllib.parse import urljoin, quote

from .base import SubtitleProvider, SubtitleResult, Language


class SubdlProvider(SubtitleProvider):
    """Proveedor para subdl.com - Sin restricciones de Cloudflare."""
    
    name = "Subdl"
    supported_languages = [Language.SPANISH_SPAIN, Language.SPANISH_LATAM, Language.ENGLISH]
    BASE_URL = "https://subdl.com"
    
    LANG_MAP = {
        Language.SPANISH_SPAIN: 'spanish',
        Language.SPANISH_LATAM: 'spanish',
        Language.ENGLISH: 'english',
    }
    
    def search(self, query: str, language: Optional[Language] = None) -> List[SubtitleResult]:
        """Busca subtítulos en Subdl."""
        results = []
        
        try:
            # Limpiar query
            clean_query = re.sub(r'S\d+E\d+', '', query).strip()
            
            search_url = f"{self.BASE_URL}/search"
            params = {'query': clean_query}
            
            response = requests.get(
                search_url,
                params=params,
                headers=self._get_headers(),
                timeout=15
            )
            
            soup = BeautifulSoup(response.text, 'lxml')
            
            # Buscar resultados (links a páginas de subtítulos)
            for item in soup.select('a.subtitle-item, div.result a, a[href*="/subtitles/"]'):
                try:
                    href = item.get('href', '')
                    if not href or '/subtitles/' not in href:
                        continue
                    
                    title = item.get_text(strip=True)
                    if not title:
                        continue
                    
                    page_url = urljoin(self.BASE_URL, href)
                    
                    # Obtener subtítulos de esta página
                    subs = self._get_subtitles_from_page(page_url, language)
                    results.extend(subs)
                    
                    if len(results) >= 15:
                        break
                        
                except Exception:
                    continue
            
            # Si no encontramos resultados en la búsqueda, intentar búsqueda directa
            if not results:
                results = self._search_direct(clean_query, language)
                    
        except Exception as e:
            print(f"Error buscando en Subdl: {e}")
        
        return results[:15]
    
    def _search_direct(self, query: str, language: Optional[Language] = None) -> List[SubtitleResult]:
        """Búsqueda directa por título."""
        results = []
        
        try:
            # Construir URL slug del título
            slug = query.lower().replace(' ', '-')
            slug = re.sub(r'[^a-z0-9-]', '', slug)
            
            url = f"{self.BASE_URL}/subtitles/{slug}"
            
            response = requests.get(
                url,
                headers=self._get_headers(),
                timeout=15
            )
            
            if response.status_code == 200:
                results = self._get_subtitles_from_page(url, language)
                
        except Exception:
            pass
        
        return results
    
    def _get_subtitles_from_page(self, page_url: str, language: Optional[Language] = None) -> List[SubtitleResult]:
        """Obtiene subtítulos de una página."""
        results = []
        
        try:
            response = requests.get(
                page_url,
                headers=self._get_headers(),
                timeout=15
            )
            
            soup = BeautifulSoup(response.text, 'lxml')
            
            # Obtener título
            title_elem = soup.find('h1') or soup.find('h2')
            page_title = title_elem.get_text(strip=True) if title_elem else "Sin título"
            
            # Idiomas a buscar
            target_langs = []
            if language:
                target_langs = [self.LANG_MAP[language]]
            else:
                target_langs = ['spanish', 'english', 'español']
            
            # Buscar filas de subtítulos
            for row in soup.select('tr, div.subtitle-row, li.subtitle-item'):
                try:
                    # Verificar idioma
                    row_text = row.get_text().lower()
                    lang_ok = False
                    detected_lang = Language.ENGLISH
                    
                    for tl in target_langs:
                        if tl in row_text or tl[:3] in row_text:
                            lang_ok = True
                            if 'spanish' in tl or 'español' in tl:
                                detected_lang = Language.SPANISH_LATAM
                            break
                    
                    if not lang_ok and target_langs:
                        continue
                    
                    # Buscar link de descarga
                    link = row.find('a', href=True)
                    if not link:
                        continue
                    
                    href = link.get('href', '')
                    sub_title = link.get_text(strip=True)
                    
                    if not sub_title or sub_title == '':
                        sub_title = page_title
                    
                    download_url = urljoin(self.BASE_URL, href)
                    
                    result = SubtitleResult(
                        title=sub_title[:100],
                        language=detected_lang,
                        provider=self.name,
                        download_url=download_url,
                        description="",
                    )
                    results.append(result)
                    
                except Exception:
                    continue
                    
        except Exception as e:
            print(f"Error obteniendo subs de página Subdl: {e}")
        
        return results
    
    def download(self, subtitle: SubtitleResult, destination: str) -> Optional[str]:
        """Descarga un subtítulo de Subdl."""
        try:
            # Si el URL ya es de descarga directa
            if '/download/' in subtitle.download_url or subtitle.download_url.endswith(('.zip', '.srt')):
                download_url = subtitle.download_url
            else:
                # Ir a la página del subtítulo
                response = requests.get(
                    subtitle.download_url,
                    headers=self._get_headers(),
                    timeout=15
                )
                
                soup = BeautifulSoup(response.text, 'lxml')
                
                # Buscar botón de descarga
                download_btn = None
                for a in soup.find_all('a', href=True):
                    href = a.get('href', '')
                    text = a.get_text().lower()
                    if 'download' in href.lower() or 'download' in text:
                        download_btn = a
                        break
                
                if not download_btn:
                    return None
                
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
            
            # Si es texto plano, guardar como .srt
            content_type = dl_response.headers.get('Content-Type', '')
            if 'text' in content_type and not filename.endswith('.srt'):
                filename = "subtitle.srt"
            
            filepath = os.path.join(destination, filename)
            
            with open(filepath, 'wb') as f:
                f.write(dl_response.content)
            
            return filepath
            
        except Exception as e:
            print(f"Error descargando de Subdl: {e}")
            return None
