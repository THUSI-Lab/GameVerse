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
    "You should only respond in the format described below, and you should not output comments or other information.\n"
    "Provide your response strictly in the format below: \n"
    "### Reasoning\n<a detailed summary of why this action was chosen>\n"
    "### Actions\n"
    "```json\n"
    "{{\n"
    '    "action_type": "PRESS",\n'
    '    "parameters": {{\n'
    '        "key": "<up|down|left|right>"\n'
    "    }}\n"
    "}}\n"
)
