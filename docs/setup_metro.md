# Mini Metro

## Prerequisites

- Mini Metro installed via Steam
- Steam account

## Setup Instructions

1. **Install the Game**

   Install "Mini Metro" from Steam.

2. **Complete Tutorial**

   Play through the in-game tutorial to unlock the main game mode.

3. **Configure Display Settings**

   Navigate to: **Menu → Options**
   
   - **Disable Full Screen mode**
   - **Set resolution to 1280×720**

4. **Start the Game**

   Begin a new game in **London** (the first available city).

5. **Run the Agent**

   Use the following command to start the agent:

   ```bash
   python scripts/play_game.py --config ./src/agent_client/configs/metro/config.yaml
   ```

## Evaluation

This game is **not automatically evaluated**. To assess performance:

- Wait until the game session ends
- Check the final screenshot for the number of travelers transported
- Record this number for comparison across experiments

## Configuration Notes

- **Do not use `coordinate_trans`**
- **Set `enable_contour_detection: true`** - This provides visual scaffolds to help LLMs understand the game state
