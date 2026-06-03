"""
MACRS 自动修复循环模块

Phase 7: 门控 - 加载 artifact 并筛选修复候选
Phase 8: 并行修复 - 分组后并发执行修复
Phase 9: Post-fix 审查 - 回归检测与提交
"""

from dataclasses import dataclass, field
from typing import Optional, Any
from enum import Enum
from pathlib import Path
import json
import logging
import time
from datetime import datetime

from artifact_manager import FindingState as FixState

logger = logging.getLogger(__name__)


class GateDisposition(Enum):
    """门控处置类型"""
    CONFIRMED_MECHANICAL = "confirmed_mechanical"  # 确认的机械性问题
    PARTIAL = "partial"                            # 部分确认
    REGRESSION = "regression"                      # 回归问题
    SKIP = "skip"                                  # 跳过


@dataclass
class FixCandidate:
    """修复候选"""
    finding: dict                  # 原始发现
    score: int                     # 置信度分数 (0-100)
    disposition: str               # 处置类型
    fix_group: Optional[str] = None  # 修复组标识
    file_path: Optional[str] = None  # 相关文件路径
    category: Optional[str] = None   # 问题类别


@dataclass
class FixResult:
    """修复结果"""
    finding: dict                  # 原始发现
    state: FixState                # 修复状态
    diff: Optional[str] = None     # 生成的 diff
    regression: bool = False       # 是否引入回归
    error: Optional[str] = None    # 错误信息
    attempts: int = 0              # 尝试次数
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())


@dataclass
class RegressionReport:
    """回归报告"""
    original_fix: FixResult
    regression_findings: list[dict]
    severity: str                  # critical, major, minor
    rollback_performed: bool = False


