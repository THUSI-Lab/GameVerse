# Video Reflection Guide

## Overview

The video reflection feature enables models to learn from failed run videos and expert videos, and inject these experiences into prompts to improve model performance.

## Workflow

1. **Generate Failure Video**: Generate obs_video.mp4 from logs path
2. **Generate Experience**: Use scripts to analyze videos and generate experiences
3. **Save Experience**: Experiences are saved to `data/reflections/` directory, categorized by game
4. **Inject Experience**: Once enabled in config, experiences are automatically injected into prompts

## Usage Steps

### 1. Generate Failure Video

First, generate a video from the logs path:

```bash
python scripts/playvideo_gen.py --log_path logs/Pwaat/qwen3-vl-32b-instruct/gui/memory_agent/20251209_131702
```

This will generate an `obs_video.mp4` file in the logs directory.

### 2. Generate Experience

Use the `generate_reflection.py` script to analyze videos and generate experiences:

```bash
python scripts/generate_reflection.py \
    --log_path logs/Pwaat/qwen3-vl-32b-instruct/gui/memory_agent/20251209_131702 \
    --game_name Pwaat \
    --llm_name gpt-4o \
    --max_length 1000
```

Parameter descriptions:
- `--log_path`: Logs path (must contain obs_video.mp4)
- `--game_name`: Game name (e.g., Pwaat, SlayTheSpire, etc.)
- `--llm_name`: LLM name for analysis (default: gpt-4o)
- `--max_length`: Maximum length of experience text (default: 1000 characters)
- `--num_frames`: Number of key frames to extract from each video (default: 10 frames)
- `--expert_video`: Expert video path (optional, auto-detected if not specified)
- `--format`: Save format (json or txt, default: json)

### 3. Expert Videos

Expert videos should be placed in one of the following locations:
- `data/expert_videos/{game_name}/skill_video.mp4`
- `data/expert_videos/{game_name}/playthrough_video.mp4`
- `data/expert_videos/{game_name}/expert.mp4`

If no expert video is provided, the script will only analyze the failure video.

### 4. Enable Experience Injection

Enable experience injection in the game's config file:

```yaml
agent:
  # ... other configurations ...
  use_reflection: true  # Enable video reflection experience
  reflection_format: "json"  # Experience file format
```

### 5. Use Experience in Prompts

Experiences are injected into `local_memory` through the `reflection_experience` field. You can use it in prompt files:

```python
PROMPT = (
    f"... other content ...\n\n"
    f"## Lessons Learned from Failures\n"
    f"{{reflection_experience}}\n\n"
    f"... other content ..."
)
```

If experience is not enabled or doesn't exist, `reflection_experience` will be an empty string.

## Experience File Format

### JSON Format

```json
{
  "game_name": "Pwaat",
  "reflections": [
    {
      "text": "Experience text...",
      "metadata": {
        "log_path": "...",
        "failure_video": "...",
        "expert_video": "...",
        "llm_name": "gpt-4o",
        "max_length": 1000
      }
    }
  ],
  "summary": "Merged experience summary..."
}
```

### TXT Format

Plain text format, appending new experiences each time.

## Experience Management

Experiences are saved in the `data/reflections/` directory, categorized by game name:
- `data/reflections/{game_name}_reflections.json`
- `data/reflections/{game_name}_reflections.txt`

## Comparison Experiments

To compare the effects with and without video reflection:

1. **Without Reflection**: Run the game with `use_reflection: false`
2. **With Reflection**: Run the game with `use_reflection: true`
3. Compare scores and performance between the two runs

## Important Notes

1. Video reflection requires multimodal LLMs (e.g., gpt-4o, qwen3-vl, etc.)
2. Experience text has length limits, ensure it's concise and specific
3. Expert videos are optional, but providing them can yield better experiences
4. Experiences are saved categorized by game, different games' experiences won't be mixed

## Troubleshooting

### Issue: Cannot find obs_video.mp4

**Solution**: Run `playvideo_gen.py` first to generate the video.

### Issue: LLM call failed

**Solution**: Check API key and network connection, ensure the LLM supports multimodal input.

### Issue: Experience not injected into prompt

**Solution**:
1. Check if `use_reflection` is set to `true` in config
2. Check if experience file exists
3. Check if prompt uses the `{reflection_experience}` field
