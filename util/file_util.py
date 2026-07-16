"""文件工具类"""
import os
import yaml


class FileUtil:
    """文件工具"""

    @staticmethod
    def get_project_root():
        """获取项目根目录"""
        return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    @staticmethod
    def get_config_path():
        """获取配置文件路径"""
        return os.path.join(FileUtil.get_project_root(), 'config', 'config.yml')

    @staticmethod
    def read_yaml(filepath):
        """读取 YAML 文件"""
        with open(filepath, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f)

    @staticmethod
    def ensure_dir(dirpath):
        """确保目录存在"""
        os.makedirs(dirpath, exist_ok=True)
        return dirpath
