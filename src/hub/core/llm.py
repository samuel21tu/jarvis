import asyncio
import json
import uuid
from datetime import datetime
from typing import List, Dict, Any

from src.hub.core.config import settings
from src.hub.core.websocket import manager
from src.hub.core.obsidian import obsidian_brain
from src.hub.core.memory import memory
from src.node.jarvis_node import is_command_safe

# Dicionário de futures para requisições assíncronas aos nós de execução
pending_requests: Dict[str, asyncio.Future] = {}

# Timeout unificado para requisições peer (Servidor <-> Nó) via WebSocket
PEER_TIMEOUT = 50.0

# Despachantes remotos para ordens enviadas do Nó Local para o Servidor
remote_server_command_dispatcher = None
remote_server_status_dispatcher = None


def set_remote_server_dispatchers(cmd_dispatcher, status_dispatcher):
    """Registra os manipuladores de envio de comandos do Nó Local para o Servidor via WebSocket."""
    global remote_server_command_dispatcher, remote_server_status_dispatcher
    remote_server_command_dispatcher = cmd_dispatcher
    remote_server_status_dispatcher = status_dispatcher


async def execute_command(target: str, cmd: str) -> str:
    """Envia um comando Bash/Shell para o nó de execução ou para o próprio servidor."""
    selected_target = (target or "").lower().strip()
    is_server = (settings.node_role != "local" and remote_server_command_dispatcher is None)

    # 1. Ordem direcionada ao SERVIDOR CasaOS
    if selected_target in ("server", "servidor", "hub"):
        if is_server:
            safe, reason = is_command_safe(cmd)
            if not safe:
                return f"Security Error: {reason}"
            await manager.stream_log_to_mobile(f"Executando no terminal (Servidor CasaOS): '{cmd}'...", level="warn")
            try:
                import subprocess
                result = await asyncio.to_thread(
                    subprocess.run, cmd, shell=True, capture_output=True, text=True, timeout=PEER_TIMEOUT
                )
                output = ""
                if result.stdout: output += f"STDOUT:\n{result.stdout}\n"
                if result.stderr: output += f"STDERR:\n{result.stderr}\n"
                if not output: output = f"Command exited with code {result.returncode} but no output."
                await manager.stream_log_to_mobile("Comando concluído no Servidor.", level="success")
                return output
            except Exception as e:
                return f"Erro local no servidor: {e}"
        else:
            # Enviado do Nó Local para o Servidor via WebSocket
            if remote_server_command_dispatcher:
                return await remote_server_command_dispatcher(cmd)
            return "Erro: Conexão com o Servidor CasaOS indisponível para executar a ordem."

    # 2. Ordem direcionada ao PC LOCAL
    if not is_server:
        try:
            from src.node.jarvis_node import execute_command as local_exec
            return await asyncio.to_thread(local_exec, cmd)
        except Exception:
            safe, reason = is_command_safe(cmd)
            if not safe:
                return f"Security Error: {reason}"
            import subprocess
            result = await asyncio.to_thread(
                subprocess.run, cmd, shell=True, capture_output=True, text=True, timeout=PEER_TIMEOUT
            )
            output = ""
            if result.stdout: output += f"STDOUT:\n{result.stdout}\n"
            if result.stderr: output += f"STDERR:\n{result.stderr}\n"
            return output or f"Command exited with code {result.returncode}."

    # 3. Estamos no Servidor e o alvo é o PC (Nó conectado)
    if selected_target not in manager.active_nodes:
        if manager.active_nodes:
            fallback_target = list(manager.active_nodes.keys())[0]
            await manager.stream_log_to_mobile(
                f"Alvo '{target}' não localizado. Redirecionando para o nó ativo '{fallback_target}'...",
                level="info"
            )
            selected_target = fallback_target
        else:
            await manager.stream_log_to_mobile(f"Erro: Nenhum nó conectado para executar '{cmd}'.", level="error")
            return f"Error: O computador ('{target}') está OFFLINE. Nenhum nó ativo conectado ao Hub."

    await manager.stream_log_to_mobile(f"Executando no terminal ({selected_target}): '{cmd}'...", level="warn")

    req_id = str(uuid.uuid4())
    loop = asyncio.get_running_loop()
    future = loop.create_future()
    pending_requests[req_id] = future

    sent = await manager.send_to_node(selected_target, {
        "action": "execute_command",
        "req_id": req_id,
        "cmd": cmd
    })

    if not sent:
        pending_requests.pop(req_id, None)
        return f"Error: Falha no envio da mensagem WebSocket para {selected_target}."

    try:
        result = await asyncio.wait_for(future, timeout=PEER_TIMEOUT)
        pending_requests.pop(req_id, None)
        await manager.stream_log_to_mobile(f"Comando concluído em {selected_target}.", level="success")
        return result
    except asyncio.TimeoutError:
        pending_requests.pop(req_id, None)
        await manager.stream_log_to_mobile(f"Timeout aguardando execução de '{cmd}'.", level="error")
        return f"Error: O comando '{cmd}' excedeu o tempo limite de execução (50s)."


