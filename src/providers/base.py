"""Clase base para proveedores de subtítulos."""
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import List, Optional
from enum import Enum


class Language(Enum):
    SPANISH_SPAIN = "es-ES"
    SPANISH_LATAM = "es-LA"
    ENGLISH = "en"


@dataclass
class SubtitleResult:
    """Representa un resultado de búsqueda de subtítulos."""
    title: str
    language: Language
    provider: str
    download_url: str
    description: str = ""
    downloads: int = 0
    rating: float = 0.0
    
    def __str__(self):
        return f"[{self.provider}] {self.title} ({self.language.value})"


class SubtitleProvider(ABC):
    """Clase base abstracta para proveedores de subtítulos."""
    
    name: str = "Base Provider"
    supported_languages: List[Language] = []
    
    @abstractmethod
    def search(self, query: str, language: Optional[Language] = None) -> List[SubtitleResult]:
        """
        Busca subtítulos según la query.
        
        Args:
            query: Término de búsqueda (nombre de película/serie)
            language: Idioma deseado (opcional)
            
        Returns:
            Lista de SubtitleResult
        """
        pass
    
    @abstractmethod
    def download(self, subtitle: SubtitleResult, destination: str) -> Optional[str]:
        """
        Descarga un subtítulo.
        
        Args:
            subtitle: El subtítulo a descargar
            destination: Carpeta donde guardar el archivo
            
        Returns:
            Ruta al archivo descargado o None si falla
        """
        pass
    
    def _get_headers(self) -> dict:
        """Headers comunes para requests."""
        return {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'es-ES,es;q=0.9,en;q=0.8',
        }
