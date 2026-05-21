import asyncio
import threading
from collections import deque
from contextlib import asynccontextmanager
from functools import lru_cache
from typing import Any

from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.core.config import get_settings
from app.repositories.risk_events import RiskEventRepository
from app.schemas.monitor import ManualAnalyzeRequest, ManualReviewRequest
from app.services.learning_engine import score_text, setup_security_models
from app.services.radar import whatsapp_monitor_worker


class ConnectionManager:
    def __init__(self) -> None:
        self.active_connections: list[WebSocket] = []
        self._lock = asyncio.Lock()

    async def connect(self, websocket: WebSocket) -> None:
        await websocket.accept()
        async with self._lock:
            self.active_connections.append(websocket)

    async def disconnect(self, websocket: WebSocket) -> None:
        async with self._lock:
            if websocket in self.active_connections:
                self.active_connections.remove(websocket)

    async def broadcast(self, payload: dict[str, Any]) -> None:
        async with self._lock:
            # Iterate over a copy to safely remove from the original list
            for connection in self.active_connections[:]:
                try:
                    await connection.send_json(payload)
                except Exception:
                    try:
                        self.active_connections.remove(connection)
                    except ValueError:
                        pass


class MonitorState:
    def __init__(self) -> None:
        self.messages = deque(maxlen=50)
        self.is_running = False
        self.thread: threading.Thread | None = None
        self._state_lock = threading.Lock()

    def append_message(self, message: dict[str, Any]) -> None:
        with self._state_lock:
            self.messages.append(message)

    def snapshot(self) -> dict[str, Any]:
        with self._state_lock:
            return {
                "is_running": self.is_running,
                "messages": list(self.messages),
            }

    def set_running(self, running: bool) -> None:
        with self._state_lock:
            self.is_running = running


@lru_cache(maxsize=1)
def get_risk_event_repository() -> RiskEventRepository:
    settings = get_settings()
    settings.runtime_dir.mkdir(parents=True, exist_ok=True)
    return RiskEventRepository(settings.risk_events_db_path)


def create_app() -> FastAPI:
    settings = get_settings()
    templates = Jinja2Templates(directory=str(settings.template_dir))
    manager = ConnectionManager()
    monitor_state = MonitorState()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        app.state.loop = asyncio.get_running_loop()
        yield
        # Ensure monitoring stops on app shutdown
        monitor_state.set_running(False)
        if monitor_state.thread and monitor_state.thread.is_alive():
            # Give the thread a moment to clean up
            monitor_state.thread.join(timeout=2.0)

    app = FastAPI(title="UTeM SOC Dashboard", lifespan=lifespan)
    app.mount("/static", StaticFiles(directory=str(settings.static_dir)), name="static")

    def publish_message(message: dict[str, Any]) -> None:
        monitor_state.append_message(message)
        loop = getattr(app.state, "loop", None)
        if loop is not None:
            asyncio.run_coroutine_threadsafe(
                manager.broadcast({"event": "message", "data": message}),
                loop,
            )

    def publish_status(is_running: bool) -> None:
        monitor_state.set_running(is_running)
        loop = getattr(app.state, "loop", None)
        if loop is not None:
            asyncio.run_coroutine_threadsafe(
                manager.broadcast({"event": "status", "data": {"is_running": is_running}}),
                loop,
            )

    @app.get("/", response_class=HTMLResponse)
    async def index(request: Request) -> HTMLResponse:
        return templates.TemplateResponse(
            request,
            "index.html",
            {
                "title": "UTeM SOC Dashboard",
                "researcher": "WONG HAN SHEN (BAXZ)",
                "supervisor": "Dr. Megat",
            },
        )

    @app.get("/favicon.ico")
    async def favicon() -> Response:
        return Response(status_code=204)

    @app.get("/api/health")
    async def health() -> dict[str, bool]:
        return {"ok": True}

    @app.get("/api/status")
    async def get_status() -> JSONResponse:
        return JSONResponse(monitor_state.snapshot())

    @app.post("/api/messages/analyze")
    async def analyze_message(payload: ManualAnalyzeRequest) -> JSONResponse:
        model_bundle = setup_security_models()
        risk_score = float(score_text(payload.text, model_bundle)["risk_score"])
        analysis_message = {
            "text": payload.text,
            "type": "manual-analysis",
            "risk": risk_score,
        }
        publish_message(analysis_message)
        return JSONResponse({"ok": True, "message": analysis_message})

    @app.post("/api/messages/review")
    async def review_message(payload: ManualReviewRequest) -> JSONResponse:
        repository = get_risk_event_repository()
        event_id = repository.create_event(
            message_text=payload.message_text,
            source_group="Manual Review",
            sender_name="Dashboard Analyst",
            risk_score=payload.risk_score,
            model_version="manual-review-v1",
        )
        repository.record_decision(
            event_id,
            decision=payload.decision,
            reviewer=payload.reviewer,
        )

        review_event = {
            "event_id": event_id,
            "text": payload.message_text,
            "type": "review-decision",
            "risk": payload.risk_score,
            "decision": payload.decision,
            "reviewer": payload.reviewer,
        }
        publish_message(review_event)
        return JSONResponse({"ok": True, "event": review_event})

    @app.post("/api/monitor/start")
    async def start_monitor() -> JSONResponse:
        if monitor_state.is_running:
            return JSONResponse(
                {"ok": False, "message": "Monitoring is already active."},
                status_code=409,
            )

        monitor_state.set_running(True)
        publish_message(
            {
                "text": "System: Preparing monitoring session.",
                "risk": 0.0,
                "type": "system",
            }
        )
        publish_status(True)

        thread = threading.Thread(
            target=whatsapp_monitor_worker,
            kwargs={
                "should_continue": lambda: monitor_state.is_running,
                "on_message": publish_message,
                "on_status_change": publish_status,
            },
            daemon=True,
        )
        monitor_state.thread = thread
        thread.start()

        return JSONResponse({"ok": True, "message": "Monitoring started."})

    @app.post("/api/monitor/stop")
    async def stop_monitor() -> JSONResponse:
        if not monitor_state.is_running:
            return JSONResponse(
                {"ok": False, "message": "Monitoring is not active."},
                status_code=409,
            )

        publish_message(
            {
                "text": "System: Stop requested. Waiting for the monitor loop to exit.",
                "risk": 0.0,
                "type": "system",
            }
        )
        publish_status(False)
        return JSONResponse({"ok": True, "message": "Monitoring stop requested."})

    @app.websocket("/ws/feed")
    async def websocket_feed(websocket: WebSocket) -> None:
        await manager.connect(websocket)
        snapshot = monitor_state.snapshot()
        await websocket.send_json({"event": "snapshot", "data": snapshot})

        try:
            while True:
                await websocket.receive_text()
        except WebSocketDisconnect:
            await manager.disconnect(websocket)

    return app
