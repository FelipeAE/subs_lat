"""
Subtitle Downloader - Aplicación para buscar y descargar subtítulos.
Usa múltiples proveedores con sistema de fallback.

Proveedores (en orden de prioridad):
1. OpenSubtitles - Principal, con hash matching
2. Subliminal - Fallback con múltiples proveedores (gestdown, podnapisi, tvsubtitles)

MODO AUTOMÁTICO: Arrastra una carpeta para descargar subtítulos automáticamente.
"""
import os
import sys
import threading
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from pathlib import Path
from typing import List, Optional, Dict
import requests
import re
import hashlib
import struct

# Agregar src al path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.utils.file_utils import get_video_files, extract_subtitle, SUBTITLE_EXTENSIONS
from src.utils.parser import parse_video_filename, build_search_query
from src.config import OPENSUBTITLES_API_KEY, API_URL

# Intentar importar tkinterdnd2 para drag & drop
try:
    from tkinterdnd2 import DND_FILES, TkinterDnD
    DND_AVAILABLE = True
except ImportError:
    DND_AVAILABLE = False

# Intentar importar Subliminal para fallback
try:
    from subliminal import scan_video, download_best_subtitles, save_subtitles
    from subliminal.core import ProviderPool
    from babelfish import Language as BabelLanguage
    SUBLIMINAL_AVAILABLE = True
except ImportError:
    SUBLIMINAL_AVAILABLE = False


