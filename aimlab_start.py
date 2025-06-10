import logging
import aimlab_debug
import config

logging.basicConfig(level=getattr(logging, config.log_level))  # 设置日志级别

aimlab_debug.aimlab_debug()