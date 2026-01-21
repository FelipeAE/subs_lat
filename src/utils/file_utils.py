"""Utilidades para manejo de archivos de video y subtítulos."""
import os
import zipfile
import tempfile
from pathlib import Path
from typing import List, Optional

try:
    import rarfile
    RAR_SUPPORT = True
except ImportError:
    RAR_SUPPORT = False

VIDEO_EXTENSIONS = {'.mkv', '.mp4', '.avi', '.mov', '.wmv', '.m4v', '.flv', '.webm'}
SUBTITLE_EXTENSIONS = {'.srt', '.sub', '.ssa', '.ass', '.vtt'}


def get_video_files(folder_path: str) -> List[str]:
    """Obtiene todos los archivos de video en una carpeta."""
    video_files = []
    folder = Path(folder_path)
    
    if not folder.exists():
        return video_files
    
    for file in folder.iterdir():
        if file.is_file() and file.suffix.lower() in VIDEO_EXTENSIONS:
            video_files.append(str(file))
    
    return sorted(video_files)


def extract_subtitle(archive_path: str, destination: str) -> Optional[str]:
    """Extrae subtítulos de un archivo .zip o .rar."""
    archive_path = Path(archive_path)
    destination = Path(destination)
    
    extracted_subtitle = None
    
    try:
        if archive_path.suffix.lower() == '.zip':
            with zipfile.ZipFile(archive_path, 'r') as zf:
                for name in zf.namelist():
                    if Path(name).suffix.lower() in SUBTITLE_EXTENSIONS:
                        zf.extract(name, destination)
                        extracted_subtitle = str(destination / name)
                        break
        
        elif archive_path.suffix.lower() == '.rar' and RAR_SUPPORT:
            with rarfile.RarFile(archive_path, 'r') as rf:
                for name in rf.namelist():
                    if Path(name).suffix.lower() in SUBTITLE_EXTENSIONS:
                        rf.extract(name, destination)
                        extracted_subtitle = str(destination / name)
                        break
        
        elif archive_path.suffix.lower() in SUBTITLE_EXTENSIONS:
            # Ya es un subtítulo, no necesita extracción
            return str(archive_path)
            
    except Exception as e:
        print(f"Error extrayendo subtítulo: {e}")
        return None
    
    return extracted_subtitle


def rename_subtitle(subtitle_path: str, video_path: str) -> str:
    """Renombra el subtítulo para que coincida con el nombre del video."""
    subtitle = Path(subtitle_path)
    video = Path(video_path)
    
    new_name = video.stem + subtitle.suffix
    new_path = video.parent / new_name
    
    # Si ya existe, agregar sufijo
    counter = 1
    while new_path.exists():
        new_name = f"{video.stem}.{counter}{subtitle.suffix}"
        new_path = video.parent / new_name
        counter += 1
    
    subtitle.rename(new_path)
    return str(new_path)
