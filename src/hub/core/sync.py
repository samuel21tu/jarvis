"""
Módulo de Sincronização Bidirecional do JARVIS (Obsidian Vault & Memória SQLite).
Garante consistência eventual e imediata entre o Nó Local (PC) e o Hub (Servidor CasaOS).
Todos os comentários e mensagens seguem o padrão em Português do Brasil (pt-BR).
"""

import os
import hashlib
import time
import sqlite3
from typing import Dict, Any, List, Tuple, Optional


def compute_file_hash(filepath: str) -> str:
    """Calcula o hash SHA-256 de um arquivo em blocos eficientes de 64KB."""
    hasher = hashlib.sha256()
    with open(filepath, "rb") as f:
        while chunk := f.read(65536):
            hasher.update(chunk)
    return hasher.hexdigest()


def compute_vault_manifest(vault_path: str) -> Dict[str, Dict[str, Any]]:
    """
    Gera o manifesto completo de arquivos Markdown do Obsidian Vault.
    Retorna: { 'rel_path.md': { 'hash': sha256_hex, 'mtime': float, 'size': int } }
    """
    manifest: Dict[str, Dict[str, Any]] = {}
    if not os.path.exists(vault_path):
        return manifest

    for root, _, files in os.walk(vault_path):
        for file in files:
            if not file.endswith(".md"):
                continue
            full_path = os.path.join(root, file)
            try:
                rel_path = os.path.relpath(full_path, vault_path).replace("\\", "/")
                stat = os.stat(full_path)
                f_hash = compute_file_hash(full_path)
                manifest[rel_path] = {
                    "hash": f_hash,
                    "mtime": stat.st_mtime,
                    "size": stat.st_size
                }
            except Exception as e:
                print(f"[SYNC] Erro ao indexar metadados da nota {full_path}: {e}")
    return manifest


def compare_vault_manifests(
    local_manifest: Dict[str, Dict[str, Any]],
    remote_manifest: Dict[str, Dict[str, Any]]
) -> Tuple[List[str], List[str]]:
    """
    Compara os manifestos locais e remotos.
    Retorna uma tupla contendo:
      - to_pull: lista de notas que o lado local precisa requisitar do remoto.
      - to_push: lista de notas que o lado local possui com versão mais recente para enviar.
    """
    to_pull: List[str] = []
    to_push: List[str] = []

    all_keys = set(local_manifest.keys()).union(set(remote_manifest.keys()))

    for key in all_keys:
        loc = local_manifest.get(key)
        rem = remote_manifest.get(key)

        if loc is None and rem is not None:
            # Não existe localmente: deve ser obtido do remoto
            to_pull.append(key)
        elif rem is None and loc is not None:
            # Não existe remotamente: deve ser enviado para o remoto
            to_push.append(key)
        elif loc and rem:
            if loc["hash"] != rem["hash"]:
                # Conteúdos diferentes: a versão com maior data de modificação prevalece
                if loc["mtime"] > rem["mtime"]:
                    to_push.append(key)
                else:
                    to_pull.append(key)

    return to_pull, to_push


def read_vault_note_raw(vault_path: str, rel_path: str) -> Optional[str]:
    """Lê o conteúdo em texto puro de uma nota com proteção defensiva contra Directory Traversal."""
    clean_rel = os.path.normpath(rel_path).lstrip("/\\")
    target = os.path.abspath(os.path.join(vault_path, clean_rel))
    vault_abs = os.path.abspath(vault_path)

    if not target.startswith(vault_abs):
        raise ValueError(f"Violação de segurança: Path traversal detectado para '{rel_path}'")

    if not os.path.exists(target):
        return None

    try:
        with open(target, "r", encoding="utf-8") as f:
            return f.read()
    except Exception as e:
        print(f"[SYNC] Erro ao ler nota {rel_path}: {e}")
        return None


def write_vault_note_atomic(
    vault_path: str,
    rel_path: str,
    content: str,
    mtime: Optional[float] = None
) -> bool:
    """Grava o conteúdo de uma nota de forma atômica (evita arquivos corrompidos em quedas de energia ou concorrência)."""
    clean_rel = os.path.normpath(rel_path).lstrip("/\\")
    target = os.path.abspath(os.path.join(vault_path, clean_rel))
    vault_abs = os.path.abspath(vault_path)

    if not target.startswith(vault_abs):
        raise ValueError(f"Violação de segurança: Path traversal detectado para '{rel_path}'")

    os.makedirs(os.path.dirname(target), exist_ok=True)
    tmp_target = f"{target}.tmp_{os.getpid()}_{int(time.time() * 1000)}"

    try:
        with open(tmp_target, "w", encoding="utf-8") as f:
            f.write(content)

        os.replace(tmp_target, target)

        if mtime is not None:
            try:
                os.utime(target, (mtime, mtime))
            except Exception:
                pass
        return True
    except Exception as e:
        if os.path.exists(tmp_target):
            try:
                os.remove(tmp_target)
            except Exception:
                pass
        print(f"[SYNC] Falha ao gravar nota atômica {rel_path}: {e}")
        return False