async def get_system_status(target: str) -> str:
    """Solicita métricas de hardware (CPU, RAM, Disco, Temperatura) ao nó ou ao servidor."""
    selected_target = (target or "").lower().strip()
    is_server = (settings.node_role != "local" and remote_server_status_dispatcher is None)

    # 1. Status do SERVIDOR CasaOS
    if selected_target in ("server", "servidor", "hub"):
        if is_server:
            import psutil
            cpu = psutil.cpu_percent(interval=None)
            ram = psutil.virtual_memory()
            disk = psutil.disk_usage('/')
            return (
                f"Status do Servidor CasaOS:\n"
                f"CPU: {cpu}%\n"
                f"RAM: {ram.percent}% ({ram.used // (1024**2)}MB / {ram.total // (1024**2)}MB)\n"
                f"Disco: {disk.percent}%"
            )
        else:
            if remote_server_status_dispatcher:
                return await remote_server_status_dispatcher()
            return "Erro: Conexão remota com o Servidor CasaOS indisponível."

    # 2. Status do PC LOCAL
    if not is_server:
        try:
            from src.node.jarvis_node import get_system_status as local_status
            return local_status()
        except Exception as e:
            return f"Erro ao coletar status local: {e}"

    # 3. Estamos no Servidor e o alvo é o PC conectado
    if selected_target not in manager.active_nodes:
        if manager.active_nodes:
            selected_target = list(manager.active_nodes.keys())[0]
        else:
            return f"Error: O computador ('{target}') está OFFLINE."

    await manager.stream_log_to_mobile(f"Coletando métricas do sistema em {selected_target}...", level="info")

    req_id = str(uuid.uuid4())
    loop = asyncio.get_running_loop()
    future = loop.create_future()
    pending_requests[req_id] = future

    sent = await manager.send_to_node(selected_target, {
        "action": "get_system_status",
        "req_id": req_id
    })

    if not sent:
        pending_requests.pop(req_id, None)
        return "Error: Falha ao enviar requisição de métricas ao nó."

    try:
        result = await asyncio.wait_for(future, timeout=PEER_TIMEOUT)
        pending_requests.pop(req_id, None)
        return result
    except asyncio.TimeoutError:
        pending_requests.pop(req_id, None)
        return "Error: Tempo limite excedido ao obter status do sistema."


def search_obsidian(query: str) -> str:
    """Encontra notas relevantes no Obsidian Vault."""
    return obsidian_brain.search_note(query)


def read_obsidian_note(filename: str) -> str:
    """Lê o conteúdo textual de uma nota específica no Obsidian."""
    return obsidian_brain.read_note(filename)


def save_obsidian_note(title: str, content: str, tags: list = None) -> str:
    """Salva aprendizados, configurações ou notas no Obsidian Vault."""
    return obsidian_brain.save_note(title, content, tags)


