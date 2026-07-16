"""测试用例数据模型"""
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import List, Optional


@dataclass
class StepLog:
    """Agent 执行的单步日志"""
    step: int = 0
    action: str = ''
    params: dict = field(default_factory=dict)
    result: dict = field(default_factory=dict)
    passed: bool = False
    timestamp: str = ''


@dataclass
class TestCase:
    """测试用例/执行记录"""
    name: str = ''
    description: str = ''
    task: str = ''
    passed: bool = False
    steps_log: List[dict] = field(default_factory=list)
    screenshots: List[str] = field(default_factory=list)
    conclusion: str = ''
    elapsed_seconds: float = 0.0
    id: str = ''
    created_at: str = ''
    tags: List[str] = field(default_factory=list)

    def __post_init__(self):
        if not self.id:
            self.id = f'case_{datetime.now().strftime("%Y%m%d%H%M%S%f")}'
        if not self.created_at:
            self.created_at = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    def to_dict(self):
        return asdict(self)

    @staticmethod
    def from_dict(data: dict):
        return TestCase(**{k: v for k, v in data.items() if k in TestCase.__dataclass_fields__})
