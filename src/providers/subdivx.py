"""Proveedor de subtítulos SubDivX - Especializado en español latino."""
import re
import os
import time
from bs4 import BeautifulSoup
from typing import List, Optional
from urllib.parse import urljoin, quote_plus

# Intentar importar Playwright
try:
    from playwright.sync_api import sync_playwright
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False

import requests

from .base import SubtitleProvider, SubtitleResult, Language


class SubDivXProvider(SubtitleProvider):
    """Proveedor para SubDivX.com - Excelente para español latino."""
    
    name = "SubDivX"
    supported_languages = [Language.SPANISH_LATAM, Language.SPANISH_SPAIN]
    BASE_URL = "https://www.subdivx.com"
    
    def __init__(self):
        self.playwright = None
        self.browser = None
        self.cookies = {}
    
    def _init_browser(self):
        """Inicializa el navegador si es necesario."""
        if not PLAYWRIGHT_AVAILABLE:
            return False
        
        if self.browser is None:
            try:
                self.playwright = sync_playwright().start()
                self.browser = self.playwright.chromium.launch(
                    headless=True,
                    args=['--disable-blink-features=AutomationControlled']
                )
            except Exception as e:
                print(f"Error iniciando navegador: {e}")
                return False
        
        return True
    
    def _close_browser(self):
        """Cierra el navegador."""
        try:
            if self.browser:
                self.browser.close()
            if self.playwright:
                self.playwright.stop()
        except:
            pass
        self.browser = None
        self.playwright = None
    
    def search(self, query: str, language: Optional[Language] = None) -> List[SubtitleResult]:
        """Busca subtítulos en SubDivX usando Playwright para bypass de Cloudflare."""
        results = []
        
        if not PLAYWRIGHT_AVAILABLE:
            print("SubDivX: Playwright no instalado. Ejecutar: pip install playwright && playwright install chromium")
            return results
        
        if not self._init_browser():
            return results
        
        try:
            context = self.browser.new_context(
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
            )
            page = context.new_page()
            
            # Construir URL de búsqueda
            search_url = f"{self.BASE_URL}/index.php?buscar2={quote_plus(query)}&acession=1&oxdown=1"
            
            # Navegar
            page.goto(search_url, wait_until='networkidle', timeout=30000)
            
            # Esperar un poco para que cargue todo
            page.wait_for_timeout(2000)
            
            # Obtener cookies para descargas posteriores
            self.cookies = {c['name']: c['value'] for c in context.cookies()}
            
            # Parsear contenido
            html = page.content()
            soup = BeautifulSoup(html, 'lxml')
            
            results = self._parse_results(soup)
            
            context.close()
            
        except Exception as e:
            print(f"Error buscando en SubDivX: {e}")
        
        return results[:15]
    
    def _parse_results(self, soup: BeautifulSoup) -> List[SubtitleResult]:
        """Parsea los resultados de búsqueda."""
        results = []
        
        # Selector 1: divs con id menu_titulo_buscador
        for titulo in soup.find_all('div', id='menu_titulo_buscador'):
            result = self._extract_result(titulo)
            if result:
                results.append(result)
        
        # Selector 2: divs con clase titulo_menu_izq
        if not results:
            for titulo in soup.select('div.titulo_menu_izq'):
                result = self._extract_result(titulo)
                if result:
                    results.append(result)
        
        # Selector 3: links directos
        if not results:
            for link in soup.find_all('a', href=re.compile(r'/subs/')):
                title = link.get_text(strip=True)
                if title:
                    results.append(SubtitleResult(
                        title=title,
                        language=Language.SPANISH_LATAM,
                        provider=self.name,
                        download_url=urljoin(self.BASE_URL, link.get('href', '')),
                        description="",
                    ))
        
        return results
    
    def _extract_result(self, element) -> Optional[SubtitleResult]:
        """Extrae un resultado de un elemento HTML."""
        try:
            link = element.find('a')
            if not link:
                return None
            
            title = link.get_text(strip=True)
            detail_url = urljoin(self.BASE_URL, link.get('href', ''))
            
            # Descripción
            desc_div = element.find_next('div', id='buscador_detalle')
            if not desc_div:
                desc_div = element.find_next('div', class_='buscador_detalle')
            description = desc_div.get_text(strip=True)[:200] if desc_div else ""
            
            # Descargas
            downloads = 0
            dl_div = element.find_next('div', id='buscador_detalle_sub')
            if dl_div:
                match = re.search(r'(\d+)\s*[Dd]ownloads?', dl_div.get_text())
                if match:
                    downloads = int(match.group(1))
            
            return SubtitleResult(
                title=title,
                language=Language.SPANISH_LATAM,
                provider=self.name,
                download_url=detail_url,
                description=description,
                downloads=downloads,
            )
        except:
            return None
    
    def download(self, subtitle: SubtitleResult, destination: str) -> Optional[str]:
        """Descarga un subtítulo de SubDivX."""
        if not PLAYWRIGHT_AVAILABLE:
            return None
        
        if not self._init_browser():
            return None
        
        try:
            context = self.browser.new_context(
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            )
            page = context.new_page()
            
            # Ir a la página del subtítulo
            page.goto(subtitle.download_url, wait_until='networkidle', timeout=30000)
            page.wait_for_timeout(1500)
            
            # Buscar link de descarga
            html = page.content()
            soup = BeautifulSoup(html, 'lxml')
            
            download_link = None
            for a in soup.find_all('a', href=True):
                href = a.get('href', '')
                if 'baession' in href or 'descargar' in href.lower():
                    download_link = urljoin(self.BASE_URL, href)
                    break
            
            if not download_link:
                # Buscar por onclick
                for elem in soup.find_all(['a', 'input'], onclick=True):
                    onclick = elem.get('onclick', '')
                    match = re.search(r"location\.href='([^']+)'", onclick)
                    if match:
                        download_link = urljoin(self.BASE_URL, match.group(1))
                        break
            
            if not download_link:
                context.close()
                return None
            
            # Obtener cookies del contexto
            cookies = {c['name']: c['value'] for c in context.cookies()}
            context.close()
            
            # Descargar usando requests con las cookies
            response = requests.get(
                download_link,
                cookies=cookies,
                headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'},
                timeout=30,
                allow_redirects=True
            )
            
            # Determinar nombre del archivo
            filename = "subtitle.zip"
            content_disp = response.headers.get('Content-Disposition', '')
            if 'filename=' in content_disp:
                match = re.search(r'filename="?([^";\n]+)"?', content_disp)
                if match:
                    filename = match.group(1)
            
            filepath = os.path.join(destination, filename)
            
            with open(filepath, 'wb') as f:
                f.write(response.content)
            
            return filepath
            
        except Exception as e:
            print(f"Error descargando de SubDivX: {e}")
            return None
    
    def __del__(self):
        """Limpieza al destruir el objeto."""
        self._close_browser()
