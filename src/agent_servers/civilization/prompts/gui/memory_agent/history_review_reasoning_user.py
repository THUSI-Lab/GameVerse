# flake8: noqa

PROMPT = (
    f"### Previous History Summary\n"
    f"{{prev_history_summary}}\n\n"
    f"**IMPORTANT**: Update this summary to 500-600 words using importance-based replacement. "
    f"Preserve CRITICAL/HIGH importance info, compress/merge similar info, replace LOW/MEDIUM with new HIGH info.\n\n"
    
    f"### Recent Historical Image+Action Pairs (Most Recent 5, Excluding Current State)\n"
    f"{{recent_pairs_count}} pairs available.\n\n"
    
    f"#### Pair 1 (Oldest)\n"
    f"**Image 1:**\n"
    f"<|recent_image_0|>\n\n"
    f"**Action 1:** {{recent_action_0}}\n"
    f"**Observation 1:** {{recent_observation_0}}\n\n"
    
    f"#### Pair 2\n"
    f"**Image 2:**\n"
    f"<|recent_image_1|>\n\n"
    f"**Action 2:** {{recent_action_1}}\n"
    f"**Observation 2:** {{recent_observation_1}}\n\n"
    
    f"#### Pair 3\n"
    f"**Image 3:**\n"
    f"<|recent_image_2|>\n\n"
    f"**Action 3:** {{recent_action_2}}\n"
    f"**Observation 3:** {{recent_observation_2}}\n\n"
    
    f"#### Pair 4\n"
    f"**Image 4:**\n"
    f"<|recent_image_3|>\n\n"
    f"**Action 4:** {{recent_action_3}}\n"
    f"**Observation 4:** {{recent_observation_3}}\n\n"
    
    f"#### Pair 5 (Most Recent Historical)\n"
    f"**Image 5:**\n"
    f"<|recent_image_4|>\n\n"
    f"**Action 5:** {{recent_action_4}}\n"
    f"**Observation 5:** {{recent_observation_4}}\n\n"
    
    f"### Current Game State (Image)\n"
    f"<|cur_state_image|>\n\n"
    
    f"### Retrieved Long-term Memory\n"
    f"{{retrieved_memory_str}}\n\n"
    
    f"**Update Instructions**:\n"
    f"1. Assess importance of all information (CRITICAL/HIGH/MEDIUM/LOW)\n"
    f"2. Preserve all CRITICAL info from previous summary\n"
    f"3. Preserve HIGH info unless new HIGH info needs space\n"
    f"4. Compress/merge similar information (e.g., multiple city updates)\n"
    f"5. Replace LOW importance old info with new HIGH importance info\n"
    f"6. Replace MEDIUM importance old info if still over 600 words\n"
    f"7. Integrate new insights from recent 5 pairs\n"
    f"8. Use dense, concise language. Target: 500-600 words.\n\n"
    
    f"**Focus Areas** (prioritize in summary):\n"
    f"- Strategic decisions (CRITICAL)\n"
    f"- Resource locations (HIGH)\n"
    f"- Diplomatic relationships (HIGH)\n"
    f"- City planning (HIGH)\n"
    f"- Military positions (MEDIUM-HIGH)\n\n"
    
    f"### History_summary\n"
    f"[Updated summary (500-600 words) using importance-based replacement and compression]\n\n"
    f"### Reasoning\n"
    f"[Your reasoning]\n\n"
    f"### Plan\n"
    f"[Your plan]\n\n"
)

