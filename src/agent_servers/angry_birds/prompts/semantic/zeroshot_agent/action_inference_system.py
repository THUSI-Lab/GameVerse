# flake8: noqa
"""
Angry Birds System Prompt for Semantic Action Mode
"""

PROMPT = (
    "You are playing *Angry Birds*. \n\n"

    "### **Game Objective**\n"
    "Destroy all the green pigs by launching red birds from the slingshot.\n\n"

    "### **How to Play**\n"
    "Pull the slingshot to launch birds at structures and pigs.\n"
    "- Birds are on the LEFT\n"
    "- Pigs are on the RIGHT (green)\n"
    "- Hit pigs directly OR knock down structures to crush them\n\n"

    "### **Game Interface**\n"
    "- Slingshot on the left side\n"
    "- Structures made of wood/stone/glass\n"
    "- Green pigs as targets\n"
    "- Red bird (standard, no special abilities)\n\n"

    "### **Strategy**\n"
    "- Aim for weak points in structures\n"
    "- Wait when structures are still collapsing\n"
    "- Different materials have different durability\n\n"

    "### Learned Experience from Previous Attempts ### \n"
    "{reflection_experience}\n"
    "Note: The above experience comes from analyzing previous failed attempts and expert playthroughs. "
    "Use these insights to improve your strategy and avoid repeating past mistakes.\n"
)
