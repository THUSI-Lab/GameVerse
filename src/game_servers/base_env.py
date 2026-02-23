from typing import Any

import gymnasium as gym

from game_servers.utils.types.game_io import Action, Obs
from game_servers.utils.types.misc import Configurable


class BaseEnv(gym.Env, Configurable):
    def initial_obs(self) -> Obs:
        pass

    def obs2text(self, obs: Obs) -> str:
        pass

    def parse_action(self, text: str) -> Action:
        pass

    def text2gui(self, text: str) -> Action:
        pass

    def step(
        self, action: Action
    ) -> tuple[Obs, float, bool, bool, dict[str, Any]]:
        pass

    def evaluate(self, obs: Obs):
        pass

    def get_game_info(self) -> dict:
        pass
