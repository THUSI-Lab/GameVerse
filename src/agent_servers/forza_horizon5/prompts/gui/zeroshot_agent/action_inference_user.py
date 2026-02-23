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
    "You should only respond in the format described below, and you should not output comments or other information.\n"
    "Provide your response in the strict format:\n"
    "### Reasoning\n"
    f"[Analyze the screenshot and explain what driving action you want to take and why]\n\n"
    f"### Actions\n"
    "```json\n"
    "[\n"
    '    {{"action_type": "...", "parameters": {{...}}}}\n'
    "]\n"
    "```\n\n"
)
