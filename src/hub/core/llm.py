import asyncio
import uuid
from datetime import datetime
from typing import List, Dict, Any
from google import genai
from google.genai import types
from google.genai import errors
import tenacity

from src.hub.core.config import settings
from src.hub.core.websocket import manager
from src.hub.core.obsidian import obsidian_brain
from src.hub.core.memory import memory

# Inicialização do cliente oficial Google GenAI
client = genai.Client(api_key=settings.gemini_api_key)

# Dicionário de futures para requisições assíncronas aos nós de execução
pending_requests: Dict[str, asyncio.Future] = {}


def is_retryable_error(exc: Exception) -> bool:
    """Verifica se o erro é passível de retry imediato (excluindo limites estritos de quota diária)."""
    err_str = str(exc)
    if "RESOURCE_EXHAUSTED" in err_str or "429" in err_str or "404" in err_str:
        return False
    return True


@tenacity.retry(
    stop=tenacity.stop_after_attempt(3),
    wait=tenacity.wait_exponential(multiplier=1, min=1, max=5),
    retry=tenacity.retry_if_exception(is_retryable_error),
    reraise=True
)
async def safe_generate_content(model: str, contents: list, config: types.GenerateContentConfig):
    """Executa a requisição ao modelo em thread separada para não bloquear o Event Loop do FastAPI."""
    return await asyncio.to_thread(
        client.models.generate_content,
        model=model,
        contents=contents,
        config=config
    )


async def execute_command(target: str, cmd: str) -> str:
    """Envia um comando Bash/Shell para o nó de execução ou para o próprio servidor."""
    selected_target = target.lower()

    if selected_target == "server" or selected_target == "servidor":
        await manager.stream_log_to_mobile(f"Executando no terminal (Servidor/Hub): '{cmd}'...", level="warn")
        try:
            import subprocess
            result = await asyncio.to_thread(
                subprocess.run, cmd, shell=True, capture_output=True, text=True, timeout=50.0
            )
            output = ""
            if result.stdout: output += f"STDOUT:\n{result.stdout}\n"
            if result.stderr: output += f"STDERR:\n{result.stderr}\n"
            if not output: output = f"Command exited with code {result.returncode} but no output."
            await manager.stream_log_to_mobile(f"Comando concluído no Servidor.", level="success")
            return output
        except Exception as e:
            return f"Erro local no servidor: {e}"

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
        result = await asyncio.wait_for(future, timeout=50.0)
        await manager.stream_log_to_mobile(f"Comando concluído em {selected_target}.", level="success")
        return result
    except asyncio.TimeoutError:
        pending_requests.pop(req_id, None)
        await manager.stream_log_to_mobile(f"Timeout aguardando execução de '{cmd}'.", level="error")
        return f"Error: O comando '{cmd}' excedeu o tempo limite de execução (50s)."


async def get_system_status(target: str) -> str:
    """Solicita métricas de hardware (CPU, RAM, Disco, Temperatura) ao nó."""
    selected_target = target
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
        result = await asyncio.wait_for(future, timeout=12.0)
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

# Schemas de declaração para o SDK do Gemini (usadas para extração de schema de tools)
def execute_command_schema(target: str, cmd: str) -> str:
    """Executa comandos nativos no terminal. O target pode ser 'server' (para o servidor/hub) ou um node_id do PC (ex: 'cachyos_linux')."""
    pass
execute_command_schema.__name__ = "execute_command"

