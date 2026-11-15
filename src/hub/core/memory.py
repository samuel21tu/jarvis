"""
Memória conversacional persistente do JARVIS.

Arquitetura (isolada do Obsidian Vault, que fica só para conhecimento/notas):
- SQLite próprio (MEMORY_DB_PATH) com WAL, sobrevivendo a reinícios do container.
- Conversa ÚNICA e contínua ("principal"), compartilhada entre HUD, celular e PC Node:
  reabrir a interface nunca zera o contexto.
- Contexto enviado ao modelo = resumo de longo prazo + últimas N mensagens literais.
- Mensagens antigas são condensadas em um resumo incremental (em background).
- Busca full-text (FTS5) em todo o histórico, exposta como ferramenta para a IA.
"""
import asyncio
import json
import os
import re
import sqlite3
import threading
from datetime import datetime
from typing import Awaitable, Callable, Dict, List, Optional

from src.hub.core.config import settings

MAIN_CONVERSATION = "principal"

# Quantidade de mensagens literais mantidas no contexto do modelo
RECENT_WINDOW = 30
# Quantas mensagens "fora da janela" acumulam antes de disparar novo resumo
SUMMARIZE_BATCH = 20

Summarizer = Callable[[str, List[Dict]], Awaitable[str]]


class MemoryManager:
    def __init__(self, db_path: Optional[str] = None):
        self.db_path = db_path or settings.memory_db_path
        os.makedirs(os.path.dirname(os.path.abspath(self.db_path)), exist_ok=True)
        self._lock = threading.Lock()
        self._summarizing = False
        self.summarizer: Optional[Summarizer] = None
        self.message_listeners: List[Callable[[Dict[str, Any]], Any]] = []
        self.summary_listeners: List[Callable[[Dict[str, Any]], Any]] = []
        self._conn = self._connect()
        self._init_schema()
        self._migrate_obsidian_sessions()

    # ------------------------------------------------------------------ infra
    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, check_same_thread=False, timeout=10)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        return conn

    def _exec(self, sql: str, params: tuple = (), many: bool = False):
        """Executa SQL com lock e reconexão automática se a conexão cair."""
        with self._lock:
            for attempt in range(2):
                try:
                    cur = self._conn.executemany(sql, params) if many else self._conn.execute(sql, params)
                    self._conn.commit()
                    return cur
                except sqlite3.ProgrammingError:
                    # Conexão fechada/inválida: reabre e tenta de novo
                    if attempt:
                        raise
                    self._conn = self._connect()

    def _init_schema(self):
        with self._lock:
            self._conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    conversation TEXT NOT NULL,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    origin TEXT,
                    created_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_msg_conv ON messages(conversation, id);

                CREATE VIRTUAL TABLE IF NOT EXISTS messages_fts USING fts5(
                    content, content='messages', content_rowid='id', tokenize='unicode61 remove_diacritics 2'
                );
                CREATE TRIGGER IF NOT EXISTS messages_ai AFTER INSERT ON messages BEGIN
                    INSERT INTO messages_fts(rowid, content) VALUES (new.id, new.content);
                END;

                CREATE TABLE IF NOT EXISTS summaries (
                    conversation TEXT PRIMARY KEY,
                    content TEXT NOT NULL,
                    last_message_id INTEGER NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT);
                """
            )
            self._conn.commit()

    def _migrate_obsidian_sessions(self):
        """Importa uma única vez os históricos antigos salvos no Obsidian (Jarvis_Session_*.md)."""
        done = self._exec("SELECT value FROM meta WHERE key='obsidian_migrated'").fetchone()
        if done:
            return
        vault = settings.obsidian_vault_path
        imported = 0
        try:
            files = []
            if os.path.isdir(vault):
                for root, _, names in os.walk(vault):
                    for n in names:
                        if n.startswith("Jarvis_Session_") and n.endswith(".md"):
                            p = os.path.join(root, n)
                            files.append((os.path.getmtime(p), p))
            for mtime, path in sorted(files):
                with open(path, encoding="utf-8") as fh:
                    match = re.search(r"<!-- JARVIS_MEMORY\n(.*?)\n-->", fh.read(), re.DOTALL)
                if not match:
                    continue
                ts = datetime.fromtimestamp(mtime).isoformat(timespec="seconds")
                rows = [
                    (MAIN_CONVERSATION, m.get("role", "user"), m.get("content", ""), "migrado", ts)
                    for m in json.loads(match.group(1))
                    if m.get("content")
                ]
                self._exec(
                    "INSERT INTO messages(conversation, role, content, origin, created_at) VALUES (?,?,?,?,?)",
                    rows, many=True,
                )
                imported += len(rows)
        except Exception as e:
            print(f"[MEMORY] Falha na migração do Obsidian (seguindo sem ela): {e}")
        self._exec("INSERT OR REPLACE INTO meta(key, value) VALUES ('obsidian_migrated', ?)", (str(imported),))
        if imported:
            print(f"[MEMORY] {imported} mensagens antigas importadas do Obsidian.")

    # -------------------------------------------------------------- API pública
    def register_message_listener(self, callback: Callable[[Dict[str, Any]], Any]):
        """Registra callback chamado ao adicionar uma nova mensagem."""
        if callback not in self.message_listeners:
            self.message_listeners.append(callback)

    def register_summary_listener(self, callback: Callable[[Dict[str, Any]], Any]):
        """Registra callback chamado ao atualizar o resumo de longo prazo."""
        if callback not in self.summary_listeners:
            self.summary_listeners.append(callback)

    def _notify_message(self, msg_dict: Dict[str, Any]):
        for listener in self.message_listeners:
            try:
                res = listener(msg_dict)
                if hasattr(res, "__await__"):
                    import asyncio
                    try:
                        asyncio.get_running_loop().create_task(res)
                    except RuntimeError:
                        pass
            except Exception as e:
                print(f"[MEMORY] Erro ao notificar ouvinte de mensagem: {e}")

    def _notify_summary(self, summary_dict: Dict[str, Any]):
        for listener in self.summary_listeners:
            try:
                res = listener(summary_dict)
                if hasattr(res, "__await__"):
                    import asyncio
                    try:
                        asyncio.get_running_loop().create_task(res)
                    except RuntimeError:
                        pass
            except Exception as e:
                print(f"[MEMORY] Erro ao notificar ouvinte de resumo: {e}")

    def add_message(self, session_id: str, role: str, content: str, origin: str = ""):
        """Grava uma mensagem. O session_id do cliente é ignorado: a conversa é única."""
        now_ts = datetime.now().isoformat(timespec="seconds")
        self._exec(
            "INSERT INTO messages(conversation, role, content, origin, created_at) VALUES (?,?,?,?,?)",
            (MAIN_CONVERSATION, role, content, origin or session_id, now_ts),
        )
        self._maybe_schedule_summary()
        self._notify_message({
            "conversation": MAIN_CONVERSATION,
            "role": role,
            "content": content,
            "origin": origin or session_id,
            "created_at": now_ts
        })

    def add_synced_message(self, conversation: str, role: str, content: str, origin: str, created_at: str) -> bool:
        """Adiciona mensagem vinda de sincronização remota sem re-disparar ouvintes nem duplicar."""
        cur = self._exec(
            "SELECT 1 FROM messages WHERE conversation=? AND role=? AND created_at=? AND content=? LIMIT 1",
            (conversation or MAIN_CONVERSATION, role, created_at, content)
        )
        if cur.fetchone():
            return False

        self._exec(
            "INSERT INTO messages(conversation, role, content, origin, created_at) VALUES (?,?,?,?,?)",
            (conversation or MAIN_CONVERSATION, role, content, origin, created_at),
        )
        return True

    def apply_synced_summary(self, conversation: str, content: str, last_message_id: int, updated_at: str) -> bool:
        """Aplica resumo vindo de sincronização remota se for mais recente."""
        conv = conversation or MAIN_CONVERSATION
        row = self._exec("SELECT updated_at FROM summaries WHERE conversation=?", (conv,)).fetchone()
        if row and row["updated_at"] and row["updated_at"] >= updated_at:
            return False

        self._exec(
            """
            INSERT INTO summaries (conversation, content, last_message_id, updated_at)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(conversation) DO UPDATE SET
                content = excluded.content,
                last_message_id = excluded.last_message_id,
                updated_at = excluded.updated_at
            """,
            (conv, content, last_message_id, updated_at),
        )
        return True

    def get_history(self, session_id: str = MAIN_CONVERSATION, limit: int = RECENT_WINDOW) -> List[Dict]:
        rows = self._exec(
            "SELECT role, content, origin, created_at FROM messages WHERE conversation=? "
            "ORDER BY id DESC LIMIT ?",
            (MAIN_CONVERSATION, limit),
        ).fetchall()
        return [dict(r) for r in reversed(rows)]

    def get_summary(self) -> str:
        row = self._exec("SELECT content FROM summaries WHERE conversation=?", (MAIN_CONVERSATION,)).fetchone()
        return row["content"] if row else ""

    def search(self, query: str, limit: int = 15) -> str:
        """Busca full-text em todo o histórico de conversas (inclusive o que já saiu do contexto)."""
        terms = re.findall(r"\w+", query, re.UNICODE)
        if not terms:
            return "Consulta vazia."
        fts_query = " OR ".join(f'"{t}"' for t in terms)
        try:
            rows = self._exec(
                "SELECT m.role, m.content, m.created_at FROM messages_fts f "
                "JOIN messages m ON m.id = f.rowid WHERE messages_fts MATCH ? "
                "ORDER BY bm25(messages_fts) LIMIT ?",
                (fts_query, limit),
            ).fetchall()
        except sqlite3.OperationalError as e:
            return f"Erro na busca: {e}"
        if not rows:
            return "Nada encontrado no histórico de conversas."
        out = []
        for r in rows:
            who = "Usuário" if r["role"] == "user" else "Jarvis"
            out.append(f"[{r['created_at']}] {who}: {r['content'][:500]}")
        return "\n".join(out)

    # ------------------------------------------------------- resumo incremental
    def _maybe_schedule_summary(self):
        if self._summarizing or self.summarizer is None:
            return
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            return
        loop.create_task(self._summarize_if_needed())

    async def _summarize_if_needed(self):
        if self._summarizing:
            return
        self._summarizing = True
        try:
            row = self._exec(
                "SELECT content, last_message_id FROM summaries WHERE conversation=?", (MAIN_CONVERSATION,)
            ).fetchone()
            prev_summary, last_id = (row["content"], row["last_message_id"]) if row else ("", 0)

            # Primeiro id que ainda está dentro da janela literal
            boundary = self._exec(
                "SELECT id FROM messages WHERE conversation=? ORDER BY id DESC LIMIT 1 OFFSET ?",
                (MAIN_CONVERSATION, RECENT_WINDOW - 1),
            ).fetchone()
            if not boundary:
                return
            pending = self._exec(
                "SELECT id, role, content FROM messages WHERE conversation=? AND id>? AND id<? ORDER BY id",
                (MAIN_CONVERSATION, last_id, boundary["id"]),
            ).fetchall()
            if len(pending) < SUMMARIZE_BATCH:
                return

            new_summary = await self.summarizer(prev_summary, [dict(r) for r in pending])
            if new_summary and new_summary.strip():
                now_ts = datetime.now().isoformat(timespec="seconds")
                self._exec(
                    "INSERT OR REPLACE INTO summaries(conversation, content, last_message_id, updated_at) "
                    "VALUES (?,?,?,?)",
                    (MAIN_CONVERSATION, new_summary.strip(), pending[-1]["id"], now_ts),
                )
                print(f"[MEMORY] Resumo de longo prazo atualizado (+{len(pending)} mensagens).")
                self._notify_summary({
                    "conversation": MAIN_CONVERSATION,
                    "content": new_summary.strip(),
                    "last_message_id": pending[-1]["id"],
                    "updated_at": now_ts
                })
        except Exception as e:
            # Falha no resumo nunca derruba o chat; tenta de novo na próxima mensagem
            print(f"[MEMORY] Falha ao gerar resumo: {e}")
        finally:
            self._summarizing = False


# Instância única compartilhada por hub e LLM
memory = MemoryManager()
