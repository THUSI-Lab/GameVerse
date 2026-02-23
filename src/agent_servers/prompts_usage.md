# prompt占位符文档

AI生成的，存下来查看。

1. env.get_game_info() → 返回基础game_info字典
                      ↓
2. runner.step() → 调用 agent(obs, game_info)
                      ↓
3. agent.__call__() → 通过MCP调用 base_server.agent_get_local_memory()
                      ↓
4. agent_get_local_memory() → 合并game_info和memory，生成local_memory字典
                      ↓
5. get_module_prompts() → 使用.format(**local_memory)填充prompt
                      ↓
6. LLM接收填充后的完整prompt

## 来自game_info返回的变量

"Game: {game_name}\n"
"Window Size: {window_width} x {window_height} pixels\n"
"Task: {task_description}\n"
"Current Step: {step_count}\n"

## memory系统的占位符

{cur_state_str} - 当前状态文本（来自 GameObs.to_text()
{prev_state_str} - 上一个状态文本
{cur_image} - 当前图像（base64编码）
{prev_image} - 上一个图像（base64编码）

<|cur_state_image|> 和 <|prev_state_image|> 不使用 {} 包围
这些是特殊标记，由MCP客户端处理并转换为实际图像

{reasoning} - 推理过程
{prev_reasoning_str} - 上一次推理
{analysis} - 分析结果
{prev_analysis_str} - 上一次分析
{plan} - 计划

动作相关：
{action} - 上一次执行的动作
{action_reasoning} - 动作推理
记忆相关：
{retrieved_memory_str} - 检索到的长期记忆
{latest_saved_memory_str} - 最近保存的记忆
{history_summary} - 历史摘要
任务相关：
{task_description} - 任务描述（也可从game_info获取）
{subtask} - 当前子任务
Reflection相关：
{reflection_experience} - 视频反思经验（如果启用）

## base sever中的占位符

自我反思
{self_reflection}, {self_reflection_summary}, {critique}, {success}

子任务规划
{history_summary}, {subtask_reasoning}, {subtask_description}, {subtask}

技能管理
{skill_description}, {retrieved_skills}

长期记忆
{clue_extraction}, {saving}

历史总结
{short_term_summary}

动作执行
{action}, {reasoning}, {action_reasoning}, {lessons_learned}, {state_summary}