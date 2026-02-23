"""
Script: generate video-based reflection experience from logs.
Reads parameters from a config file, analyzes failure and expert videos, and saves reflections.
"""
import argparse
import logging
import os
import sys

# Add src directory to Python path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
src_path = os.path.join(project_root, 'src')
if src_path not in sys.path:
    sys.path.insert(0, src_path)

from omegaconf import OmegaConf
from agent_servers.video_reflection import reflect_from_videos
from agent_servers.reflection_manager import ReflectionManager
from agent_client.llms.llm import load_model


def setup_logging():
    """Configure logging."""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler()
        ]
    )


def parse_args():
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description='Generate video reflection experience from logs (using config file parameters)',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python generate_reflection.py --config src/agent_client/configs/twenty_fourty_eight/config.yaml --log_path logs/TwentyFourtyEight/...
  python generate_reflection.py --config config.yaml --failure_video_path path/to/fail.mp4 --expert_video_path path/to/expert.mp4
        """
    )
    parser.add_argument(
        '--config',
        type=str,
        required=True,
        help='config file path (agent_client config file)'
    )
    parser.add_argument(
        '--log_path',
        type=str,
        default=None,
        help='logs path (used to infer obs_images if not set in config)'
    )
    parser.add_argument(
        '--failure_video_path',
        type=str,
        default=None,
        help='failure video path (takes precedence over config)'
    )
    parser.add_argument(
        '--expert_video_path',
        type=str,
        default=None,
        help='expert video path (takes precedence over config)'
    )
    parser.add_argument(
        '--obs_images_dir',
        type=str,
        default=None,
        help='obs_images directory path (takes precedence over config)'
    )
    parser.add_argument(
        '--max_length',
        type=int,
        default=None,
        help='max reflection text length (CLI takes precedence, config fallback, default 1000)'
    )
    
    return parser.parse_args()


def main():
    """Main entry point."""
    setup_logging()
    logger = logging.getLogger(__name__)
    
    args = parse_args()
    
    # Load config
    if not os.path.exists(args.config):
        logger.error(f"Config file does not exist: {args.config}")
        sys.exit(1)
    
    try:
        cfg = OmegaConf.load(args.config)
    except Exception as e:
        logger.error(f"Failed to load config file: {e}")
        sys.exit(1)
    
    # Get game name
    game_name = cfg.get("env_name", "")
    if not game_name:
        logger.error("env_name was not found in config")
        sys.exit(1)
    
    # Get agent config
    agent_cfg = cfg.get("agent", {})
    if not agent_cfg:
        logger.error("agent config was not found in config file")
        sys.exit(1)
    
    # Get LLM configuration
    llm_name = agent_cfg.get("llm_name", "gpt-4o")
    api_key = agent_cfg.get("api_key", "")
    api_base_url = agent_cfg.get("api_base_url", "")
    temperature = agent_cfg.get("temperature", 0.7)
    
    # Get video reflection generation config
    reflection_cfg = agent_cfg.get("reflection_generation", {})
    
    # Resolve max_length (CLI has priority)
    if args.max_length is not None:
        max_length = args.max_length
    else:
        max_length = reflection_cfg.get("max_length", 1000)
    
    # Resolve failure video path (required, CLI has priority)
    if args.failure_video_path:
        failure_video_path = args.failure_video_path
    else:
        failure_video_path = reflection_cfg.get("failure_video_path")
    
    if not failure_video_path or failure_video_path == "":
        logger.error("failure_video_path is not specified (via CLI argument or config)")
        sys.exit(1)
    
    failure_video_path = os.path.abspath(failure_video_path)
    if not os.path.exists(failure_video_path):
        logger.error(f"Failure video does not exist: {failure_video_path}")
        sys.exit(1)
    
    # Resolve expert video path (required, CLI has priority)
    if args.expert_video_path:
        expert_video_path = args.expert_video_path
    else:
        expert_video_path = reflection_cfg.get("expert_video_path")
    
    if not expert_video_path or expert_video_path == "":
        logger.error("expert_video_path is not specified (via CLI argument or config)")
        sys.exit(1)
    
    expert_video_path = os.path.abspath(expert_video_path)
    if not os.path.exists(expert_video_path):
        logger.error(f"Expert video does not exist: {expert_video_path}")
        sys.exit(1)
    
    # Resolve obs_images directory path (optional, CLI has priority)
    if args.obs_images_dir:
        obs_images_dir = args.obs_images_dir
    else:
        obs_images_dir = reflection_cfg.get("obs_images_dir")
        if not obs_images_dir or obs_images_dir == "":
            # If not specified, infer from log_path
            if args.log_path:
                log_path = os.path.abspath(args.log_path)
                obs_images_dir = os.path.join(log_path, "obs_images")
            else:
                log_path = cfg.get("log_path", "")
                if log_path:
                    obs_images_dir = os.path.join(log_path, "obs_images")
    
    if obs_images_dir:
        obs_images_dir = os.path.abspath(obs_images_dir)
        if not os.path.exists(obs_images_dir):
            logger.warning(f"obs_images directory does not exist: {obs_images_dir}; it will be ignored")
            obs_images_dir = None
    
    # Get reflection storage format
    reflection_format = agent_cfg.get("reflection_format", "json")
    
    logger.info(f"Game name: {game_name}")
    logger.info(f"LLM: {llm_name}")
    logger.info(f"Failure video: {failure_video_path}")
    logger.info(f"Expert video: {expert_video_path}")
    if obs_images_dir:
        logger.info(f"obs_images directory: {obs_images_dir}")
    logger.info(f"Max length: {max_length}")
    
    # Load LLM
    logger.info(f"Loading LLM: {llm_name}")
    try:
        loaded_model = load_model(
            llm_name,
            temperature=temperature,
            api_key=api_key if api_key else None,
            api_base_url=api_base_url if api_base_url else None
        )
        llm = loaded_model["llm"]
    except Exception as e:
        logger.error(f"Failed to load LLM: {e}")
        sys.exit(1)
    
    # Generate reflection
    logger.info("Analyzing videos and generating reflection...")
    reflection_text = reflect_from_videos(
        llm=llm,
        model_name=llm_name,
        game_name=game_name,
        failure_video_path=failure_video_path,
        expert_video_path=expert_video_path,
        obs_images_dir=obs_images_dir,
        max_length=max_length
    )
    
    if not reflection_text:
        logger.error("Failed to generate reflection")
        sys.exit(1)
    
    logger.info(f"Generated reflection: {reflection_text[:1000]}...")
    
    # Save reflection
    manager = ReflectionManager()
    metadata = {
        "failure_video": failure_video_path,
        "expert_video": expert_video_path,
        "obs_images_dir": obs_images_dir,
        "llm_name": llm_name,
        "max_length": max_length
    }
    
    success = manager.save_reflection(
        game_name=game_name,
        reflection_text=reflection_text,
        metadata=metadata,
        format=reflection_format,
        max_length=max_length
    )
    
    if success:
        logger.info(f"Reflection saved successfully to: {manager.get_reflection_path(game_name, reflection_format)}")
    else:
        logger.error("Failed to save reflection")
        sys.exit(1)


if __name__ == "__main__":
    main()
