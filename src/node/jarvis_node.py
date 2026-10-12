import os
import sys
import json
import time
import asyncio
import platform
import subprocess
import datetime
import psutil
import websockets
from websockets.exceptions import ConnectionClosed

# Configurações do Nó de Execução
NEXUS_URL = os.getenv("NEXUS_URL", "ws://192.168.1.92:8080")
NEXUS_API_KEY = os.getenv("NEXUS_API_KEY", "default_secure_key_change_me_in_prod")
NODE_ID = os.getenv("NODE_ID", f"{platform.node().lower()}_{platform.system().lower()}")

# Cores para o terminal do Nó (Ciano e Âmbar)
CYAN = '\033[0;36m'
GREEN = '\033[0;32m'
AMBER = '\033[0;33m'
RED = '\033[0;31m'
NC = '\033[0m' # No Color


def get_distro_name() -> str:
    """Identifica o nome da distribuição Linux ou sistema operacional."""
    if platform.system() == "Linux" and os.path.exists("/etc/os-release"):
        try:
            with open("/etc/os-release", "r") as f:
                for line in f:
                    if line.startswith("PRETTY_NAME="):
                        return line.strip().split("=")[1].strip('"')
        except Exception:
            pass
    return f"{platform.system()} {platform.release()}"


def get_realtime_metrics() -> dict:
    """Coleta métricas detalhadas de hardware e sistema operacional em tempo real."""
    try:
        cpu = psutil.cpu_percent(interval=None)
        ram = psutil.virtual_memory()
        disk = psutil.disk_usage('/')

        temps = "N/A"
        if hasattr(psutil, "sensors_temperatures"):
            try:
                t = psutil.sensors_temperatures()
                if t:
                    for s_name, entries in t.items():
                        if entries:
                            temps = f"{entries[0].current:.0f}°C"
                            break
            except Exception:
                pass

        # Cálculo de tempo de atividade (Uptime)
        uptime_seconds = time.time() - psutil.boot_time()
        hours = int(uptime_seconds // 3600)
        minutes = int((uptime_seconds % 3600) // 60)
        uptime_str = f"{hours:02d}:{minutes:02d}"

        return {
            "cpu": cpu,
            "ram": ram.percent,
            "ram_used_mb": ram.used // (1024 ** 2),
            "ram_total_mb": ram.total // (1024 ** 2),
            "disk": disk.percent,
            "temp": temps,
            "uptime": uptime_str,
            "procs": len(psutil.pids()),
            "os": "ARCH" if "arch" in get_distro_name().lower() or "cachy" in get_distro_name().lower() else platform.system()
        }
    except Exception as e:
        return {"error": str(e), "cpu": 0, "ram": 0, "disk": 0, "temp": "N/A", "uptime": "00:00", "procs": 0, "os": "LINUX"}


def get_system_status() -> str:
    """Gera resumo em texto para o modelo LLM do status do sistema."""
    m = get_realtime_metrics()
    return (
        f"OS: {get_distro_name()}\n"
        f"CPU: {m['cpu']}%\n"
        f"RAM: {m['ram']}% ({m['ram_used_mb']}MB / {m['ram_total_mb']}MB)\n"
        f"Disk: {m['disk']}%\n"
        f"Temp: {m['temp']}\n"
        f"Uptime: {m['uptime']}\n"
        f"Processos: {m['procs']}"
    )


import re

# Padrões estritamente proibidos de execução automática pelo nó
DANGEROUS_PATTERNS = [
    r"\brm\s+(-[a-zA-Z]*[rfRF][a-zA-Z]*\s+)+(\*|/\*?|~/\*?|\$HOME/?|\.\./?)($|\s)",
    r"\bmkfs(\.[a-zA-Z0-9]+)?\b",
    r"\bdd\s+if=",
    r":\(\)\s*\{\s*:\s*\|\s*:\s*&\s*\}\s*;\s*:",  # Fork bomb
    r"\bchmod\s+(-[a-zA-Z]*R[a-zA-Z]*\s+)?777\s+(/|/etc|/boot)",
    r"\b(shutdown|reboot|poweroff|init\s+0)\b",
    r"\b(curl|wget)\s+.*\|\s*(bash|sh)\b",
    r"\bcat\s+.*\.ssh/id_[a-zA-Z0-9_-]+\b",
]

def is_command_safe(cmd: str) -> tuple[bool, str]:
    """Valida se o comando não viola as diretrizes de segurança defensiva."""
    normalized = cmd.strip()
    for pattern in DANGEROUS_PATTERNS:
        if re.search(pattern, normalized, re.IGNORECASE):
            return False, f"Comando bloqueado por política de segurança estrita: padrão de risco detectado ({pattern})"
    return True, ""


def execute_command(cmd: str) -> str:
    """Executa comandos nativos no terminal Bash (Linux) ou PowerShell (Windows) com validação defensiva."""
    try:
        is_safe, reason = is_command_safe(cmd)
        if not is_safe:
            print(f"{RED}[ALERTA DE SEGURANÇA] {reason}{NC}")
            return f"Security Error: {reason}"

        print(f"{CYAN}[*] Executando comando localmente:{NC} {cmd}")
        use_shell = True
        executable = "/bin/bash" if platform.system() != "Windows" else None
        
        if platform.system() == "Windows":
            cmd = f"powershell -Command \"{cmd}\""
        elif os.path.exists("/.flatpak-info"):
            # Escapa aspas para o subshell do host
            escaped_cmd = cmd.replace('"', '\\"')
            cmd = f'flatpak-spawn --host bash -c "{escaped_cmd}"'

        result = subprocess.run(
            cmd,
            shell=use_shell,
            executable=executable,
            capture_output=True,
            text=True,
            timeout=50.0
        )

        output = ""
        if result.stdout:
            output += f"STDOUT:\n{result.stdout}\n"
        if result.stderr:
            output += f"STDERR:\n{result.stderr}\n"

        if not output:
            output = f"Command exited with code {result.returncode} but no output."

        status_color = GREEN if result.returncode == 0 else RED
        print(f"{status_color}[+] Saída do comando ({result.returncode}):{NC}\n{output[:200]}...")
        return output

    except subprocess.TimeoutExpired:
        print(f"{RED}[!] Timeout de execução para comando: {cmd}{NC}")
        return "Error: Command execution timed out after 50 seconds."
    except Exception as e:
        print(f"{RED}[!] Erro ao executar comando: {e}{NC}")
        return f"Error executing command: {e}"


async def handle_server_message(ws, message: str):
    """Processa mensagens e comandos enviados do Servidor (Hub) para o PC (Nó)."""
    try:
        payload = json.loads(message)
        action = payload.get("action")
        req_id = payload.get("req_id")

        result_data = "Unknown action."

        # 1. Servidor mandou executar um comando no PC
        if action == "execute_command":
            cmd = payload.get("cmd", "")
            result_data = execute_command(cmd)

        # 2. Servidor pediu status detalhado do PC
        elif action == "get_system_status":
            result_data = get_system_status()

        # 3. Servidor respondeu a um comando que o PC enviou
        elif action == "node_prompt_response":
            prompt = payload.get("prompt")
            resp = payload.get("response")
            print(f"\n{GREEN}[JARVIS RESPOSTA PARA '{prompt}']:{NC}\n{resp}\n")
            return

        # 4. Servidor enviou notificação para o PC
        elif action == "notify":
            title = payload.get("title", "JARVIS")
            msg = payload.get("message", "")
            print(f"\n{AMBER}[NOTIFICAÇÃO DO SERVIDOR - {title}]:{NC} {msg}\n")
            if platform.system() == "Linux":
                subprocess.Popen(["notify-send", title, msg], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return

        # Devolve resposta com o req_id correspondente
        if req_id:
            response = {
                "req_id": req_id,
                "result": result_data
            }
            await ws.send(json.dumps(response))

    except Exception as e:
        print(f"[!] Erro ao processar mensagem do servidor: {e}")


async def telemetry_loop(ws):
    """Envia periodicamente telemetria de hardware real do PC para o Servidor a cada 2.5s."""
    while True:
        try:
            metrics = get_realtime_metrics()
            payload = {
                "action": "telemetry",
                "node_id": NODE_ID,
                "metrics": metrics
            }
            await ws.send(json.dumps(payload))
            await asyncio.sleep(2.5)
        except asyncio.CancelledError:
            break
        except Exception as e:
            print(f"[!] Erro no loop de telemetria: {e}")
            break


async def terminal_interactive_input(ws):
    """Permite ao usuário digitar comandos diretamente no terminal do PC e enviar ao Servidor."""
    # Se não estiver rodando em terminal interativo (ex: em background no start_jarvis.sh), não tenta ler stdin
    if not sys.stdin.isatty():
        return

    loop = asyncio.get_running_loop()
    print(f"\n{CYAN}>>> TERMINAL INTERATIVO DO NÓ ATIVO <<<{NC}")
    print(f"Digite qualquer comando para o Jarvis processar via Servidor ou 'status' para ver telemetria.\n")
    print(f"\n{CYAN}>>> TERMINAL INTERATIVO DESATIVADO NO MODO TRAY <<<{NC}")
    return

async def run_node():
    """Ciclo de vida principal do nó com reconexão automática e tarefas assíncronas."""
    uri = f"{NEXUS_URL}/ws/node/{NODE_ID}"
    headers = {"nexus-api-key": NEXUS_API_KEY}

    print(f"{CYAN}=== INICIANDO NÓ DE COMUNICAÇÃO BIDIRECIONAL (BACKGROUND/TRAY): {NODE_ID} ==={NC}")
    print(f"[*] Conectando ao Servidor em {uri}...")

    # Inicializa psutil para o primeiro cálculo de CPU não retornar 0
    psutil.cpu_percent(interval=None)

    while True:
        try:
            async with websockets.connect(uri, additional_headers=headers) as ws:
                print(f"{GREEN}[+] Conectado com sucesso ao Jarvis Hub! Comunicação bidirecional ativa.{NC}")

                # Inicia tarefas concorrentes: telemetria contínua, leitura do terminal e escuta de ordens
                telemetry_task = asyncio.create_task(telemetry_loop(ws))
                cli_task = asyncio.create_task(terminal_interactive_input(ws))

                try:
                    async for message in ws:
                        await handle_server_message(ws, message)
                finally:
                    telemetry_task.cancel()
                    cli_task.cancel()

        except ConnectionClosed:
            print(f"{AMBER}[-] Conexão com o servidor encerrada. Reconectando em 3 segundos...{NC}")
        except Exception as e:
            print(f"{RED}[!] Falha na conexão com o servidor: {e}. Nova tentativa em 3 segundos...{NC}")

        await asyncio.sleep(3)


if __name__ == "__main__":
    try:
        asyncio.run(run_node())
    except KeyboardInterrupt:
        print(f"\n{AMBER}[*] Desligando nó local com segurança.{NC}")
