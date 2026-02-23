import sys
import os
import json
from datetime import datetime
from typing import Tuple
import omegaconf
import logging
import base64
from io import BytesIO

from game_servers.utils.module_creator import EnvCreator

logger = logging.getLogger(__name__)


if sys.platform == 'win32':
    import msvcrt
    msvcrt.setmode(sys.stdin.fileno(), os.O_BINARY)
    msvcrt.setmode(sys.stdout.fileno(), os.O_BINARY)

def set_log_path(cfg, expand_log_path: bool = True) -> omegaconf.omegaconf.DictConfig:
    if expand_log_path:
        log_path = os.path.join(
            cfg.log_path,
            cfg.env_name,
            datetime.now().strftime("%Y%m%d_%H%M%S")
        )
        cfg.env.log_path = log_path
        os.makedirs(log_path, exist_ok=True)

    logging.basicConfig(
        level=logging.INFO,
        format='[%(asctime)s] [%(levelname)s] [%(filename)s:%(lineno)d] %(message)s',
        handlers=[
            logging.FileHandler(os.path.join(cfg.log_path, 'game_server.log')),
            logging.StreamHandler()
        ],
        force=True
    )
    
    return cfg

# MCPGameServer class has been removed as it depended on MCP protocol.
# The MCP server functionality is no longer needed as we use direct Python calls instead.
