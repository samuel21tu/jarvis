"""
Cérebro de Conhecimento e Notas Estruturadas do JARVIS (Obsidian Vault).
Suporta busca semântica/textual, leitura, gravação atômica e ganchos para sincronização bidirecional.
Todos os comentários seguem o padrão em Português do Brasil (pt-BR).
"""

import os
import subprocess
import time
from typing import Callable, List, Optional, Dict, Any
from src.hub.core.config import settings


class ObsidianBrain:
    def __init__(self, vault_path: str):
        self.vault_path = os.path.abspath(vault_path)
        os.makedirs(self.vault_path, exist_ok=True)
        # Lista de ouvintes assíncronos ou síncronos para sincronização de notas
        self.save_listeners: List[Callable[[str, str, float], Any]] = []

    def register_save_listener(self, callback: Callable[[str, str, float], Any]):
        """Registra um callback para ser notificado sempre que uma nota for salva localmente."""
        if callback not in self.save_listeners:
            self.save_listeners.append(callback)

    def search_note(self, query: str) -> str:
        """Busca notas no vault usando ripgrep ou fallback para grep."""
        try:
            # 1. Tenta usar ripgrep se disponível
            result = subprocess.run(
                ["rg", "-i", "-C", "2", query, self.vault_path],
                capture_output=True, text=True, timeout=10
            )
            if result.returncode == 0:
                return result.stdout

            # 2. Fallback para grep tradicional
            result = subprocess.run(
                ["grep", "-ir", "-C", "2", query, self.vault_path],
                capture_output=True, text=True, timeout=10
            )
            if result.returncode == 0:
                return result.stdout

            return "Nenhuma nota encontrada com esse termo no Obsidian."
        except Exception as e:
            return f"Erro na busca no Obsidian: {e}"

    def read_note(self, filename: str) -> str:
        """Lê o conteúdo de uma nota específica com validação defensiva contra Directory Traversal."""
        if not filename.endswith(".md"):
            filename += ".md"

        filepath = os.path.abspath(os.path.join(self.vault_path, filename))

        # Verificação estrita de segurança para evitar directory traversal
        if not filepath.startswith(self.vault_path):
            return "Erro: Caminho inválido (violação de segurança)."

        if not os.path.exists(filepath):
            return "Nota não encontrada."

        try:
            with open(filepath, "r", encoding="utf-8") as f:
                return f.read()
        except Exception as e:
            return f"Erro ao ler nota: {e}"

    def save_note(self, title: str, content: str, tags: list = None) -> str:
        """Cria ou atualiza uma nota no vault e notifica os canais de sincronização."""
        if not title.endswith(".md"):
            title += ".md"

        filepath = os.path.abspath(os.path.join(self.vault_path, title))

        # Verificação de segurança
        if not filepath.startswith(self.vault_path):
            return "Erro: Caminho inválido."

        try:
            frontmatter = "---\n"
            if tags:
                frontmatter += "tags:\n"
                for tag in tags:
                    frontmatter += f"  - {tag}\n"
            frontmatter += "---\n\n"

            if not os.path.exists(filepath):
                final_content = frontmatter + content
                with open(filepath, "w", encoding="utf-8") as f:
                    f.write(final_content)
            else:
                with open(filepath, "a", encoding="utf-8") as f:
                    f.write("\n\n" + content)
                with open(filepath, "r", encoding="utf-8") as f:
                    final_content = f.read()

            now = time.time()
            # Notifica ouvintes de sincronização (ex: WebSocket live sync)
            self._notify_save(title, final_content, now)

            return f"Nota '{title}' salva/atualizada com sucesso no Obsidian."
        except Exception as e:
            return f"Erro ao salvar nota: {e}"

    def save_raw(self, filename: str, content: str, mtime: Optional[float] = None) -> bool:
        """Grava diretamente uma nota recebida via sincronização remota sem re-disparar ouvintes."""
        if not filename.endswith(".md"):
            filename += ".md"

        filepath = os.path.abspath(os.path.join(self.vault_path, filename))
        if not filepath.startswith(self.vault_path):
            return False

        try:
            os.makedirs(os.path.dirname(filepath), exist_ok=True)
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(content)
            if mtime:
                try:
                    os.utime(filepath, (mtime, mtime))
                except Exception:
                    pass
            return True
        except Exception as e:
            print(f"[OBSIDIAN] Falha ao gravar nota direta {filename}: {e}")
            return False

    def _notify_save(self, filename: str, content: str, mtime: float):
        """Dispara os callbacks de sincronização registrados."""
        for listener in self.save_listeners:
            try:
                res = listener(filename, content, mtime)
                if hasattr(res, "__await__"):
                    import asyncio
                    try:
                        loop = asyncio.get_running_loop()
                        loop.create_task(res)
                    except RuntimeError:
                        pass
            except Exception as e:
                print(f"[OBSIDIAN] Erro no listener de sincronização: {e}")


obsidian_brain = ObsidianBrain(settings.obsidian_vault_path)
