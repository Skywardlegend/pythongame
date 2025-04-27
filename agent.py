from stable_baselines3 import PPO
import numpy as np

class RLAgent:
    def __init__(self, model=None, env=None):
        self.env = env
        self.model = model
    
    def train(self, total_timesteps=100000, log_interval=1000):
        """Train the agent using PPO algorithm"""
        if self.model is None:
            self.model = PPO('MlpPolicy', self.env, verbose=1, 
                             learning_rate=0.0003,
                             n_steps=2048,
                             batch_size=64,
                             gae_lambda=0.95,
                             gamma=0.99,
                             n_epochs=10,
                             ent_coef=0.01,
                             clip_range=0.2)
        
        self.model.learn(total_timesteps=total_timesteps, log_interval=log_interval)
        return self.model
    
    def save_model(self, path):
        """Save the trained model"""
        self.model.save(path)
    
    def load_model(self, path):
        """Load a trained model"""
        self.model = PPO.load(path)
    
    def predict_action(self, state):
        """Predict the next best action based on current state"""
        action, _ = self.model.predict(state)
        return action
    
    def play_game(self, board=None):
        """Play a complete game of battleship"""
        from game_logic import Board
        
        # Reset environment
        obs = self.env.reset()
        
        # If a custom board is provided, use it
        if board:
            self.env.set_board(board)
        
        total_reward = 0
        turns = 0
        done = False
        
        while not done:
            # Get action from the model
            action, _states = self.model.predict(obs)
            
            # Take the action
            obs, reward, done, info = self.env.step(action)
            total_reward += reward
            turns += 1
            
            if done:
                break
        
        return turns, total_reward
