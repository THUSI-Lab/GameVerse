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
    f"Please analyze the board image carefully and make your move based on the visual information.\n"
    f"You are in GUI mode, so you must output mouse click coordinates in JSON format.\n"
    f"**IMPORTANT**: Before making your move, carefully examine the image to ensure that the position you want to choose is empty and not already occupied by X or O.\n"
    f"Clicking outside the board or on an occupied position will result in immediate loss.\n"
    f"You should only respond in the format described below, and you should not output comments or other information.\n"
    f"Provide your response in the strict format:\n"
    f"### Reasoning\n"
    f"<a detailed summary of why this move was chosen based on visual analysis>\n"
    f"### Actions\n"
    f"```json\n"
    f"<your action in JSON format>\n"
    f"```\n"
)
