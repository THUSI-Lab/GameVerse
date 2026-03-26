"""
Script: generate video-based reflection experience from logs.
Reads parameters from a config file, analyzes failure and expert videos, and saves reflections.
"""
import argparse
import logging
import os
import sys
from typing import List

# Add src directory to Python path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
src_path = os.path.join(project_root, 'src')
if src_path not in sys.path:
    sys.path.insert(0, src_path)

from omegaconf import OmegaConf
from agent_servers.video_reflection import reflect_from_videos, reflect_from_multiple_failure_videos
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
        '--failure_video_paths',
        nargs='+',
        default=None,
        help='multiple failure video paths for multi-video reflection'
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
        '--obs_images_dirs',
        nargs='+',
        default=None,
        help='multiple obs_images directories corresponding to --failure_video_paths'
    )
    parser.add_argument(
        '--max_length',
        type=int,
        default=None,
        help='max reflection text length (CLI takes precedence, config fallback, default 1000)'
    )
    
    return parser.parse_args()


def merge_multi_video_reflections(reflection_texts: List[str], failure_video_paths: List[str], game_name: str) -> str:
    """Concatenate reflections from multiple failure videos with a simple source note."""
    valid_texts = [text.strip() for text in reflection_texts if text and text.strip()]
    if not valid_texts:
        return ""

    header = [
        f"Multi-video reflection summary for {game_name}.",
        "The following experience is concatenated from multiple failure videos."
    ]
    body = []
    for idx, text in enumerate(valid_texts, start=1):
        body.append(f"\n[Reflection from failure video {idx}]\n{text}")

    return "\n".join(header) + "\n" + "\n".join(body)


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
    
    # Resolve failure video path(s)
    failure_video_paths = []
    if args.failure_video_paths:
        failure_video_paths = [os.path.abspath(path) for path in args.failure_video_paths]
    elif args.failure_video_path:
        failure_video_paths = [os.path.abspath(args.failure_video_path)]
    else:
        cfg_failure_video = reflection_cfg.get("failure_video_path")
        if cfg_failure_video:
            failure_video_paths = [os.path.abspath(cfg_failure_video)]

    if not failure_video_paths:
        logger.error("failure_video_path(s) are not specified (via CLI arguments or config)")
        sys.exit(1)

    for failure_video_path in failure_video_paths:
        if not os.path.exists(failure_video_path):
            logger.error(f"Failure video does not exist: {failure_video_path}")
            sys.exit(1)
    
    # Resolve expert video path (optional; empty means ablation without expert video)
    if args.expert_video_path is not None:
        expert_video_path = args.expert_video_path
    else:
        expert_video_path = reflection_cfg.get("expert_video_path")

    if expert_video_path is not None:
        expert_video_path = str(expert_video_path).strip()

    if expert_video_path in ["", "null", "none", "None"]:
        expert_video_path = None

    if expert_video_path:
        expert_video_path = os.path.abspath(expert_video_path)
        if not os.path.exists(expert_video_path):
            logger.error(f"Expert video does not exist: {expert_video_path}")
            sys.exit(1)
    
    # Resolve obs_images directory path(s) (optional, CLI has priority)
    obs_images_dirs = None
    if args.obs_images_dirs:
        obs_images_dirs = [os.path.abspath(path) for path in args.obs_images_dirs]
    elif args.obs_images_dir:
        obs_images_dirs = [os.path.abspath(args.obs_images_dir)]
    else:
        cfg_obs_images_dir = reflection_cfg.get("obs_images_dir")
        if cfg_obs_images_dir:
            obs_images_dirs = [os.path.abspath(cfg_obs_images_dir)]
        else:
            # If not specified, infer from log_path
            if args.log_path:
                log_path = os.path.abspath(args.log_path)
                inferred = os.path.join(log_path, "obs_images")
                obs_images_dirs = [inferred]
            else:
                log_path = cfg.get("log_path", "")
                if log_path:
                    inferred = os.path.join(log_path, "obs_images")
                    obs_images_dirs = [os.path.abspath(inferred)]

    if obs_images_dirs:
        normalized_obs_dirs = []
        for obs_images_dir in obs_images_dirs:
            obs_images_dir = os.path.abspath(obs_images_dir)
            if not os.path.exists(obs_images_dir):
                logger.warning(f"obs_images directory does not exist: {obs_images_dir}; it will be ignored")
                normalized_obs_dirs.append(None)
            else:
                normalized_obs_dirs.append(obs_images_dir)
        obs_images_dirs = normalized_obs_dirs

    if len(failure_video_paths) == 1 and obs_images_dirs and len(obs_images_dirs) > 1:
        obs_images_dirs = [obs_images_dirs[0]]
    
    # Get reflection storage format
    reflection_format = agent_cfg.get("reflection_format", "json")
    
    logger.info(f"Game name: {game_name}")
    logger.info(f"LLM: {llm_name}")
    if len(failure_video_paths) == 1:
        logger.info(f"Failure video: {failure_video_paths[0]}")
    else:
        logger.info(f"Failure videos ({len(failure_video_paths)}):")
        for i, path in enumerate(failure_video_paths, start=1):
            logger.info(f"  {i}. {path}")
    logger.info(f"Expert video: {expert_video_path if expert_video_path else 'None (ablation mode)'}")
    if obs_images_dirs:
        logger.info(f"obs_images directories ({len(obs_images_dirs)}):")
        for i, obs_dir in enumerate(obs_images_dirs, start=1):
            logger.info(f"  {i}. {obs_dir}")
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
    if len(failure_video_paths) == 1:
        reflection_text = reflect_from_videos(
            llm=llm,
            model_name=llm_name,
            game_name=game_name,
            failure_video_path=failure_video_paths[0],
            expert_video_path=expert_video_path,
            obs_images_dir=obs_images_dirs[0] if obs_images_dirs else None,
            max_length=max_length
        )
    else:
        reflection_text = reflect_from_multiple_failure_videos(
            llm=llm,
            model_name=llm_name,
            game_name=game_name,
            failure_video_paths=failure_video_paths,
            expert_video_path=expert_video_path,
            obs_images_dirs=obs_images_dirs,
            max_length=max_length,
            merge_reflections_fn=merge_multi_video_reflections
        )
    
    if not reflection_text:
        logger.error("Failed to generate reflection")
        sys.exit(1)
    
    logger.info(f"Generated reflection: {reflection_text[:1000]}...")
    
    # Save reflection
    manager = ReflectionManager()
    metadata = {
        "failure_video": failure_video_paths[0] if len(failure_video_paths) == 1 else None,
        "failure_videos": failure_video_paths if len(failure_video_paths) > 1 else None,
        "expert_video": expert_video_path,
        "obs_images_dir": obs_images_dirs[0] if obs_images_dirs and len(obs_images_dirs) == 1 else None,
        "obs_images_dirs": obs_images_dirs if obs_images_dirs and len(obs_images_dirs) > 1 else None,
        "llm_name": llm_name,
        "max_length": max_length,
        "reflection_mode": "multi-video" if len(failure_video_paths) > 1 else "single-video"
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
