import gymnasium as gym
from stable_baselines3 import PPO
from stable_baselines3.common.monitor import Monitor
from stable_baselines3.common.vec_env import DummyVecEnv
import numpy as np
import time
import os

# Register the custom environment
from gymnasium.envs.registration import register

def register_env():
    from gymnasium.envs.registration import registry
    if 'BattleshipEnv-v0' not in registry:
        register(
            id='BattleshipEnv-v0',
            entry_point='battleship_env:BattleshipEnv',
            max_episode_steps=100,
        )

def create_env():
    register_env()
    env = gym.make('BattleshipEnv-v0')
    env = Monitor(env)
    return DummyVecEnv([lambda: env])

# Train and save the model
def train_agent(timesteps=500000):
    env = create_env()
    model = PPO('MlpPolicy', env, verbose=1,
                learning_rate=0.0003,
                n_steps=2048,
                batch_size=64,
                gae_lambda=0.95,
                gamma=0.99,
                n_epochs=10,
                ent_coef=0.01,
                clip_range=0.2)
    
    print("Training model...")
    start_time = time.time()
    model.learn(total_timesteps=timesteps)
    training_time = time.time() - start_time
    print(f"Training completed in {training_time:.2f} seconds")
    
    model_dir = "models"
    os.makedirs(model_dir, exist_ok=True)

    timestamp = time.strftime("%Y%m%d-%H%M%S")
    model_path = f"{model_dir}/battleship_ppo_{timestamp}"
    model.save(model_path)
    print(f"Model saved to {model_path}")

    return model_path  # Return only the path

# Load the saved model
def load_model(path):
    env = create_env()
    model = PPO.load(path, env=env)
    print(f"Model loaded from {path}")
    return model

# Evaluate the model
def evaluate_agent(model, num_games=100):
    env = gym.make('BattleshipEnv-v0')
    
    scores = []
    rewards = []
    
    for _ in range(num_games):
        obs, _ = env.reset()
        done = False
        game_reward = 0
        moves = 0
        
        while not done:
            action, _ = model.predict(obs)
            obs, reward, terminated, truncated, _ = env.step(action)
            done = terminated or truncated
            game_reward += reward
            moves += 1
        
        scores.append(moves)
        rewards.append(game_reward)
    
    avg_score = sum(scores) / len(scores)
    avg_reward = sum(rewards) / len(rewards)
    
    print(f"Evaluation over {num_games} games:")
    print(f"Average moves to win: {avg_score:.2f}")
    print(f"Average reward: {avg_reward:.2f}")
    print(f"Best game (fewest moves): {min(scores)}")
    
    return scores, rewards

# Main process
if __name__ == "__main__":
    register_env()

    # Train and save the model
    model_path = train_agent(timesteps=500000)

    # Load the saved model
    model = load_model(model_path)

    # Evaluate the loaded model
    scores, rewards = evaluate_agent(model, num_games=20)

    print("Done!")
