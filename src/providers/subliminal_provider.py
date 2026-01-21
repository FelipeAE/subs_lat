"""Proveedor usando Subliminal - Biblioteca especializada en subtítulos."""
import os
from typing import List, Optional
from pathlib import Path

try:
    from subliminal import download_best_subtitles, save_subtitles, scan_video
    from subliminal.providers.opensubtitlescom import OpenSubtitlesComProvider
    from subliminal.core import ProviderPool
    from babelfish import Language as BabelLanguage
    SUBLIMINAL_AVAILABLE = True
except ImportError:
    SUBLIMINAL_AVAILABLE = False

from .base import SubtitleProvider, SubtitleResult, Language


class SubliminalProvider(SubtitleProvider):
    """Proveedor usando la biblioteca Subliminal."""
    
    name = "Subliminal"
    supported_languages = [Language.SPANISH_SPAIN, Language.SPANISH_LATAM, Language.ENGLISH]
    
    LANG_MAP = {
        Language.SPANISH_SPAIN: BabelLanguage('spa') if SUBLIMINAL_AVAILABLE else None,
        Language.SPANISH_LATAM: BabelLanguage('spa') if SUBLIMINAL_AVAILABLE else None,
        Language.ENGLISH: BabelLanguage('eng') if SUBLIMINAL_AVAILABLE else None,
    }
    
    def __init__(self):
        self.available = SUBLIMINAL_AVAILABLE
        if not self.available:
            print("Subliminal no está instalado. Instalar con: pip install subliminal")
    
    def search(self, query: str, language: Optional[Language] = None) -> List[SubtitleResult]:
        """
        Subliminal no tiene búsqueda por query, trabaja con archivos de video.
        Este método retorna una lista vacía - usar search_for_video en su lugar.
        """
        return []
    
    def search_for_video(self, video_path: str, language: Optional[Language] = None) -> List[SubtitleResult]:
        """Busca subtítulos para un archivo de video específico."""
        if not self.available:
            return []
        
        results = []
        
        try:
            # Escanear el video
            video = scan_video(video_path)
            
            # Determinar idiomas
            if language:
                languages = {self.LANG_MAP[language]}
            else:
                languages = {BabelLanguage('spa'), BabelLanguage('eng')}
            
            # Buscar subtítulos usando múltiples proveedores
            with ProviderPool() as pool:
                subtitles = pool.list_subtitles(video, languages)
                
                for sub in subtitles[:15]:
                    lang_enum = Language.ENGLISH
                    if sub.language == BabelLanguage('spa'):
                        lang_enum = Language.SPANISH_LATAM
                    
                    result = SubtitleResult(
                        title=f"{sub.id} - {sub.provider_name}",
                        language=lang_enum,
                        provider=f"Subliminal ({sub.provider_name})",
                        download_url=str(sub.id),
                        description=getattr(sub, 'release', ''),
                    )
                    # Guardar referencia al subtítulo original
                    result._subliminal_sub = sub
                    result._subliminal_video = video
                    results.append(result)
                    
        except Exception as e:
            print(f"Error buscando con Subliminal: {e}")
        
        return results
    
    def download(self, subtitle: SubtitleResult, destination: str) -> Optional[str]:
        """Descarga un subtítulo usando Subliminal."""
        if not self.available:
            return None
        
        try:
            sub = getattr(subtitle, '_subliminal_sub', None)
            video = getattr(subtitle, '_subliminal_video', None)
            
            if not sub or not video:
                return None
            
            with ProviderPool() as pool:
                pool.download_subtitle(sub)
            
            # Guardar el subtítulo
            saved = save_subtitles(video, [sub], directory=destination)
            
            if saved:
                # Encontrar el archivo guardado
                for lang, sub_list in saved.items():
                    if sub_list:
                        return str(sub_list[0].path)
            
            return None
            
        except Exception as e:
            print(f"Error descargando con Subliminal: {e}")
            return None


def download_subtitles_for_video(video_path: str, languages: List[str] = None, destination: str = None) -> Optional[str]:
    """
    Función helper para descargar subtítulos directamente para un video.
    
    Args:
        video_path: Ruta al archivo de video
        languages: Lista de idiomas ['es', 'en']
        destination: Carpeta donde guardar (por defecto: misma carpeta del video)
    
    Returns:
        Ruta al subtítulo descargado o None
    """
    if not SUBLIMINAL_AVAILABLE:
        print("Subliminal no está instalado")
        return None
    
    try:
        # Convertir códigos de idioma
        lang_set = set()
        for lang in (languages or ['es', 'en']):
            if lang in ('es', 'spa', 'spanish'):
                lang_set.add(BabelLanguage('spa'))
            elif lang in ('en', 'eng', 'english'):
                lang_set.add(BabelLanguage('eng'))
        
        # Escanear video
        video = scan_video(video_path)
        
        # Descargar mejor subtítulo
        subtitles = download_best_subtitles([video], lang_set)
        
        if video in subtitles and subtitles[video]:
            dest = destination or os.path.dirname(video_path)
            saved = save_subtitles(video, subtitles[video], directory=dest)
            
            if saved:
                for lang, sub_list in saved.items():
                    if sub_list:
                        return str(Path(dest) / sub_list[0].path.name)
        
        return None
        
    except Exception as e:
        print(f"Error: {e}")
        return None
