"""Adaptadores provider-neutral para os provedores de LLM do JARVIS."""

import asyncio
import base64
import inspect
import ipaddress
import json
import logging
import re
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import urlparse

import aiohttp

logger = logging.getLogger(__name__)


# Fragmentos que parecem segredos em corpos de erro: headers Bearer/sk-* e chaves/tokens.
_PATTERN_SEGRETO = re.compile(
    r"(?i)"
    r"bearer\s+[\w\-\.~+/=]+"
    r"|sk-[A-Za-z0-9\-_]{8,}"
    r"|(?:api[_-]?key|x[_-]?api[_-]?key|access[_-]?token|token|secret|password|authorization)"
    r"['\"]?\s*[:=]\s*['\"]?[\w\-\.~+/=]{4,}"
)


def _redigir_segredos(texto: str) -> str:
    """Redige fragmentos que parecem segredos de uma string antes de logar."""
    if not texto:
        return texto
    return _PATTERN_SEGRETO.sub("[SEGREDO_REMOVIDO]", texto)


@dataclass
class ToolCall:
    """Chamada de ferramenta normalizada entre APIs."""
    name: str
    arguments: dict[str, Any] = field(default_factory=dict)
    call_id: str = ""

@dataclass
class LLMResponse:
    """Resposta normalizada de texto e/ou ferramentas."""
    text: str = ""
    tool_calls: list[ToolCall] = field(default_factory=list)
    assistant_content: Any = None
    model: str = ""

class LLMProviderError(Exception):
    """Erro sanitizado de comunicação com um provider."""
    def __init__(self, message: str, status: int | None = None, retryable: bool = False):
        super().__init__(message)
        self.status = status
        self.retryable = retryable

def _schema_ferramenta(funcao: Any) -> dict[str, Any]:
    """Extrai um schema simples e seguro das assinaturas das ferramentas."""
    propriedades: dict[str, Any] = {}
    obrigatorios: list[str] = []
    for nome, parametro in inspect.signature(funcao).parameters.items():
        anotacao = parametro.annotation
        tipo = "string" if anotacao in (str, inspect.Parameter.empty) else "object"
        propriedades[nome] = {"type": tipo}
        if parametro.default is inspect.Parameter.empty:
            obrigatorios.append(nome)
    esquema = {"type": "object", "properties": propriedades, "additionalProperties": False}
    if obrigatorios:
        esquema["required"] = obrigatorios
    return esquema

def _data_url(data: str, mime_type: str) -> str:
    """Converte base64 recebido pelo websocket em data URL OpenAI."""
    valor = data.split(",", 1)[-1]
    # Validação básica de base64
    base64.b64decode(valor, validate=True)
    return f"data:{mime_type};base64,{valor}"

def mensagens_router(history: list[dict[str, Any]], system_prompt: str, prompt: str,
                     attachments: list[dict[str, Any]] | None = None) -> list[dict[str, Any]]:
    """Traduz o histórico do JARVIS para o formato Chat Completions usado pelo roteador."""
    mensagens: list[dict[str, Any]] = [{"role": "system", "content": system_prompt}]

    for item in history:
        papel = item.get("role", "user")
        # Normaliza papéis legados: 'model' -> 'assistant'
        if papel == "model":
            papel = "assistant"
        elif papel not in {"user", "assistant", "system", "tool"}:
            papel = "user"

        conteudo = item.get("content", "")
        mensagens.append({"role": papel, "content": conteudo})

    partes: list[dict[str, Any]] = [{"type": "text", "text": prompt or "Analise o conteúdo fornecido."}]

    for anexo in attachments or []:
        try:
            if anexo.get("data"):
                partes.append({
                    "type": "image_url",
                    "image_url": {
                        "url": _data_url(anexo.get("data", ""), anexo.get("mime_type", "image/png"))
                    }
                })
        except (ValueError, TypeError, base64.binascii.Error) as erro:
            raise LLMProviderError(f"Anexo inválido: {erro}") from erro

    mensagens.append({"role": "user", "content": partes})
    return mensagens


# Alias mantido para importações antigas.
mensagens_openrouter = mensagens_router


def _eh_loopback(url: str) -> bool:
    """True para gateways locais (OmniRoute roda em localhost por padrão)."""
    host = (urlparse(url or "").hostname or "").lower()
    return host in {"localhost", "127.0.0.1", "::1"}


