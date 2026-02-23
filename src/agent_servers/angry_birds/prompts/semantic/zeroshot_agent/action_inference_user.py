# flake8: noqa
"""
Angry Birds User Prompt for Semantic Action Mode
"""

PROMPT = (
    "### Target task\n"
    "{task_description}\n\n"

    "### Previous state\n"
    "<|prev_state_image|>\n\n"

    "### Current state\n"
    "<|cur_state_image|>\n\n"

    "Based on the current game screenshot, analyze the situation and decide your next action.\n\n"

    "### Available Actions\n"
    "- shoot(angle=X, power=Y): Launch the current bird\n"
    "  * angle: 0-90 degrees (0=horizontal right, 90=vertical up)\n"
    "  * power: 0.0-1.0 (shot strength)\n"
    "- wait(): Observe physics simulation without shooting (use after shots to see full impact)\n\n"

    "### Output Format\n"
    "Analyze the screenshot and provide your action:\n\n"
    "```\n"
    "### Reasoning\n"
    "<Your analysis of pig positions, structures, and chosen strategy>\n\n"
    "### Actions\n"
    "[shoot(angle=X, power=Y)] or [wait()]\n"
    "```\n"
)
