# flake8: noqa

AGENT_MODULES = {
    "zeroshot_agent": [
        "action_inference"
    ],
    "reflection_agent": [
        "self_reflection",
        "action_inference"
    ],
    "planning_agent": [
        "subtask_planning",
        "action_inference"
    ],
    "reflection_planning_agent": [
        "self_reflection",
        "subtask_planning",
        "action_inference"
    ],
    "pwaat_agent": [
        "self_reflection",
        "long_term_management",
        "action_inference"
    ],
    "memory_agent": [
        "history_review_reasoning",
        "long_term_memory_retrieval",
        "action_inference_with_memory",
        "update_short_term_history"
    ]
}

# GUI mode: uses action_inference with different prompts
# The prompt path is configured to use gui/ directory
GUI_AGENT_MODULES = {
    "zeroshot_agent": [
        "action_inference"
    ],
    "reflection_agent": [
        "self_reflection",
        "action_inference"
    ],
    "planning_agent": [
        "subtask_planning",
        "action_inference"
    ],
    "reflection_planning_agent": [
        "self_reflection",
        "subtask_planning",
        "action_inference"
    ],
    "pwaat_agent": [
        "self_reflection",
        "long_term_management",
        "action_inference"
    ],
    "memory_agent": [
        "history_review_reasoning",
        "long_term_memory_retrieval",
        "action_inference_with_memory",
        "update_short_term_history"
    ]
}

# More AGENT TYPES?
# ReACT ...
# ["self_reflection", "subtask_planning", "knowledge_retrieval", "action_inference"]