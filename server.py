import socket
import threading
import pickle
import pygame
import numpy as np
import sys
import time
import json
from datetime import datetime
from pygame.locals import *

ROW_COUNT = 6
COLUMN_COUNT = 7
SQUARE_SIZE = 100
RADIUS = int(SQUARE_SIZE/2 - 5)
WIDTH = COLUMN_COUNT * SQUARE_SIZE
HEIGHT = (ROW_COUNT + 1) * SQUARE_SIZE + 50
BLUE = (0, 0, 255)
BLACK = (0, 0, 0)
RED = (255, 0, 0)
YELLOW = (255, 255, 0)
WHITE = (255, 255, 255)
GREEN = (0, 255, 0)
GRAY = (128, 128, 128)

class GameAnalytics:
    def __init__(self):
        self.games_played = 0
        self.total_moves = 0
        self.game_durations = []
        self.wins_by_player = [0, 0]
        self.draws = 0
        self.move_patterns = {}
        self.session_start = time.time()
        
    def record_game_start(self):
        self.games_played += 1
        self.game_start_time = time.time()
        
    def record_move(self, player, column):
        self.total_moves += 1
        move_key = f"player_{player}_col_{column}"
        self.move_patterns[move_key] = self.move_patterns.get(move_key, 0) + 1
        
    def record_game_end(self, winner):
        game_duration = time.time() - self.game_start_time
        self.game_durations.append(game_duration)
        
        if winner is not None:
            self.wins_by_player[winner] += 1
        else:
            self.draws += 1
    
    def get_stats(self):
        avg_duration = sum(self.game_durations) / len(self.game_durations) if self.game_durations else 0
        avg_moves_per_game = self.total_moves / self.games_played if self.games_played > 0 else 0
        session_duration = time.time() - self.session_start
        
        return {
            'games_played': self.games_played,
            'total_moves': self.total_moves,
            'avg_game_duration': avg_duration,
            'avg_moves_per_game': avg_moves_per_game,
            'wins_player_1': self.wins_by_player[0],
            'wins_player_2': self.wins_by_player[1],
            'draws': self.draws,
            'session_duration': session_duration,
            'most_popular_moves': self.get_popular_moves()
        }
    
    def get_popular_moves(self):
        if not self.move_patterns:
            return {}
        sorted_moves = sorted(self.move_patterns.items(), key=lambda x: x[1], reverse=True)
        return dict(sorted_moves[:5])  

