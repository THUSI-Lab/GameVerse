# Plants vs. Zombies Game Server Module

from game_servers.pvz.game.pvz_env import PvzEnv, PvZObs, PvZAction

# 为了与框架的命名约定兼容 (env_name: "Pvz" -> PvzEnv)
PlantsVsZombiesEnv = PvzEnv

__all__ = [
    'PvzEnv',
    'PlantsVsZombiesEnv', 
    'PvZObs', 
    'PvZAction'
]
