"""
MACRS 多模型团队配置模块

支持 YAML 配置文件定义团队组成，包含模型别名系统和多种配置形式。
"""

from dataclasses import dataclass, field
from typing import Optional, Any
import yaml


@dataclass
class ReviewerInstance:
    """审查者实例"""
    persona: str
    instance_index: int
    name: str
    model: Optional[str] = None

    def __post_init__(self):
        """初始化后处理"""
        if not self.name:
            self.name = f"{self.persona}-{self.instance_index}"


@dataclass
class TeamConfig:
    """团队配置"""
    team: list[ReviewerInstance]
    aliases: dict[str, str]
    default_model: Optional[str] = None

    def get_model(self, model_ref: Optional[str]) -> Optional[str]:
        """解析模型引用，支持别名"""
        if model_ref is None:
            return None
        return self.aliases.get(model_ref, model_ref)


def parse_persona_config(persona_name: str, config: Any) -> list[dict]:
    """
    解析单个 persona 的配置，支持三种形式：
    1. 简写：quality: 2  (数字表示实例数量)
    2. 对象：security: { count: 1, model: big-brain }
    3. 列表：principal: [{ model: big-brain }, { model: workhorse }]
    """
    instances = []

    if isinstance(config, int):
        # 简写形式：quality: 2
        for i in range(config):
            instances.append({
                "persona": persona_name,
                "instance_index": i,
                "model": None
            })

    elif isinstance(config, dict):
        # 对象形式：security: { count: 1, model: big-brain }
        count = config.get("count", 1)
        model = config.get("model")
        for i in range(count):
            instances.append({
                "persona": persona_name,
                "instance_index": i,
                "model": model
            })

    elif isinstance(config, list):
        # 列表形式：principal: [{ model: big-brain }, { model: workhorse }]
        for i, item in enumerate(config):
            if isinstance(item, dict):
                model = item.get("model")
            else:
                model = None
            instances.append({
                "persona": persona_name,
                "instance_index": i,
                "model": model
            })

    return instances


def resolve_model(
    instance_model: Optional[str],
    team_model: Optional[str],
    aliases: dict[str, str],
    default_model: Optional[str]
) -> Optional[str]:
    """
    解析链：instance > team > default > None

    Args:
        instance_model: 实例级别指定的模型
        team_model: 团队级别指定的模型
        aliases: 模型别名字典
        default_model: 默认模型

    Returns:
        解析后的实际模型名称，或 None
    """
    # 按优先级选择模型引用
    model_ref = instance_model or team_model or default_model

    if model_ref is None:
        return None

    # 解析别名
    return aliases.get(model_ref, model_ref)


def load_team_config(config_path: str) -> TeamConfig:
    """
    从 YAML 加载团队配置

    Args:
        config_path: YAML 配置文件路径

    Returns:
        TeamConfig 实例

    Raises:
        FileNotFoundError: 配置文件不存在
        yaml.YAMLError: YAML 解析错误
        ValueError: 配置格式错误
    """
    with open(config_path, 'r', encoding='utf-8') as f:
        raw_config = yaml.safe_load(f)

    if not isinstance(raw_config, dict):
        raise ValueError("配置文件格式错误：顶层必须是字典")

    # 提取别名配置
    aliases = raw_config.get("aliases", {})
    if not isinstance(aliases, dict):
        raise ValueError("配置文件格式错误：aliases 必须是字典")

    # 提取默认模型
    default_model = raw_config.get("default_model")

    # 提取团队配置
    team_raw = raw_config.get("team", {})
    if not isinstance(team_raw, dict):
        raise ValueError("配置文件格式错误：team 必须是字典")

    # 团队级别模型
    team_model = raw_config.get("team_model")

    # 解析所有 persona 配置
    team = []
    for persona_name, persona_config in team_raw.items():
        instances_config = parse_persona_config(persona_name, persona_config)

        for inst_config in instances_config:
            # 解析最终模型
            resolved_model = resolve_model(
                instance_model=inst_config["model"],
                team_model=team_model,
                aliases=aliases,
                default_model=default_model
            )

            reviewer = ReviewerInstance(
                persona=inst_config["persona"],
                instance_index=inst_config["instance_index"],
                name=f"{inst_config['persona']}-{inst_config['instance_index']}",
                model=resolved_model
            )
            team.append(reviewer)

    return TeamConfig(
        team=team,
        aliases=aliases,
        default_model=default_model
    )


def get_team_summary(config: TeamConfig) -> str:
    """
    返回团队配置摘要

    Args:
        config: TeamConfig 实例

    Returns:
        格式化的团队配置摘要字符串
    """
    lines = ["=" * 60]
    lines.append("MACRS 团队配置摘要")
    lines.append("=" * 60)

    # 别名信息
    if config.aliases:
        lines.append("\n模型别名：")
        for alias, model in config.aliases.items():
            lines.append(f"  {alias} -> {model}")

    # 默认模型
    if config.default_model:
        lines.append(f"\n默认模型：{config.default_model}")

    # 团队成员
    lines.append(f"\n团队成员（共 {len(config.team)} 个实例）：")
    lines.append("-" * 40)

    # 按 persona 分组显示
    personas = {}
    for reviewer in config.team:
        if reviewer.persona not in personas:
            personas[reviewer.persona] = []
        personas[reviewer.persona].append(reviewer)

    for persona, instances in personas.items():
        lines.append(f"\n  {persona}（{len(instances)} 个实例）：")
        for inst in instances:
            model_display = inst.model or "未指定"
            lines.append(f"    - {inst.name}: {model_display}")

    lines.append("\n" + "=" * 60)

    return "\n".join(lines)


# 示例配置模板
EXAMPLE_CONFIG = """
# MACRS 团队配置示例
# 支持三种配置形式

# 模型别名
aliases:
  workhorse: claude-sonnet-4-6
  big-brain: claude-opus-4-6
  fast: claude-haiku-4-6

# 默认模型（当实例和团队都未指定时使用）
default_model: workhorse

# 团队级别模型（覆盖默认模型，被实例模型覆盖）
team_model: workhorse

# 团队成员配置
team:
  # 简写形式：数字表示实例数量
  quality: 2

  # 对象形式：指定数量和模型
  security:
    count: 1
    model: big-brain

  # 列表形式：每个实例单独配置
  principal:
    - model: big-brain
    - model: workhorse

  # 最简形式：单个实例
  performance: 1
"""


def generate_example_config(output_path: str) -> None:
    """
    生成示例配置文件

    Args:
        output_path: 输出文件路径
    """
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(EXAMPLE_CONFIG)


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1:
        config_path = sys.argv[1]
        try:
            config = load_team_config(config_path)
            print(get_team_summary(config))
        except Exception as e:
            print(f"错误：{e}")
            sys.exit(1)
    else:
        print("用法：python team_config.py <config.yaml>")
        print("\n示例配置：")
        print(EXAMPLE_CONFIG)
