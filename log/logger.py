"""日志工具"""
import os
import logging
from logging.handlers import RotatingFileHandler
from datetime import datetime


class LoggerUtil:
    """日志工具类"""
    _loggers = {}

    @staticmethod
    def get_logger(name='agent'):
        if name in LoggerUtil._loggers:
            return LoggerUtil._loggers[name]

        logger = logging.getLogger(name)
        logger.setLevel(logging.DEBUG)

        # 控制台输出
        console = logging.StreamHandler()
        console.setLevel(logging.INFO)
        fmt = logging.Formatter('%(asctime)s [%(levelname)s] %(filename)s:%(funcName)s - %(message)s', datefmt='%H:%M:%S')
        console.setFormatter(fmt)
        logger.addHandler(console)

        # 文件输出
        log_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'log')
        os.makedirs(log_dir, exist_ok=True)
        log_file = os.path.join(log_dir, f'agent_{datetime.now().strftime("%Y%m%d")}.log')
        file_handler = RotatingFileHandler(log_file, maxBytes=10*1024*1024, backupCount=5, encoding='utf-8')
        file_handler.setLevel(logging.DEBUG)
        file_fmt = logging.Formatter('%(asctime)s [%(levelname)s] %(filename)s:%(funcName)s - %(message)s')
        file_handler.setFormatter(file_fmt)
        logger.addHandler(file_handler)

        LoggerUtil._loggers[name] = logger
        return logger

    @staticmethod
    def info(msg):
        LoggerUtil.get_logger().info(msg)

    @staticmethod
    def error(msg):
        LoggerUtil.get_logger().error(msg)

    @staticmethod
    def warning(msg):
        LoggerUtil.get_logger().warning(msg)

    @staticmethod
    def debug(msg):
        LoggerUtil.get_logger().debug(msg)