def get_system_status_schema(target: str) -> str:
    """Obtém o status atual do computador (uso de CPU, porcentagem de memória RAM, espaço em disco e temperaturas)."""
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
    config = types.GenerateContentConfig(temperature=0.1)
    for model in ['gemini-flash-latest', 'gemini-3.5-flash', 'gemini-flash-lite-latest']:
        try:
            resp = await safe_generate_content(model, [types.Content(role="user", parts=[types.Part.from_text(text=prompt)])], config)
            if resp.text:
                return resp.text
        except Exception as e:
            print(f"[MEMORY] Resumo falhou com {model}: {e}")
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
    """Gerencia a conversa com o Gemini com suporte a visão multimodal (análise de imagens/documentos) e ferramentas."""
    import base64

    # Configuração de modelos Gemini oficiais e disponíveis com cota ativa
    active_model = 'gemini-flash-latest'
    fallback_models = ['gemini-3.5-flash', 'gemini-flash-lite-latest', 'gemini-3.5-flash-lite']

    await manager.stream_log_to_mobile(f"Processando solicitação com {active_model}...", level="info")

    system_prompt = build_system_prompt(origin)

    # Monta histórico de mensagens
    contents = []
    for msg in history:
        role = msg.get('role', 'user')
        if role not in ['user', 'model']:
            role = 'user'
        contents.append(types.Content(role=role, parts=[types.Part.from_text(text=msg.get('content', ''))]))

    # Constrói os componentes da mensagem atual (texto + imagens/anexos)
    user_parts = []
    if attachments:
        for att in attachments:
            try:
                b64_str = att.get("data", "")
                if "," in b64_str:
                    b64_str = b64_str.split(",", 1)[1]
                raw_bytes = base64.b64decode(b64_str)
                mime_type = att.get("mime_type", "image/png")
                user_parts.append(types.Part.from_bytes(data=raw_bytes, mime_type=mime_type))
                await manager.stream_log_to_mobile(f"Imagem/Anexo carregado para visão: {att.get('name', 'imagem')}", level="info")
            except Exception as att_err:
                print(f"[!] Erro ao processar anexo {att.get('name')}: {att_err}")

    text_content = prompt or "Analise a imagem/conteúdo fornecido e descreva ou leia os detalhes."
    user_parts.append(types.Part.from_text(text=text_content))

    contents.append(types.Content(role="user", parts=user_parts))

    # Configuração com Automatic Function Calling DESABILITADO
    config = types.GenerateContentConfig(
        system_instruction=system_prompt,
        tools=jarvis_tools,
        automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
        temperature=0.2
    )

    async def execute_model_request(target_model: str, req_contents: list) -> tuple[types.GenerateContentResponse, str]:
        """Executa a requisição com tolerância a falhas e salva o modelo reserva que obteve sucesso."""
        try:
            resp = await safe_generate_content(target_model, req_contents, config)
            return resp, target_model
        except Exception as primary_err:
            err_msg = str(primary_err)
            if any(k in err_msg for k in ["RESOURCE_EXHAUSTED", "429", "503", "404", "NOT_FOUND", "invalid"]):
                for fb in fallback_models:
                    if fb == target_model:
                        continue
                    try:
                        await manager.stream_log_to_mobile(f"Alternando para modelo reserva {fb}...", level="warn")
                        resp = await safe_generate_content(fb, req_contents, config)
                        return resp, fb
                    except Exception:
                        continue
                if "RESOURCE_EXHAUSTED" in err_msg or "429" in err_msg:
                    raise Exception("Senhor, meus subsistemas de processamento estão em sua capacidade máxima no momento e preciso de alguns minutos para resfriá-los. Poderia me dar um instante, por favor?")
            raise primary_err

    max_turns = 6
    current_turn = 0
    current_model = active_model

    try:
        while current_turn < max_turns:
            current_turn += 1

            response, used_model = await execute_model_request(current_model, contents)
            current_model = used_model

            # Se não houver chamadas de ferramentas, retornamos o texto final gerado
            if not response.function_calls:
                final_text = response.text or "Comando processado com sucesso pelos meus sistemas, senhor."
                return final_text

            # Adiciona a resposta do modelo (com as intenções de tool call) ao histórico de contexto
            if response.candidates and response.candidates[0].content:
                contents.append(response.candidates[0].content)

            # Executa cada uma das ferramentas requisitadas pelo modelo
            tool_response_parts = []
            for function_call in response.function_calls:
                tool_name = function_call.name
                tool_args = function_call.args or {}

                await manager.stream_log_to_mobile(f"Invocando ferramenta: {tool_name}...", level="warn")

                if tool_name in AVAILABLE_TOOLS:
                    handler = AVAILABLE_TOOLS[tool_name]
                    try:
                        if asyncio.iscoroutinefunction(handler):
                            tool_output = await handler(**tool_args)
                        else:
                            tool_output = handler(**tool_args)
                    except Exception as exec_err:
                        tool_output = f"Erro na execução da ferramenta {tool_name}: {str(exec_err)}"
                else:
                    tool_output = f"Erro: Ferramenta '{tool_name}' não disponível no Jarvis."

                tool_response_parts.append(
                    types.Part.from_function_response(
                        name=tool_name,
                        response={"result": str(tool_output)}
                    )
                )

            # Retorna o resultado de todas as ferramentas para o modelo prosseguir o raciocínio
            contents.append(types.Content(role="user", parts=tool_response_parts))

        # Se atingiu o limite de turnos, gera uma resposta final
        fallback_final, _ = await execute_model_request(current_model, contents)
        return fallback_final.text or "Processamento concluído após múltiplas etapas de sistema, senhor."

    except Exception as e:
        error_str = str(e)
        if "429" in error_str or "RESOURCE_EXHAUSTED" in error_str:
            import re
            retry_match = re.search(r"retryDelay':\s*'(\d+)s'", error_str) or re.search(r"retry in (\d+)", error_str) or re.search(r"(\d+)s", error_str)
            seconds = int(retry_match.group(1)) if retry_match else 30
            if seconds > 300:
                seconds = 45
            return f"Meus núcleos de processamento neural atingiram a capacidade máxima temporária, senhor. Peço que aguarde aproximadamente {seconds} segundos enquanto resfrio meus capacitores e recalibro os circuitos antes de processarmos seu próximo comando."
        return f"Perdoe-me, senhor, ocorreu uma oscilação inesperada nos meus sistemas internos: {error_str}"
