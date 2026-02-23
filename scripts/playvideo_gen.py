"""
Script: generate an obs_images video from a logs path.
Given a run log path, convert files in obs_images into an MP4.
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

from game_servers.utils.video_generator import create_video_from_log_path


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
        description='Generate an obs_images video from a logs path',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python playvideo_gen.py --log_path logs/Pwaat/qwen3-vl-32b-instruct/gui/memory_agent/20251209_131702
  python playvideo_gen.py --log_path logs/Pwaat/qwen3-vl-32b-instruct/gui/memory_agent/20251209_131702 --fps 5
        """
    )
    parser.add_argument(
        '--log_path',
        type=str,
        required=True,
        help='logs path (should contain an obs_images directory)'
    )
    parser.add_argument(
        '--fps',
        type=int,
        default=2,
        help='video frame rate (frames per second), default is 2'
    )
    parser.add_argument(
        '--output',
        type=str,
        default=None,
        help='output MP4 path; if omitted, auto-generated under log_path'
    )
    
    return parser.parse_args()


def main():
    """Main entry point."""
    setup_logging()
    logger = logging.getLogger(__name__)
    
    args = parse_args()
    
    # Check whether log_path exists
    log_path = os.path.abspath(args.log_path)
    if not os.path.exists(log_path):
        logger.error(f"Specified logs path does not exist: {log_path}")
        sys.exit(1)
    
    # Check whether obs_images directory exists
    obs_images_dir = os.path.join(log_path, "obs_images")
    if not os.path.exists(obs_images_dir):
        logger.error(f"obs_images directory not found under {log_path}")
        sys.exit(1)
    
    logger.info(f"Starting video generation from {log_path}...")
    logger.info(f"obs_images directory: {obs_images_dir}")
    logger.info(f"Frame rate: {args.fps} fps")
    
    # Generate video
    if args.output:
        # Use images_to_video when an explicit output path is provided
        from game_servers.utils.video_generator import images_to_video
        video_path = images_to_video(obs_images_dir, output_path=args.output, fps=args.fps)
    else:
        video_path = create_video_from_log_path(log_path, fps=args.fps)
    
    if video_path:
        logger.info(f"Video generated successfully: {video_path}")
        logger.info("You can open this file with any video player")
    else:
        logger.error("Video generation failed")
        sys.exit(1)


if __name__ == "__main__":
    main()

