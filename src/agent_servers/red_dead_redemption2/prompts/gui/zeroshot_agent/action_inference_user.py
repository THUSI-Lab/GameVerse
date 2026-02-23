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
    f"[Analyze the screenshot and explain what action you want to take and why."
    "Consider whether the last action resulted in noticeable positional or scene changes. "
    "If little or no change is observed, take this into account when deciding the next action, "
    "to avoid ineffective repetition or getting stuck against invisible barriers or obstacles.]\n\n"
    f"### Actions\n"
    "```json\n"
    "[\n"
    '    {{"action_type": "...", "parameters": {{...}}}}\n'
    "]\n"
    "```\n\n"
)
