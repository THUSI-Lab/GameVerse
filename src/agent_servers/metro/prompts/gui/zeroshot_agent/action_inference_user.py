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
    f"{{cur_state_str}}\n\n" # str方式描述站点和UI图标位置
    "You should only respond in the format described below, and you should not output comments or other information.\n"
    "Provide your response in the strict format:\n"
    "### Reasoning\n"
    f"[Analyze the screenshot and explain what UI element you want to interact with and why]\n\n"
    f"### Actions\n"
    "```json\n"
    "[\n"
    '    {{"action_type": "...", "parameters": {{...}}}}\n'
    "]\n"
    "```\n\n"
)