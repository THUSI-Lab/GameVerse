# flake8: noqa
"""
Angry Birds GUI Mode User Prompt
"""

PROMPT = (
    "### **Previous state:**\n"
    "<|prev_state_image|>\n\n"

    "### **Last executed action:**\n"
    "{action}\n\n"

    "### **Current state:**\n"
    "<|cur_state_image|>\n\n"

    "Analyze the current game screenshot and output the GUI action(s) to execute.\n"
    "Remember to use absolute pixel coordinates based on the window size ({window_width}x{window_height}).\n"
    "Estimate the pixel positions of UI elements (slingshot, targets, etc.) from the screenshot.\n\n"

    "You should only respond in the format described below.\n"
    "Provide your response in the strict format:\n"
    "### Reasoning\n<detailed strategic analysis>\n"
    "### Actions\n```json\n<your GUI action JSON>\n```\n"
)
