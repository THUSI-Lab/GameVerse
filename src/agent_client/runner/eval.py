import logging
from dataclasses import dataclass

from game_servers.utils.types.misc import Configurable
from game_servers.base_env import BaseEnv
from agent_client.base_agent import BaseAgent

logger = logging.getLogger(__name__)


class BaseRunner(Configurable):
    @dataclass
    class Config:
        max_steps: int

    cfg: Config

    def configure(self):
        self.max_steps = self.cfg.max_steps

    def set_agent(self, agent: BaseAgent):
        self.agent = agent
        if hasattr(self, "env") and self.env is not None:
            self._connect_agent_to_env()

    def set_env(self, env: BaseEnv):
        self.env = env
        if hasattr(self, "agent") and self.agent is not None:
            self._connect_agent_to_env()

    def set_toolset(self, toolset):
        self.toolset = toolset

    def _connect_agent_to_env(self):
        """
        Connect the environment instance to the agent, so the agent
        or its internal tools can access real-time state if needed.
        """
        self.agent.set_env_interface(self.env)

    def step(self, obs):
        # FIXME: logger
        game_info = self.env.get_game_info()
        text = self.agent(obs, game_info)
        
        action = self.env.parse_action(text)
        
        logger.info(f"executing actions: {action}")
        obs, reward, terminated, truncated, info = self.env.step(action)
        
        _, done = self.env.evaluate(obs)

        return obs, terminated | truncated | done

    def play(self):
        obs = self.env.initial_obs()
        score = 0.0  # 初始化分数

        for i in range(self.max_steps):
            logger.info(f"================step: {i+1}/{self.max_steps}================")
            obs, done = self.step(obs)
            # 每次step后都获取当前分数（包括游戏结束时）
            score, _ = self.env.evaluate(obs)
            if done:
                break
            
        return score, i+1
