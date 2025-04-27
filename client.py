import socket
import threading
import pickle
import pygame
import sys
import numpy as np
import time
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

class FallingPiece:
    def __init__(self, col, end_row, color):
        self.col = col
        self.end_row = end_row
        self.color = color
        self.y = SQUARE_SIZE/2
        self.end_y = HEIGHT - 50 - (end_row * SQUARE_SIZE + SQUARE_SIZE/2)
        self.speed = 15
        self.active = True
        self.bounces = 0
        self.max_bounces = 1
        self.bounce_factor = 1
        
    def update(self):
        if not self.active:
            return
        
        if self.bounces < self.max_bounces and self.y >= self.end_y:
            self.speed = -self.speed * self.bounce_factor
            self.bounces += 1
            self.y += self.speed
        else:
            self.y += self.speed
            
            if self.bounces >= self.max_bounces:
                    self.y = self.end_y
                    self.active = False
            elif self.speed < 0 and self.y <= 0:
                self.speed = -self.speed
        return self.active
    
    def draw(self, screen):
        pygame.draw.circle(screen, self.color, (int(self.col * SQUARE_SIZE + SQUARE_SIZE/2), int(self.y)), RADIUS)

class ConnectFourClient:
    def __init__(self, host='localhost', port=5555):
        self.client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            self.client.connect((host, port))
            self.connected = True
        except Exception as e:
            print(f"Connection error: {e}")
            self.connected = False
            return
        
        self.player_number = int(self.client.recv(1024).decode())
        self.player_color = RED if self.player_number == 0 else YELLOW
        self.opponent_color = YELLOW if self.player_number == 0 else RED
        
        self.board = np.zeros((ROW_COUNT, COLUMN_COUNT))
        self.visual_board = np.zeros((ROW_COUNT, COLUMN_COUNT))
        self.turn = 0
        self.game_over = False
        self.winner = None
        self.game_id = 0
        self.waiting_restart = [False, False]
        self.falling_pieces = []
        
        pygame.init()
        self.screen = pygame.display.set_mode((WIDTH, HEIGHT))
        pygame.display.set_caption(f'Connect 4 - Player {self.player_number + 1}')
        self.font = pygame.font.SysFont("monospace", 30)
        self.large_font = pygame.font.SysFont("monospace", 50)
        
        self.restart_button = pygame.Rect(WIDTH//2 - 100, HEIGHT - 40, 200, 30)

        self.receive_thread = threading.Thread(target=self.receive_data)
        self.receive_thread.daemon = True
        self.receive_thread.start()
        
        self.run_game()
        
    def receive_data(self):
        while self.connected:
            try:
                data = self.client.recv(4096)
                if not data:
                    print("Disconnected from server")
                    self.connected = False
                    break
                
                message = pickle.loads(data)
                
                if message['type'] == 'game_start' or message['type'] == 'game_update':
                    new_board = np.array(message.get('board', self.board))
                    
                    if message['type'] == 'game_update':
                        self.add_falling_animations(new_board)
                    
                    self.board = new_board
                    self.turn = message.get('turn', self.turn)
                    self.game_over = message.get('game_over', self.game_over)
                    
                    if 'game_id' in message:
                        self.game_id = message['game_id']
                        self.visual_board = np.zeros((ROW_COUNT, COLUMN_COUNT))
                    
                    if self.game_over and message.get('result') == 'win':
                        self.winner = message.get('winner')
                        
                elif message['type'] == 'player_disconnected':
                    self.game_over = True
                    disconnected_player = message.get('player')
                    print(f"Player {disconnected_player + 1} disconnected")
                
                elif message['type'] == 'restart_requested':
                    self.waiting_restart = message['waiting_restart']
                
            except Exception as e:
                print(f"Error receiving data: {e}")
                self.connected = False
                break
    
    def add_falling_animations(self, new_board):
        for c in range(COLUMN_COUNT):
            for r in range(ROW_COUNT):
                if new_board[r][c] != 0 and self.visual_board[r][c] == 0:
                    piece_color = RED if new_board[r][c] == 1 else YELLOW
                    self.falling_pieces.append(FallingPiece(c, r, piece_color))
                    
                    self.visual_board[r][c] = new_board[r][c]
    
    def send_move(self, column):
        if self.connected and not self.game_over and self.turn == self.player_number:
            message = {
                'type': 'move',
                'column': column
            }
            try:
                self.client.send(pickle.dumps(message))
            except Exception as e:
                print(f"Error sending move: {e}")
                self.connected = False
    
    def request_restart(self):
        if self.connected:
            message = {
                'type': 'restart_request'
            }
            try:
                self.client.send(pickle.dumps(message))
                self.falling_pieces = []
            except Exception as e:
                print(f"Error requesting restart: {e}")
                self.connected = False
    
    def draw_board(self):
        pygame.draw.rect(self.screen, BLUE, (0, SQUARE_SIZE, WIDTH, HEIGHT - SQUARE_SIZE - 50))
        
        for c in range(COLUMN_COUNT):
            for r in range(ROW_COUNT):
                pygame.draw.circle(self.screen, BLACK, 
                                  (int(c * SQUARE_SIZE + SQUARE_SIZE / 2), 
                                   int((r + 1) * SQUARE_SIZE + SQUARE_SIZE / 2)), 
                                  RADIUS)
                
        animated_positions = [(p.col, ROW_COUNT - 1 - p.end_row) for p in self.falling_pieces if p.active]
        
        for c in range(COLUMN_COUNT):
            for r in range(ROW_COUNT):
                if (c, r) not in animated_positions and self.visual_board[ROW_COUNT-1-r][c] != 0:
                    piece_color = RED if self.visual_board[ROW_COUNT-1-r][c] == 1 else YELLOW
                    pygame.draw.circle(self.screen, piece_color, 
                                      (int(c * SQUARE_SIZE + SQUARE_SIZE / 2), 
                                       int((r + 1) * SQUARE_SIZE + SQUARE_SIZE / 2)), 
                                      RADIUS)
    
    def update_animations(self):
        i = 0
        while i < len(self.falling_pieces):
            if not self.falling_pieces[i].update():
                del self.falling_pieces[i]
            else:
                i += 1
    
    def draw_animations(self):
        for piece in self.falling_pieces:
            piece.draw(self.screen)
    
    def draw_status_area(self):
        pygame.draw.rect(self.screen, BLACK, (0, 0, WIDTH, SQUARE_SIZE))
        
        if self.game_over:
            if self.winner is not None:
                if self.winner == self.player_number:
                    text = self.large_font.render("You Win!", True, self.player_color)
                else:
                    text = self.large_font.render("You Lose!", True, self.opponent_color)
            else:
                text = self.large_font.render("It's a Draw!", True, WHITE)
        else:
            if self.turn == self.player_number:
                text = self.font.render("Your Turn", True, self.player_color)
            else:
                text = self.font.render("Opponent's Turn", True, self.opponent_color)
        
        text_rect = text.get_rect(center=(WIDTH//2, SQUARE_SIZE//2))
        self.screen.blit(text, text_rect)
        
        player_text = self.font.render(f"You: Player {self.player_number + 1}", True, self.player_color)
        self.screen.blit(player_text, (10, 10))
        
        if any(self.waiting_restart):
            if self.waiting_restart[self.player_number]:
                waiting_text = self.font.render("Waiting for opponent to restart...", True, WHITE)
            else:
                waiting_text = self.font.render("Opponent wants to restart", True, WHITE)
            waiting_rect = waiting_text.get_rect(center=(WIDTH//2, SQUARE_SIZE//2 + 30))
            self.screen.blit(waiting_text, waiting_rect)
    
    def draw_restart_button(self):
        if self.waiting_restart[self.player_number]:
            button_color = GRAY
        else:
            button_color = GREEN if self.game_over else BLUE
        
        pygame.draw.rect(self.screen, button_color, self.restart_button)
        restart_text = self.font.render("Restart", True, WHITE)
        text_rect = restart_text.get_rect(center=self.restart_button.center)
        self.screen.blit(restart_text, text_rect)
    
    def run_game(self):
        if not self.connected:
            print("Not connected to server, exiting")
            return
        
        running = True
        clock = pygame.time.Clock()
        
        while running:
            self.update_animations()
            
            self.screen.fill(BLACK)
            self.draw_board()
            self.draw_animations()
            self.draw_status_area()
            self.draw_restart_button()
            
            if not self.game_over and self.turn == self.player_number and not self.falling_pieces:
                posx = pygame.mouse.get_pos()[0]
                pygame.draw.circle(self.screen, self.player_color, 
                                  (posx, int(SQUARE_SIZE/2)), 
                                  RADIUS)
            
            pygame.display.update()
            
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                    pygame.quit()
                    sys.exit()
                
                elif event.type == pygame.MOUSEBUTTONDOWN:
                    if self.restart_button.collidepoint(event.pos):
                        if not self.waiting_restart[self.player_number]:
                            self.request_restart()
                    
                    elif not self.game_over and self.turn == self.player_number and not self.falling_pieces:
                        posx = event.pos[0]
                        col = int(posx // SQUARE_SIZE)
                        if 0 <= col < COLUMN_COUNT:
                            self.send_move(col)
            
            clock.tick(60)
        
        pygame.quit()
        self.client.close()

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='Connect Four Client')
    parser.add_argument('--host', default='localhost', help='Server host address')
    parser.add_argument('--port', type=int, default=5555, help='Server port')
    args = parser.parse_args()
    
    client = ConnectFourClient(host=args.host, port=args.port)