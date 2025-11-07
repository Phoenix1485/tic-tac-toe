
document.addEventListener("DOMContentLoaded", () => {
    const boardEl = document.getElementById("board");
    const statusEl = document.getElementById("status");
    const resetBtn = document.getElementById("resetBtn");
    const playerNameInput = document.getElementById("playerName");
    const startBtn = document.getElementById("startBtn");
    const joinBtn = document.getElementById("joinBtn");
    const joinCodeInput = document.getElementById("joinCodeInput");
    const sessionCodeDisplay = document.getElementById("sessionCodeDisplay");

    const API_BASE = "http://127.0.0.1:8000/api";
    let ws = null;
    let sessionCode = null;

    const createBoard = () => {
        boardEl.innerHTML = "";
        Array.from({ length: 9 }).forEach((_, i) => {
            const cell = document.createElement("button");
            cell.type = "button";
            cell.className =
                "bg-gray-700 hover:bg-gray-600 text-2xl font-bold h-20 w-20 flex items-center justify-center rounded transition duration-150";
            cell.dataset.index = i;
            cell.addEventListener("click", () => handleMove(i));
            boardEl.appendChild(cell);
        });
    };

    const updateStatus = (state) => {
        if (state.winner) {
            statusEl.textContent = `🎉 Spieler ${state.winner} hat gewonnen!`;
        } else if (state.winner === "DRAW") {
            statusEl.textContent = "🤝 Unentschieden!";
        } else {
            statusEl.textContent = `Spieler am Zug: ${state.turn}`;
        }
    };

    const updateBoard = (state) => {
        [...boardEl.children].forEach((cell, i) => {
            const value = state.board[i];
            cell.textContent = value;
            const disabled = value !== "" || state.winner;
            cell.disabled = disabled;
            cell.classList.toggle("cursor-not-allowed", disabled);
        });
        updateStatus(state);
    };

    const connectWebSocket = (code) => {
        ws = new WebSocket(`ws://127.0.0.1:8000/ws/${code}`);
        ws.onmessage = (event) => {
            const msg = JSON.parse(event.data);
            if (msg.type === "state") {
                updateBoard(msg);
            } else if (msg.type === "you") {
                sessionCode = msg.code;
                sessionCodeDisplay.textContent = `Session-Code: ${sessionCode}`;
            }
        };
        ws.onclose = () => {
            statusEl.textContent = "❌ Verbindung getrennt.";
        };
    };

    const handleMove = (index) => {
        if (!ws || ws.readyState !== WebSocket.OPEN) {
            alert("WebSocket nicht verbunden.");
            return;
        }
        ws.send(JSON.stringify({ type: "move", i: index }));
    };

    const resetGame = () => {
        if (!ws || ws.readyState !== WebSocket.OPEN) {
            alert("WebSocket nicht verbunden.");
            return;
        }
        ws.send(JSON.stringify({ type: "reset" }));
    };

    const startGame = async () => {
        try {
            const res = await fetch(`${API_BASE}/session`, {
                method: "POST",
                credentials: "include"
            });
            const data = await res.json();
            if (data.code) {
                connectWebSocket(data.code);
            } else {
                alert("Fehler beim Erstellen der Session.");
            }
        } catch {
            alert("❌ Fehler beim Starten des Spiels.");
        }
    };

    const joinGame = () => {
        const code = joinCodeInput.value.trim().toUpperCase();
        if (!code) {
            alert("Bitte gib einen Session-Code ein.");
            return;
        }
        connectWebSocket(code);
    };

    resetBtn.addEventListener("click", resetGame);
    startBtn.addEventListener("click", startGame);
    joinBtn.addEventListener("click", joinGame);

    createBoard();
});