def search_conversations(query: str) -> str:
    """Busca em todo o histórico de conversas anteriores."""
    return memory.search(query)


# Mapeamento de funções executáveis reais
AVAILABLE_TOOLS = {
    "execute_command": execute_command,
    "get_system_status": get_system_status,
    "search_obsidian": search_obsidian,
    "read_obsidian_note": read_obsidian_note,
    "save_obsidian_note": save_obsidian_note,
    "search_conversations": search_conversations
}

# Schemas das ferramentas (function calling compatível com o roteador de IA)
def execute_command_schema(target: str, cmd: str) -> str:
    """Executa comandos nativos no terminal Bash/Shell. Use target='server' para executar no Servidor (CasaOS) ou target='pc' (ou 'local') para executar no PC local."""
    pass
execute_command_schema.__name__ = "execute_command"

def get_system_status_schema(target: str) -> str:
    """Obtém o status de hardware e sistema operacional (CPU, RAM, disco, temperatura). Use target='server' para o Servidor CasaOS ou target='pc' para o PC local."""
    pass
get_system_status_schema.__name__ = "get_system_status"

def search_obsidian_schema(query: str) -> str:
    """Encontra notas relevantes no Cérebro Digital (Obsidian Vault) usando palavras-chave ou conceitos. Use antes de salvar notas para ver se o conceito já existe."""
    pass
search_obsidian_schema.__name__ = "search_obsidian"

def read_obsidian_note_schema(filename: str) -> str:
    """Lê o conteúdo textual completo de uma nota específica no Cérebro Digital (Obsidian Vault)."""
    pass
read_obsidian_note_schema.__name__ = "read_obsidian_note"

def save_obsidian_note_schema(title: str, content: str, tags: list[str] = None) -> str:
    """Salva aprendizados, memórias ou informações no Cérebro Digital (Obsidian Vault).
    IMPORTANTE: Sempre crie notas separadas para pessoas, projetos ou lugares.
    No texto ('content'), NOMEIE as entidades usando colchetes duplos para criar links bidirecionais. Exemplo: 'Falei com o [[João Silva]] sobre o [[Projeto Alpha]]'."""
    pass
save_obsidian_note_schema.__name__ = "save_obsidian_note"

def search_conversations_schema(query: str) -> str:
    """Busca por palavras-chave em TODO o histórico de conversas com o usuário (dias/semanas atrás), incluindo o que já saiu do contexto recente. Use quando o usuário citar algo dito antes ('lembra que...', 'aquilo que falamos', 'de novo') e você não tiver o detalhe."""
    pass
search_conversations_schema.__name__ = "search_conversations"

jarvis_tools = [
    execute_command_schema,
    get_system_status_schema,
    search_obsidian_schema,
    read_obsidian_note_schema,
    save_obsidian_note_schema,
    search_conversations_schema
]


async def summarize_conversation(previous_summary: str, messages: list) -> str:
    """Condensa mensagens antigas no resumo de longo prazo (chamado em background pela memória)."""
    transcript = "\n".join(
        f"{'Usuário' if m['role'] == 'user' else 'Jarvis'}: {m['content'][:1500]}" for m in messages
    )
    prompt = f"""Você mantém a memória de longo prazo do assistente JARVIS sobre o usuário.
Atualize o RESUMO ATUAL incorporando os fatos do NOVO TRECHO de conversa.
Regras: máximo ~600 palavras, tópicos curtos em pt-BR; preserve preferências, dados pessoais relevantes,
projetos em andamento, decisões tomadas, pendências e caminhos/configurações técnicas; descarte conversa trivial;
se algo novo contradiz o resumo, mantenha a versão mais recente. Responda APENAS com o resumo.

RESUMO ATUAL:
{previous_summary or '(vazio)'}

NOVO TRECHO:
{transcript}"""
    from src.hub.core.llm_providers import RouterProvider, LLMProviderError

    mensagens = [{"role": "user", "content": prompt}]
    modelos = settings.modelos_llm_router()
    if not modelos:
        print("[MEMORY] LLM_ROUTER_MODEL não configurada; resumo ignorado")
        return ""

    provider = RouterProvider(
        settings.llm_router_api_key,
        settings.llm_router_base_url,
        settings.llm_timeout_seconds,
        settings.llm_router_http_referer,
        settings.llm_router_x_title,
        settings.llm_router_allowed_hosts,
    )
    try:
        for model in modelos:
            try:
                resposta = await provider.generate(model, mensagens, temperature=0.1)
                if resposta.text:
                    return resposta.text
            except LLMProviderError as erro:
                print(f"[MEMORY] Resumo falhou: {erro}")
    finally:
        await provider.close()
    return ""


