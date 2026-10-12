"""Connect four: board logic and the Witch's AI (alpha-beta search)."""
from __future__ import annotations

import random

ROWS, COLS = 6, 7
ORDER = [3, 2, 4, 1, 5, 0, 6]  # centre first: better pruning, stronger play


def new_board() -> list[list[int]]:
    return [[0] * COLS for _ in range(ROWS)]  # row 0 is the top


def valid(board) -> list[int]:
    return [c for c in ORDER if board[0][c] == 0]


def drop(board, col: int, piece: int) -> int:
    """Drop a piece; returns the row it lands on."""
    for r in range(ROWS - 1, -1, -1):
        if board[r][col] == 0:
            board[r][col] = piece
            return r
    raise ValueError("column full")


def winner_cells(board, piece: int) -> list[tuple[int, int]] | None:
    for r in range(ROWS):
        for c in range(COLS):
            for dr, dc in ((0, 1), (1, 0), (1, 1), (1, -1)):
                cells = [(r + k * dr, c + k * dc) for k in range(4)]
                if all(0 <= rr < ROWS and 0 <= cc < COLS and board[rr][cc] == piece for rr, cc in cells):
                    return cells
    return None


def full(board) -> bool:
    return all(board[0][c] for c in range(COLS))


def _window_score(window, piece):
    other = 3 - piece
    mine, theirs, empty = window.count(piece), window.count(other), window.count(0)
    if mine == 4:
        return 1000
    if mine == 3 and empty == 1:
        return 6
    if mine == 2 and empty == 2:
        return 2
    if theirs == 3 and empty == 1:
        return -8
    return 0


def evaluate(board, piece: int) -> int:
    score = 3 * sum(1 for r in range(ROWS) if board[r][COLS // 2] == piece)
    for r in range(ROWS):
        for c in range(COLS):
            for dr, dc in ((0, 1), (1, 0), (1, 1), (1, -1)):
                end_r, end_c = r + 3 * dr, c + 3 * dc
                if 0 <= end_r < ROWS and 0 <= end_c < COLS:
                    score += _window_score([board[r + k * dr][c + k * dc] for k in range(4)], piece)
    return score


def _search(board, depth, alpha, beta, maximizing, piece):
    other = 3 - piece
    if winner_cells(board, piece):
        return 100000 + depth, None
    if winner_cells(board, other):
        return -100000 - depth, None
    moves = valid(board)
    if depth == 0 or not moves:
        return evaluate(board, piece), None
    best_col = moves[0]
    if maximizing:
        value = -10**9
        for col in moves:
            row = drop(board, col, piece)
            score, _ = _search(board, depth - 1, alpha, beta, False, piece)
            board[row][col] = 0
            if score > value:
                value, best_col = score, col
            alpha = max(alpha, value)
            if alpha >= beta:
                break
    else:
        value = 10**9
        for col in moves:
            row = drop(board, col, other)
            score, _ = _search(board, depth - 1, alpha, beta, True, piece)
            board[row][col] = 0
            if score < value:
                value, best_col = score, col
            beta = min(beta, value)
            if alpha >= beta:
                break
    return value, best_col


def ai_move(board, piece: int = 2, depth: int = 4, blunder: float = 0.12, rnd=random) -> int:
    """The Witch's move: strong, but she sometimes gets distracted (``blunder``)."""
    moves = valid(board)
    for col in moves:  # always take a win, always block an immediate loss
        for who in (piece, 3 - piece):
            row = drop(board, col, who)
            won = winner_cells(board, who)
            board[row][col] = 0
            if won:
                return col
    if rnd.random() < blunder:
        return rnd.choice(moves)
    _, col = _search([row[:] for row in board], depth, -10**9, 10**9, True, piece)
    return col if col is not None else moves[0]
