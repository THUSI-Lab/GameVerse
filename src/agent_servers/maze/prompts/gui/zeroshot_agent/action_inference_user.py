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
    f"Provide your response in the strict format:\n"
    f"### Reasoning\n"
    f"<a detailed summary of why this direction was chosen based on visual analysis of the maze>\n"
    f"### Actions\n"
    f"```json\n"
    f"<your action in JSON format>\n"
    f"```\n"
)