memory.summarizer = summarize_conversation


def build_system_prompt(origin: str) -> str:
    """Gera o prompt de instruções de sistema com contexto em tempo real dos nós conectados e da origem."""
    active_node_list = list(manager.active_nodes.keys())
    active_nodes_str = ", ".join(active_node_list) if active_node_list else "nenhum nó conectado"

    # Define o alvo de execução por padrão
    default_target = "server" if origin == "server" else origin.replace("node:", "")
    
    return f"""Você é o JARVIS, assistente de inteligência artificial de elite pessoal do usuário.
Você está conversando atualmente com o usuário que está acessando através do '{origin}'.
Por padrão (quando o usuário pedir para executar algo sem especificar onde), você deve usar target='{default_target}'.
Se o usuário pedir explicitamente para rodar algo no "PC", "meu pc", "computador", use um dos nós disponíveis: [{active_nodes_str}].
Se pedir para rodar no "Servidor", "hub", "sua máquina", use target='server'.
Você tem acesso ao mesmo Obsidian Vault independentemente da origem (PC ou Servidor), pois ele é compartilhado.

DIRETRIZES FUNDAMENTAIS E INEGOCIÁVEIS:
1. TRATAMENTO E PERSONALIDADE: Você DEVE SEMPRE tratar o usuário como "senhor" (Sir), exatamente como o JARVIS trata Tony Stark / Homem de Ferro. Mantenha uma postura elegante, leal, descontraída e refinada, com toques sutis de inteligência e perspicácia.
2. PROIBIDO ALUCINAR EXECUÇÃO NO TERMINAL: Você NUNCA deve responder em texto que criou pastas, removeu arquivos, executou comandos ou instalou pacotes sem ANTES ter chamado a ferramenta `execute_command` e recebido o resultado real do comando no terminal.
3. VALIDAÇÃO REAL: Sempre que criar uma pasta ou arquivo via comando, verifique a criação de fato usando `ls -ld <caminho>` ou comando equivalente. Se retornar erro, investigue.
4. OBSIDIAN & RAG SEMÂNTICO: Quando o usuário falar sobre ALGUÉM (uma pessoa), ALGO (um projeto, conceito, lugar) ou uma IDEIA importante:
   - Você DEVE usar a ferramenta `save_obsidian_note` para criar uma nota individual para essa entidade.
   - O título da nota deve ser o nome exato da entidade.
   - Dentro das notas, crie conexões semânticas usando links no formato [[Nome da Entidade]] sempre que mencionar outras pessoas, lugares ou projetos que também possam ser notas.
   - Isso constrói um "Cérebro Digital" otimizado onde tudo é interligado.
   - Antes de responder sobre um assunto complexo, use `search_obsidian` para ver se você já anotou algo sobre aquilo no passado.
5. SENHA ROOT/SUDO: Para operações privileged no Arch Linux, peça a senha se necessário.
6. INTERAÇÃO POR VOZ: O usuário se comunica prioritariamente por voz. Seja objetivo, direto e sempre refinado.
7. MEMÓRIA CONTÍNUA: Esta é uma conversa única e contínua com o usuário, que persiste entre dispositivos e reinícios. NUNCA aja como se fosse a primeira conversa nem peça para ele repetir algo que já está no histórico ou na memória abaixo. Se faltar detalhe de algo antigo, use `search_conversations`.

MEMÓRIA DE LONGO PRAZO (resumo das conversas anteriores):
{memory.get_summary() or '(ainda vazia)'}

Data/hora atual: {datetime.now().strftime('%d/%m/%Y %H:%M')}"""


