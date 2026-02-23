# flake8: noqa

PROMPT = (
    "### Target task\n"
    "{task_description}\n\n"
    "### Previous state\n"
    "<|prev_state_image|>\n\n"
    "### Last executed action\n"
    "{action}\n\n"
    "### Current state\n"
    "<|cur_state_image|>\n\n"
    # f"{{cur_state_str}}\n\n"
    "### Navigation & Exploration Guidelines\n"
    "- Look Around: Use camera movement (MOVE_BY) to adjust your view first, confirming the target direction and passable paths.\n"
    "- Identify Clues: Observe the mini-map, yellow quest markers/distance numbers, terrain paths, stairs, bridges, and interaction prompts.\n"
    "- Plan Path: Choose the shortest and safest route. If necessary, open the map (PRESS 'm') or use the navigation key (PRESS 'v').\n"
    "- Control Strategy: Move in steps and WAIT to observe. Avoid depleting stamina. Jump, climb, or detour around obstacles.\n"
    "- Arrival Interaction: Upon reaching the target, press 'F' to confirm, talk, or activate mechanisms.\n\n"
    "You should only respond in the format described below, and you should not output comments or other information.\n"
    "Provide your response in the strict format:\n"
    "### Reasoning\n"
    "[Analyze the screenshot to explain your exploration strategy: how you look around, identify clues, plan the route to the target point, and the intent of each step]\n\n"
    f"### Actions\n"
    "```json\n"
    "[\n"
    '    {{"action_type": "...", "parameters": {{...}}}}\n'
    "]\n"
    "```\n\n"
)
