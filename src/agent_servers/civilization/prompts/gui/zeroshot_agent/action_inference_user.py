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
    "### Analysis & Action Decision\n"
    "First, carefully analyze the current screenshot:\n"
    "1. Identify the current game phase (turn number, era, year)\n"
    "2. Check for any notifications or alerts (units awaiting orders, cities needing production, tech completed, etc.)\n"
    "3. Examine your cities: population, production queue, available resources\n"
    "4. Review your units: location, status, movement points available\n"
    "5. Assess strategic situation: neighbors, threats, opportunities for expansion\n"
    "6. Check top panel: gold, science, culture, happiness levels\n"
    "7. Determine highest priority action based on current state\n\n"
    
    "You should only respond in the format described below, and you should not output comments or other information.\n"
    "Provide your response in the strict format:\n\n"
    "[Provide a brief analysis of the screenshot: What do you see? What needs attention? What is your strategic priority this turn?]\n\n"
    
    "### Actions\n"
    "```json\n"
    "[\n"
    '    {{"action_type": "...", "parameters": {{...}}}}\n'
    "]\n"
    "```\n\n"
)
