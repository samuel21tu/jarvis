import os
import json
import asyncio
import platform
import subprocess
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from src.hub.core.config import settings
from src.hub.core.websocket import manager
from src.hub.core.memory import memory
from src.hub.core.llm import chat_with_nexus, pending_requests, set_remote_server_dispatchers
from src.hub.core.tts import generate_tts_audio_base64
from src.node.jarvis_node import is_command_safe, EXECUTION_TIMEOUT

app = FastAPI(title="Jarvis Nexus Hub")

import hmac

ALLOWED_ORIGINS = [
    "https://jarvis.samuel21tu.space",
    "http://localhost:8000",
    "http://localhost:8080",
    "http://127.0.0.1:8000",
    "http://127.0.0.1:8080",
    "http://localhost:8081",
    "http://127.0.0.1:8081",
]
extra_origins = os.getenv("ALLOWED_ORIGINS", "")
if extra_origins:
    ALLOWED_ORIGINS.extend([o.strip() for o in extra_origins.split(",") if o.strip()])

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def _wire_peer_dispatchers():
    """No PC (node_role=local), liga as ferramentas ao par remoto quando ele estiver online."""
    if settings.node_role.strip().lower() == "local":
        from src.node.jarvis_node import peer_execute_command, peer_get_system_status
        set_remote_server_dispatchers(peer_execute_command, peer_get_system_status)
        print("[PC] Modo local ativo: OmniRoute próprio, par remoto opcional via WebSocket.")


@app.middleware("http")
async def security_and_cache_middleware(request: Request, call_next):
    """Aplica cabeçalhos defensivos de segurança e desativa cache em assets estáticos."""
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "SAMEORIGIN"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"

    path = request.url.path.lower()
    if path == "/" or path.endswith((".html", ".js", ".css")):
        response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate, max-age=0"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
    return response


# Memória única e persistente (SQLite) definida em src.hub.core.memory


@app.websocket("/ws/node/{node_id}")
async def websocket_node_endpoint(websocket: WebSocket, node_id: str):
    """Endpoint de comunicação bidirecional autenticado com os nós de execução."""
    # Validação de credenciais com tempo constante (anti-timing attack)
    if settings.nexus_api_key:
        client_key = websocket.headers.get("nexus-api-key") or websocket.query_params.get("key") or ""
        if not hmac.compare_digest(client_key, settings.nexus_api_key):
            print(f"[!] Tentativa de conexão não autorizada no nó {node_id}")
            await websocket.close(code=4001, reason="Credenciais inválidas")
            return

    await manager.connect_node(node_id, websocket)
    try:
        while True:
            data = await websocket.receive_text()
            payload = json.loads(data)

            # 1. Resposta a uma ordem anterior enviada pelo Servidor ao Nó
            if "req_id" in payload and payload["req_id"] in pending_requests:
                future = pending_requests[payload["req_id"]]
                if not future.done():
                    future.set_result(payload.get("result", "No result provided"))
                pending_requests.pop(payload["req_id"], None)

            # 2. Telemetria de hardware periódica enviada pelo PC para o Servidor
            elif payload.get("action") == "telemetry":
                metrics = payload.get("metrics", {})
                await manager.broadcast_hardware_metrics(node_id, metrics)

            # 2b. Comando/status enviado pelo PC para execução LOCAL no servidor
            elif payload.get("action") in ("execute_command", "get_system_status"):
                req_id = payload.get("req_id")
                action = payload.get("action")
                # Registra a requisição no store de correlação: entrada presente
                # durante a execução e removida no sucesso (resposta enviada).
                if req_id:
                    pending_requests.setdefault(req_id, asyncio.get_running_loop().create_future())
                try:
                    if action == "get_system_status":
                        import psutil
                        result_data = (
                            "Status do Servidor:\n"
                            f"CPU: {psutil.cpu_percent(interval=None)}%\n"
                            f"RAM: {psutil.virtual_memory().percent}%\n"
                            f"Disco: {psutil.disk_usage('/').percent}%\n"
                            f"OS: {platform.system()}"
                        )
                    else:
                        cmd = payload.get("cmd", "")
                        safe, reason = is_command_safe(cmd)
                        if not safe:
                            result_data = f"Security Error: {reason}"
                        else:
                            proc = await asyncio.to_thread(
                                subprocess.run, cmd, shell=True,
                                capture_output=True, text=True, timeout=EXECUTION_TIMEOUT
                            )
                            out = ""
                            if proc.stdout:
                                out += f"STDOUT:\n{proc.stdout}\n"
                            if proc.stderr:
                                out += f"STDERR:\n{proc.stderr}\n"
                            result_data = out or f"Comando encerrado com código {proc.returncode}."
                except Exception as exc:
                    result_data = f"Erro ao executar no servidor: {exc}"

                if req_id:
                    await websocket.send_json({"req_id": req_id, "result": result_data})
                    pending_requests.pop(req_id, None)

            # 3. Comando enviado do PC (terminal ou script local) para o Servidor processar
            elif payload.get("action") == "node_prompt":
                prompt = payload.get("prompt", "")
                session_id = payload.get("session_id", f"node_{node_id}")

                await manager.stream_log_to_mobile(f"Comando recebido do terminal local ({node_id}): {prompt}", level="info")

                history = memory.get_history(session_id)
                try:
                    response_text = await chat_with_nexus(prompt, history, origin=f"node:{node_id}")
                    memory.add_message(session_id, "user", prompt, origin=f"node:{node_id}")
                    memory.add_message(session_id, "model", response_text, origin=f"node:{node_id}")

                    # Envia a resposta de volta para o terminal do PC
                    await websocket.send_json({
                        "action": "node_prompt_response",
                        "prompt": prompt,
                        "response": response_text
                    })

                    # Notifica também o HUD web para sincronização visual e vocal
                    # Gera áudio de alta qualidade via backend (Edge-TTS fallback garantido) para funcionar no background Headless
                    audio_data = await generate_tts_audio_base64(response_text)
                    for mobile_ws in list(manager.active_mobiles.values()):
                        try:
                            await mobile_ws.send_json({
                                "type": "chat_response",
                                "content": response_text,
                                "audio_data": audio_data,
                                "source": f"node:{node_id}"
                            })
                        except Exception:
                            pass

                except Exception as e:
                    err_msg = f"Erro no processamento do comando: {str(e)}"
                    await websocket.send_json({
                        "action": "node_prompt_response",
                        "prompt": prompt,
                        "response": err_msg,
                        "error": True
                    })

            # 4. Alerta proativo de sistema gerado pelo PC (ex: recursos críticos)
            elif payload.get("action") == "system_alert":
                msg = payload.get("message", "Alerta do sistema")
                level = payload.get("level", "warn")
                await manager.stream_log_to_mobile(f"⚠️ [{node_id.upper()}] {msg}", level=level)

    except WebSocketDisconnect:
        manager.disconnect_node(node_id)
    except Exception as e:
        print(f"[!] Erro no WebSocket do Nó ({node_id}): {e}")
        manager.disconnect_node(node_id)


