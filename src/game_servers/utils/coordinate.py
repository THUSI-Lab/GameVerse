def transform_coordinate(value: int, max_val: int, normalize_scale: int = 1000) -> int:
    """
    Transform and clamp coordinate from normalized scale to actual resolution.
    
    Args:
        value: The normalized coordinate value (e.g. from 0-1000)
        max_val: The actual screen dimension (width or height)
        normalize_scale: The normalization scale (default 1000)
        
    Returns:
        The transformed coordinate, clamped between 0 and max_val-1
    """
    new_val = int(value / normalize_scale * max_val)
    # Clamp to [0, max_val - 1]
    return max(0, min(new_val, max_val - 1))
