import gymnasium as gym
import numpy as np
from gymnasium import spaces

class BattleshipEnv(gym.Env):
    """
    Battleship environment for reinforcement learning
    Based on OpenAI Gym environment
    """
    def __init__(self):
        super(BattleshipEnv, self).__init__()
        
        self.board_size = 10
        
        # Action space: Choose a grid coordinate (0-99)
        self.action_space = spaces.Discrete(self.board_size * self.board_size)
        
        # Observation space: Grid with -1 (miss), 0 (unknown), 1 (hit)
        self.observation_space = spaces.Box(
            low=-1, high=1, 
            shape=(self.board_size, self.board_size),
            dtype=np.int32
        )
        
        # Reward parameters
        self.hit_reward = 0.5
        self.repeated_penalty = -0.2
        self.persistence_penalty = -0.01
        self.proximity_reward = 0.2
        self.win_reward = 100.0
        self.proximity_radius = 2
        
        self.reset()
    
    def reset(self, seed=None, options=None):
        super().reset(seed=seed)
        from game_logic import Board
        
        self.board = Board()
        self.board.place_ships_randomly()
        
        # Initialize state as all unknown (0)
        self.state = np.zeros((self.board_size, self.board_size), dtype=np.int32)
        self.done = False
        self.info = {}
        
        return self.state, self.info
    
    def step(self, action):
        # Convert flat action to x,y coordinates
        x = action % self.board_size
        y = action // self.board_size
        
        # Check if already fired at this location
        if self.state[y][x] != 0:
            return self.state, self.repeated_penalty, self.done, False, {}
        
        # Fire at the chosen position
        result = self.board.fire(x, y)
        
        # Update state based on result
        if result == 'hit' or result == 'sunk':
            self.state[y][x] = 1
            reward = self.hit_reward
        elif result == 'miss':
            self.state[y][x] = -1
            reward = self.persistence_penalty
        else:  # already fired (shouldn't happen due to earlier check)
            reward = self.repeated_penalty
        
        # Check for proximity reward
        neighbors = self._get_neighbors(x, y, self.proximity_radius)
        for nx, ny in neighbors:
            if 0 <= nx < self.board_size and 0 <= ny < self.board_size:
                if self.state[ny][nx] == 1:  # If neighbor is a hit
                    reward += self.proximity_reward
        
        # Check if game is over
        self.done = self.board.all_ships_sunk()
        if self.done:
            reward += self.win_reward
        
        # Add truncated=False parameter for gym v26/gymnasium
        return self.state, reward, self.done, False, {}
    
    def _get_neighbors(self, x, y, radius):
        neighbors = []
        for r in range(1, radius + 1):
            neighbors.extend([
                (x+r, y), (x-r, y), (x, y+r), (x, y-r),
                (x+r, y+r), (x+r, y-r), (x-r, y+r), (x-r, y-r)
            ])
        return neighbors
    
    def set_board(self, board):
        """Override the board for testing purposes"""
        self.board = board