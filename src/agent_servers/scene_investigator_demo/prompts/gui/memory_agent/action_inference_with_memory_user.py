# flake8: noqa

PROMPT = (
    f"### Target task\n"
    f"{{task_description}}\n\n"
    
    f"### History Summary\n"
    f"{{history_summary}}\n\n"
    
    f"### Reasoning\n"
    f"{{reasoning}}\n\n"
    
    f"### Plan\n"
    f"{{plan}}\n\n"
    
    f"### Retrieved Long-term Memory\n"
    f"{{retrieved_memory_str}}\n\n"
    
    f"### Last executed action\n"
    f"{{action}}\n\n"
    
    f"### Current state (image)\n"
    f"<|cur_state_image|>\n\n"
    
    f"**Task**: (1) Analyze screenshot, consider history/reasoning/plan/memories, (2) Determine best action, "
    f"(3) Decide if ANY important info should be saved to long-term memory.\n\n"
    
    f"**Memory Saving**: Save evidence, important clues, locations, observations, patterns, strategic insights. "
    f"Be proactive: when in doubt, save it. Be specific: include context and location.\n\n"
    
    f"### Reasoning\n"
    f"[Your reasoning]\n\n"
    f"### Actions\n"
    "```json\n"
    "[\n"
    '    {{"action_type": "...", "parameters": {{...}}}}\n'
    "]\n"
    "```\n\n"
    f"### New_memory\n"
    f"[Important info with context, or \"None\" if nothing important]\n\n"
    f"### Should_save\n"
    f"[Yes if ANY important info, No ONLY if truly nothing. When in doubt, Yes.]\n\n"
)

