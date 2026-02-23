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
    f"Please analyze the game board image carefully and make your move based on the visual information.\n"
    f"**IMPORTANT**: Before choosing a direction, carefully examine the image to:\n"
    f"- Identify the snake's current position and direction\n"
    f"- Locate all food items and their lifespans (numbers on food)\n"
    f"- Identify all obstacles and walls\n"
    f"- Plan your path to avoid hitting walls, obstacles, or your own body\n"
    f"- Consider which food to prioritize based on value (red=positive, yellow=negative) and lifespan\n"
    f"- Remember you cannot reverse direction immediately\n"
    f"You should only respond in the format described below, and you should not output comments or other information.\n"
    f"Provide your response in the strict format: \n### Reasoning\n<a detailed summary of why this direction was chosen based on visual analysis>\n### Actions\n<direction: L, R, U, or D>\n"
)