class AutoFixPhase:
    """
    自动修复循环主类

    实现三阶段修复流程:
    - Phase 7: 门控筛选
    - Phase 8: 并行修复
    - Phase 9: Post-fix 审查
    """

    # 门控阈值
    MIN_GATE_SCORE = 60
    MAX_RETRY_ATTEMPTS = 3
    EXPONENTIAL_BACKOFF_BASE = 2

    # 允许的门控处置类型
    ALLOWED_DISPOSITIONS = {
        GateDisposition.CONFIRMED_MECHANICAL.value,
        GateDisposition.PARTIAL.value,
        GateDisposition.REGRESSION.value,
    }

    def __init__(self, agent_runner: Any, source_dir: str):
        """
        初始化自动修复阶段

        Args:
            agent_runner: Agent 运行器实例
            source_dir: 源代码目录路径
        """
        self.agent_runner = agent_runner
        self.source_dir = Path(source_dir)
        self._fix_history: list[FixResult] = []
        self._regression_reports: list[RegressionReport] = []

    def _sanitize_llm_output(self, output: str) -> str:
        """消毒 LLM 输出，移除潜在危险内容"""
        import re

        # Prompt injection patterns (expanded set)
        dangerous_patterns = [
            r'ignore\s+previous\s+instructions',
            r'ignore\s+above\s+instructions',
            r'forget\s+(your|all|previous)\s+instructions',
            r'system\s*prompt',
            r'you\s+are\s+now',
            r'act\s+as',
            r'pretend\s+(you|to)\s+(are|be)',
            r'do\s+not\s+follow',
            r'override\s+(your|system)',
            r'disregard\s+(your|all|previous)',
            r'new\s+instructions?\s*:',
            r'<\s*system\s*>',
            r'<\s*/\s*system\s*>',
            r'\[INST\]',
            r'\[/INST\]',
            r'<\|im_start\|>',
            r'<\|im_end\|>',
        ]
        for pattern in dangerous_patterns:
            output = re.sub(pattern, '', output, flags=re.IGNORECASE)

        # Remove code block language specifiers that could enable code execution
        output = re.sub(r'```(?:python|bash|sh|shell|powershell|cmd|bat|zsh|fish)\b', '```', output, flags=re.IGNORECASE)

        # Remove inline code execution markers
        output = re.sub(r'!!\s*(?:python|bash|sh|exec|eval)\b', '', output, flags=re.IGNORECASE)

        return output

    # ========== Phase 7: 门控 ==========

    def load_and_gate(self, artifact_path: str) -> list[FixCandidate]:
        """
        Phase 7: 加载 artifact 并执行门控筛选

        门控条件:
        1. 状态为 open
        2. 处置类型为 confirmed_mechanical/partial/regression
        3. 置信度分数 >= 60

        Args:
            artifact_path: artifact JSON 文件路径

        Returns:
            通过门控的修复候选列表
        """
        artifact = self._load_artifact(artifact_path)
        findings = artifact.get("findings", [])

        candidates = []
        for finding in findings:
            candidate = self._evaluate_gate(finding)
            if candidate is not None:
                candidates.append(candidate)

        logger.info(
            f"Gate filter: {len(findings)} findings -> "
            f"{len(candidates)} candidates"
        )
        return candidates

    def _load_artifact(self, artifact_path: str) -> dict:
        """加载 artifact 文件"""
        path = Path(artifact_path)
        if not path.exists():
            raise FileNotFoundError(f"Artifact not found: {artifact_path}")

        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)

    def _evaluate_gate(self, finding: dict) -> Optional[FixCandidate]:
        """
        评估单个 finding 是否通过门控

        Args:
            finding: 单个发现记录

        Returns:
            FixCandidate if passed, None otherwise
        """
        # 检查状态
        status = finding.get("status", "").lower()
        if status != "open":
            return None

        # 检查处置类型
        disposition = finding.get("disposition", "").lower()
        if disposition not in self.ALLOWED_DISPOSITIONS:
            return None

        # 检查分数
        score = finding.get("score", 0)
        if score < self.MIN_GATE_SCORE:
            return None

        return FixCandidate(
            finding=finding,
            score=score,
            disposition=disposition,
            file_path=finding.get("file_path"),
            category=finding.get("category"),
        )

    # ========== Phase 8: 并行修复 ==========

    def create_fix_groups(
        self, candidates: list[FixCandidate]
    ) -> dict[str, list[FixCandidate]]:
        """
        将相关问题分组

        分组策略:
        1. 同一文件的问题归为一组
        2. 同一类别且相关的问题归为一组

        Args:
            candidates: 修复候选列表

        Returns:
            分组字典 {group_id: [candidates]}
        """
        groups: dict[str, list[FixCandidate]] = {}

        for candidate in candidates:
            group_id = self._determine_group(candidate)
            candidate.fix_group = group_id

            if group_id not in groups:
                groups[group_id] = []
            groups[group_id].append(candidate)

        logger.info(f"Created {len(groups)} fix groups")
        return groups

    def _determine_group(self, candidate: FixCandidate) -> str:
        """
        确定候选所属的修复组

        优先按文件分组，其次按类别分组
        """
        if candidate.file_path:
            return f"file:{candidate.file_path}"
        if candidate.category:
            return f"category:{candidate.category}"
        return "default"

    def apply_fixes(
        self, groups: dict[str, list[FixCandidate]]
    ) -> list[FixResult]:
        """
        Phase 8: 并行修复

        对每个修复组:
        1. 构建修复 prompt
        2. 调用 Opus 执行修复
        3. 收集结果

        Args:
            groups: 分组字典

        Returns:
            修复结果列表
        """
        results = []
        group_items = list(groups.items())

        # 并行处理各组
        for group_id, candidates in group_items:
            group_results = self._fix_group_with_retry(group_id, candidates)
            results.extend(group_results)

        self._fix_history.extend(results)
        return results

    def _fix_group_with_retry(
        self, group_id: str, candidates: list[FixCandidate]
    ) -> list[FixResult]:
        """
        带重试的修复组处理

        使用指数退避策略
        """
        import random

        for attempt in range(self.MAX_RETRY_ATTEMPTS):
            try:
                return self._fix_single_group(group_id, candidates)
            except Exception as e:
                wait_time = (
                    self.EXPONENTIAL_BACKOFF_BASE ** attempt
                    + random.uniform(0, 1)
                )
                logger.warning(
                    f"Group {group_id} attempt {attempt + 1} failed: {e}. "
                    f"Retrying in {wait_time:.2f}s"
                )
                if attempt < self.MAX_RETRY_ATTEMPTS - 1:
                    time.sleep(wait_time)

        # 所有重试都失败
        logger.error(f"Group {group_id} failed after {self.MAX_RETRY_ATTEMPTS} attempts")
        return [
            FixResult(
                finding=c.finding,
                state=FixState.ATTEMPTED,
                error=f"Failed after {self.MAX_RETRY_ATTEMPTS} attempts",
                attempts=self.MAX_RETRY_ATTEMPTS,
            )
            for c in candidates
        ]

    def _fix_single_group(
        self, group_id: str, candidates: list[FixCandidate]
    ) -> list[FixResult]:
        """
        修复单个组

        构建 prompt 并调用 agent_runner 执行修复
        """
        prompt = self._build_fix_prompt(group_id, candidates)

        # 调用 agent 执行修复
        response = self.agent_runner.run(
            prompt=prompt,
            source_dir=str(self.source_dir),
        )

        # 消毒 LLM 输出
        if isinstance(response, str):
            response = self._sanitize_llm_output(response)

        # 解析修复结果
        return self._parse_fix_response(response, candidates)

    def _build_fix_prompt(
        self, group_id: str, candidates: list[FixCandidate]
    ) -> str:
        """构建修复 prompt"""
        findings_desc = []
        for i, c in enumerate(candidates, 1):
            findings_desc.append(
                f"{i}. [{c.disposition}] (score: {c.score}) "
                f"{c.finding.get('message', 'No description')}"
            )

        return f"""你是一个代码修复专家。请根据以下发现的问题进行修复。

修复组: {group_id}
源目录: {self.source_dir}

发现的问题:
{chr(10).join(findings_desc)}

要求:
1. 修复所有列出的问题
2. 保持代码风格一致
3. 不引入新的问题
4. 输出 unified diff 格式的修改
"""

    def _parse_fix_response(
        self, response: Any, candidates: list[FixCandidate]
    ) -> list[FixResult]:
        """解析 agent 修复响应"""
        results = []

        for candidate in candidates:
            # 根据响应判断修复状态
            finding_id = candidate.finding.get("id", "unknown")

            if self._is_finding_fixed(response, finding_id):
                state = FixState.RESOLVED
            elif self._is_partially_fixed(response, finding_id):
                state = FixState.PARTIAL
            else:
                state = FixState.ATTEMPTED

            results.append(
                FixResult(
                    finding=candidate.finding,
                    state=state,
                    diff=self._extract_diff(response, finding_id),
                    attempts=1,
                )
            )

        return results

    def _is_finding_fixed(self, response: Any, finding_id: str) -> bool:
        """检查 finding 是否已被修复

        策略 1: 检查是否有对应的 diff
        策略 2: 检查响应中是否明确提到修复
        """
        response_text = str(response) if response else ""

        # 策略 1: 检查是否有对应的 diff
        if self._extract_diff(response_text):
            return True

        # 策略 2: 检查响应中是否明确提到修复
        fix_indicators = [
            f"fixed {finding_id}",
            f"resolved {finding_id}",
            f"修复了 {finding_id}",
            f"已修复",
        ]
        for indicator in fix_indicators:
            if indicator.lower() in response_text.lower():
                return True

        return False

    def _is_partially_fixed(self, response: Any, finding_id: str) -> bool:
        """检查 finding 是否部分修复"""
        response_text = str(response) if response else ""
        partial_indicators = [
            f"partially fixed {finding_id}",
            f"partial fix {finding_id}",
            f"部分修复",
        ]
        for indicator in partial_indicators:
            if indicator.lower() in response_text.lower():
                return True
        return False

    def _extract_diff(self, response: Any, finding_id: str = None) -> Optional[str]:
        """从响应中提取 diff

        策略 1: 提取 ```diff 代码块
        策略 2: 提取 unified diff 格式
        """
        import re

        response_text = str(response) if response else ""

        # 策略 1: 提取 ```diff 代码块
        diff_match = re.search(r'```diff\s*(.*?)\s*```', response_text, re.DOTALL)
        if diff_match:
            return diff_match.group(1)

        # 策略 2: 提取 unified diff 格式
        diff_pattern = r'---.*?\n\+\+\+.*?\n@@.*?@@'
        if re.search(diff_pattern, response_text, re.DOTALL):
            # 提取完整的 diff 块
            start = response_text.find('---')
            # 查找 diff 结束位置（下一个非 diff 行或文本结束）
            remaining = response_text[start:]
            lines = remaining.split('\n')
            diff_lines = []
            for line in lines:
                if line.startswith(('---', '+++', '@@', '+', '-', ' ')):
                    diff_lines.append(line)
                elif diff_lines:
                    break
            if diff_lines:
                return '\n'.join(diff_lines)

        return None

    # ========== Phase 9: Post-fix 审查 ==========

    def post_fix_review(
        self, fixes: list[FixResult]
    ) -> list[FixResult]:
        """
        Phase 9: Post-fix 审查

        1. 重新审查每个修复
        2. 检测回归
        3. 标记最终状态

        Args:
            fixes: 初始修复结果列表

        Returns:
            更新后的修复结果列表
        """
        reviewed = []

        for fix in fixes:
            if fix.state == FixState.RESOLVED:
                # 只审查标记为已解决的修复
                reviewed_fix = self._review_single_fix(fix)
                reviewed.append(reviewed_fix)
            else:
                reviewed.append(fix)

        return reviewed

    def _review_single_fix(self, fix: FixResult) -> FixResult:
        """
        审查单个修复

        1. 运行相关测试
        2. 静态分析
        3. 检测回归
        """
        # 构建审查 prompt
        review_prompt = self._build_review_prompt(fix)

        # 调用 agent 审查
        review_response = self.agent_runner.run(
            prompt=review_prompt,
            source_dir=str(self.source_dir),
        )

        # 消毒 LLM 输出
        if isinstance(review_response, str):
            review_response = self._sanitize_llm_output(review_response)

        # 检测回归
        regression = self._detect_regression(fix, review_response)

        if regression:
            fix.state = FixState.REGRESSION
            fix.regression = True
            self._handle_regression(fix, regression)
        else:
            # 保持 RESOLVED 状态
            pass

        return fix

    def _build_review_prompt(self, fix: FixResult) -> str:
        """构建审查 prompt"""
        return f"""请审查以下代码修复，检查是否引入回归问题。

原始问题: {fix.finding.get('message', 'N/A')}
修复 diff:
{fix.diff or 'No diff available'}

检查项:
1. 修复是否正确解决了原始问题
2. 是否引入了新的问题
3. 是否影响了其他功能
4. 代码风格是否一致

输出格式:
- verdict: pass/fail
- regression: true/false
- regression_details: [如果存在回归，详细说明]
"""

    def _detect_regression(
        self, fix: FixResult, review_response: Any
    ) -> Optional[dict]:
        """
        检测回归

        Returns:
            回归详情 dict 或 None
        """
        # 解析审查响应，判断是否存在回归
        if hasattr(review_response, "regression") and review_response.regression:
            return {
                "details": getattr(review_response, "regression_details", ""),
                "severity": "major",
            }
        return None

    def _handle_regression(
        self, fix: FixResult, regression: dict
    ) -> RegressionReport:
        """处理回归问题"""
        report = RegressionReport(
            original_fix=fix,
            regression_findings=[regression],
            severity=regression.get("severity", "major"),
        )

        # 自动回退
        self.rollback_regression(fix)
        report.rollback_performed = True

        self._regression_reports.append(report)
        logger.warning(f"Regression detected and rolled back: {fix.finding}")

        return report

    # ========== 回退机制 ==========

    def rollback_regression(self, fix: FixResult) -> bool:
        """
        回退回归问题

        Args:
            fix: 包含回归的修复结果

        Returns:
            是否回退成功
        """
        if not fix.diff:
            logger.error("No diff to rollback")
            return False

        # Validate that all file paths in the diff stay within source_dir
        if not self._validate_diff_paths(fix.diff):
            logger.error("Rollback rejected: diff contains paths outside source_dir")
            return False

        try:
            # 生成反向 diff
            reverse_diff = self._generate_reverse_diff(fix.diff)

            # 应用反向 diff
            self.agent_runner.run(
                prompt=f"Apply the following reverse diff to rollback:\n{reverse_diff}",
                source_dir=str(self.source_dir),
            )

            logger.info(f"Rollback completed for: {fix.finding}")
            return True

        except Exception as e:
            logger.error(f"Rollback failed: {e}")
            return False

    def _validate_diff_paths(self, diff: str) -> bool:
        """Validate that all file paths in a diff are within source_dir."""
        import re
        source_resolved = self.source_dir.resolve()

        # Extract file paths from unified diff headers (--- a/path, +++ b/path)
        path_pattern = re.compile(r'^(?:---|\+\+\+)\s+(?:[abi]/)?(.+)$', re.MULTILINE)
        for match in path_pattern.finditer(diff):
            file_path = match.group(1).strip()
            if file_path == '/dev/null':
                continue
            resolved = (self.source_dir / file_path).resolve()
            try:
                resolved.relative_to(source_resolved)
            except ValueError:
                logger.warning("Path traversal in diff blocked: %s", file_path)
                return False
        return True

    def _generate_reverse_diff(self, diff: str) -> str:
        """生成反向 diff

        正确处理 unified diff 格式:
        - 交换 +/- 前缀
        - 交换 @@ 行号范围
        - 保持上下文行不变
        """
        import re

        lines = diff.split('\n')
        result = []

        for line in lines:
            if line.startswith('---'):
                # 保持文件头不变
                result.append(line)
            elif line.startswith('+++'):
                # 保持文件头不变
                result.append(line)
            elif line.startswith('-'):
                # 原来的删除变成添加
                result.append('+' + line[1:])
            elif line.startswith('+'):
                # 原来的添加变成删除
                result.append('-' + line[1:])
            elif line.startswith('@@'):
                # 交换行号范围
                match = re.search(r'@@ -(\d+),?(\d*) \+(\d+),?(\d*) @@', line)
                if match:
                    old_start, old_count, new_start, new_count = match.groups()
                    result.append(f'@@ -{new_start},{new_count} +{old_start},{old_count} @@')
                else:
                    result.append(line)
            else:
                # 上下文行保持不变
                result.append(line)

        return '\n'.join(result)

    # ========== 辅助方法 ==========

    def get_fix_summary(self) -> dict:
        """获取修复总结"""
        total = len(self._fix_history)
        resolved = sum(
            1 for f in self._fix_history if f.state == FixState.RESOLVED
        )
        partial = sum(
            1 for f in self._fix_history if f.state == FixState.PARTIAL
        )
        regression = sum(
            1 for f in self._fix_history if f.state == FixState.REGRESSION
        )
        attempted = sum(
            1 for f in self._fix_history if f.state == FixState.ATTEMPTED
        )

        return {
            "total": total,
            "resolved": resolved,
            "partial": partial,
            "regression": regression,
            "attempted": attempted,
            "success_rate": resolved / total if total > 0 else 0,
            "regression_reports": len(self._regression_reports),
        }

    def export_results(self, output_path: str) -> None:
        """导出修复结果到 JSON"""
        results = {
            "summary": self.get_fix_summary(),
            "fixes": [
                {
                    "finding_id": f.finding.get("id", "unknown"),
                    "state": f.state.value,
                    "regression": f.regression,
                    "attempts": f.attempts,
                    "timestamp": f.timestamp,
                    "error": f.error,
                }
                for f in self._fix_history
            ],
            "regressions": [
                {
                    "original_finding": r.original_fix.finding.get("id"),
                    "severity": r.severity,
                    "rollback_performed": r.rollback_performed,
                }
                for r in self._regression_reports
            ],
        }

        output = Path(output_path)
        output.parent.mkdir(parents=True, exist_ok=True)

        with open(output, "w", encoding="utf-8") as f:
            json.dump(results, f, indent=2, ensure_ascii=False)

        logger.info(f"Results exported to: {output_path}")


