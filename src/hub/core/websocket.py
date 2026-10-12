import asyncio
from typing import Dict, Any
from fastapi import WebSocket

class ConnectionManager:
    """Gerenciador central de conexões WebSocket para nós de execução (PCs) e interfaces (HUDs)."""
    def __init__(self):
        self.active_nodes: Dict[str, WebSocket] = {}
        self.active_mobiles: Dict[str, WebSocket] = {}
        # Cache das últimas métricas de hardware recebidas dos computadores conectados
        self.latest_node_metrics: Dict[str, Any] = {}

    async def connect_node(self, node_id: str, websocket: WebSocket):
        """Aceita conexão de um novo computador/nó no cluster."""
        await websocket.accept()
        self.active_nodes[node_id] = websocket
        await self.broadcast_telemetry()
        await self.stream_log_to_mobile(f"Nó de execução '{node_id}' conectado e operacional.", level="success")

    async def connect_mobile(self, mobile_id: str, websocket: WebSocket):
        """Aceita conexão da interface HUD/Mobile."""
        await websocket.accept()
        self.active_mobiles[mobile_id] = websocket
        await self.broadcast_telemetry()
        
        # Envia as últimas métricas disponíveis se houver
        if self.latest_node_metrics:
            try:
                await websocket.send_json({
                    "type": "hardware_telemetry",
                    "metrics": self.latest_node_metrics
                })
            except Exception:
                pass

    def disconnect_node(self, node_id: str):
        """Remove o nó desconectado e atualiza a telemetria."""
        if node_id in self.active_nodes:
            del self.active_nodes[node_id]
        asyncio.create_task(self.broadcast_telemetry())
        asyncio.create_task(self.stream_log_to_mobile(f"Nó de execução '{node_id}' desconectado.", level="error"))

    def disconnect_mobile(self, mobile_id: str):
        """Remove a interface HUD desconectada."""
        if mobile_id in self.active_mobiles:
            del self.active_mobiles[mobile_id]

    async def send_to_node(self, node_id: str, message: dict) -> bool:
        """Envia mensagem/comando específico do Servidor para um Nó específico."""
        if node_id in self.active_nodes:
            try:
                await self.active_nodes[node_id].send_json(message)
                return True
            except Exception as e:
                print(f"[!] Erro ao enviar comando para o nó {node_id}: {e}")
                return False
        return False

    async def broadcast_to_nodes(self, message: dict):
        """Envia mensagem/comando do Servidor para todos os Nós conectados."""
        for node_id, ws in list(self.active_nodes.items()):
            try:
                await ws.send_json(message)
            except Exception:
                pass

    async def stream_log_to_mobile(self, message: str, level: str = "info"):
        """Transmite mensagens de log em tempo real para os HUDs conectados."""
        log_data = {"type": "log_stream", "level": level, "content": message}
        for ws in list(self.active_mobiles.values()):
            try:
                await ws.send_json(log_data)
            except Exception:
                pass

    async def broadcast_hardware_metrics(self, node_id: str, metrics: dict):
        """Transmite métricas de hardware reais enviadas pelo PC para os HUDs."""
        self.latest_node_metrics = metrics
        payload = {
            "type": "hardware_telemetry",
            "node_id": node_id,
            "metrics": metrics
        }
        for ws in list(self.active_mobiles.values()):
            try:
                await ws.send_json(payload)
            except Exception:
                pass

    async def broadcast_telemetry(self):
        """Transmite o status de presença (ONLINE/OFFLINE) de todos os nós conectados."""
        nodes_status = {node_id: "ONLINE" for node_id in self.active_nodes.keys()}
        telemetry_data = {"type": "telemetry", "nodes": nodes_status}
        for ws in list(self.active_mobiles.values()):
            try:
                await ws.send_json(telemetry_data)
            except Exception:
                pass

manager = ConnectionManager()
