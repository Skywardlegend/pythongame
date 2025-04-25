# server.py

import asyncio
import json
import random
import game_logic

# Store active games
games = {}

class BattleshipGame:
    def __init__(self, game_id):
        self.game_id = game_id
        self.players = []
        self.boards = {}
        self.current_turn = None
        self.started = False
        
    def add_player(self, writer):
        if len(self.players) < 2:
            player_id = len(self.players)
            self.players.append(writer)
            self.boards[player_id] = game_logic.Board()
            self.boards[player_id].place_ships_randomly()
            return player_id
        return None
    
    def start_game(self):
        if len(self.players) == 2 and not self.started:
            self.started = True
            self.current_turn = random.randint(0, 1)  # Randomly choose who goes first
            return True
        return False
    
    def get_opponent(self, player_id):
        return 1 if player_id == 0 else 0
    
    async def process_shot(self, player_id, x, y):
        if not self.started or player_id != self.current_turn:
            return {"status": "error", "message": "Not your turn"}
        
        opponent_id = self.get_opponent(player_id)
        result = self.boards[opponent_id].fire(x, y)
        
        response = {
            "status": "ok",
            "result": result,
            "position": {"x": x, "y": y},
            "type": "shot",
            "shooter": player_id,
        }
        
        if result != "already":
            # Switch turns if it's a miss
            if result == "miss":
                self.current_turn = opponent_id
                response["your_turn"] = opponent_id
            else:
                response["your_turn"] = player_id
            
            # Check for game over
            if self.boards[opponent_id].all_ships_sunk():
                response["game_over"] = True
                response["winner"] = player_id
        
        # Notify opponent of the shot
        await self.notify_opponent(player_id, x, y, result)
        return response
    
    async def notify_opponent(self, player_id, x, y, result):
        opponent_id = self.get_opponent(player_id)
        opponent_writer = self.players[opponent_id]
        
        notification = {
            "type": "shot",
            "position": {"x": x, "y": y},
            "result": result,
            "your_turn": result == "miss"
        }
        
        if result == "sunk" and self.boards[opponent_id].all_ships_sunk():
            notification["game_over"] = True
            notification["winner"] = player_id
        
        opponent_writer.write((json.dumps(notification) + "\n").encode())
        await opponent_writer.drain()
    
    def get_board_state(self, player_id):
        own_board = self.boards[player_id].get_full_grid()
        opponent_id = self.get_opponent(player_id)
        opponent_board = None
        
        if opponent_id in self.boards:
            opponent_board = self.boards[opponent_id].get_visible_grid()
        else:
            # Create an empty grid when opponent doesn't exist yet
            opponent_board = [['~' for _ in range(game_logic.BOARD_SIZE)] for _ in range(game_logic.BOARD_SIZE)]
        
        return {
            "own_board": own_board,
            "opponent_board": opponent_board
        }
    
    def restart(self):
        # Reset the boards
        for player_id in self.boards:
            self.boards[player_id] = game_logic.Board()
            self.boards[player_id].place_ships_randomly()
        
        # Reset game state
        self.started = True
        self.current_turn = random.randint(0, 1)  # Randomly choose who goes first
        
        return True


async def handle_client(reader, writer):
    addr = writer.get_extra_info('peername')
    print(f"New connection from {addr}")
    
    game_id = None
    player_id = None
    
    try:
        # Send welcome message
        writer.write((json.dumps({"type": "welcome"}) + "\n").encode())
        await writer.drain()
        
        # Find or create game
        for gid, game in games.items():
            if len(game.players) < 2:
                game_id = gid
                player_id = game.add_player(writer)
                print(f"Player {player_id} joined existing game {game_id}")
                
                if len(game.players) == 2:
                    game.start_game()
                    # Notify both players that game has started
                    for i, p_writer in enumerate(game.players):
                        start_msg = {
                            "type": "game_start",
                            "player_id": i,
                            "your_turn": game.current_turn == i,
                            "boards": game.get_board_state(i)
                        }
                        p_writer.write((json.dumps(start_msg) + "\n").encode())
                        await p_writer.drain()
                break
        
        if game_id is None:
            # Create new game
            game_id = len(games)
            games[game_id] = BattleshipGame(game_id)
            player_id = games[game_id].add_player(writer)
            print(f"Player {player_id} created new game {game_id}")
            
            # Let player know they're waiting for opponent
            writer.write((json.dumps({
                "type": "waiting",
                "player_id": player_id,
                "game_id": game_id,
                "boards": games[game_id].get_board_state(player_id)
            }) + "\n").encode())
            await writer.drain()
        
        # Main communication loop
        while True:
            data = await reader.readline()
            if not data:
                break
                
            message = json.loads(data.decode())
            game = games.get(game_id)
            
            if message["type"] == "shot":
                x, y = message["position"]["x"], message["position"]["y"]
                result = await game.process_shot(player_id, x, y)
                writer.write((json.dumps(result) + "\n").encode())
                await writer.drain()
                
            elif message["type"] == "get_boards":
                boards = game.get_board_state(player_id)
                writer.write((json.dumps({
                    "type": "board_state",
                    "boards": boards,
                    "your_turn": game.current_turn == player_id
                }) + "\n").encode())
                await writer.drain()
                
            elif message["type"] == "restart_game":
                if game.restart():
                    # Notify both players of restart
                    for i, p_writer in enumerate(game.players):
                        restart_msg = {
                            "type": "game_start",  # Reuse game_start for simplicity
                            "player_id": i,
                            "your_turn": game.current_turn == i,
                            "boards": game.get_board_state(i),
                            "restarted": True  # Flag to indicate this is a restart
                        }
                        p_writer.write((json.dumps(restart_msg) + "\n").encode())
                        await p_writer.drain()
                        
            elif message["type"] == "player_quit":
                
                break
                
    except (ConnectionResetError, BrokenPipeError):
        print(f"Connection closed by client {addr}")
    finally:
        print(f"Closing connection to {addr}")
        writer.close()
        await writer.wait_closed()
        
        # Clean up the game if necessary
        if game_id is not None and game_id in games:
            # Notify other player that opponent disconnected
            game = games[game_id]
            if len(game.players) > 1:
                opponent_id = 1 if player_id == 0 else 0
                try:
                    opponent_writer = game.players[opponent_id]
                    
                    # Send disconnect message to opponent
                    disconnect_msg = {
                        "type": "opponent_disconnected",
                        "game_over": True,  # Set game_over flag to true
                        "winner": None      # Set winner to None to trigger the "OPPONENT DISCONNECTED" message
                    }
                    
                    opponent_writer.write((json.dumps(disconnect_msg) + "\n").encode())
                    await opponent_writer.drain()
                except Exception:
                    pass
            
            # Remove the game if both players have disconnected
            if all(p.is_closing() for p in game.players):
                del games[game_id]
                print(f"Game {game_id} removed")


async def main():
    server = await asyncio.start_server(
        handle_client, '0.0.0.0', 8888)

    addr = server.sockets[0].getsockname()
    print(f'Serving on {addr}')

    async with server:
        await server.serve_forever()


if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Server stopped")