import socket
import threading
import pickle
import pygame
import sys
import numpy as np
import time
import math
import argparse
import random
from pygame.locals import *

ROW_COUNT = 6
COLUMN_COUNT = 7
SQUARE_SIZE = 100
RADIUS = int(SQUARE_SIZE / 2 - 5)
WIDTH = COLUMN_COUNT * SQUARE_SIZE
HEIGHT = (ROW_COUNT + 1) * SQUARE_SIZE + 50
BLUE = (0, 0, 255)
BLACK = (0, 0, 0)
RED = (255, 0, 0)
YELLOW = (255, 255, 0)
WHITE = (255, 255, 255)
GREEN = (0, 255, 0)
GRAY = (128, 128, 128)
PURPLE = (128, 0, 128)
ORANGE = (255, 165, 0)


class Circle:


    def __init__(self, center, radius):
        self.center = pygame.math.Vector2(center)
        self.radius = radius

    def support(self, direction):
        return self.center + self.radius * direction.normalize()


def gjk(shape1, shape2):
    def support(dir):

        return shape1.support(dir) - shape2.support(-dir)

    simplex = []

    direction = pygame.math.Vector2(1, 0)

    simplex.append(support(direction))

    direction = -simplex[0]

    for _ in range(100):
        a = support(direction)

        if a.dot(direction) < 0:
            return False

        simplex.append(a)

        if len(simplex) == 2:
            b, a = simplex
            ab = b - a
            ao = -a

            direction = (
                pygame.math.Vector2(-ab.y, ab.x)
                if ab.cross(ao) > 0
                else pygame.math.Vector2(ab.y, -ab.x)
            )

        elif len(simplex) == 3:
            c, b, a = simplex
            ab = b - a
            ac = c - a
            ao = -a

            ab_perp = pygame.math.Vector2(-ab.y, ab.x)
            ac_perp = pygame.math.Vector2(ac.y, -ac.x)

            if ab_perp.dot(ao) > 0:
                simplex.pop(0)
                direction = ab_perp
            elif ac_perp.dot(ao) > 0:
                simplex.pop(1)
                direction = ac_perp
            else:

                return True
    return False


class GameMetrics:
    def __init__(self):
        self.reset()

    def reset(self):
        self.moves_made = 0
        self.game_start_time = time.time()
        self.move_times = []
        self.last_move_time = time.time()
        self.collision_checks = 0
        self.animations_played = 0
        self.total_think_time = 0

    def record_move(self):
        current_time = time.time()
        think_time = current_time - self.last_move_time
        self.move_times.append(think_time)
        self.total_think_time += think_time
        self.moves_made += 1
        self.last_move_time = current_time

    def record_collision_check(self):
        self.collision_checks += 1

    def record_animation(self):
        self.animations_played += 1

    def get_game_duration(self):
        return time.time() - self.game_start_time

    def get_average_move_time(self):
        return sum(self.move_times) / len(self.move_times) if self.move_times else 0

    def get_moves_per_minute(self):
        duration = self.get_game_duration() / 60
        return self.moves_made / duration if duration > 0 else 0


class FallingPiece:
    def __init__(self, col, end_row, color):
        self.col = col
        self.end_row = end_row
        self.color = color
        self.x = col * SQUARE_SIZE + SQUARE_SIZE / 2
        self.y = SQUARE_SIZE / 2
        self.speed = 0
        self.gravity = 0.8
        self.active = True
        self.bounces = 0
        self.max_bounces = 1
        self.bounce_factor = 0.4
        self.settled = False

        self.collision_triggered = False

        self.target_y = (self.end_row + 1) * SQUARE_SIZE + SQUARE_SIZE / 2

    def update(self):

        if not self.active or self.settled:
            return False
        self.speed += self.gravity
        self.y += self.speed
        if self.y >= self.target_y:
            if self.bounces < self.max_bounces and self.speed > 3:
                self.speed = -self.speed * self.bounce_factor
                self.y = self.target_y
                self.bounces += 1
            else:
                self.y = self.target_y
                self.speed = 0
                self.settled = True
                self.active = False
                return False
        return self.active

    def draw(self, surface):
        center_x = int(self.x)
        center_y = int(self.y)
        pygame.draw.circle(surface, (50, 50, 50), (center_x + 2, center_y + 2), RADIUS)
        glow_radius = RADIUS + 3
        glow_color = tuple(min(255, c + 30) for c in self.color)
        pygame.draw.circle(surface, glow_color, (center_x, center_y), glow_radius)
        pygame.draw.circle(surface, self.color, (center_x, center_y), RADIUS)
        highlight_color = tuple(min(255, c + 80) for c in self.color)
        pygame.draw.circle(
            surface, highlight_color, (center_x - 8, center_y - 8), RADIUS // 3
        )