# ==============================================================================
# Sincronização de Banco de Memória Conversacional (SQLite)
# ==============================================================================

def get_memory_state(db_path: str) -> Dict[str, Any]:
    """Obtém o estado atual da base de memória conversacional do SQLite."""
    if not os.path.exists(db_path):
        return {"msg_count": 0, "max_created_at": "", "summary": None}

    conn = sqlite3.connect(db_path, timeout=5)
    conn.row_factory = sqlite3.Row
    try:
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) as count, MAX(created_at) as max_time FROM messages")
        row = cur.fetchone()
        count = row["count"] if row else 0
        max_time = row["max_time"] if row and row["max_time"] else ""

        cur.execute("SELECT conversation, content, last_message_id, updated_at FROM summaries WHERE conversation = 'principal'")
        sum_row = cur.fetchone()
        summary = dict(sum_row) if sum_row else None

        return {
            "msg_count": count,
            "max_created_at": max_time,
            "summary": summary
        }
    except Exception as e:
        print(f"[SYNC] Erro ao consultar estado da memória: {e}")
        return {"msg_count": 0, "max_created_at": "", "summary": None}
    finally:
        conn.close()


def get_messages_for_sync(
    db_path: str,
    since_timestamp: Optional[str] = None,
    limit: int = 200
) -> List[Dict[str, Any]]:
    """Recupera mensagens recentes a partir de um timestamp para envio sincronizado."""
    if not os.path.exists(db_path):
        return []

    conn = sqlite3.connect(db_path, timeout=5)
    conn.row_factory = sqlite3.Row
    try:
        cur = conn.cursor()
        if since_timestamp:
            cur.execute(
                "SELECT conversation, role, content, origin, created_at FROM messages WHERE created_at > ? ORDER BY id ASC LIMIT ?",
                (since_timestamp, limit)
            )
        else:
            cur.execute(
                "SELECT conversation, role, content, origin, created_at FROM messages ORDER BY id DESC LIMIT ?",
                (limit,)
            )
            rows = cur.fetchall()
            return [dict(r) for r in reversed(rows)]
        return [dict(r) for r in cur.fetchall()]
    except Exception as e:
        print(f"[SYNC] Erro ao extrair mensagens para sincronização: {e}")
        return []
    finally:
        conn.close()


def insert_synced_messages(db_path: str, messages: List[Dict[str, Any]]) -> int:
    """Insere mensagens sincronizadas de outro nó com prevenção estrita de duplicações."""
    if not messages or not os.path.exists(db_path):
        return 0

    conn = sqlite3.connect(db_path, timeout=10)
    inserted = 0
    try:
        cur = conn.cursor()
        for msg in messages:
            conv = msg.get("conversation", "principal")
            role = msg.get("role", "user")
            content = msg.get("content", "")
            origin = msg.get("origin", "sync")
            created_at = msg.get("created_at", "")

            # Evita duplicação conferindo tupla única
            cur.execute(
                "SELECT 1 FROM messages WHERE conversation = ? AND role = ? AND created_at = ? AND content = ? LIMIT 1",
                (conv, role, created_at, content)
            )
            if not cur.fetchone():
                cur.execute(
                    "INSERT INTO messages (conversation, role, content, origin, created_at) VALUES (?, ?, ?, ?, ?)",
                    (conv, role, content, origin, created_at)
                )
                inserted += 1
        conn.commit()
        return inserted
    except Exception as e:
        print(f"[SYNC] Erro ao mesclar mensagens sincronizadas: {e}")
        return inserted
    finally:
        conn.close()


def apply_synced_summary(db_path: str, summary: Dict[str, Any]) -> bool:
    """Aplica o resumo sincronizado caso a versão recebida seja mais recente que a local."""
    if not summary or not os.path.exists(db_path):
        return False

    conn = sqlite3.connect(db_path, timeout=5)
    conn.row_factory = sqlite3.Row
    try:
        cur = conn.cursor()
        conv = summary.get("conversation", "principal")
        new_updated_at = summary.get("updated_at", "")

        cur.execute("SELECT updated_at FROM summaries WHERE conversation = ?", (conv,))
        row = cur.fetchone()
        if row and row["updated_at"] and row["updated_at"] >= new_updated_at:
            return False  # O resumo local já é igual ou mais novo

        cur.execute(
            """
            INSERT INTO summaries (conversation, content, last_message_id, updated_at)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(conversation) DO UPDATE SET
                content = excluded.content,
                last_message_id = excluded.last_message_id,
                updated_at = excluded.updated_at
            """,
            (conv, summary.get("content", ""), summary.get("last_message_id", 0), new_updated_at)
        )
        conn.commit()
        return True
    except Exception as e:
        print(f"[SYNC] Erro ao aplicar resumo sincronizado: {e}")
        return False
    finally:
        conn.close()