def _validar_base_url(base_url: str, allowed_hosts: str = "") -> str:
    """Valida a URL do roteador: HTTPS remoto ou HTTP somente em loopback (SSRF)."""
    parsed = urlparse(base_url or "")
    host = (parsed.hostname or "").lower()
    if not host:
        raise LLMProviderError("LLM_ROUTER_BASE_URL inválida (ex.: http://localhost:20128/v1)")

    loopback = _eh_loopback(base_url)
    if parsed.scheme == "http" and not loopback:
        raise LLMProviderError("LLM_ROUTER_BASE_URL HTTP só é permitida em localhost/127.0.0.1")
    if parsed.scheme not in ("http", "https"):
        raise LLMProviderError("LLM_ROUTER_BASE_URL deve usar http (loopback) ou https")

    if not loopback:
        try:
            if ipaddress.ip_address(host).is_private:
                raise LLMProviderError("LLM_ROUTER_BASE_URL não pode apontar para IP privado")
        except ValueError:
            pass  # hostname público normal

    permitidos = [h.strip().lower() for h in (allowed_hosts or "").split(",") if h.strip()]
    if permitidos and host not in permitidos:
        raise LLMProviderError(f"Host '{host}' não está em LLM_ROUTER_ALLOWED_HOSTS")

    return base_url.rstrip("/")


class RouterProvider:
    """Cliente assíncrono para roteadores de IA compatíveis com Chat Completions (OmniRoute)."""

    def __init__(self, api_key: str, base_url: str, timeout: float = 45.0,
                 http_referer: str = "", x_title: str = "JARVIS", allowed_hosts: str = ""):
        self.base_url = _validar_base_url(base_url, allowed_hosts)
        # Gateways locais (OmniRoute) normalmente não exigem chave; remotos, sim.
        if not api_key and not _eh_loopback(self.base_url):
            raise LLMProviderError("LLM_ROUTER_API_KEY não configurada")
        self.api_key = api_key or ""
        self.timeout_seconds = timeout
        self.http_referer = http_referer
        self.x_title = x_title
        self._session: aiohttp.ClientSession | None = None

    async def _get_session(self) -> aiohttp.ClientSession:
        """Sessão preguiçosa (lazy) reutilizável."""
        if self._session is None or self._session.closed:
            timeout = aiohttp.ClientTimeout(total=self.timeout_seconds)
            headers = {"Content-Type": "application/json"}
            if self.api_key:
                headers["Authorization"] = f"Bearer {self.api_key}"
            if self.http_referer:
                headers["HTTP-Referer"] = self.http_referer
            if self.x_title:
                headers["X-Title"] = self.x_title

            self._session = aiohttp.ClientSession(headers=headers, timeout=timeout)
        return self._session

    async def generate(self, model: str, messages: list[dict[str, Any]], tools: list[Any] | None = None,
                       temperature: float = 0.2) -> LLMResponse:
        """Executa a requisição de geração de conteúdo."""
        payload: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "temperature": temperature
        }

        if tools:
            payload["tools"] = [{
                "type": "function",
                "function": {
                    "name": tool.__name__,
                    "description": (tool.__doc__ or "").strip(),
                    "parameters": _schema_ferramenta(tool),
                }
            } for tool in tools]
            payload["tool_choice"] = "auto"

        session = await self._get_session()
        try:
            async with session.post(f"{self.base_url}/chat/completions", json=payload) as resp:
                if resp.status >= 400:
                    categoria = "requisição rejeitada" if resp.status < 500 else "serviço indisponível"
                    # Sanitização de erro para não vazar payload ou tokens no log se o status vier com corpo sensível
                    corpo_erro = await resp.text()
                    logger.error(f"Erro do roteador de IA ({resp.status}): {_redigir_segredos(corpo_erro[:200])}...")
                    raise LLMProviderError(
                        f"Roteador de IA: {categoria} (HTTP {resp.status})",
                        resp.status,
                        resp.status == 429 or resp.status >= 500
                    )

                dados = await resp.json()
        except asyncio.TimeoutError as erro:
            raise LLMProviderError("Roteador de IA: timeout de conexão", retryable=True) from erro
        except aiohttp.ClientError as erro:
            raise LLMProviderError("Roteador de IA: falha de conexão", retryable=True) from erro
        except Exception as erro:
            raise LLMProviderError(f"Roteador de IA: erro inesperado: {str(erro)}") from erro

        # Parsing da resposta
        escolha = (dados.get("choices") or [{}])[0]
        mensagem = escolha.get("message") or {}

        chamadas = []
        for chamada in mensagem.get("tool_calls") or []:
            funcao = chamada.get("function") or {}
            try:
                # Argumentos costumam vir como string JSON
                argumentos = funcao.get("arguments")
                if isinstance(argumentos, str):
                    argumentos = json.loads(argumentos)
            except (TypeError, ValueError):
                argumentos = {}

            chamadas.append(ToolCall(
                name=funcao.get("name", ""),
                arguments=argumentos or {},
                call_id=chamada.get("id", "")
            ))

        return LLMResponse(
            text=mensagem.get("content") or "",
            tool_calls=chamadas,
            assistant_content=mensagem,
            model=dados.get("model", model)
        )

    async def close(self):
        """Fecha a sessão HTTP."""
        if self._session and not self._session.closed:
            await self._session.close()