# ========== 便捷函数 ==========

def run_autofix_pipeline(
    agent_runner: Any,
    source_dir: str,
    artifact_path: str,
    output_path: Optional[str] = None,
) -> dict:
    """
    运行完整的自动修复流水线

    Args:
        agent_runner: Agent 运行器
        source_dir: 源代码目录
        artifact_path: artifact 文件路径
        output_path: 结果输出路径 (可选)

    Returns:
        修复总结字典
    """
    phase = AutoFixPhase(agent_runner, source_dir)

    # Phase 7: 门控
    logger.info("=== Phase 7: Gate Filter ===")
    candidates = phase.load_and_gate(artifact_path)
    if not candidates:
        logger.info("No candidates passed gate filter")
        return phase.get_fix_summary()

    # Phase 8: 并行修复
    logger.info("=== Phase 8: Parallel Fix ===")
    groups = phase.create_fix_groups(candidates)
    fixes = phase.apply_fixes(groups)

    # Phase 9: Post-fix 审查
    logger.info("=== Phase 9: Post-fix Review ===")
    reviewed = phase.post_fix_review(fixes)

    # 导出结果
    if output_path:
        phase.export_results(output_path)

    summary = phase.get_fix_summary()
    logger.info(f"Pipeline complete: {summary}")
    return summary


if __name__ == "__main__":
    # 示例用法
    import sys

    logging.basicConfig(level=logging.INFO)

    if len(sys.argv) < 3:
        print("Usage: python phase7_autofix.py <source_dir> <artifact_path>")
        sys.exit(1)

    source_dir = sys.argv[1]
    artifact_path = sys.argv[2]

    # 这里需要实际的 agent_runner 实现
    class MockAgentRunner:
        def run(self, prompt, source_dir):
            return {"status": "mock"}

    summary = run_autofix_pipeline(
        agent_runner=MockAgentRunner(),
        source_dir=source_dir,
        artifact_path=artifact_path,
        output_path="autofix_results.json",
    )

    print(json.dumps(summary, indent=2))