def get_file_hash(filepath: str) -> Optional[str]:
    """Calcula el hash OpenSubtitles de un archivo de video."""
    try:
        longlongformat = '<q'
        bytesize = struct.calcsize(longlongformat)
        
        with open(filepath, "rb") as f:
            filesize = os.path.getsize(filepath)
            hash_val = filesize
            
            if filesize < 65536 * 2:
                return None
            
            for _ in range(65536 // bytesize):
                buffer = f.read(bytesize)
                (l_value,) = struct.unpack(longlongformat, buffer)
                hash_val += l_value
                hash_val = hash_val & 0xFFFFFFFFFFFFFFFF
            
            f.seek(max(0, filesize - 65536), 0)
            for _ in range(65536 // bytesize):
                buffer = f.read(bytesize)
                (l_value,) = struct.unpack(longlongformat, buffer)
                hash_val += l_value
                hash_val = hash_val & 0xFFFFFFFFFFFFFFFF
        
        return "%016x" % hash_val
    except:
        return None


class OpenSubtitlesAPI:
    """Cliente para la API de OpenSubtitles."""
    
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = API_URL
    
    def _headers(self) -> dict:
        return {
            'Api-Key': self.api_key,
            'Content-Type': 'application/json',
            'User-Agent': 'SubtitleDownloaderApp v1.0',
        }
    
    def search(self, query: str = None, file_hash: str = None, 
               languages: str = "es,en", imdb_id: str = None,
               season: int = None, episode: int = None) -> List[Dict]:
        """Busca subtítulos en OpenSubtitles."""
        params = {'languages': languages}
        
        if query:
            params['query'] = query
        if file_hash:
            params['moviehash'] = file_hash
        if imdb_id:
            params['imdb_id'] = imdb_id
        if season:
            params['season_number'] = season
        if episode:
            params['episode_number'] = episode
        
        try:
            response = requests.get(
                f"{self.base_url}/subtitles",
                params=params,
                headers=self._headers(),
                timeout=15
            )
            
            if response.status_code == 200:
                data = response.json()
                return data.get('data', [])
            else:
                print(f"Error API: {response.status_code} - {response.text[:200]}")
                return []
                
        except Exception as e:
            print(f"Error buscando: {e}")
            return []
    
    def download(self, file_id: int) -> Optional[str]:
        """Obtiene el link de descarga de un subtítulo."""
        try:
            response = requests.post(
                f"{self.base_url}/download",
                json={'file_id': file_id},
                headers=self._headers(),
                timeout=15
            )
            
            if response.status_code == 200:
                data = response.json()
                return data.get('link')
            else:
                print(f"Error descarga: {response.status_code}")
                return None
                
        except Exception as e:
            print(f"Error: {e}")
            return None


class SubliminalFallback:
    """Fallback usando Subliminal - múltiples proveedores integrados."""
    
    PROVIDERS = ['gestdown', 'podnapisi', 'tvsubtitles']
    
    def search_for_video(self, video_path: str, languages: str = "es,en") -> List[Dict]:
        """Busca subtítulos para un archivo de video usando Subliminal."""
        results = []
        
        if not SUBLIMINAL_AVAILABLE:
            print("Subliminal no disponible")
            return results
        
        try:
            # Escanear video
            video = scan_video(video_path)
            
            # Convertir idiomas
            lang_set = set()
            for lang in languages.split(','):
                if lang.strip() == 'es':
                    lang_set.add(BabelLanguage('spa'))
                elif lang.strip() == 'en':
                    lang_set.add(BabelLanguage('eng'))
            
            # Buscar con múltiples proveedores
            with ProviderPool(providers=self.PROVIDERS) as pool:
                subs = pool.list_subtitles(video, lang_set)
                
                for sub in subs[:15]:
                    lang_code = 'es' if sub.language == BabelLanguage('spa') else 'en'
                    release = getattr(sub, 'release', '') or getattr(sub, 'releases', [''])[0] if hasattr(sub, 'releases') else str(sub.id)[:50]
                    
                    results.append({
                        'provider': f'Subliminal ({sub.provider_name})',
                        'attributes': {
                            'release': release[:100],
                            'language': lang_code,
                            'download_count': 0,
                            'fps': '-',
                            'files': [{'file_id': None}],
                        },
                        '_subliminal_sub': sub,
                        '_subliminal_video': video,
                    })
                    
        except Exception as e:
            print(f"Error Subliminal: {e}")
        
        return results
    
    def download(self, subtitle_data: Dict, destination: str) -> Optional[bytes]:
        """Descarga un subtítulo usando Subliminal."""
        if not SUBLIMINAL_AVAILABLE:
            return None
        
        try:
            sub = subtitle_data.get('_subliminal_sub')
            video = subtitle_data.get('_subliminal_video')
            
            if not sub or not video:
                return None
            
            with ProviderPool(providers=self.PROVIDERS) as pool:
                pool.download_subtitle(sub)
            
            if sub.content:
                return sub.content
            
            return None
            
        except Exception as e:
            print(f"Error descarga Subliminal: {e}")
            return None


class SubtitleDownloaderApp:
    """Aplicación principal para descargar subtítulos."""
    
    def __init__(self, root):
        self.root = root
        self.root.title("Subtitle Downloader")
        self.root.geometry("950x700")
        self.root.minsize(800, 500)
        
        # APIs - Orden de prioridad para fallback
        self.opensubtitles = OpenSubtitlesAPI(OPENSUBTITLES_API_KEY)
        self.subliminal = SubliminalFallback()
        
        # Para compatibilidad
        self.api = self.opensubtitles
        
        # Variables
        self.folder_path = tk.StringVar()
        self.status_text = tk.StringVar(value="🎯 Arrastra una carpeta aquí para descargar subtítulos automáticamente")
        self.video_files: List[str] = []
        self.current_results: List[Dict] = []
        self.current_video_path: str = None
        self.auto_mode = tk.BooleanVar(value=True)  # Modo automático activado por defecto
        
        # Configurar UI
        self._setup_ui()
        self._setup_styles()
        self._setup_drag_drop()
    
    def _setup_drag_drop(self):
        """Configura drag & drop si está disponible."""
        if DND_AVAILABLE:
            self.root.drop_target_register(DND_FILES)
            self.root.dnd_bind('<<Drop>>', self._on_drop)
            self.status_text.set("🎯 Arrastra una carpeta aquí para descargar subtítulos automáticamente")
        else:
            self.status_text.set("Selecciona una carpeta con videos (instalar tkinterdnd2 para drag & drop)")
    
    def _on_drop(self, event):
        """Maneja el evento de soltar archivos/carpetas."""
        # Obtener la ruta (puede venir con llaves si tiene espacios)
        path = event.data
        if path.startswith('{') and path.endswith('}'):
            path = path[1:-1]
        
        # Si son múltiples archivos, tomar el primero
        if ' ' in path and not os.path.exists(path):
            paths = path.split()
            for p in paths:
                p = p.strip('{}')
                if os.path.exists(p):
                    path = p
                    break
        
        if os.path.isdir(path):
            self.folder_path.set(path)
            self._load_videos()
            
            # Si modo automático está activado, descargar todo
            if self.auto_mode.get():
                videos_sin_sub = [v for v in self.video_files if not self._has_subtitle(v)]
                if videos_sin_sub:
                    self.status_text.set(f"🚀 Iniciando descarga automática de {len(videos_sin_sub)} subtítulos...")
                    thread = threading.Thread(target=self._do_download_all, args=(videos_sin_sub,))
                    thread.daemon = True
                    thread.start()
                else:
                    self.status_text.set("✓ Todos los videos ya tienen subtítulos")
        elif os.path.isfile(path):
            # Si es un archivo de video, procesar solo ese
            folder = os.path.dirname(path)
            self.folder_path.set(folder)
            self._load_videos()
            
            if self.auto_mode.get() and not self._has_subtitle(path):
                self.status_text.set(f"🚀 Descargando subtítulo para: {os.path.basename(path)}")
                thread = threading.Thread(target=self._do_download_all, args=([path],))
                thread.daemon = True
                thread.start()
    
    def _setup_styles(self):
        style = ttk.Style()
        style.configure('Title.TLabel', font=('Segoe UI', 14, 'bold'))
        style.configure('Status.TLabel', font=('Segoe UI', 10))
        style.configure('Drop.TFrame', background='#e8f4e8')
    
    def _setup_ui(self):
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # === Zona de Drop ===
        drop_frame = ttk.LabelFrame(main_frame, text="📁 Carpeta de Videos (o arrastra aquí)", padding="10")
        drop_frame.pack(fill=tk.X, pady=(0, 10))
        
        ttk.Entry(drop_frame, textvariable=self.folder_path, width=60).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 10))
        ttk.Button(drop_frame, text="Examinar...", command=self._select_folder).pack(side=tk.LEFT)
        ttk.Button(drop_frame, text="Cargar", command=self._load_videos).pack(side=tk.LEFT, padx=(5, 0))
        ttk.Checkbutton(drop_frame, text="Auto", variable=self.auto_mode).pack(side=tk.LEFT, padx=(10, 0))
        
        # === Panel dividido ===
        paned = ttk.PanedWindow(main_frame, orient=tk.HORIZONTAL)
        paned.pack(fill=tk.BOTH, expand=True, pady=(0, 10))
        
        # Panel izquierdo: Videos
        left_frame = ttk.LabelFrame(paned, text="🎬 Videos", padding="5")
        paned.add(left_frame, weight=1)
        
        self.video_listbox = tk.Listbox(left_frame, selectmode=tk.SINGLE, font=('Consolas', 10))
        video_scroll = ttk.Scrollbar(left_frame, orient=tk.VERTICAL, command=self.video_listbox.yview)
        self.video_listbox.configure(yscrollcommand=video_scroll.set)
        self.video_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        video_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.video_listbox.bind('<<ListboxSelect>>', self._on_video_select)
        
        # Panel derecho: Resultados
        right_frame = ttk.LabelFrame(paned, text="📝 Subtítulos Encontrados", padding="5")
        paned.add(right_frame, weight=1)
        
        columns = ('Release', 'Idioma', 'Descargas', 'FPS')
        self.results_tree = ttk.Treeview(right_frame, columns=columns, show='headings', height=15)
        
        # Configurar headings con ordenamiento
        self.sort_reverse = {}  # Track del estado de ordenamiento por columna
        for col in columns:
            self.sort_reverse[col] = False
            self.results_tree.heading(col, text=col, command=lambda c=col: self._sort_column(c))
        
        self.results_tree.column('Release', width=280)
        self.results_tree.column('Idioma', width=80)
        self.results_tree.column('Descargas', width=80)
        self.results_tree.column('FPS', width=50)
        
        results_scroll = ttk.Scrollbar(right_frame, orient=tk.VERTICAL, command=self.results_tree.yview)
        self.results_tree.configure(yscrollcommand=results_scroll.set)
        self.results_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        results_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.results_tree.bind('<Double-1>', self._on_download_double_click)
        
        # === Botones ===
        action_frame = ttk.Frame(main_frame)
        action_frame.pack(fill=tk.X, pady=(0, 10))
        
        ttk.Button(action_frame, text="🔍 Buscar Subtítulos", command=self._search_selected).pack(side=tk.LEFT)
        ttk.Button(action_frame, text="📥 Descargar Todos", command=self._download_all).pack(side=tk.LEFT, padx=5)
        ttk.Button(action_frame, text="⬇️ Descargar Seleccionado", command=self._download_selected).pack(side=tk.LEFT, padx=5)
        
        # Idioma - Español como prioridad
        ttk.Label(action_frame, text="Idioma:").pack(side=tk.LEFT, padx=(20, 5))
        self.lang_var = tk.StringVar(value="es")
        lang_combo = ttk.Combobox(action_frame, textvariable=self.lang_var, width=20, state='readonly')
        lang_combo['values'] = ('es', 'es,en', 'en')
        lang_combo.pack(side=tk.LEFT)
        
        # === Estado ===
        status_frame = ttk.Frame(main_frame)
        status_frame.pack(fill=tk.X)
        
        ttk.Label(status_frame, textvariable=self.status_text, style='Status.TLabel').pack(side=tk.LEFT)
        self.progress = ttk.Progressbar(status_frame, mode='indeterminate', length=150)
        self.progress.pack(side=tk.RIGHT)
    
    def _select_folder(self):
        folder = filedialog.askdirectory(title="Seleccionar carpeta con videos")
        if folder:
            self.folder_path.set(folder)
            self._load_videos()
    
    def _load_videos(self):
        folder = self.folder_path.get()
        if not folder or not os.path.isdir(folder):
            messagebox.showerror("Error", "Selecciona una carpeta válida")
            return
        
        self.video_files = get_video_files(folder)
        
        self.video_listbox.delete(0, tk.END)
        for vf in self.video_files:
            filename = os.path.basename(vf)
            has_sub = self._has_subtitle(vf)
            prefix = "✓ " if has_sub else "  "
            self.video_listbox.insert(tk.END, prefix + filename)
        
        self.status_text.set(f"Se encontraron {len(self.video_files)} videos")
    
    def _has_subtitle(self, video_path: str) -> bool:
        video = Path(video_path)
        for ext in SUBTITLE_EXTENSIONS:
            if video.with_suffix(ext).exists():
                return True
            # También verificar con sufijo de idioma
            for lang in ['.es', '.en', '.spa', '.eng']:
                sub_name = video.stem + lang + ext
                if (video.parent / sub_name).exists():
                    return True
        return False
    
    def _on_video_select(self, event):
        selection = self.video_listbox.curselection()
        if selection:
            idx = selection[0]
            self.current_video_path = self.video_files[idx]
            video_name = os.path.basename(self.current_video_path)
            self.status_text.set(f"Seleccionado: {video_name}")
    
    
    def _sort_column(self, col: str):
        """Ordena el treeview por la columna clickeada."""
        # Obtener todos los items
        items = [(self.results_tree.set(item, col), item) for item in self.results_tree.get_children('')]
        
        # Determinar si es numérico
        try:
            # Intentar convertir a número para ordenar numéricamente
            items = [(int(val) if val.isdigit() else float(val) if val.replace('.', '').isdigit() else val, item) 
                     for val, item in items]
            numeric = True
        except (ValueError, AttributeError):
            numeric = False
        
        # Ordenar
        reverse = self.sort_reverse[col]
        items.sort(key=lambda x: x[0] if numeric else str(x[0]).lower(), reverse=reverse)
        
        # Reordenar items en el treeview
        for index, (_, item) in enumerate(items):
            self.results_tree.move(item, '', index)
        
        # También reordenar current_results para que coincida
        new_order = [self.results_tree.index(item) for _, item in items]
        
        # Toggle el orden para la próxima vez
        self.sort_reverse[col] = not reverse
        
        # Actualizar header para mostrar dirección
        arrow = "▼" if reverse else "▲"
        for c in ('Release', 'Idioma', 'Descargas', 'FPS'):
            text = c + (f" {arrow}" if c == col else "")
            self.results_tree.heading(c, text=text, command=lambda c=c: self._sort_column(c))
    
    def _search_selected(self):
        selection = self.video_listbox.curselection()
        if not selection:
            messagebox.showwarning("Aviso", "Selecciona un video primero")
            return
        
        idx = selection[0]
        video_path = self.video_files[idx]
        self.current_video_path = video_path
        
        thread = threading.Thread(target=self._do_search, args=(video_path,))
        thread.daemon = True
        thread.start()
    
    def _do_search(self, video_path: str):
        self._start_progress()
        video_name = os.path.basename(video_path)
        
        self._update_status(f"Calculando hash de: {video_name}...")
        file_hash = get_file_hash(video_path)
        
        # Parsear nombre para query alternativa
        info = parse_video_filename(video_name)
        query = build_search_query(info)
        
        self._update_status(f"Buscando subtítulos...")
        
        results = []
        
        # 1. OpenSubtitles - Búsqueda por hash (más precisa)
        if file_hash and OPENSUBTITLES_API_KEY:
            self._update_status(f"[OpenSubtitles] Buscando por hash...")
            results = self.opensubtitles.search(
                file_hash=file_hash,
                languages=self.lang_var.get()
            )
        
        # 2. OpenSubtitles - Búsqueda por nombre
        if not results and OPENSUBTITLES_API_KEY:
            self._update_status(f"[OpenSubtitles] Buscando: {query}...")
            results = self.opensubtitles.search(
                query=query,
                languages=self.lang_var.get(),
                season=info.get('season'),
                episode=info.get('episode')
            )
        
        # 3. FALLBACK: Subliminal (múltiples proveedores)
        if not results and SUBLIMINAL_AVAILABLE:
            self._update_status(f"[Subliminal] Buscando con proveedores alternativos...")
            results = self.subliminal.search_for_video(video_path, self.lang_var.get())
        
        self.current_results = results
        self._update_results_tree(results)
        
        if results:
            provider = results[0].get('provider', 'OpenSubtitles')
            self._update_status(f"✓ {len(results)} subtítulos encontrados [{provider}]")
        else:
            self._update_status(f"✗ No se encontraron subtítulos para: {video_name}")
        
        self._stop_progress()
    
    def _update_results_tree(self, results: List[Dict]):
        def update():
            for item in self.results_tree.get_children():
                self.results_tree.delete(item)
            
            for idx, sub in enumerate(results):
                attrs = sub.get('attributes', {})
                
                release = attrs.get('release', 'Sin nombre')
                language = attrs.get('language', '??')
                downloads = attrs.get('download_count', 0)
                fps = attrs.get('fps', '-')
                
                # Mapear idioma
                lang_display = {'es': 'Español', 'en': 'English'}.get(language, language)
                
                # Guardar índice original como tag
                self.results_tree.insert('', tk.END, values=(
                    release[:50],
                    lang_display,
                    downloads,
                    fps,
                ), tags=(str(idx),))
        
        self.root.after(0, update)
    
    def _on_download_double_click(self, event):
        self._download_selected()
    
    def _download_selected(self):
        selection = self.results_tree.selection()
        if not selection:
            messagebox.showwarning("Aviso", "Selecciona un subtítulo para descargar")
            return
        
        if not self.current_video_path:
            messagebox.showwarning("Aviso", "Selecciona un video primero")
            return
        
        # Obtener índice original desde tags
        item = selection[0]
        tags = self.results_tree.item(item, 'tags')
        if tags:
            original_idx = int(tags[0])
        else:
            original_idx = self.results_tree.index(item)
        
        if original_idx >= len(self.current_results):
            return
        
        subtitle = self.current_results[original_idx]
        
        thread = threading.Thread(target=self._do_download, args=(subtitle,))
        thread.daemon = True
        thread.start()
    
    def _do_download(self, subtitle: Dict):
        self._start_progress()
        
        attrs = subtitle.get('attributes', {})
        provider = subtitle.get('provider', 'OpenSubtitles')
        
        self._update_status(f"Descargando de {provider}...")
        
        content = None
        
        # Descargar según el proveedor
        if 'Subliminal' in provider:
            # Subliminal tiene su propio sistema de descarga
            video_dir = str(Path(self.current_video_path).parent)
            content = self.subliminal.download(subtitle, video_dir)
        else:
            # OpenSubtitles
            files = attrs.get('files', [])
            if files:
                file_id = files[0].get('file_id')
                if file_id:
                    download_link = self.opensubtitles.download(file_id)
                    if download_link:
                        try:
                            response = requests.get(download_link, timeout=30)
                            if response.status_code == 200:
                                content = response.content
                        except:
                            pass
        
        if not content:
            self._update_status("Error: No se pudo descargar el subtítulo")
            self._show_message("Error", "No se pudo descargar el subtítulo", error=True)
            self._stop_progress()
            return
        
        try:
            # Guardar junto al video
            video = Path(self.current_video_path)
            language = attrs.get('language', 'es')
            
            # Extraer si es zip
            content = self._extract_subtitle_content(content)
            
            sub_name = f"{video.stem}.{language}.srt"
            sub_path = video.parent / sub_name
            
            with open(sub_path, 'wb') as f:
                f.write(content)
            
            self._update_status(f"✓ Descargado: {sub_name}")
            self._show_message("Éxito", f"Subtítulo descargado:\n{sub_name}")
            
            # Recargar lista
            self.root.after(100, self._load_videos)
                
        except Exception as e:
            self._update_status(f"Error: {e}")
            self._show_message("Error", f"Error guardando: {e}", error=True)
        
        self._stop_progress()
    
    def _extract_subtitle_content(self, content: bytes) -> bytes:
        """Extrae el contenido del subtítulo si viene en zip."""
        import zipfile
        import io
        
        # Verificar si es un ZIP
        if content[:4] == b'PK\x03\x04':
            try:
                with zipfile.ZipFile(io.BytesIO(content)) as zf:
                    for name in zf.namelist():
                        if name.endswith('.srt'):
                            return zf.read(name)
                    # Si no hay .srt, tomar el primer archivo
                    if zf.namelist():
                        return zf.read(zf.namelist()[0])
            except:
                pass
        
        return content
    
    def _download_all(self):
        if not self.video_files:
            messagebox.showwarning("Aviso", "Primero carga una carpeta con videos")
            return
        
        videos_sin_sub = [v for v in self.video_files if not self._has_subtitle(v)]
        
        if not videos_sin_sub:
            messagebox.showinfo("Info", "Todos los videos ya tienen subtítulos")
            return
        
        result = messagebox.askyesno(
            "Confirmar",
            f"Se buscarán y descargarán subtítulos para {len(videos_sin_sub)} videos.\n\n¿Continuar?"
        )
        
        if result:
            thread = threading.Thread(target=self._do_download_all, args=(videos_sin_sub,))
            thread.daemon = True
            thread.start()
    
    def _do_download_all(self, videos: List[str]):
        self._start_progress()
        total = len(videos)
        downloaded = 0
        
        for i, video_path in enumerate(videos):
            video_name = os.path.basename(video_path)
            self._update_status(f"[{i+1}/{total}] Procesando: {video_name}")
            
            try:
                # Buscar por hash
                file_hash = get_file_hash(video_path)
                info = parse_video_filename(video_name)
                query = build_search_query(info)
                languages = self.lang_var.get()
                
                results = []
                
                # 1. OpenSubtitles por hash
                if file_hash and OPENSUBTITLES_API_KEY:
                    results = self.opensubtitles.search(file_hash=file_hash, languages=languages)
                
                # 2. OpenSubtitles por nombre
                if not results and OPENSUBTITLES_API_KEY:
                    results = self.opensubtitles.search(
                        query=query,
                        languages=languages,
                        season=info.get('season'),
                        episode=info.get('episode')
                    )
                
                # 3. Fallback: Subliminal
                if not results and SUBLIMINAL_AVAILABLE:
                    results = self.subliminal.search_for_video(video_path, languages)
                
                if results:
                    sub = results[0]
                    attrs = sub.get('attributes', {})
                    provider = sub.get('provider', 'OpenSubtitles')
                    
                    content = None
                    
                    # Descargar según proveedor
                    if 'Subliminal' in provider:
                        video_dir = str(Path(video_path).parent)
                        content = self.subliminal.download(sub, video_dir)
                    else:
                        files = attrs.get('files', [])
                        if files:
                            file_id = files[0].get('file_id')
                            if file_id:
                                download_link = self.opensubtitles.download(file_id)
                                if download_link:
                                    response = requests.get(download_link, timeout=30)
                                    if response.status_code == 200:
                                        content = response.content
                    
                    if content:
                        video = Path(video_path)
                        language = attrs.get('language', 'es')
                        
                        # Extraer si es zip
                        content = self._extract_subtitle_content(content)
                        
                        sub_name = f"{video.stem}.{language}.srt"
                        sub_path = video.parent / sub_name
                        
                        with open(sub_path, 'wb') as f:
                            f.write(content)
                        
                        downloaded += 1
                                
            except Exception as e:
                print(f"Error con {video_name}: {e}")
        
        self._update_status(f"✓ Completado: {downloaded}/{total} subtítulos descargados")
        self._show_message("Completado", f"Se descargaron {downloaded} de {total} subtítulos")
        self.root.after(100, self._load_videos)
        self._stop_progress()
    
    def _update_status(self, text: str):
        self.root.after(0, lambda: self.status_text.set(text))
    
    def _start_progress(self):
        self.root.after(0, self.progress.start)
    
    def _stop_progress(self):
        self.root.after(0, self.progress.stop)
    
    def _show_message(self, title: str, message: str, error: bool = False):
        def show():
            if error:
                messagebox.showerror(title, message)
            else:
                messagebox.showinfo(title, message)
        self.root.after(0, show)


def main():
    # Usar TkinterDnD si está disponible para drag & drop
    if DND_AVAILABLE:
        root = TkinterDnD.Tk()
    else:
        root = tk.Tk()
    
    app = SubtitleDownloaderApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