# Alias mantido para importações antigas.
OpenRouterProvider = RouterProvider


class OllamaProvider:
    """Cliente assíncrono para a API local do Ollama via endpoint OpenAI compatível (/v1/chat/completions)."""

    def __init__(self, base_url: str = "http://localhost:11434", timeout: float = 60.0):
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout
        self._session: aiohttp.ClientSession | None = None

    async def _get_session(self) -> aiohttp.ClientSession:
        """Sessão HTTP reutilizável com timeout configurado para inferência local."""
        if self._session is None or self._session.closed:
            timeout = aiohttp.ClientTimeout(total=self.timeout_seconds)
            headers = {"Content-Type": "application/json"}
            self._session = aiohttp.ClientSession(headers=headers, timeout=timeout)
        return self._session

    async def generate(self, model: str, messages: list[dict[str, Any]], tools: list[Any] | None = None,
                       temperature: float = 0.2) -> LLMResponse:
        """Executa geração neural com o Ollama local com suporte a function calling / tool calling."""
        payload: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "stream": False
        }

        if tools:
            payload["tools"] = [{
                "type": "function",
                "function": {
                    "name": tool.__name__,
                    "description": (tool.__doc__ or "").strip(),
                    "parameters": _schema_ferramenta(tool),
                }
            } for tool in tools]
            payload["tool_choice"] = "auto"

        session = await self._get_session()
        url = f"{self.base_url}/v1/chat/completions"

        try:
            async with session.post(url, json=payload) as resp:
                if resp.status >= 400:
                    corpo_erro = await resp.text()
                    logger.error(f"Erro Ollama ({resp.status}): {corpo_erro[:200]}...")
                    raise LLMProviderError(
                        f"Ollama: falha na geração (HTTP {resp.status}) - {corpo_erro[:120]}",
                        resp.status,
                        retryable=True
                    )
                dados = await resp.json()
        except asyncio.TimeoutError as erro:
            raise LLMProviderError(f"Ollama: tempo limite ({self.timeout_seconds}s) excedido para o modelo {model}", retryable=True) from erro
        except aiohttp.ClientError as erro:
            raise LLMProviderError(f"Ollama: falha ao conectar em {self.base_url}. O serviço Ollama está ativo?", retryable=True) from erro
        except Exception as erro:
            if isinstance(erro, LLMProviderError):
                raise
            raise LLMProviderError(f"Ollama: erro inesperado: {str(erro)}") from erro

        # Processamento da resposta
        escolha = (dados.get("choices") or [{}])[0]
        mensagem = escolha.get("message") or {}

        chamadas = []
        for chamada in mensagem.get("tool_calls") or []:
            funcao = chamada.get("function") or {}
            argumentos = funcao.get("arguments")
            if isinstance(argumentos, str):
                try:
                    argumentos = json.loads(argumentos)
                except Exception:
                    argumentos = {}

            chamadas.append(ToolCall(
                name=funcao.get("name", ""),
                arguments=argumentos or {},
                call_id=chamada.get("id", f"call_{len(chamadas)}")
            ))

        return LLMResponse(
            text=mensagem.get("content") or "",
            tool_calls=chamadas,
            assistant_content=mensagem,
            model=dados.get("model", model)
        )

    async def close(self):
        """Encerra a sessão HTTP do Ollama."""
        if self._session and not self._session.closed:
            await self._session.close()
