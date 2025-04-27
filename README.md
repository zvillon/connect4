## Connect 4 Network Game
A networked version of the classic Connect 4 game with animations, built using Python and Pygame.

## Features

- Network play between two separate computers
- Animated falling pieces with realistic bouncing
- Visual indication of whose turn it is
- Restart button that requires both players to agree

## Installation

1. Clone or download this repository to your local machine
2. Install the required dependencies:
    ```pip install -r requirements.txt```


## How to Play

1. First, start the server:
```python server.py```

2. Then start two client instances (on different computers or terminals):
    ```python client.py --host localhost```
   If connecting over a network, replace "localhost" with the server's IP address:
    ```python client.py --host 192.168.1.xxx```

3. Each client will connect and be assigned as either Player 1 (red) or Player 2 (yellow).
4. Take turns dropping pieces by clicking on the column where you want to place your piece.
5. Connect four of your pieces horizontally, vertically, or diagonally to win!
6. When the game ends, either player can click the restart button. The game will restart once both players have requested it.

## Some bugs

Right now there's some bug I discovered, first, if you leave and you rejoin you might have to restart the server, second bug, if you play with first player and second player is offline, then second player join after player one joined the game, you might have to restart the server, because first client will be waiting for second player to play, but second player won't be able to play.