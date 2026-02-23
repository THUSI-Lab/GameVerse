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
    f"Note: the index of monsters did not change after it was gone. You should use the string description of the current monsters instead of the screenshot number to avoid attacking dead monsters.\n"
    f"{{cur_state_str}}\n\n" # str方式描述怪物index，防止输出攻击死怪物的动作
    f"### Your Response\n"
    f"Respond in the following format:\n\n"
    f"### Reasoning\n"
    f"[Describe what you see in the image and your strategic thinking]\n\n"
    f"### Actions\n"
    f"[Your action commands, one per line]"
)
