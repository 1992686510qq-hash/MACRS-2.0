"""
MACRS Artifact 状态管理模块

Finding state 流转: open -> attempted -> resolved/partial/regression
持久化到 JSON 文件，支持断点续传。
"""

from dataclasses import dataclass, field, asdict
from typing import Optional
from enum import Enum
from datetime import datetime
import json
from pathlib import Path

from validation_gate import Disposition


class FindingState(Enum):
    OPEN = "open"
    ATTEMPTED = "attempted"
    RESOLVED = "resolved"
    PARTIAL = "partial"
    REGRESSION = "regression"


# 合法的状态流转表
_VALID_TRANSITIONS: dict[FindingState, set[FindingState]] = {
    FindingState.OPEN: {FindingState.ATTEMPTED, FindingState.RESOLVED, FindingState.PARTIAL, FindingState.REGRESSION},
    FindingState.ATTEMPTED: {FindingState.RESOLVED, FindingState.PARTIAL, FindingState.REGRESSION},
    FindingState.RESOLVED: {FindingState.REGRESSION},      # 允许 RESOLVED -> REGRESSION
    FindingState.PARTIAL: {FindingState.RESOLVED, FindingState.REGRESSION},
    FindingState.REGRESSION: {FindingState.ATTEMPTED},     # 可重新尝试
}


@dataclass
class FindingArtifact:
    id: str
    file: str
    line: int
    description: str
    severity: str
    state: FindingState = FindingState.OPEN
    disposition: Optional[Disposition] = None
    score: int = 0
    confidence: int = 50
    source_families: list[str] = field(default_factory=list)
    history: list[dict] = field(default_factory=list)