class AIHeuristics:
    
    @staticmethod
    def evaluate_position(board, piece):
        score = 0
        
        
        center_count = sum(1 for r in range(ROW_COUNT) if board[r][COLUMN_COUNT//2] == piece)
        score += center_count * 3
        
        
        score += AIHeuristics.evaluate_window_sequences(board, piece, horizontal=True)
        
        
        score += AIHeuristics.evaluate_window_sequences(board, piece, vertical=True)
        
        
        score += AIHeuristics.evaluate_window_sequences(board, piece, diagonal=True)
        
        return score
    
    @staticmethod
    def evaluate_window_sequences(board, piece, horizontal=False, vertical=False, diagonal=False):
        score = 0
        
        if horizontal:
            for r in range(ROW_COUNT):
                for c in range(COLUMN_COUNT - 3):
                    window = [board[r][c+i] for i in range(4)]
                    score += AIHeuristics.score_window(window, piece)
        
        if vertical:
            for c in range(COLUMN_COUNT):
                for r in range(ROW_COUNT - 3):
                    window = [board[r+i][c] for i in range(4)]
                    score += AIHeuristics.score_window(window, piece)
        
        if diagonal:
            
            for r in range(ROW_COUNT - 3):
                for c in range(COLUMN_COUNT - 3):
                    window = [board[r+i][c+i] for i in range(4)]
                    score += AIHeuristics.score_window(window, piece)
            
            
            for r in range(3, ROW_COUNT):
                for c in range(COLUMN_COUNT - 3):
                    window = [board[r-i][c+i] for i in range(4)]
                    score += AIHeuristics.score_window(window, piece)
        
        return score
    
    @staticmethod
    def score_window(window, piece):
        score = 0
        opponent_piece = 2 if piece == 1 else 1
        
        piece_count = window.count(piece)
        empty_count = window.count(0)
        opponent_count = window.count(opponent_piece)
        
        if piece_count == 4:
            score += 100
        elif piece_count == 3 and empty_count == 1:
            score += 10
        elif piece_count == 2 and empty_count == 2:
            score += 2
        
        if opponent_count == 3 and empty_count == 1:
            score -= 80  
        
        return score

class ConnectFourServer:
    def __init__(self, host='localhost', port=5555):
        self.server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server.bind((host, port))
        self.server.listen(2)
        print(f"Enhanced Server started, listening on {host}:{port}")
        
        self.clients = []
        self.board = np.zeros((ROW_COUNT, COLUMN_COUNT))
        self.turn = 0
        self.game_over = False
        self.game_id = 0
        self.waiting_restart = [False, False]
        self.analytics = GameAnalytics()
        self.move_history = []
        self.game_start_time = None
        
        threading.Thread(target=self.accept_connections).start()
        threading.Thread(target=self.analytics_loop).start()
        
    def analytics_loop(self):
        while True:
            time.sleep(30)  
            if self.analytics.games_played > 0:
                stats = self.analytics.get_stats()
                print("\n=== SERVER ANALYTICS ===")
                print(f"Games played: {stats['games_played']}")
                print(f"Total moves: {stats['total_moves']}")
                print(f"Average game duration: {stats['avg_game_duration']:.1f}s")
                print(f"Player 1 wins: {stats['wins_player_1']}")
                print(f"Player 2 wins: {stats['wins_player_2']}")
                print(f"Draws: {stats['draws']}")
                print(f"Session uptime: {stats['session_duration']:.1f}s")
                if stats['most_popular_moves']:
                    print("Popular moves:", stats['most_popular_moves'])
                print("========================\n")
        
    def accept_connections(self):
        while len(self.clients) < 2:
            client_socket, addr = self.server.accept()
            print(f"Connected with {addr}")
            
            player_number = len(self.clients)
            client_socket.send(str(player_number).encode())
            
            self.clients.append(client_socket)
            
            threading.Thread(target=self.handle_client, args=(client_socket, player_number)).start()
            
            if len(self.clients) == 2:
                self.start_game()
                
    def start_game(self):
        self.board = np.zeros((ROW_COUNT, COLUMN_COUNT))
        self.turn = 0
        self.game_over = False
        self.game_id += 1
        self.waiting_restart = [False, False]
        self.move_history = []
        self.game_start_time = time.time()
        self.analytics.record_game_start()
        
        print(f"Starting game #{self.game_id}")
        
        game_state = {
            'type': 'game_start',
            'board': self.board.tolist(),
            'turn': self.turn,
            'game_over': self.game_over,
            'game_id': self.game_id
        }
        self.broadcast(game_state)
        
    def handle_client(self, client_socket, player_number):
        while True:
            try:
                data = client_socket.recv(4096)
                if not data:
                    break
                
                message = pickle.loads(data)
                
                if message['type'] == 'move':
                    if not self.game_over and self.turn == player_number:
                        col = message['column']
                        self.process_move(player_number, col)
                
                elif message['type'] == 'restart_request':
                    self.waiting_restart[player_number] = True
                    print(f"Player {player_number + 1} requested restart")
                    
                    if all(self.waiting_restart):
                        print("Both players agreed to restart")
                        self.start_game()
                    else:
                        restart_msg = {
                            'type': 'restart_requested',
                            'player': player_number,
                            'waiting_restart': self.waiting_restart
                        }
                        self.broadcast(restart_msg)
                
            except Exception as e:
                print(f"Error handling client {player_number}: {e}")
                break
        
        if client_socket in self.clients:
            self.clients.remove(client_socket)
            
        client_socket.close()
        print(f"Client {player_number} disconnected")
        
        if len(self.clients) < 2 and not self.game_over:
            self.game_over = True
            game_state = {
                'type': 'player_disconnected',
                'player': player_number
            }
            self.broadcast(game_state)
    
    def process_move(self, player, col):
        if 0 <= col < COLUMN_COUNT and self.is_valid_location(col):
            row = self.get_next_open_row(col)
            self.drop_piece(row, col, player + 1)
            
            
            self.analytics.record_move(player, col)
            self.move_history.append({
                'player': player,
                'column': col,
                'row': row,
                'timestamp': time.time() - self.game_start_time
            })
            
            print(f"Player {player + 1} played column {col}")
            
            
            current_score = AIHeuristics.evaluate_position(self.board, player + 1)
            opponent_score = AIHeuristics.evaluate_position(self.board, (player + 1) % 2 + 1)
            
            print(f"Position evaluation - Player {player + 1}: {current_score}, Opponent: {opponent_score}")
            
            if self.winning_move(player + 1):
                self.game_over = True
                result = 'win'
                winner = player
                self.analytics.record_game_end(winner)
                print(f"Game {self.game_id} ended - Player {player + 1} wins!")
                self.log_game_summary(winner)
            elif self.is_board_full():
                self.game_over = True
                result = 'draw'
                winner = None
                self.analytics.record_game_end(None)
                print(f"Game {self.game_id} ended in a draw!")
                self.log_game_summary(None)
            else:
                result = None
                winner = None
                self.turn = (self.turn + 1) % 2
            
            game_state = {
                'type': 'game_update',
                'board': self.board.tolist(),
                'turn': self.turn,
                'game_over': self.game_over,
                'result': result,
                'winner': winner
            }
            self.broadcast(game_state)
    
    def log_game_summary(self, winner):
        game_duration = time.time() - self.game_start_time
        total_moves = len(self.move_history)
        
        print(f"\n=== GAME {self.game_id} SUMMARY ===")
        print(f"Duration: {game_duration:.1f} seconds")
        print(f"Total moves: {total_moves}")
        print(f"Average time per move: {game_duration/total_moves:.2f}s")
        
        if winner is not None:
            print(f"Winner: Player {winner + 1}")
        else:
            print("Result: Draw")
        
        
        move_freq = {}
        for move in self.move_history:
            col = move['column']
            move_freq[col] = move_freq.get(col, 0) + 1
        
        print("Column usage:", {f"Col {k}": v for k, v in sorted(move_freq.items())})
        print("===============================\n")
    
    def broadcast(self, message):
        data = pickle.dumps(message)
        disconnected_clients = []
        
        for client in self.clients:
            try:
                client.send(data)
            except:
                disconnected_clients.append(client)
        
        
        for client in disconnected_clients:
            if client in self.clients:
                self.clients.remove(client)
    
    def create_board(self):
        return np.zeros((ROW_COUNT, COLUMN_COUNT))

    def drop_piece(self, row, col, piece):
        self.board[row][col] = piece

    def is_valid_location(self, col):
        return self.board[ROW_COUNT-1][col] == 0

    def get_next_open_row(self, col):
        for r in range(ROW_COUNT):
            if self.board[r][col] == 0:
                return r

    def winning_move(self, piece):
        
        for c in range(COLUMN_COUNT-3):
            for r in range(ROW_COUNT):
                if (self.board[r][c] == piece and self.board[r][c+1] == piece and 
                    self.board[r][c+2] == piece and self.board[r][c+3] == piece):
                    return True

        
        for c in range(COLUMN_COUNT):
            for r in range(ROW_COUNT-3):
                if (self.board[r][c] == piece and self.board[r+1][c] == piece and 
                    self.board[r+2][c] == piece and self.board[r+3][c] == piece):
                    return True

        
        for c in range(COLUMN_COUNT-3):
            for r in range(ROW_COUNT-3):
                if (self.board[r][c] == piece and self.board[r+1][c+1] == piece and 
                    self.board[r+2][c+2] == piece and self.board[r+3][c+3] == piece):
                    return True

        
        for c in range(COLUMN_COUNT-3):
            for r in range(3, ROW_COUNT):
                if (self.board[r][c] == piece and self.board[r-1][c+1] == piece and 
                    self.board[r-2][c+2] == piece and self.board[r-3][c+3] == piece):
                    return True

        return False

    def is_board_full(self):
        for col in range(COLUMN_COUNT):
            if self.is_valid_location(col):
                return False
        return True

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='Enhanced Connect Four Server')
    parser.add_argument('--host', default='localhost', help='Server host address')
    parser.add_argument('--port', type=int, default=5555, help='Server port')
    args = parser.parse_args()
    
    server = ConnectFourServer(host=args.host, port=args.port)
    try:
        print("Server running... Press Ctrl+C to stop")
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nServer shutting down...")
        sys.exit()