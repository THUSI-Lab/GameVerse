# flake8: noqa

PROMPT = (
    f"### Target task\n"
    f"{{task_description}}\n\n"
    f"### Previous state\n"
    f"<|prev_state_image|>\n\n"
    f"### Last executed action\n"
    f"{{action}}\n\n"
    f"### Current state\n"
    f"<|cur_state_image|>\n\n"
    f"You should only respond in the format described below, and you should not output comments or other information.\n"
    f"Provide your response in the following format.\n\n"
    f"### Reasoning\n"
    f"[Analyze the screenshot and explain what UI element you want to interact with and why]\n\n"
    f"### Actions\n"
    "```json\n"
    "[\n"
    '    {{"action_type": "...", "parameters": {{...}}}}\n'
    
    "]\n"
    "```\n\n"
)
