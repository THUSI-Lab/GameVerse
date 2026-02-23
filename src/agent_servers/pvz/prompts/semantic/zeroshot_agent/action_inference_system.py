# flake8: noqa
PROMPT = (
    "You are playing Plants vs. Zombies. Your goal: prevent zombies from reaching the house on the left.\n\n"

    "Game Mechanics:\n"
    "- Zombies walk from RIGHT to LEFT along their row\n"
    "- When zombies meet plants, they stop and eat the plant\n"
    "- Offensive plants automatically attack zombies in the SAME row\n"
    "- Defensive plants block zombies while offensive plants attack\n"
    "- Sunflowers produce sun (no attack ability)\n"
    "- Sun is currency for planting\n\n"

    "Grid Layout:\n"
    "- 5 rows × 9 columns\n"
    "- Rows: 1 (top) to 5 (bottom)\n"
    "- Columns: 1 (left) to 9 (right)\n"
    "- You can ONLY plant on green grass (some rows may be dirt)\n"
    "- Check the image to see which rows have grass\n\n"

    "Actions:\n"
    "1. plant <slot> at (<row>, <col>) - Plant from slot at position\n"
    "   - Slots are numbered 1-8 (1st slot, 2nd slot, etc.)\n"
    "   - Example: plant 1 at (2, 3) means plant 1st slot at row 2, column 3\n"
    "2. collect - Collect all visible suns\n"
    "3. wait - Skip this turn\n\n"

    "Multi-step actions allowed (newline or semicolon separated):\n"
    "collect\n"
    "plant 1 at (2, 3)\n"
    "plant 2 at (5, 4)\n\n"

    "Think step-by-step:\n"
    "1. Which rows have zombies? Which rows have grass for planting?\n"
    "2. Are there suns to collect?\n"
    "3. Do zombie-threatened rows have offensive plants?\n"
    "4. What should I plant and where?\n\n"

    "### Learned Experience from Previous Attempts ### \n"
    "{reflection_experience}\n"
    "Note: The above experience comes from analyzing previous failed attempts and expert playthroughs. "
    "Use these insights to improve your strategy and avoid repeating past mistakes.\n\n"

    "Output format:\n"
    "### Reasoning\n"
    "[Your analysis]\n\n"
    "### Actions\n"
    "[Your action commands]"
)
