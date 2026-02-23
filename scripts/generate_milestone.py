"""
Script: extract game milestones from an expert video.
Reads parameters from a config file, analyzes the expert video, and saves milestones.
"""
import argparse
import logging
import os
import sys
import json

# Add src directory to Python path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
src_path = os.path.join(project_root, 'src')
if src_path not in sys.path:
    sys.path.insert(0, src_path)

from omegaconf import OmegaConf
from agent_servers.video_reflection import extract_milestones_from_expert_video, find_expert_video, get_model_type
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
        description='Extract game milestones from an expert video (using config file parameters)',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python generate_milestone.py --config src/agent_client/configs/twenty_fourty_eight/config.yaml
        """
    )
    parser.add_argument(
        '--config',
        type=str,
        required=True,
        help='config file path (agent_client config file)'
    )
    parser.add_argument(
        '--expert_video_path',
        type=str,
        default=None,
        help='expert video path (auto-discovered if not specified in config)'
    )
    
    return parser.parse_args()


def calculate_milestone_statistics(milestones_data: dict) -> dict:
    """
    Compute milestone statistics.

    Args:
        milestones_data: Milestone data dictionary.

    Returns:
        Statistics dictionary.
    """
    milestones = milestones_data.get("milestones", [])
    
    # Total count
    total_count = len(milestones)
    
    # Distribution by category
    category_count = {}
    for milestone in milestones:
        category = milestone.get("category", "Unknown")
        category_count[category] = category_count.get(category, 0) + 1
    
    # Distribution by importance
    importance_count = {}
    for milestone in milestones:
        importance = milestone.get("importance", "Unknown")
        importance_count[importance] = importance_count.get(importance, 0) + 1
    
    # Compute time range
    time_ranges = []
    for milestone in milestones:
        timestamp = milestone.get("timestamp", "")
        if " - " in timestamp:
            try:
                start_time = float(timestamp.split(" - ")[0])
                time_ranges.append(start_time)
            except:
                pass
    
    min_time = min(time_ranges) if time_ranges else 0
    max_time = max(time_ranges) if time_ranges else 0
    
    statistics = {
        "total_milestones": total_count,
        "category_distribution": category_count,
        "importance_distribution": importance_count,
        "time_range": {
            "min_time": min_time,
            "max_time": max_time,
            "duration": max_time - min_time if max_time > min_time else 0
        }
    }
    
    return statistics


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
    
    # Get milestone_model from env config
    env_cfg = cfg.get("env", {})
    milestone_model = env_cfg.get("milestone_model")
    
    if not milestone_model:
        logger.error("env.milestone_model was not found in config")
        sys.exit(1)
    
    # Get agent config (API settings)
    agent_cfg = cfg.get("agent", {})
    api_key = agent_cfg.get("api_key", "")
    api_base_url = agent_cfg.get("api_base_url", "")
    temperature = agent_cfg.get("temperature", 0.7)
    
    # Resolve expert video path (priority: CLI arg > config > auto-discovery)
    expert_video_path = args.expert_video_path
    if not expert_video_path:
        # Try reading from reflection_generation in config
        reflection_gen = agent_cfg.get("reflection_generation", {})
        if reflection_gen and reflection_gen.get("expert_video_path"):
            expert_video_path = reflection_gen.get("expert_video_path")
            # Normalize path separators (Windows/Unix)
            expert_video_path = os.path.normpath(expert_video_path)
            # Convert relative path to absolute path
            if not os.path.isabs(expert_video_path):
                expert_video_path = os.path.join(project_root, expert_video_path)
            expert_video_path = os.path.normpath(expert_video_path)
    
    if not expert_video_path:
        # Try searching based on log_path in config
        log_path = cfg.get("log_path", "")
        if log_path:
            expert_video_path = find_expert_video(game_name, log_path)
        else:
            # Search from project root
            expert_video_path = find_expert_video(game_name, str(project_root))
    
    if not expert_video_path or not os.path.exists(expert_video_path):
        logger.error(f"Expert video not found: {expert_video_path}")
        sys.exit(1)
    
    expert_video_path = os.path.abspath(expert_video_path)
    
    logger.info(f"Game name: {game_name}")
    logger.info(f"Milestone extraction model: {milestone_model}")
    logger.info(f"Expert video: {expert_video_path}")
    
    # Load LLM
    logger.info(f"Loading LLM: {milestone_model}")
    try:
        loaded_model = load_model(
            milestone_model,
            temperature=temperature,
            api_key=api_key if api_key else None,
            api_base_url=api_base_url if api_base_url else None
        )
        llm = loaded_model["llm"]
    except Exception as e:
        logger.error(f"Failed to load LLM: {e}")
        sys.exit(1)
    
    # Extract milestones
    logger.info("Analyzing expert video and extracting milestones...")
    model_type = get_model_type(milestone_model)
    milestones_data = extract_milestones_from_expert_video(
        llm=llm,
        model_type=model_type,
        game_name=game_name,
        expert_video_path=expert_video_path
    )
    
    if not milestones_data or not milestones_data.get("milestones"):
        logger.error("Milestone extraction failed or no milestones were found")
        sys.exit(1)
    
    logger.info(f"Successfully extracted {len(milestones_data['milestones'])} milestones")
    
    # Create output directory
    output_dir = os.path.join(project_root, "data", "milestone", game_name)
    os.makedirs(output_dir, exist_ok=True)
    
    # Save milestone JSON
    milestone_file = os.path.join(output_dir, "milestones.json")
    with open(milestone_file, 'w', encoding='utf-8') as f:
        json.dump(milestones_data, f, ensure_ascii=False, indent=2)
    
    logger.info(f"Milestones saved to: {milestone_file}")
    
    # Compute and save statistics
    statistics = calculate_milestone_statistics(milestones_data)
    statistics_file = os.path.join(output_dir, "statistics.json")
    with open(statistics_file, 'w', encoding='utf-8') as f:
        json.dump(statistics, f, ensure_ascii=False, indent=2)
    
    logger.info(f"Statistics saved to: {statistics_file}")
    logger.info(f"Total milestones: {statistics['total_milestones']}")
    logger.info(f"Category distribution: {statistics['category_distribution']}")
    logger.info(f"Importance distribution: {statistics['importance_distribution']}")
    logger.info(f"Time range: {statistics['time_range']['min_time']:.2f} - {statistics['time_range']['max_time']:.2f} seconds")


if __name__ == "__main__":
    main()

