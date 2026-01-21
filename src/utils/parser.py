"""Parser para nombres de archivos de video."""
import re
from typing import Dict, Optional

try:
    from guessit import guessit
    GUESSIT_AVAILABLE = True
except ImportError:
    GUESSIT_AVAILABLE = False


def parse_video_filename(filename: str) -> Dict[str, Optional[str]]:
    """
    Extrae información del nombre del archivo de video.
    Retorna dict con: title, year, season, episode, release_group
    """
    if GUESSIT_AVAILABLE:
        return _parse_with_guessit(filename)
    return _parse_manual(filename)


def _parse_with_guessit(filename: str) -> Dict[str, Optional[str]]:
    """Usa guessit para parsear el nombre."""
    info = guessit(filename)
    
    # guessit puede devolver listas para episodios múltiples
    season = info.get('season')
    episode = info.get('episode')
    
    if isinstance(season, list):
        season = season[0] if season else None
    if isinstance(episode, list):
        episode = episode[0] if episode else None
    
    return {
        'title': info.get('title'),
        'year': str(info.get('year')) if info.get('year') else None,
        'season': season,
        'episode': episode,
        'release_group': info.get('release_group'),
        'source': info.get('source'),
    }


def _parse_manual(filename: str) -> Dict[str, Optional[str]]:
    """Parser manual básico sin dependencias."""
    result = {
        'title': None,
        'year': None,
        'season': None,
        'episode': None,
        'release_group': None,
        'source': None,
    }
    
    # Limpiar extensión y reemplazar puntos/guiones bajos
    name = re.sub(r'\.[a-zA-Z0-9]{2,4}$', '', filename)
    name = name.replace('.', ' ').replace('_', ' ')
    
    # Buscar año (1900-2099)
    year_match = re.search(r'\b(19\d{2}|20\d{2})\b', name)
    if year_match:
        result['year'] = year_match.group(1)
        # El título suele estar antes del año
        title_part = name[:year_match.start()].strip()
        result['title'] = title_part if title_part else None
    
    # Buscar temporada y episodio (S01E01, 1x01, etc.)
    se_match = re.search(r'[Ss](\d{1,2})[Ee](\d{1,2})', name)
    if not se_match:
        se_match = re.search(r'(\d{1,2})x(\d{1,2})', name)
    
    if se_match:
        result['season'] = int(se_match.group(1))
        result['episode'] = int(se_match.group(2))
        # Si no tenemos título del año, tomarlo antes del S01E01
        if not result['title']:
            title_part = name[:se_match.start()].strip()
            result['title'] = title_part if title_part else None
    
    # Si aún no hay título, usar el nombre limpio
    if not result['title']:
        # Remover calidad común y otros tags
        clean = re.sub(r'\b(720p|1080p|2160p|4k|x264|x265|bluray|webrip|hdtv|brrip)\b', '', name, flags=re.IGNORECASE)
        result['title'] = clean.strip()
    
    return result


def build_search_query(parsed_info: Dict[str, Optional[str]]) -> str:
    """Construye una query de búsqueda a partir de la info parseada."""
    parts = []
    
    if parsed_info.get('title'):
        parts.append(parsed_info['title'])
    
    if parsed_info.get('year'):
        parts.append(parsed_info['year'])
    
    if parsed_info.get('season') is not None and parsed_info.get('episode') is not None:
        parts.append(f"S{parsed_info['season']:02d}E{parsed_info['episode']:02d}")
    
    return ' '.join(parts)
