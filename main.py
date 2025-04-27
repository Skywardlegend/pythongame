import pygame
import sys
import json
import asyncio
import game_logic
import os

# Initialize pygame
pygame.init()

# Constants
SCREEN_WIDTH = 800
SCREEN_HEIGHT = 500
CELL_SIZE = 30
GRID_SIZE = game_logic.BOARD_SIZE

# Bright Color Theme
WATER = (65, 157, 244)  # Bright Blue
SHIP = (95, 211, 188)   # Teal
MISS = (255, 239, 148)  # Light Yellow
HIT = (255, 99, 99)     # Bright Red
BG_COLOR = (240, 245, 249)  # Very Light Blue
TEXT_COLOR = (0, 0, 0)   # Black (changed from gray)
BUTTON_COLOR = (124, 179, 255)  # Light Blue
BUTTON_HOVER = (77, 148, 255)   # Brighter Blue
TITLE_COLOR = (42, 84, 191)  # Royal Blue


YOUR_TURN_COLOR = (0, 100, 0)  # Dark Green
OPPONENT_TURN_COLOR = (139, 0, 0)  # Dark Red

class BattleshipClient:
    def __init__(self):
        self.screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
        pygame.display.set_caption("Battleship Game")
        # Increased font size from 16 to 18
        self.font = pygame.font.SysFont('Arial', 18)
        # Increased font size from 24 to 28
        self.title_font = pygame.font.SysFont('Arial', 28, bold=True)
        
        # Load background image
        self.load_background()
        
        # Game state
        self.player_id = None
        self.game_id = None
        self.connected = False
        self.game_started = False
        self.waiting_for_opponent = False
        self.your_turn = None
        self.game_over = False
        self.winner = None
        self.message = "Welcome to Battleship!"
        
        # Board data
        self.player_board = [['' for _ in range(GRID_SIZE)] for _ in range(GRID_SIZE)]
        self.opponent_board = [['' for _ in range(GRID_SIZE)] for _ in range(GRID_SIZE)]
        
        # Board positions
        self.player_board_pos = (50, 100)
        self.opponent_board_pos = (450, 100)
        
        # Define buttons
        self.play_button = pygame.Rect(SCREEN_WIDTH//2 - 75, SCREEN_HEIGHT//2 + 50, 150, 40)
        self.restart_button = pygame.Rect(SCREEN_WIDTH//2 - 75, SCREEN_HEIGHT - 100, 150, 40)
        
        # Server connection
        self.server_host = 'localhost'
        self.server_port = 8888
        self.message_queue = asyncio.Queue()
        
        
        self.just_fired_shot = False
        self.processing_shot = False  
        
        # Initialize event loop
        self.event_loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.event_loop)
    
    def load_background(self):
        try:
        
            background_path = os.path.join('assets', 'background.jpg')
            self.background_image = pygame.image.load(background_path)
            self.background_image = pygame.transform.scale(self.background_image, (SCREEN_WIDTH, SCREEN_HEIGHT))
            self.background_image.set_alpha(150)  
        except Exception as e:
            print(f"Error loading background image: {e}")
            self.background_image = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT))
            self.background_image.fill(BG_COLOR)
            self.background_image.set_alpha(150)
    
    async def connect_to_server(self):
        try:
            self.reader, self.writer = await asyncio.open_connection(
                self.server_host, self.server_port)
            self.connected = True
            self.message = "Connected! Waiting for game..."
            
            response = await self.reader.readline()
            data = json.loads(response.decode())
            
            # Start listening for messages
            asyncio.create_task(self.listen_for_messages())
        
        except Exception as e:
            self.connected = False
            self.message = f"Connection failed: {str(e)}"
    
    async def restart_game(self):
        if self.connected:
            message = {"type": "restart_game"}
            self.writer.write((json.dumps(message) + "\n").encode())
            await self.writer.drain()
            
            # Reset game state
            self.game_started = False
            self.waiting_for_opponent = True
            self.your_turn = False
            self.game_over = False
            self.winner = None
            self.message = "Waiting for a new game..."
            self.player_board = [['' for _ in range(GRID_SIZE)] for _ in range(GRID_SIZE)]
            self.opponent_board = [['' for _ in range(GRID_SIZE)] for _ in range(GRID_SIZE)]
            self.just_fired_shot = False
            self.processing_shot = False

    async def send_disconnect_notification(self):
        if self.connected and self.game_started:
            message = {"type": "player_quit"}
            self.writer.write((json.dumps(message) + "\n").encode())
            await self.writer.drain()

    async def listen_for_messages(self):
        try:
            while self.connected:
                data = await self.reader.readline()
                if not data:
                    self.connected = False
                    self.message = "Connection lost"
                    break
                    
                message = json.loads(data.decode())
                await self.message_queue.put(message)
        except Exception:
            self.connected = False
            self.message = "Connection lost"
    
    def process_server_message(self, message):
        if not isinstance(message, dict) or "type" not in message:
            return
            
        message_type = message["type"]
        
        if message_type == "waiting":
            self.player_id = message.get("player_id")
            self.game_id = message.get("game_id")
            self.waiting_for_opponent = True
            self.message = "Waiting for opponent to join..."
            if "boards" in message:
                self._update_boards(message["boards"])
        
        elif message_type == "game_start":
            self.player_id = message.get("player_id", self.player_id)
            self.game_started = True
            self.waiting_for_opponent = False
            self.your_turn = message.get("your_turn", False)
            self.message = "Game started!"
            
            if "boards" in message:
                self._update_boards(message["boards"])
        
        elif message_type == "shot":
            self.processing_shot = True
            pos = message.get("position", {})
            result = message.get("result", "unknown")
            shooter_is_player = message.get("shooter") == self.player_id
            
            # For player shots, handle your_turn based on hit/miss logic
            if shooter_is_player and self.just_fired_shot:
                if result == "hit" or result == "sunk":
                    # If it's a hit or sunk, it's still your turn
                    self.your_turn = True
                else:
                    # If it's a miss, it becomes opponent's turn
                    self.your_turn = False
                    
                self.just_fired_shot = False  # Reset the flag
            else:
                # For opponent shots or other updates, trust the server
                self.your_turn = message.get("your_turn", self.your_turn)
            
            if isinstance(pos, dict) and "x" in pos and "y" in pos:
                x, y = pos["x"], pos["y"]
                
                # Only update message for ship sunk events
                if result == "sunk":
                    if shooter_is_player:
                        self.message = f"You SUNK a ship at {chr(65+x)}{y+1}!"
                    else:
                        self.message = f"Opponent SUNK your ship at {chr(65+x)}{y+1}!"
                # For hits, clear the message unless it's a sink
                elif result == "hit" and shooter_is_player:
                    self.message = "Successful hit! Your turn"
                # For all other cases, keep message empty
                elif result != "sunk":
                    self.message = ""
            
            # Request board update after shot
            self.event_loop.create_task(self.request_board_update())
            
            if message.get("game_over", False):
                self.game_over = True
                self.winner = message.get("winner")
                self.message = "Game over! " + ("You won!" if self.winner == self.player_id else "You lost.")
                
            self.processing_shot = False
        
        elif message_type == "board_state":
            if "boards" in message:
                self._update_boards(message["boards"])
            
            # Only update turn status from board_state if we're not processing a shot
            # his update happens only if self.processing_shot is False. 
            # This ensures that the turn status is not updated while the client is still processing the result of a shot
            if "your_turn" in message and not self.processing_shot:
                self.your_turn = message.get("your_turn")
        
        elif message_type == "opponent_disconnected":
            self.message = "Your opponent disconnected!"
            self.game_over = True
            # Clear the winner so we don't show "YOU LOSE!" message
            self.winner = None

    def _update_boards(self, boards):
        if "own_board" in boards:
            self.player_board = boards["own_board"]
        if "opponent_board" in boards:
            self.opponent_board = boards["opponent_board"]
    
    async def send_shot(self, x, y):
        if not self.connected or not self.your_turn or self.game_over:
            return
        
        message = {
            "type": "shot",
            "position": {"x": x, "y": y}
        }
        
        self.writer.write((json.dumps(message) + "\n").encode())
        await self.writer.drain()
        
        # Set the flag to indicate we just fired a shot
        self.just_fired_shot = True
        # Don't change your_turn here - we'll handle it in process_server_message
    
    async def request_board_update(self):
        if self.connected and self.game_started:
            message = {"type": "get_boards"}
            self.writer.write((json.dumps(message) + "\n").encode())
            await self.writer.drain()
    
    def draw_board(self, grid, position):
        x, y = position
        
        # Draw grid labels
        for i in range(GRID_SIZE):
            label = self.font.render(chr(65 + i), True, TEXT_COLOR)
            self.screen.blit(label, (x + i * CELL_SIZE + CELL_SIZE//2 - 5, y - 25))
            
            label = self.font.render(str(i + 1), True, TEXT_COLOR)
            self.screen.blit(label, (x - 25, y + i * CELL_SIZE + CELL_SIZE//2 - 8))
        
        # Draw cells
        for row in range(GRID_SIZE):
            for col in range(GRID_SIZE):
                rect = pygame.Rect(
                    x + col * CELL_SIZE, 
                    y + row * CELL_SIZE,
                    CELL_SIZE, 
                    CELL_SIZE
                )
                
                cell = grid[row][col] if grid and row < len(grid) and col < len(grid[row]) else '~'
                if cell == 'S':
                    pygame.draw.rect(self.screen, SHIP, rect)
                elif cell == 'X':
                    pygame.draw.rect(self.screen, HIT, rect)
                elif cell == 'O':
                    pygame.draw.rect(self.screen, MISS, rect)
                else:  # '~' water
                    pygame.draw.rect(self.screen, WATER, rect)
                
                # Draw cell border
                pygame.draw.rect(self.screen, TEXT_COLOR, rect, 1)
    
    def get_cell_from_click(self, position, board_pos):
        mouse_x, mouse_y = position
        board_x, board_y = board_pos
        
        if (board_x <= mouse_x < board_x + GRID_SIZE * CELL_SIZE and
            board_y <= mouse_y < board_y + GRID_SIZE * CELL_SIZE):
            col = (mouse_x - board_x) // CELL_SIZE
            row = (mouse_y - board_y) // CELL_SIZE
            return col, row
        
        return None
    
    def draw_button(self, rect, text):
        mouse_pos = pygame.mouse.get_pos()
        button_color = BUTTON_HOVER if rect.collidepoint(mouse_pos) else BUTTON_COLOR
        pygame.draw.rect(self.screen, button_color, rect, border_radius=5)
        
        button_text = self.font.render(text, True, TEXT_COLOR)
        text_rect = button_text.get_rect(center=rect.center)
        self.screen.blit(button_text, text_rect)
    
    def draw(self):
        # Clear screen
        self.screen.fill(BG_COLOR)
        
        # If connected, add the background image
        if self.connected:
            self.screen.blit(self.background_image, (0, 0))
        
        # Draw title
        title = self.title_font.render("BATTLESHIP ONLINE", True, TITLE_COLOR)
        self.screen.blit(title, (SCREEN_WIDTH//2 - 120, 20))
        
        if not self.connected:
            # Welcome screen
            welcome_text = self.title_font.render("Welcome to the Battleship Game!", True, TITLE_COLOR)
            self.screen.blit(welcome_text, (SCREEN_WIDTH//2 - 200, SCREEN_HEIGHT//2 - 40))
            
            # Draw play button
            self.draw_button(self.play_button, "Play")
            
        elif self.waiting_for_opponent:
            # Draw waiting screen
            message_text = self.font.render(self.message, True, TEXT_COLOR)
            self.screen.blit(message_text, (SCREEN_WIDTH//2 - 120, 60))
            
            # Position the board title higher to avoid overlap
            board_title = self.font.render("YOUR FLEET (waiting for opponent)", True, TEXT_COLOR)
            self.screen.blit(board_title, (SCREEN_WIDTH//2 - 140, 80))
            
            # Draw preview of own board with more vertical spacing
            self.draw_board(self.player_board, (SCREEN_WIDTH//2 - GRID_SIZE*CELL_SIZE//2, 130))
            
        else:  # Game is active
            # Draw board titles
            player_title = self.font.render("YOUR FLEET", True, TEXT_COLOR)
            self.screen.blit(player_title, (self.player_board_pos[0] + 30, self.player_board_pos[1] - 45))
            
            enemy_title = self.font.render("ENEMY WATERS", True, TEXT_COLOR)
            self.screen.blit(enemy_title, (self.opponent_board_pos[0] + 25, self.opponent_board_pos[1] - 45))
            
            # Draw current turn indicator with darker colors
            if self.your_turn:
                turn_text = "YOUR TURN"
                turn_label = self.font.render(turn_text, True, YOUR_TURN_COLOR)
                self.screen.blit(turn_label, (SCREEN_WIDTH//2 - 50, 60))
            else:
                # Split "OPPONENT'S TURN" into two lines
                turn_text1 = "OPPONENT'S"
                turn_text2 = "TURN"
                turn_label1 = self.font.render(turn_text1, True, OPPONENT_TURN_COLOR)
                turn_label2 = self.font.render(turn_text2, True, OPPONENT_TURN_COLOR)
                self.screen.blit(turn_label1, (SCREEN_WIDTH//2 - 50, 55))
                self.screen.blit(turn_label2, (SCREEN_WIDTH//2 - 30, 75))
            
            # Draw boards
            self.draw_board(self.player_board, self.player_board_pos)
            self.draw_board(self.opponent_board, self.opponent_board_pos)
            
            # Only draw message if it's not empty, and center it properly
            if self.message:
                message_text = self.font.render(self.message, True, TEXT_COLOR)
                message_rect = message_text.get_rect(center=(SCREEN_WIDTH//2, SCREEN_HEIGHT - 60))
                self.screen.blit(message_text, message_rect)
            
            # Draw game over screen
            if self.game_over:
                # Draw semi-transparent overlay
                overlay = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
                overlay.fill((255, 255, 255, 180))  # Semi-transparent white
                self.screen.blit(overlay, (0, 0))
                
                # Draw game over message centered
                game_over_text = self.title_font.render("GAME OVER", True, TITLE_COLOR)
                game_over_rect = game_over_text.get_rect(center=(SCREEN_WIDTH//2, SCREEN_HEIGHT//2 - 40))
                self.screen.blit(game_over_text, game_over_rect)
                
                # If opponent disconnected (winner is None), show appropriate message
                if self.winner is None:
                    winner_text = "OPPONENT DISCONNECTED"
                    winner_color = (255, 152, 0)  # Orange color for disconnect message
                else:
                    winner_text = "YOU WIN!" if self.winner == self.player_id else "YOU LOSE!"
                    winner_color = (76, 175, 80) if self.winner == self.player_id else (255, 87, 34)
                
                # Center the winner text under game over
                winner_label = self.title_font.render(winner_text, True, winner_color)
                winner_rect = winner_label.get_rect(center=(SCREEN_WIDTH//2, SCREEN_HEIGHT//2))
                self.screen.blit(winner_label, winner_rect)
                
                # Draw play again button
                self.draw_button(self.restart_button, "Play Again")
        
        # Draw quit button
        quit_button = pygame.Rect(SCREEN_WIDTH - 100, 20, 80, 30)
        self.draw_button(quit_button, "Quit")
        
        # Update display
        pygame.display.flip()
    
    async def run(self):
        clock = pygame.time.Clock()
        running = True
        
        while running:
            # Process pygame events
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                    # Send disconnect notification when quitting
                    if self.connected and self.game_started:
                        await self.send_disconnect_notification()
                
                elif event.type == pygame.MOUSEBUTTONDOWN:
                    if event.button == 1:  # Left click
                        mouse_pos = pygame.mouse.get_pos()
                        
                        # Check for quit button
                        quit_button = pygame.Rect(SCREEN_WIDTH - 100, 20, 80, 30)
                        if quit_button.collidepoint(mouse_pos):
                            # Send disconnect notification when clicking quit button
                            if self.connected and self.game_started:
                                await self.send_disconnect_notification()
                            running = False
                        
                        # Check for play button if not connected
                        if not self.connected and self.play_button.collidepoint(mouse_pos):
                            await self.connect_to_server()
                        
                        # Check for restart button if game is over
                        if self.game_over and self.restart_button.collidepoint(mouse_pos):
                            await self.restart_game()
                        
                        # Check for board click during game
                        if self.connected and self.game_started and self.your_turn and not self.game_over:
                            cell = self.get_cell_from_click(mouse_pos, self.opponent_board_pos)
                            if cell:
                                x, y = cell
                                await self.send_shot(x, y)
            
            # Process server messages
            try:
                while not self.message_queue.empty():
                    message = self.message_queue.get_nowait()
                    self.process_server_message(message)
            except Exception:
                pass
            
            # Request periodic updates if game is active
            if self.connected and self.game_started and not self.game_over:
                if pygame.time.get_ticks() % 5000 < 100:  # Roughly every 5 seconds
                    await self.request_board_update()
            # The condition pygame.time.get_ticks() % 5000 < 100 creates a ~100ms window every 5 seconds
            #During this window, it requests a board update from the server
            # Draw everything
            self.draw()
            
            # Cap the frame rate
            clock.tick(30)
            
            # Let asyncio run other tasks
            await asyncio.sleep(0)
        
        # Clean up
        if hasattr(self, 'writer') and self.writer:
            self.writer.close()
            try:
                await self.writer.wait_closed()
            except:
                pass
    
    def start(self):
        self.event_loop.run_until_complete(self.run())
        pygame.quit()
        sys.exit()

if __name__ == "__main__":
    client = BattleshipClient()
    client.start()