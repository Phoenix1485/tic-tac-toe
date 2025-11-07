from __future__ import annotations
import asyncio
import random
import contextlib
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware

# -----------------------------------------------------------------------------
# Konfiguration
# -----------------------------------------------------------------------------
SESSION_CODE_LEN = 6
SESSION_TTL_SECONDS = 30 * 60        # 30 Minuten Inaktivität
CLEANUP_INTERVAL_SECONDS = 30        # alle 30s aufräumen
MAX_SESSIONS = 5000                  # harter Deckel gegen Abuse
ALLOW_CORS = True                   # True setzen, wenn Frontend auf anderem Origin läuft

# Zeichen ohne leicht verwechselbare Buchstaben/Ziffern
CODE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"  # kein I, O, 0, 1

# -----------------------------------------------------------------------------
# Model & Utilities
# -----------------------------------------------------------------------------
Board = List[str]  # 9 Felder, Werte: '', 'X', 'O'

WIN_LINES = [
    (0, 1, 2), (3, 4, 5), (6, 7, 8),
    (0, 3, 6), (1, 4, 7), (2, 5, 8),
    (0, 4, 8), (2, 4, 6)
]


def gen_code(n: int = SESSION_CODE_LEN) -> str:
    return ''.join(random.choices(CODE_ALPHABET, k=n))


def check_winner(b: Board) -> Optional[str]:
    for a, c, d in WIN_LINES:
        if b[a] and b[a] == b[c] == b[d]:
            return b[a]  # 'X' oder 'O'
    if all(b):
        return "DRAW"
    return None


@dataclass
class Session:
    code: str
    board: Board = field(default_factory=lambda: [""] * 9)
    turn: str = "X"
    winner: Optional[str] = None
    players: List[str] = field(default_factory=list)  # z.B. ['X'] oder ['X','O']
    sockets: Set[WebSocket] = field(default_factory=set)
    last_activity: float = field(default_factory=time.time)

    def assign_symbol(self) -> Optional[str]:
        """Weist dem beitretenden Spieler 'X' oder 'O' zu, oder None wenn voll."""
        if 'X' not in self.players:
            self.players.append('X')
            return 'X'
        if 'O' not in self.players:
            self.players.append('O')
            return 'O'
        return None

    def release_symbol(self, symbol: str) -> None:
        """Gibt ein Symbol beim Disconnect wieder frei."""
        try:
            self.players.remove(symbol)
        except ValueError:
            pass

    def reset(self) -> None:
        self.board = [""] * 9
        self.turn = "X"
        self.winner = None


# -----------------------------------------------------------------------------
# App Setup
# -----------------------------------------------------------------------------
app = FastAPI(title="TicTacToe Sessions Backend", version="1.0.0")
if ALLOW_CORS:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://127.0.0.1:5500", "https://fuzzy-xylophone-pxwqx59jp45f7gxp-5500.app.github.dev"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

sessions: Dict[str, Session] = {}
LOCK = asyncio.Lock()
_cleanup_task: Optional[asyncio.Task] = None


# -----------------------------------------------------------------------------
# Helper: Broadcast State
# -----------------------------------------------------------------------------
async def send_state(code: str) -> None:
    s = sessions.get(code)
    if not s:
        return
    payload = {
        "type": "state",
        "board": s.board,
        "turn": s.turn,
        "winner": s.winner,
        "players": len(s.players),
        "code": s.code,
    }
    # Senden ohne App-Crash bei toten Verbindungen
    dead: List[WebSocket] = []
    for ws in list(s.sockets):
        try:
            await ws.send_json(payload)
        except Exception:
            dead.append(ws)
    for ws in dead:
        s.sockets.discard(ws)


# -----------------------------------------------------------------------------
# REST Endpoints (ohne Frontend)
# -----------------------------------------------------------------------------
@app.get("/health")
async def health():
    async with LOCK:
        return {
            "ok": True,
            "sessions": len(sessions),
        }


@app.post("/api/session")
async def create_session():
    async with LOCK:
        if len(sessions) >= MAX_SESSIONS:
            return JSONResponse({"error": "capacity_reached"}, status_code=503)

        code = gen_code()
        # minimale Wahrscheinlichkeit von Kollisionen absichern
        while code in sessions:
            code = gen_code()

        sessions[code] = Session(code=code)
        return JSONResponse({"code": code})