class ConnectFourClient:
    def __init__(self, host="localhost", port=5555):
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
        self.metrics = GameMetrics()
        self.show_metrics = True
        self.hover_collision_detected = False

        pygame.init()
        self.screen = pygame.display.set_mode((WIDTH, HEIGHT + 150))
        pygame.display.set_caption(
            f"Enhanced Connect 4 - Player {self.player_number + 1}"
        )

        self.display_surface = pygame.Surface((WIDTH, HEIGHT + 150))
        self.shake_timer = 0
        self.shake_intensity = 5

        self.font = pygame.font.SysFont("monospace", 24)
        self.small_font = pygame.font.SysFont("monospace", 18)
        self.large_font = pygame.font.SysFont("monospace", 40)

        self.restart_button = pygame.Rect(WIDTH // 2 - 100, HEIGHT - 40, 200, 30)
        self.metrics_button = pygame.Rect(10, HEIGHT - 40, 100, 30)

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
                if message["type"] == "game_start" or message["type"] == "game_update":
                    new_board = np.array(message.get("board", self.board))
                    if message["type"] == "game_update":
                        self.add_falling_animations(new_board)
                        if message.get("turn") != self.turn:
                            self.metrics.record_move()
                    self.board = new_board
                    self.turn = message.get("turn", self.turn)
                    self.game_over = message.get("game_over", self.game_over)
                    if "game_id" in message:
                        self.game_id = message["game_id"]
                        self.visual_board = np.zeros((ROW_COUNT, COLUMN_COUNT))
                        self.metrics.reset()
                        self.falling_pieces = []
                    if self.game_over and message.get("result") == "win":
                        self.winner = message.get("winner")
                        self.visual_board = self.board.copy()
                elif message["type"] == "player_disconnected":
                    self.game_over = True
                    print(f"Player {message.get('player') + 1} disconnected")
                elif message["type"] == "restart_requested":
                    self.waiting_restart = message["waiting_restart"]
            except Exception as e:
                print(f"Error receiving data: {e}")
                self.connected = False
                break

    def add_falling_animations(self, new_board):
        for c in range(COLUMN_COUNT):
            for r in range(ROW_COUNT):
                if new_board[r][c] != 0 and self.visual_board[r][c] == 0:
                    piece_color = RED if new_board[r][c] == 1 else YELLOW
                    visual_row = ROW_COUNT - 1 - r
                    falling_piece = FallingPiece(c, visual_row, piece_color)
                    self.falling_pieces.append(falling_piece)
                    self.metrics.record_animation()
                    self.visual_board[r][c] = new_board[r][c]

    def check_gjk_collisions(self):

        if self.game_over or not self.falling_pieces:
            return

        posx = pygame.mouse.get_pos()[0]
        hover_circle = Circle((posx, SQUARE_SIZE / 2), RADIUS)

        collision_found = False
        for piece in self.falling_pieces:

            if piece.color != self.player_color:
                falling_circle = Circle((piece.x, piece.y), RADIUS)
                if gjk(falling_circle, hover_circle):
                    collision_found = True
                    self.metrics.record_collision_check()
                    break

        if collision_found and self.shake_timer <= 0:
            self.shake_timer = 0.2

    def send_move(self, column):
        if self.connected and not self.game_over and self.turn == self.player_number:
            message = {"type": "move", "column": column}
            try:
                self.client.send(pickle.dumps(message))
            except Exception as e:
                print(f"Error sending move: {e}")
                self.connected = False

    def request_restart(self):
        if self.connected:
            message = {"type": "restart_request"}
            try:
                self.client.send(pickle.dumps(message))
                self.falling_pieces = []
            except Exception as e:
                print(f"Error requesting restart: {e}")
                self.connected = False

    def draw_board(self, surface):
        for y in range(SQUARE_SIZE, HEIGHT - 50):
            intensity = int(
                200 + 55 * ((y - SQUARE_SIZE) / (HEIGHT - 50 - SQUARE_SIZE))
            )
            color = (0, 0, min(255, intensity))
            pygame.draw.rect(surface, color, (0, y, WIDTH, 1))
        for c in range(COLUMN_COUNT):
            for r in range(ROW_COUNT):
                center_x = int(c * SQUARE_SIZE + SQUARE_SIZE / 2)
                center_y = int((r + 1) * SQUARE_SIZE + SQUARE_SIZE / 2)
                pygame.draw.circle(
                    surface, (20, 20, 40), (center_x + 2, center_y + 2), RADIUS
                )
                pygame.draw.circle(surface, BLACK, (center_x, center_y), RADIUS)
        for c in range(COLUMN_COUNT):
            for r in range(ROW_COUNT):
                if self.visual_board[ROW_COUNT - 1 - r][c] != 0:
                    is_animated = any(
                        p.col == c and p.end_row == r and p.active
                        for p in self.falling_pieces
                    )
                    if not is_animated:
                        piece_color = (
                            RED
                            if self.visual_board[ROW_COUNT - 1 - r][c] == 1
                            else YELLOW
                        )
                        center_x = int(c * SQUARE_SIZE + SQUARE_SIZE / 2)
                        center_y = int((r + 1) * SQUARE_SIZE + SQUARE_SIZE / 2)
                        self.draw_static_piece(surface, center_x, center_y, piece_color)

    def draw_static_piece(self, surface, center_x, center_y, piece_color):
        highlight = tuple(min(255, c + 80) for c in piece_color)
        shadow = tuple(max(0, c - 80) for c in piece_color)
        pygame.draw.circle(surface, shadow, (center_x + 3, center_y + 3), RADIUS)
        pygame.draw.circle(surface, piece_color, (center_x, center_y), RADIUS)
        pygame.draw.circle(
            surface, highlight, (center_x - 5, center_y - 5), RADIUS // 3
        )

    def update_animations(self):
        i = 0
        while i < len(self.falling_pieces):
            piece = self.falling_pieces[i]

            if not piece.collision_triggered:

                next_y = piece.y + piece.speed

                collision_threshold = piece.target_y - (RADIUS / 2)

                if next_y >= collision_threshold:

                    if self.shake_timer <= 0:
                        self.shake_timer = 0.2
                        self.metrics.record_collision_check()

                    piece.collision_triggered = True

            if not piece.update():

                board_row = ROW_COUNT - 1 - piece.end_row
                self.visual_board[board_row][piece.col] = self.board[board_row][
                    piece.col
                ]
                del self.falling_pieces[i]
            else:
                i += 1

    def draw_animations(self, surface):
        for piece in self.falling_pieces:
            piece.draw(surface)

    def draw_status_area(self, surface):
        for y in range(SQUARE_SIZE):
            intensity = int(40 + 20 * (y / SQUARE_SIZE))
            color = (intensity, intensity, intensity)
            pygame.draw.rect(surface, color, (0, y, WIDTH, 1))

        if self.game_over:
            if self.winner is not None:
                text = self.large_font.render(
                    "Victory!" if self.winner == self.player_number else "Defeat!",
                    True,
                    GREEN if self.winner == self.player_number else RED,
                )
            else:
                text = self.large_font.render("Draw!", True, WHITE)
        else:
            text = self.font.render(
                "Your Turn" if self.turn == self.player_number else "Opponent's Turn",
                True,
                (
                    self.player_color
                    if self.turn == self.player_number
                    else self.opponent_color
                ),
            )

        text_rect = text.get_rect(center=(WIDTH // 2, SQUARE_SIZE // 2))
        surface.blit(text, text_rect)
        player_text = self.font.render(
            f"Player {self.player_number + 1}", True, self.player_color
        )
        surface.blit(player_text, (10, 10))
        if any(self.waiting_restart):
            waiting_text_str = (
                "Waiting for opponent..."
                if self.waiting_restart[self.player_number]
                else "Opponent wants restart"
            )
            waiting_text = self.small_font.render(
                waiting_text_str,
                True,
                WHITE if self.waiting_restart[self.player_number] else ORANGE,
            )
            waiting_rect = waiting_text.get_rect(
                center=(WIDTH // 2, SQUARE_SIZE // 2 + 30)
            )
            surface.blit(waiting_text, waiting_rect)

    def draw_metrics(self, surface):
        if not self.show_metrics:
            return
        metrics_y, metrics_area_height = HEIGHT + 10, 150
        pygame.draw.rect(surface, (30, 30, 30), (0, HEIGHT, WIDTH, metrics_area_height))
        duration = self.metrics.get_game_duration()
        avg_move = self.metrics.get_average_move_time()
        moves_min = self.metrics.get_moves_per_minute()
        metrics_text = [
            f"Game Duration: {duration:.1f}s",
            f"Moves Made: {self.metrics.moves_made}",
            f"Avg Move Time: {avg_move:.2f}s",
            f"Moves/Min: {moves_min:.1f}",
            f"GJK Checks: {self.metrics.collision_checks}",
            f"Animations: {self.metrics.animations_played}",
        ]
        for i, text in enumerate(metrics_text):
            color = WHITE if i < 4 else PURPLE
            rendered = self.small_font.render(text, True, color)
            surface.blit(rendered, (10 + (i % 2) * 280, metrics_y + (i // 2) * 25))

    def draw_buttons(self, surface):
        button_color = (
            GRAY
            if self.waiting_restart[self.player_number]
            else (GREEN if self.game_over else BLUE)
        )
        pygame.draw.rect(surface, button_color, self.restart_button)
        pygame.draw.rect(surface, WHITE, self.restart_button, 2)
        restart_text = self.font.render("Restart", True, WHITE)
        surface.blit(
            restart_text, restart_text.get_rect(center=self.restart_button.center)
        )

        metrics_color = ORANGE if self.show_metrics else GRAY
        pygame.draw.rect(surface, metrics_color, self.metrics_button)
        pygame.draw.rect(surface, WHITE, self.metrics_button, 2)
        metrics_text = self.font.render("Metrics", True, WHITE)
        surface.blit(
            metrics_text, metrics_text.get_rect(center=self.metrics_button.center)
        )

    def draw_hover_piece(self, surface):

        if not self.game_over and self.turn == self.player_number:
            posx = pygame.mouse.get_pos()[0]
            pulse = abs(math.sin(time.time() * 3)) * 0.3 + 0.7
            hover_color = tuple(int(c * pulse) for c in self.player_color)
            pygame.draw.circle(
                surface, hover_color, (posx, int(SQUARE_SIZE / 2)), RADIUS
            )

    def run_game(self):
        if not self.connected:
            return
        running, clock = True, pygame.time.Clock()
        while running:
            delta_time = clock.tick(60) / 1000.0

            if self.shake_timer > 0:
                self.shake_timer -= delta_time
            self.check_gjk_collisions()
            self.update_animations()

            self.display_surface.fill(BLACK)
            self.draw_board(self.display_surface)
            self.draw_animations(self.display_surface)
            self.draw_status_area(self.display_surface)
            self.draw_metrics(self.display_surface)
            self.draw_buttons(self.display_surface)
            self.draw_hover_piece(self.display_surface)

            shake_offset = (0, 0)
            if self.shake_timer > 0:
                shake_offset = (
                    random.randint(-self.shake_intensity, self.shake_intensity),
                    random.randint(-self.shake_intensity, self.shake_intensity),
                )

            self.screen.fill(BLACK)
            self.screen.blit(self.display_surface, shake_offset)
            pygame.display.update()

            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                elif event.type == pygame.MOUSEBUTTONDOWN:
                    if self.restart_button.collidepoint(event.pos):
                        if not self.waiting_restart[self.player_number]:
                            self.request_restart()
                    elif self.metrics_button.collidepoint(event.pos):
                        self.show_metrics = not self.show_metrics
                    elif (
                        not self.game_over
                        and self.turn == self.player_number
                        and not self.falling_pieces
                    ):
                        col = int(event.pos[0] // SQUARE_SIZE)
                        if 0 <= col < COLUMN_COUNT:
                            self.send_move(col)

        pygame.quit()
        self.client.close()
        sys.exit()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Enhanced Connect Four Client")
    parser.add_argument("--host", default="localhost", help="Server host address")
    parser.add_argument("--port", type=int, default=5555, help="Server port")
    args = parser.parse_args()
    client = ConnectFourClient(host=args.host, port=args.port)
