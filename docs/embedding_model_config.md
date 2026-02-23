# Embedding Model Configuration Guide

## Overview

The framework now supports selecting different embedding models for long-term memory functionality in the configuration file. Currently, two embedding models are supported:

- **OpenAI**: Uses OpenAI's text-embedding model (default)
- **Qwen**: Uses Qwen's text-embedding model

## Configuration Method

In the game's `config.yaml` file, you can add embedding-related configuration in the `agent` section:

```yaml
agent:
  # ... other configurations ...
  
  # Embedding model configuration (for long-term memory)
  embedding_model: "openai"  # Options: "openai" or "qwen", default is "openai"
  embedding_config:  # Additional embedding model configuration
    # For qwen model, you can configure:
    model: "text-embedding-v4"  # Qwen embedding model name
    dimensions: 1536  # Vector dimensions (default 1536, consistent with OpenAI text-embedding-ada-002, optional)
    api_key: "your-dashscope-api-key"  # Specify here if DASHSCOPE_API_KEY environment variable is not set
    base_url: "https://dashscope.aliyuncs.com/compatible-mode/v1"  # API base URL (optional)
```

## Using OpenAI Embedding (Default)

If you don't specify `embedding_model` or set it to `"openai"`, OpenAI's embedding model will be used:

```yaml
agent:
  embedding_model: "openai"  # Or omit this configuration
```

## Using Qwen Embedding

To use Qwen's embedding model, you need to:

1. Set `embedding_model` to `"qwen"`
2. Configure the `DASHSCOPE_API_KEY` environment variable, or specify `api_key` in `embedding_config`
3. (Optional) Specify other parameters in `embedding_config`

### Example Configuration

```yaml
agent:
  embedding_model: "qwen"
  embedding_config:
    model: "text-embedding-v4"
    dimensions: 1536  # Default 1536, consistent with OpenAI (optional, set to None to not specify dimensions)
    # api_key: "your-key"  # Optional, can be omitted if environment variable is set
```

### Environment Variable Configuration

When using Qwen embedding, you need to set the DashScope API key:

```bash
# Windows PowerShell
$env:DASHSCOPE_API_KEY="your-api-key"

# Linux/Mac
export DASHSCOPE_API_KEY="your-api-key"
```

## Supported Qwen Embedding Models

- `text-embedding-v4`: Latest version, supports custom dimensions
- Other Qwen embedding models (according to DashScope API documentation)

## Important Notes

1. **Vector Dimension Compatibility**: Different embedding models may have different vector dimensions. If you switch embedding models, you may need to regenerate the vector database.

2. **API Keys**: 
   - OpenAI: Uses `OPENAI_API_KEY` environment variable
   - Qwen: Uses `DASHSCOPE_API_KEY` environment variable or specified in config file

3. **Backward Compatibility**: If `embedding_model` is not configured, OpenAI embedding is used by default for backward compatibility.

4. **Long-term Memory and Skill Management**: The configured embedding model is applied to both:
   - Long-term Memory (GenericMemory)
   - Skill Management (SkillManager)

## Examples

### Complete Configuration Example (Using Qwen)

```yaml
agent:
  llm_name: qwen3-vl-32b-instruct
  agent_type: memory_agent
  prompt_path: agent_servers.pwaat.prompts.gui.memory_agent
  long_term_memory_len: 5
  
  # Use Qwen embedding
  embedding_model: "qwen"
  embedding_config:
    model: "text-embedding-v4"
    dimensions: 1536  # Default 1536, consistent with OpenAI
```

### Complete Configuration Example (Using OpenAI)

```yaml
agent:
  llm_name: gpt-4o
  agent_type: memory_agent
  prompt_path: agent_servers.angry_birds.prompts.gui.memory_agent
  
  # Use OpenAI embedding (default)
  embedding_model: "openai"
  # Or omit embedding_model configuration
```