class ArtifactManager:
    """管理 FindingArtifact 的增删改查与持久化。"""

    def __init__(self, artifact_path: str):
        self.artifact_path = Path(artifact_path)
        self.findings: dict[str, FindingArtifact] = {}
        self._load()

    # ── 持久化 ──────────────────────────────────────────────

    def _load(self):
        """从 JSON 文件加载 artifact，文件不存在则跳过。"""
        if not self.artifact_path.exists():
            return
        try:
            with open(self.artifact_path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except (json.JSONDecodeError, OSError):
            return

        for item in data.get("findings", []):
            finding = FindingArtifact(
                id=item["id"],
                file=item["file"],
                line=item["line"],
                description=item["description"],
                severity=item["severity"],
                state=FindingState(item["state"]),
                disposition=Disposition(item["disposition"]) if item.get("disposition") else None,
                score=item.get("score", 0),
                confidence=item.get("confidence", 50),
                source_families=item.get("source_families", []),
                history=item.get("history", []),
            )
            self.findings[finding.id] = finding

    def save(self):
        """将当前 findings 持久化到 JSON 文件（原子写入）。"""
        self.artifact_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "saved_at": datetime.now().isoformat(),
            "count": len(self.findings),
            "findings": [self._serialize(f) for f in self.findings.values()],
        }
        tmp = self.artifact_path.with_suffix(".tmp")
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
        tmp.replace(self.artifact_path)

    @staticmethod
    def _serialize(finding: FindingArtifact) -> dict:
        """将 FindingArtifact 转为可序列化字典。"""
        d = asdict(finding)
        d["state"] = finding.state.value
        if finding.disposition is not None:
            d["disposition"] = finding.disposition.value
        return d

    # ── CRUD ─────────────────────────────────────────────────

    def add_finding(self, finding: FindingArtifact):
        """添加新发现并自动保存。"""
        if finding.id in self.findings:
            raise ValueError(f"Finding '{finding.id}' already exists")
        finding.history.append({
            "action": "created",
            "state": finding.state.value,
            "ts": datetime.now().isoformat(),
        })
        self.findings[finding.id] = finding
        self.save()

    def get_finding(self, finding_id: str) -> Optional[FindingArtifact]:
        """按 ID 获取单个 finding。"""
        return self.findings.get(finding_id)

    def remove_finding(self, finding_id: str) -> bool:
        """删除指定 finding 并保存，返回是否成功。"""
        if finding_id not in self.findings:
            return False
        del self.findings[finding_id]
        self.save()
        return True

    # ── 状态流转 ─────────────────────────────────────────────

    def update_state(self, finding_id: str, new_state: FindingState, reason: str = ""):
        """更新 finding 的状态，校验合法流转后自动保存。"""
        finding = self._require(finding_id)
        allowed = _VALID_TRANSITIONS.get(finding.state, set())
        if new_state not in allowed:
            raise ValueError(
                f"Invalid transition: {finding.state.value} -> {new_state.value}. "
                f"Allowed: {[s.value for s in allowed]}"
            )
        old_state = finding.state
        finding.state = new_state
        finding.history.append({
            "action": "state_change",
            "from": old_state.value,
            "to": new_state.value,
            "reason": reason,
            "ts": datetime.now().isoformat(),
        })
        self.save()

    def update_disposition(self, finding_id: str, disposition: Disposition):
        """更新 finding 的 disposition 并自动保存。"""
        finding = self._require(finding_id)
        old = finding.disposition
        finding.disposition = disposition
        finding.history.append({
            "action": "disposition_change",
            "from": old.value if old else None,
            "to": disposition.value,
            "ts": datetime.now().isoformat(),
        })
        self.save()

    def update_score(self, finding_id: str, score: int, confidence: Optional[int] = None):
        """更新评分和可选置信度。"""
        finding = self._require(finding_id)
        finding.score = max(0, min(100, score))
        if confidence is not None:
            finding.confidence = max(0, min(100, confidence))
        finding.history.append({
            "action": "score_update",
            "score": finding.score,
            "confidence": finding.confidence,
            "ts": datetime.now().isoformat(),
        })
        self.save()

    # ── 查询 ─────────────────────────────────────────────────

    def get_by_state(self, state: FindingState) -> list[FindingArtifact]:
        """按状态筛选 findings。"""
        return [f for f in self.findings.values() if f.state == state]

    def get_by_disposition(self, disposition: Disposition) -> list[FindingArtifact]:
        """按 disposition 筛选 findings。"""
        return [f for f in self.findings.values() if f.disposition == disposition]

    def get_gate_candidates(self, min_score: int = 60) -> list[FindingArtifact]:
        """获取门控候选：score >= min_score 且 state 为 OPEN 或 ATTEMPTED。"""
        active = {FindingState.OPEN, FindingState.ATTEMPTED}
        return sorted(
            [f for f in self.findings.values() if f.state in active and f.score >= min_score],
            key=lambda f: f.score,
            reverse=True,
        )

    def get_pending(self) -> list[FindingArtifact]:
        """获取待验证的 findings（disposition 为 PENDING_VALIDATION）。"""
        return [
            f for f in self.findings.values()
            if f.disposition == Disposition.PENDING_VALIDATION
        ]

    # ── 统计 ─────────────────────────────────────────────────

    def export_summary(self) -> dict:
        """导出统计摘要。"""
        state_counts = {s.value: 0 for s in FindingState}
        disposition_counts = {}
        severity_counts = {}
        total_score = 0

        for f in self.findings.values():
            state_counts[f.state.value] += 1

            if f.disposition:
                disposition_counts[f.disposition.value] = disposition_counts.get(f.disposition.value, 0) + 1

            severity_counts[f.severity] = severity_counts.get(f.severity, 0) + 1
            total_score += f.score

        count = len(self.findings)
        return {
            "total": count,
            "avg_score": round(total_score / count, 1) if count else 0,
            "by_state": state_counts,
            "by_disposition": disposition_counts,
            "by_severity": severity_counts,
            "open_active": state_counts[FindingState.OPEN.value] + state_counts[FindingState.ATTEMPTED.value],
            "resolved": state_counts[FindingState.RESOLVED.value],
        }

    # ── 内部工具 ─────────────────────────────────────────────

    def _require(self, finding_id: str) -> FindingArtifact:
        """获取 finding，不存在则抛异常。"""
        finding = self.findings.get(finding_id)
        if finding is None:
            raise KeyError(f"Finding '{finding_id}' not found")
        return finding