@app.get("/api/session/{code}")
async def get_session(code: str):
    async with LOCK:
        s = sessions.get(code.upper())
        if not s:
            return JSONResponse({"error": "not_found"}, status_code=404)
        return {
            "code": s.code,
            "players": len(s.players),
            "turn": s.turn,
            "winner": s.winner,
            "board": s.board,
            "last_activity": s.last_activity,
        }


# -----------------------------------------------------------------------------
# WebSocket: Join & Game
# - Client verbindet auf: ws://<host>/ws/{code}
# - Direkte Messages:
#     { "type": "move", "i": 0..8 }
#     { "type": "reset" }
# - Server sendet:
#     { "type": "you", "symbol": "X"|"O", "code": "ABC123" }
#     { "type": "state", "board": [...], "turn": "X", "winner": null|"X"|"O"|"DRAW", "players": 1|2, "code": "..." }
# -----------------------------------------------------------------------------
@app.websocket("/ws/{code}")
async def ws_handler(ws: WebSocket, code: str):
    code = code.upper()
    await ws.accept()

    # Session lookup & Slotzuweisung
    async with LOCK:
        s = sessions.get(code)
        if not s:
            await ws.close(code=4404)  # Not Found (custom policy)
            return

        symbol = s.assign_symbol()
        if symbol is None:
            await ws.close(code=4403)  # Room Full (custom policy)
            return

        s.sockets.add(ws)
        s.last_activity = time.time()

    # Private Begrüßung an diesen Client
    await ws.send_json({"type": "you", "symbol": symbol, "code": code})
    await send_state(code)

    try:
        while True:
            msg = await ws.receive_json()
            mtype = msg.get("type")
            async with LOCK:
                s = sessions.get(code)
                if not s:
                    # Session wurde evtl. schon gelöscht
                    try:
                        await ws.close(code=4404)
                    finally:
                        break

                s.last_activity = time.time()

                if mtype == "move":
                    # Validierung
                    i = msg.get("i", None)
                    if not isinstance(i, int) or not (0 <= i <= 8):
                        # ignorieren statt Fehler zu werfen
                        continue
                    if s.winner:
                        continue
                    if s.board[i]:
                        continue
                    if s.turn != symbol:
                        continue

                    # Zug anwenden
                    s.board[i] = symbol
                    win = check_winner(s.board)
                    if win:
                        s.winner = win
                    else:
                        s.turn = "O" if s.turn == "X" else "X"

                    await send_state(code)

                elif mtype == "reset":
                    # Reset ist bewusst liberal (keine Zustimmung beider Spieler notwendig)
                    s.reset()
                    await send_state(code)

                # Optional: weitere Message-Typen hier verarbeiten

    except WebSocketDisconnect:
        pass
    finally:
        # Aufräumen bei Disconnect
        async with LOCK:
            s = sessions.get(code)
            if s:
                s.sockets.discard(ws)
                s.release_symbol(symbol)
                # Session löschen, wenn keine aktiven Sockets mehr vorhanden
                if not s.sockets:
                    sessions.pop(code, None)
                else:
                    # verbleibenden Client über neuen Status informieren
                    await send_state(code)


# -----------------------------------------------------------------------------
# Hintergrund: Cleanup abgelaufener Sessions
# -----------------------------------------------------------------------------
async def _cleanup_worker():
    try:
        while True:
            await asyncio.sleep(CLEANUP_INTERVAL_SECONDS)
            cutoff = time.time() - SESSION_TTL_SECONDS
            to_delete: List[str] = []
            async with LOCK:
                for code, s in list(sessions.items()):
                    if s.last_activity < cutoff or (not s.sockets and not s.players and (time.time() - s.last_activity) > 10):
                        to_delete.append(code)
                for code in to_delete:
                    sessions.pop(code, None)
    except asyncio.CancelledError:
        # Sauber beenden
        return


@app.on_event("startup")
async def on_startup():
    global _cleanup_task
    _cleanup_task = asyncio.create_task(_cleanup_worker())


@app.on_event("shutdown")
async def on_shutdown():
    global _cleanup_task
    if _cleanup_task:
        _cleanup_task.cancel()
        with contextlib.suppress(Exception):
            await _cleanup_task
    # Bestehende Sockets sauber schließen (best effort)
    async with LOCK:
        for s in sessions.values():
            for ws in list(s.sockets):
                with contextlib.suppress(Exception):
                    await ws.close(code=1001)
        sessions.clear()


# -----------------------------------------------------------------------------
# Main (optional lokal starten)
# -----------------------------------------------------------------------------
if __name__ == "__main__":
    import uvicorn, contextlib

    uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=True)
