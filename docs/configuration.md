# Configuration Guide

## Overview

All games in `scripts/play_game.py` are configured using [OmegaConf](https://github.com/omry/omegaconf). Each game has its configuration file at `./src/agent_client/configs/{game}/config.yaml`. Configurations are categorized into three main sections: `runner`, `env`, and `agent`.

## Core Configuration Sections

### Runner Configuration

Controls the evaluation loop behavior.

| Parameter     | Description                                 | Type | Required | Default |
| ------------- | ------------------------------------------- | ---- | -------- | ------- |
| `max_steps` | Maximum number of game steps for evaluation | int  | Yes      | -       |

**Example:**

```yaml
runner:
  max_steps: 50
```

---

### Environment Configuration

Game-specific settings and task definitions.

#### Common Parameters

| Parameter       | Description                                                            | Type   | Required | Default        |
| --------------- | ---------------------------------------------------------------------- | ------ | -------- | -------------- |
| `task`        | Description of the task to be completed                                | string | Yes      | -              |
| `action_mode` | How agent interacts with the game:`"semantic"` or `"gui"`          | string | Yes      | `"semantic"` |
| `log_path`    | Path where logs are saved (auto-generated from top-level `log_path`) | string | Auto     | -              |

#### GUI Mode Parameters

Only needed for games using GUI interaction (e.g., Angry Birds, PVZ, Metro).

| Parameter        | Description                                                        | Type   | When Needed        | Default       |
| ---------------- | ------------------------------------------------------------------ | ------ | ------------------ | ------------- |
| `window_title` | Game window title for capture (supports regex)                     | string | GUI mode           | Game-specific |
| `coor_trans`   | Enable coordinate transformation (1000×1000 → actual resolution) | bool   | GUI with VL models | `false`     |

**Common GUI timing parameters:**

- `screenshot_interval`: Time between screenshots (seconds)
- `wait_after_action`: Wait time after executing actions (seconds)
- `timeout`: Maximum time before giving up (seconds)

#### Game-Specific Parameters

Each game may have unique parameters:

- **Slay the Spire**: `player_class`, `ascension_level`, `seed`, `mod_input_path`, `mod_output_path`
- **Snake**: `board_size`, `num_obstacles`, `game_mode` (`"discrete"` or `"realtime"`)
- **TwentyFourtyEight**: `target_tile`, `show_graphic`
- **Angry Birds**: `slingshot_pos_x`, `slingshot_pos_y`, `slingshot_pull_ratio`
- **PVZ**: `grid_rows`, `grid_cols`, `plant_slot_width`

**Example:**

```yaml
env:
  task: "Slay the Spire"
  action_mode: "semantic"
  player_class: "IRONCLAD"
  ascension_level: 0
  seed: 0
```

---

### Agent Configuration

LLM and agent behavior settings.

#### Required Parameters

| Parameter       | Description                  | Type   | Required | Default              |
| --------------- | ---------------------------- | ------ | -------- | -------------------- |
| `llm_name`    | LLM model name               | string | Yes      | -                    |
| `agent_type`  | Agent type to use            | string | Yes      | `"zeroshot_agent"` |
| `prompt_path` | Python module path to prompt | string | Yes      | -                    |

**Supported LLM models:**

- **OpenAI**: `gpt-4o`, `gpt-4o-mini`
- **Google**: `gemini-2.5-flash`, `gemini-2.5-pro`
- **Qwen**: `qwen3-vl-8b-instruct`, `qwen3-vl-32b-instruct`
- **Seed**: `doubao-seed-1-8-251228`

**Supported agent types:**

- `zeroshot_agent`: Direct task completion without memory
- `memory_agent`: Uses long-term memory and skill management

#### LLM API Configuration

For commercial APIs or self-hosted models:

| Parameter              | Description                | Type   | Required    | Default |
| ---------------------- | -------------------------- | ------ | ----------- | ------- |
| `api_key`            | API key for authentication | string | API-based   | `""`  |
| `api_base_url`       | Base URL for API endpoint  | string | Self-hosted | `""`  |
| `temperature`        | Sampling temperature       | float  | No          | `0.0` |
| `repetition_penalty` | Repetition penalty         | float  | No          | `1.0` |

**Example:**

```yaml
agent:
  llm_name: gpt-4o
  temperature: 0.0
  agent_type: zeroshot_agent
  prompt_path: agent_servers.slay_the_spire.prompts.semantic.zeroshot_agent
```

#### Advanced Parameters

##### Long-term Memory (for `memory_agent`)

| Parameter                | Description                                | Type   | Default      |
| ------------------------ | ------------------------------------------ | ------ | ------------ |
| `long_term_memory_len` | Number of recent memories to retrieve      | int    | `10`       |
| `embedding_model`      | Embedding model:`"openai"` or `"qwen"` | string | `"openai"` |
| `embedding_config`     | Additional embedding configuration         | dict   | `{}`       |

**Example:**

```yaml
agent:
  agent_type: memory_agent
  long_term_memory_len: 10
  embedding_model: "qwen"
  embedding_config:
    model: "text-embedding-v4"
    dimensions: 1024
```

##### Video Reflection 

| Parameter                | Description                                    | Type   | Default        |
| ------------------------ | ---------------------------------------------- | ------ | -------------- |
| `use_reflection`       | Enable video reflection experience             | bool   | `false`      |
| `reflection_format`    | Reflection file format:`"json"` or `"txt"` | string | `"json"`     |
| `reflection_file_path` | Path to reflection file                        | string | Auto-generated |

**Example:**

```yaml
agent:
  use_reflection: true
  reflection_format: "json"
  reflection_file_path: "data/reflections/Snake_reflections.json"
```

##### Debug Mode

| Parameter      | Description          | Type | Default   |
| -------------- | -------------------- | ---- | --------- |
| `debug_mode` | Enable debug logging | bool | `false` |
