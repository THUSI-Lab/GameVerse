"""
Utility module: convert images in an obs_images directory into an MP4 video.
"""
import os
import logging
from pathlib import Path
from typing import Optional
import imageio
import numpy as np
from PIL import Image

logger = logging.getLogger(__name__)


def images_to_video(
    obs_images_dir: str,
    output_path: Optional[str] = None,
    fps: int = 2
) -> str:
    """
    Convert images in an obs_images directory into an MP4 video.

    Args:
        obs_images_dir: Path to the obs_images directory.
        output_path: Output MP4 path. If None, it is generated automatically.
        fps: Video frame rate (frames per second).

    Returns:
        The generated MP4 file path, or an empty string on failure.
    """
    obs_images_path = Path(obs_images_dir)
    
    if not obs_images_path.exists():
        logger.warning(f"obs_images directory does not exist: {obs_images_dir}")
        return ""
    
    # Collect all step_*.png files and sort by filename
    # image_files = sorted(obs_images_path.glob("step_*.png"))
    # Extract trailing numeric index to avoid lexical order issues (e.g., step_10 before step_3)
    try:
        image_files = sorted(obs_images_path.glob("step_*.png"), key=lambda x: int(x.stem.split('_')[-1]))
    except ValueError:
        # Fallback to default sort if filenames do not match the expected numeric suffix format
        logger.warning("Unexpected filename format; falling back to default lexical sorting")
        image_files = sorted(obs_images_path.glob("step_*.png"))
    
    if not image_files:
        logger.warning(f"No step_*.png files found in {obs_images_dir}")
        return ""
    
    logger.info(f"Found {len(image_files)} images. Starting video generation...")
    
    # If output_path is not provided, create the video in the parent directory of obs_images
    if output_path is None:
        parent_dir = obs_images_path.parent
        output_path = os.path.join(parent_dir, "obs_video.mp4")
    
    # Ensure output directory exists
    output_dir = os.path.dirname(output_path)
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)
    
    # Read all images
    images = []
    for img_file in image_files:
        try:
            img = Image.open(img_file)
            # Convert to RGB for compatibility
            if img.mode != 'RGB':
                img = img.convert('RGB')
            images.append(img)
        except Exception as e:
            logger.warning(f"Failed to read image {img_file}: {e}")
            continue
    
    if not images:
        logger.error("No usable images available for video generation")
        return ""
    
    # Generate video with imageio
    try:
        # Get frame size from the first image
        width, height = images[0].size
        
        # Create video writer
        writer = imageio.get_writer(
            output_path,
            fps=fps,
            codec='libx264',
            quality=8,
            pixelformat='yuv420p'
        )
        
        # Write all frames
        for img in images:
            # Ensure consistent frame dimensions
            if img.size != (width, height):
                img = img.resize((width, height), Image.Resampling.LANCZOS)
            # Convert PIL Image to numpy array
            img_array = np.array(img)
            writer.append_data(img_array)
        
        writer.close()
        
        logger.info(f"Video generated successfully: {output_path}")
        logger.info(f"Video info: {len(images)} frames, {fps} fps, resolution: {width}x{height}")
        
        return output_path
        
    except Exception as e:
        logger.error(f"Error while generating video: {e}")
        return ""


def create_video_from_log_path(log_path: str, fps: int = 2) -> str:
    """
    Auto-discover obs_images under log_path and generate a video.

    Args:
        log_path: Log directory path.
        fps: Video frame rate.

    Returns:
        The generated MP4 file path, or an empty string on failure.
    """
    obs_images_dir = os.path.join(log_path, "obs_images")
    return images_to_video(obs_images_dir, fps=fps)

