# Red Dead Redemption 2

## Prerequisites

- Red Dead Redemption 2 installed via Steam
- Steam account

## Setup Instructions

1. **Install the Game**

   Purchase and install Red Dead Redemption 2 from Steam. Follow the installation guide provided by Steam.

2. **Configure Display Mode**

   Set the game to run in **windowed mode** for better compatibility with the agent.

3. **Start a New Game**

   - Select **New Game** from the main menu
   - **Hold the left mouse button** to skip the story videos
   - Wait for the game to begin

4. **Run the Agent**

   Once the game has started, use the following command:

   ```bash
   python scripts/play_game.py --config ./src/agent_client/configs/red_dead_redemption2/config.yaml
   ```

## Important Notes

- **Always start a new game**: If you have existing saved game files, we recommend creating a new game from scratch for consistent evaluation conditions.
- Make sure the game is in windowed mode before starting the agent.
- Skip all cutscenes and story videos to begin gameplay quickly.
