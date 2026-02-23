# flake8: noqa
PROMPT = (
    "You are an AI agent playing 'Maze New': navigate a blue ball to a red target in a {maze_size}×{maze_size} black-white maze.\n\n"

    "### Game Rules ###\n"
    "- {maze_size}×{maze_size} grid: black walls (50%+) and white paths\n"
    "- Blue circle = your ball, Red circle = target (both randomly placed on white paths)\n"
    "- No grid lines; blocks are seamlessly connected\n"
    "- Win when ball reaches target\n\n"
    f"### Task ###\n"
    f"- Infer the shortest valid path from the blue ball starting point to the red goal circle.\n"
    f"- Movement can only occur between adjacent open tiles — up, down, left, or right.\n"
    f"- Diagonal movement is not allowed, and the path must not cross or touch any black walls.\n"


    "### Movement ###\n"
    "- One cell per action (up/down/left/right)\n"
    "- Can only move to white paths (not black walls)\n"
    "- Invalid moves fail silently (ball stays in place)\n\n"

    "### Learned Experience from Previous Attempts ### \n"
    "{reflection_experience}\n"
    "Note: The above experience comes from analyzing previous failed attempts and expert playthroughs. "
    "Use these insights to improve your strategy and avoid repeating past mistakes.\n\n"

    "### Decision Output Format ### \n"
    "Analyze the provided game state and determine the **single most optimal action** to take next. \n"

    "Return your decision in the following exact format: \n"
    '### Reasoning\n<a detailed summary of why this direction was chosen based on visual analysis of the maze>\n### Actions\n<up, down, left, or right>\n\n'

    "Ensure that: \n"
    "- The '### Reasoning' field provides a clear explanation of why the direction is the best choice, including analysis of the maze layout, ball position, target position, and path planning.\n"
    "- The '### Actions' field contains only one of the four valid directions: 'up', 'down', 'left', or 'right'.\n"
)

