"""Proveedor de subtítulos Subscene - Buena cobertura multi-idioma."""
import os
import re
import requests
from bs4 import BeautifulSoup
from typing import List, Optional
from urllib.parse import urljoin, quote

from .base import SubtitleProvider, SubtitleResult, Language


class SubsceneProvider(SubtitleProvider):
    """Proveedor para Subscene.com"""
    
    name = "Subscene"
    supported_languages = [Language.SPANISH_SPAIN, Language.SPANISH_LATAM, Language.ENGLISH]
    BASE_URL = "https://subscene.com"
    
    # IDs de idiomas en Subscene
    LANG_IDS = {
        Language.SPANISH_SPAIN: 'spanish',
        Language.SPANISH_LATAM: 'spanish',
        Language.ENGLISH: 'english',
    }
    
    def search(self, query: str, language: Optional[Language] = None) -> List[SubtitleResult]:
        """Busca subtítulos en Subscene."""
        results = []
        
        try:
            # Primero buscar la película/serie
            search_url = f"{self.BASE_URL}/subtitles/searchbytitle"
            
            response = requests.post(
                search_url,
                data={'query': query},
                headers=self._get_headers(),
                timeout=15,
                allow_redirects=True
            )
            
            soup = BeautifulSoup(response.text, 'lxml')
            
            # Encontrar resultados de búsqueda (links a páginas de subtítulos)
            title_links = []
            for div in soup.select('div.title a'):
                href = div.get('href', '')
                if href and '/subtitles/' in href:
                    title_links.append(urljoin(self.BASE_URL, href))
            
            # Si no hay resultados, intentar búsqueda directa
            if not title_links:
                # Puede que haya redirigido directamente a la página de subtítulos
                title_links = [response.url]
            
            # Obtener subtítulos del primer resultado (o del redirect)
            for title_url in title_links[:3]:  # Limitar a 3 títulos
                subs = self._get_subtitles_from_page(title_url, language)
                results.extend(subs)
                if len(results) >= 15:
                    break
                    
        except Exception as e:
            print(f"Error buscando en Subscene: {e}")
        
        return results[:15]
    
    def _get_subtitles_from_page(self, page_url: str, language: Optional[Language] = None) -> List[SubtitleResult]:
        """Obtiene subtítulos de una página de título."""
        results = []
        
        try:
            response = requests.get(
                page_url,
                headers=self._get_headers(),
                timeout=15
            )
            
            soup = BeautifulSoup(response.text, 'lxml')
            
            # Determinar idiomas a buscar
            target_langs = []
            if language:
                target_langs = [self.LANG_IDS[language]]
            else:
                target_langs = ['spanish', 'english']
            
            # Buscar filas de subtítulos
            for row in soup.select('table tbody tr'):
                try:
                    # Columna de idioma
                    lang_cell = row.select_one('td.a1')
                    if not lang_cell:
                        continue
                    
                    lang_span = lang_cell.select_one('span')
                    if not lang_span:
                        continue
                    
                    lang_text = lang_span.get_text(strip=True).lower()
                    
                    # Filtrar por idioma
                    if not any(tl in lang_text for tl in target_langs):
                        continue
                    
                    # Link y título
                    link = lang_cell.select_one('a')
                    if not link:
                        continue
                    
                    href = link.get('href', '')
                    title_spans = link.select('span')
                    title = ' '.join(s.get_text(strip=True) for s in title_spans)
                    
                    # Determinar Language enum
                    if 'english' in lang_text:
                        lang_enum = Language.ENGLISH
                    else:
                        lang_enum = Language.SPANISH_SPAIN
                    
                    # Comentario/descripción
                    comment_cell = row.select_one('td.a6')
                    comment = ""
                    if comment_cell:
                        comment_div = comment_cell.select_one('div')
                        if comment_div:
                            comment = comment_div.get_text(strip=True)
                    
                    result = SubtitleResult(
                        title=title,
                        language=lang_enum,
                        provider=self.name,
                        download_url=urljoin(self.BASE_URL, href),
                        description=comment[:200],
                    )
                    results.append(result)
                    
                except Exception:
                    continue
                    
        except Exception as e:
            print(f"Error obteniendo subtítulos de página Subscene: {e}")
        
        return results
    
    def download(self, subtitle: SubtitleResult, destination: str) -> Optional[str]:
        """Descarga un subtítulo de Subscene."""
        try:
            # Primero ir a la página del subtítulo
            response = requests.get(
                subtitle.download_url,
                headers=self._get_headers(),
                timeout=15
            )
            
            soup = BeautifulSoup(response.text, 'lxml')
            
            # Buscar botón de descarga
            download_btn = soup.select_one('a#downloadButton, a.download')
            if not download_btn:
                # Buscar cualquier link de descarga
                for a in soup.find_all('a', href=True):
                    if 'download' in a.get('href', '').lower():
                        download_btn = a
                        break
            
            if not download_btn:
                print("No se encontró botón de descarga en Subscene")
                return None
            
            download_url = urljoin(self.BASE_URL, download_btn.get('href', ''))
            
            # Descargar archivo
            dl_response = requests.get(
                download_url,
                headers=self._get_headers(),
                timeout=30,
                allow_redirects=True
            )
            
            # Determinar nombre del archivo
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
            print(f"Error descargando de Subscene: {e}")
            return None
