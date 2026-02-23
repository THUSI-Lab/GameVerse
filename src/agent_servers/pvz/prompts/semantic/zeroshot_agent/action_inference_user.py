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
    f"Based on the current game screenshot, analyze the situation and decide your next action.\n"
    f"Consider: current sunlight, zombie positions, plant placement, and available plants.\n\n"
    f"You should only respond in the format described below, and you should not output comments or other information.\n"
    f"Provide your response in the strict format:\n"
    f"### Reasoning\n<detailed strategic analysis>\n"
    f"### Actions\n<your action command>\n"
)
