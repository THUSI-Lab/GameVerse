import re

async def action_execution(action_str: str, runner, agent_server_id):
    runner.memories = await runner.client.call_get_memories(agent_server_id)

    action_str = action_str.split("\n")[0]
    actions = [part.strip() for part in re.split(r'\s*(\||\n)\s*', action_str) if part.strip() and part.strip() not in ("|", "\n")]
    actions = actions[:5]
    messages = []
    flag = ""
    for action_idx, action in enumerate(actions):
        if action_idx==0:
            if 'use_tool' in action:
                messages.append(f"{action}\n(isSuccess,Feedback):{await runner.toolset.execute_action_response(action)}")
                flag = 'use_tool'
            else:
                messages.append(action)
                flag = 'low'
        else:
            if flag == 'use_tool':
                if 'use_tool' in action:
                    messages.append(f"{action}\n(isSuccess,Feedback):{await runner.toolset.execute_action_response(action)}")
                else:
                    break
            else:
                if 'use_tool' in action:
                    break
                else:
                    messages.append(action)
    final_action = "|".join(messages)

    # runner.agent.memory.add("action", final_action)
    runner.memories['action'].append(final_action)

    data = {
        # f"{runner.step_count}th_state": runner.agent.memory.get_last('environment_perception'),
        f"{runner.step_count}th_state": runner.memories['environment_perception'][-1],
        f"{runner.step_count}th_action": final_action,
    }

    # runner.agent.memory.histories.append(data)
    # runner.agent.memory.histories = runner.agent.memory.histories[-runner.agent.memory.num_history_buffer:]
    # runner.agent.memory.add("short_term_history", runner.agent.memory.histories)
    runner.histories.append(data)
    runner.histories = runner.histories[-runner.num_history_buffer:]
    if 'short_term_history' not in runner.memories:
        runner.memories['short_term_history'] = []
    runner.memories['short_term_history'].append(runner.histories)

    # update long-term memory
    # lessons = runner.agent.memory.get_last('lessons_learned')
    lessons = runner.memories['lessons_learned'][-1]
    if lessons and lessons != "Not Provided":
        lessons_list = lessons.split('\n')
        for lesson in lessons_list:
            lesson = lesson.strip()
            lesson_match = re.match(r"^\s*[-*]\s*(.*)", lesson)
            if lesson_match:
                lesson_text = lesson_match.group(1).strip()
                if lesson_text:
                    # runner.agent.memory.add_long_term_memory(lesson_text, similarity_threshold=0.2)
                    await runner.client.call_add_long_term_memory(lesson_text, 0.2, agent_server_id)
            elif lesson:
                # runner.agent.memory.add_long_term_memory(lesson, similarity_threshold=0.2)
                await runner.client.call_add_long_term_memory(lesson, 0.2, agent_server_id)

    # await runner.client.call_set_memories(agent_server_id, runner.agent.memory.memories)
    await runner.client.call_set_memories(agent_server_id, runner.memories)

    return final_action