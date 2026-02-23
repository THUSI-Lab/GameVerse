import argparse
import logging
import os
import sys
import json
from datetime import datetime

# Add src directory to Python path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
src_path = os.path.join(project_root, 'src')
if src_path not in sys.path:
    sys.path.insert(0, src_path)

from omegaconf import OmegaConf

from agent_client.runner.eval import BaseRunner
from game_servers.utils.module_creator import EnvCreator
from agent_client.base_agent import BaselineAgent
from game_servers.utils.video_generator import create_video_from_log_path


logger = logging.getLogger(__name__)
# logging.basicConfig(level=logging.INFO)


def set_log_path(cfg):
    log_path = os.path.join(
                cfg.log_path,
                cfg.env_name,
                cfg.agent.llm_name,
                cfg.env.action_mode,
                cfg.agent.agent_type,
                datetime.now().strftime("%Y%m%d_%H%M%S")
            )
    cfg.env.log_path = log_path
    cfg.agent.log_path = log_path
    os.makedirs(log_path, exist_ok=True)

    config_path = os.path.join(log_path, 'config.yaml')
    with open(config_path, 'w') as f:
        OmegaConf.save(config=cfg, f=f.name)

    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(os.path.join(log_path, 'run.log')),
            logging.StreamHandler()
        ]
    )

    return cfg

def parse_configs():
    # Define argparse arguments
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--config",
        type=str,
        default="configs/slay_the_spire/config.yaml"
    )
    args, unknown = parser.parse_known_args()

    # Load configuration file
    cfg = OmegaConf.load(args.config)

    # Override with command-line arguments
    cli_cfg = OmegaConf.from_cli(unknown)
    cfg = OmegaConf.merge(cfg, cli_cfg)

    # Set logging
    cfg = set_log_path(cfg)

    return cfg


def main():
    config = parse_configs()
    logger.debug(config)
    runner = BaseRunner(config.runner)
    # setup Game_env
    env = EnvCreator(config).create()

    # load LLM agent
    llm_agent = BaselineAgent(config.agent)
    logger.info(f"Action_mode: {config.env.action_mode}")
    logger.info(f"Agent_type: {config.agent.agent_type}")
    runner.set_env(env)
    runner.set_agent(llm_agent)
    
    try:
        score, step = runner.play()
    finally:
        if env:
            env.close()

    # save result
    out_path = f"{config.env.log_path}/final_score.json"
    result = {
        "game": config.env_name,
        "llm": config.agent.llm_name,
        "agent_type": config.agent.agent_type,
        "task": config.env.task,
        "score": score,
        "final_step": step,
        "action_mode": config.env.action_mode
    }
    
    # Add game_mode if available (for snake game)
    # Add an extra field to preserve realtime/discrete mode
    if config.env_name == "Snake" and hasattr(config.env, 'game_mode'):
        result["game_mode"] = config.env.game_mode
        logger.info(f"Game Mode: {config.env.game_mode}")
        if config.env.game_mode == "realtime":
            if hasattr(config.env, 'action_timeout'):
                result["action_timeout"] = config.env.action_timeout
            if hasattr(config.env, 'max_duration'):
                result["max_duration"] = config.env.max_duration
    
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=4)

    logger.info(f"Game: {config.env_name}")
    logger.info(f"LLM: {config.agent.llm_name}")
    logger.info(f"Agent: {config.agent.agent_type}")
    logger.info(f"Task: {config.env.task}")
    logger.info(f"Score: {score}")
    logger.info(f"Step: {step}")
    logger.info(f"Action Mode: {config.env.action_mode}")
    
    # Generate MP4 video
    logger.info("Starting obs_images video generation...")
    video_path = create_video_from_log_path(config.env.log_path, fps=2)
    if video_path:
        logger.info(f"Video generated successfully: {video_path}")
    else:
        logger.warning("Video generation failed or obs_images directory not found")


if __name__ == "__main__":
    main()
