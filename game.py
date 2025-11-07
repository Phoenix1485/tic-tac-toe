class TicTacToe:
    def __init__(self):
        self.board = [""] * 9
        self.current_player = "X"
        self.winner = None
        self.game_over = False

    def make_move(self, index: int) -> dict:
        if self.game_over:
            return {"error": "Game is already over."}
        if not (0 <= index < 9):
            return {"error": "Invalid move index."}
        if self.board[index] != "":
            return {"error": "Cell already taken."}

        self.board[index] = self.current_player

        if self.check_winner():
            self.winner = self.current_player
            self.game_over = True
        elif "" not in self.board:
            self.game_over = True
        else:
            self.current_player = "O" if self.current_player == "X" else "X"

        return self.get_state()

    def check_winner(self) -> bool:
        combos = [
            [0, 1, 2], [3, 4, 5], [6, 7, 8],
            [0, 3, 6], [1, 4, 7], [2, 5, 8],
            [0, 4, 8], [2, 4, 6]
        ]
        for a, b, c in combos:
            if self.board[a] == self.board[b] == self.board[c] != "":
                return True
        return False

    def get_state(self) -> dict:
        return {
            "board": self.board,
            "current_player": self.current_player,
            "winner": self.winner,
            "game_over": self.game_over
        }

    def load_state(self, state: dict):
        try:
            self.board = state.get("board", [""] * 9)
            self.current_player = state.get("current_player", "X")
            self.winner = state.get("winner", None)
            self.game_over = state.get("game_over", False)
        except Exception as e:
            print("Fehler beim Laden des Zustands:", e)