async def chat_with_nexus(prompt: str, history: list, origin: str = "server", attachments: list = None) -> str:
    """Gerencia conversa multimodal exclusivamente pelo roteador de IA configurado."""
    from src.hub.core.llm_providers import RouterProvider, LLMProviderError, mensagens_router

    modelos = settings.modelos_llm_router()
    if not modelos:
        return "Senhor, o roteador de IA não está configurado. Defina LLM_ROUTER_MODEL no ambiente."

    provider = RouterProvider(
        settings.llm_router_api_key,
        settings.llm_router_base_url,
        settings.llm_timeout_seconds,
        settings.llm_router_http_referer,
        settings.llm_router_x_title,
        settings.llm_router_allowed_hosts,
    )

    try:
        mensagens = mensagens_router(history, build_system_prompt(origin), prompt, attachments)

        for modelo in modelos:
            await manager.stream_log_to_mobile("Processando solicitação...", level="info")
            try:
                resposta = await provider.generate(modelo, mensagens, jarvis_tools)

                # Loop de tool calling com limite de turnos (o roteador devolve tool_calls
                # no formato Chat Completions, executamos e devolvemos os resultados).
                for _ in range(6):
                    if not resposta.tool_calls:
                        return resposta.text or "Comando processado com sucesso pelos meus sistemas, senhor."

                    mensagens.append({
                        "role": "assistant",
                        "content": resposta.text or None,
                        "tool_calls": [
                            {
                                "id": chamada.call_id,
                                "type": "function",
                                "function": {
                                    "name": chamada.name,
                                    "arguments": json.dumps(chamada.arguments, ensure_ascii=False),
                                },
                            }
                            for chamada in resposta.tool_calls
                        ],
                    })

                    for chamada in resposta.tool_calls:
                        handler = AVAILABLE_TOOLS.get(chamada.name)
                        await manager.stream_log_to_mobile(
                            f"Invocando ferramenta: {chamada.name}...", level="warn"
                        )
                        try:
                            if handler is None:
                                raise ValueError("ferramenta indisponível")
                            if asyncio.iscoroutinefunction(handler):
                                resultado = await handler(**chamada.arguments)
                            else:
                                resultado = handler(**chamada.arguments)
                        except Exception as exec_err:
                            resultado = f"Erro na execução da ferramenta: {type(exec_err).__name__}"

                        mensagens.append({
                            "role": "tool",
                            "tool_call_id": chamada.call_id,
                            "name": chamada.name,
                            "content": str(resultado),
                        })

                    resposta = await provider.generate(modelo, mensagens, jarvis_tools)

                return resposta.text or "Processamento concluído após múltiplas etapas de sistema, senhor."

            except LLMProviderError as erro:
                await manager.stream_log_to_mobile(
                    f"Roteador indisponível ({erro.status or 'rede'}).", level="warn"
                )
                if erro.status in (400, 401, 403):
                    break  # credencial/configuração inválida: outros modelos não ajudariam

        return "Senhor, o roteador de IA não respondeu. Verifique LLM_ROUTER_API_KEY, LLM_ROUTER_BASE_URL e LLM_ROUTER_MODEL."

    except LLMProviderError as erro:
        return f"Senhor, o roteador de IA falhou: {erro}"
    except Exception as erro:
        return f"Perdoe-me, senhor, ocorreu uma oscilação inesperada nos meus sistemas internos: {erro}"
    finally:
        await provider.close()
