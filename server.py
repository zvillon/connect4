import socket
import threading
import pickle
import pygame
import numpy as np
import sys
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

class ConnectFourServer:
    def __init__(self, host='localhost', port=5555):
        self.server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server.bind((host, port))
        self.server.listen(2)
        print(f"Server started, listening on {host}:{port}")
        
        self.clients = []
        self.board = np.zeros((ROW_COUNT, COLUMN_COUNT))
        self.turn = 0
        self.game_over = False
        self.game_id = 0
        self.waiting_restart = [False, False]
        
        threading.Thread(target=self.accept_connections).start()
        
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
                    
                    if all(self.waiting_restart):
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
            
            if self.winning_move(player + 1):
                self.game_over = True
                result = 'win'
                winner = player
            elif self.is_board_full():
                self.game_over = True
                result = 'draw'
                winner = None
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
    
    def broadcast(self, message):
        data = pickle.dumps(message)
        for client in self.clients:
            try:
                client.send(data)
            except:
                if client in self.clients:
                    self.clients.remove(client)
    
    def create_board(self):
        """Create an empty board"""
        return np.zeros((ROW_COUNT, COLUMN_COUNT))

    def drop_piece(self, row, col, piece):
        """Drop a piece onto the board"""
        self.board[row][col] = piece

    def is_valid_location(self, col):
        """Check if a column is a valid move (not full)"""
        return self.board[ROW_COUNT-1][col] == 0

    def get_next_open_row(self, col):
        """Find the next open row in the given column"""
        for r in range(ROW_COUNT):
            if self.board[r][col] == 0:
                return r

    def winning_move(self, piece):
        """Check if the last move was a winning move"""
        for c in range(COLUMN_COUNT-3):
            for r in range(ROW_COUNT):
                if self.board[r][c] == piece and self.board[r][c+1] == piece and \
                   self.board[r][c+2] == piece and self.board[r][c+3] == piece:
                    return True

        for c in range(COLUMN_COUNT):
            for r in range(ROW_COUNT-3):
                if self.board[r][c] == piece and self.board[r+1][c] == piece and \
                   self.board[r+2][c] == piece and self.board[r+3][c] == piece:
                    return True

        for c in range(COLUMN_COUNT-3):
            for r in range(ROW_COUNT-3):
                if self.board[r][c] == piece and self.board[r+1][c+1] == piece and \
                   self.board[r+2][c+2] == piece and self.board[r+3][c+3] == piece:
                    return True

        for c in range(COLUMN_COUNT-3):
            for r in range(3, ROW_COUNT):
                if self.board[r][c] == piece and self.board[r-1][c+1] == piece and \
                   self.board[r-2][c+2] == piece and self.board[r-3][c+3] == piece:
                    return True

        return False

    def is_board_full(self):
        """Check if the board is completely full"""
        for col in range(COLUMN_COUNT):
            if self.is_valid_location(col):
                return False
        return True

if __name__ == "__main__":
    server = ConnectFourServer()
    try:
        while True:
            pass
    except KeyboardInterrupt:
        print("Server shutting down...")
        sys.exit()