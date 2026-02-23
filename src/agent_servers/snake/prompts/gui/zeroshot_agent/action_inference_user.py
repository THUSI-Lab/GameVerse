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

    "### Your Response Format ### \n"
    "First, analyze the provided game state image and explain your reasoning. \n"
    "Then, output your keyboard action in the JSON format above. \n\n"

    "Response template: \n"
    "### Reasoning\n"
    "<explain why you choose this direction based on visual analysis, including the RED APPLE position, obstacles, and potential dangers>\n\n"
    "### Actions\n"
    "```json\n"
    "<your action in JSON format>\n"
    "```\n\n"

    "- The '### Reasoning' field provides a clear explanation based on what you see in the image. \n"
    "- The '### Actions' field contains exactly the JSON format with PRESS action and key. \n"
)
