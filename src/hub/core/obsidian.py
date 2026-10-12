import os
import subprocess
from src.hub.core.config import settings

class ObsidianBrain:
    def __init__(self, vault_path: str):
        self.vault_path = os.path.abspath(vault_path)
        os.makedirs(self.vault_path, exist_ok=True)

    def search_note(self, query: str) -> str:
        """Search notes using ripgrep or grep."""
        try:
            # First try ripgrep
            result = subprocess.run(
                ["rg", "-i", "-C", "2", query, self.vault_path],
                capture_output=True, text=True, timeout=10
            )
            if result.returncode == 0:
                return result.stdout
                
            # Fallback to grep
            result = subprocess.run(
                ["grep", "-ir", "-C", "2", query, self.vault_path],
                capture_output=True, text=True, timeout=10
            )
            if result.returncode == 0:
                return result.stdout
                
            return "Nenhuma nota encontrada com esse termo."
        except Exception as e:
            return f"Erro na busca: {e}"

    def read_note(self, filename: str) -> str:
        """Read a specific note."""
        if not filename.endswith(".md"):
            filename += ".md"
            
        filepath = os.path.join(self.vault_path, filename)
        
        # Security check to prevent directory traversal
        if not os.path.abspath(filepath).startswith(self.vault_path):
            return "Erro: Caminho inválido."
            
        if not os.path.exists(filepath):
            return "Nota não encontrada."
            
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                return f.read()
        except Exception as e:
            return f"Erro ao ler nota: {e}"

    def save_note(self, title: str, content: str, tags: list = None) -> str:
        """Create or update a note."""
        if not title.endswith(".md"):
            title += ".md"
            
        filepath = os.path.join(self.vault_path, title)
        
        # Security check
        if not os.path.abspath(filepath).startswith(self.vault_path):
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
                
            return f"Nota '{title}' salva/atualizada com sucesso."
        except Exception as e:
            return f"Erro ao salvar nota: {e}"

obsidian_brain = ObsidianBrain(settings.obsidian_vault_path)