@app.websocket("/ws/mobile/{mobile_id}")
async def websocket_mobile_endpoint(websocket: WebSocket, mobile_id: str):
    """Endpoint de comunicação com a interface holográfica (HUD)."""
    await manager.connect_mobile(mobile_id, websocket)
    try:
        while True:
            data = await websocket.receive_text()
            payload = json.loads(data)

            if payload.get("action") == "get_history":
                # HUD acabou de abrir/reconectar: devolve a conversa recente para continuar de onde parou
                try:
                    limit = max(1, min(int(payload.get("limit", 20)), 100))
                    await websocket.send_json({"type": "history", "messages": memory.get_history(limit=limit)})
                except Exception as e:
                    print(f"[!] Falha ao enviar histórico: {e}")

            elif payload.get("action") == "chat":
                prompt = payload.get("prompt", "").strip()
                attachments = payload.get("attachments", [])
                session_id = payload.get("session_id", "default")

                if not prompt and not attachments:
                    continue # Guard-rail contra buffers de silêncio ou frames vazios repetidos do frontend

                log_desc = f"Recebido do HUD: {prompt}" if prompt else "Recebido anexo/imagem para visão."
                await manager.stream_log_to_mobile(log_desc, level="info")

                history = memory.get_history(session_id)

                try:
                    response_text = await chat_with_nexus(prompt, history, origin="server", attachments=attachments)

                    stored_prompt = prompt or "[Imagem/Arquivo analisado]"
                    if attachments:
                        att_names = ", ".join(a.get("name", "imagem") for a in attachments)
                        stored_prompt = f"[Imagem enviada: {att_names}] {stored_prompt}".strip()

                    memory.add_message(session_id, "user", stored_prompt, origin=f"hud:{mobile_id}")
                    memory.add_message(session_id, "model", response_text, origin=f"hud:{mobile_id}")

                    # Gera áudio de alta qualidade (ElevenLabs se API Key presente, fallback Edge-TTS)
                    audio_data = await generate_tts_audio_base64(response_text)

                    await websocket.send_json({
                        "type": "chat_response",
                        "content": response_text,
                        "audio_data": audio_data
                    })
                    await manager.stream_log_to_mobile("Resposta vocal e visual transmitida.", level="success")

                except Exception as e:
                    await manager.stream_log_to_mobile(f"Erro no Jarvis: {str(e)}", level="error")
                    await websocket.send_json({
                        "type": "chat_response",
                        "content": f"**Erro de Sistema:** {str(e)}"
                    })

    except WebSocketDisconnect:
        manager.disconnect_mobile(mobile_id)
    except Exception as e:
        print(f"[!] Erro no WebSocket do HUD ({mobile_id}): {e}")
        manager.disconnect_mobile(mobile_id)


# Servir frontend estático na raiz
mobile_dir = os.path.join(os.path.dirname(__file__), "..", "mobile")
if os.path.exists(mobile_dir):
    app.mount("/", StaticFiles(directory=mobile_dir, html=True), name="mobile")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("src.hub.jarvis_hub:app", host="0.0.0.0", port=settings.jarvis_port, reload=False)
