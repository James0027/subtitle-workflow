"""Unit Format routes: trusted actor + path-bound task are required (fail-closed).

设计参照 ``code/backend/modules/culture_check/router.py``：

- 未注入认证适配器 → 503，绝不回落到匿名/模拟旁路；
- 主体缺 ``actor_id`` 或 ``allowed=False`` → 403；
- 路径任务与请求体 ``task_ref`` 不一致 → 403（禁止跨任务写入他任务产物）；
- 本路由纯确定性计算，零外部模型调用（``model_used=false``、``token_used=0``）。

路由不做持久化：``repository`` 仅在显式注入且实现 ``save_result`` 时落库，
未注入时只把候选结果返回调用方（不新建业务表，不冒充已归档）。
"""

from typing import Callable, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field

from .contract import (
    CONVERSION_POLICY_VERSION,
    DEFAULT_LOCALE,
    DEFAULT_MARKET,
    UnitFormatRequest,
    UnitFormatResult,
    UnitFormatUnitInput,
)
from .handler import UnitConversionError, extract_and_convert_units


class UnitFormatConvertRequest(BaseModel):
    """任务范围的单位/格式换算请求体。

    ``task_ref`` 可省略（默认取路径任务）；若显式给出则必须与路径一致。
    """

    model_config = ConfigDict(extra="forbid")

    task_ref: Optional[str] = Field(None, min_length=1, description="任务编号；省略时取路径任务")
    task_revision: int = Field(1, ge=1, description="当前目标稿修订版本")
    target_language: str = Field(DEFAULT_LOCALE, description="目标语言变体，首批固定 es-MX")
    target_market: str = Field(DEFAULT_MARKET, description="目标市场代码，首批固定 MX")
    conversion_policy_ref: str = Field(
        f"conversion-policy:{CONVERSION_POLICY_VERSION}",
        description="换算策略引用（版本随候选固化）",
    )
    units: List[UnitFormatUnitInput] = Field(..., min_length=1, description="待本地化字幕单元")


def create_unit_format_router(
    get_actor_context: Optional[Callable] = None,
    repository=None,
):
    """构造单位与格式本地化路由（默认 fail-closed）。"""
    router = APIRouter(prefix="/api/v1/units", tags=["Unit Format"])

    def current_actor(request: Request):
        if get_actor_context is None:
            raise HTTPException(503, "Unit format authentication adapter is not configured")
        actor = get_actor_context(request)

        def value(key, default=None):
            return actor.get(key, default) if isinstance(actor, dict) else getattr(actor, key, default)

        if not value("actor_id") or not value("allowed", False):
            raise HTTPException(403, "Unit format operation is not authorized")
        return actor

    def actor_value(actor, key):
        return actor.get(key) if isinstance(actor, dict) else getattr(actor, key, None)

    def persist(result: UnitFormatResult, actor) -> None:
        """显式注入的仓储必须可用；缺方法即 503，不静默吞掉落库失败。"""
        if repository is None:
            return
        saver = getattr(repository, "save_result", None)
        if saver is None:
            raise HTTPException(503, "Unit format repository adapter is not configured")
        saver(
            result,
            actor_id=actor_value(actor, "actor_id"),
            actor_role=actor_value(actor, "actor_role"),
        )

    @router.post("/tasks/{task_id}/convert", response_model=UnitFormatResult)
    def convert(task_id: str, req: UnitFormatConvertRequest, actor=Depends(current_actor)):
        if req.task_ref is not None and req.task_ref != task_id:
            raise HTTPException(403, "路径任务与请求任务不一致，禁止跨任务换算")
        request = UnitFormatRequest(
            task_ref=task_id,
            task_revision=req.task_revision,
            target_language=req.target_language,
            target_market=req.target_market,
            conversion_policy_ref=req.conversion_policy_ref,
            units=req.units,
        )
        try:
            result = extract_and_convert_units(request)
        except UnitConversionError as exc:
            # 反向验算/舍入超差：整条候选不输出数值，交人工复核。
            raise HTTPException(422, f"UNIT_CONVERSION_BLOCKED: {exc}")
        except ValueError as exc:
            raise HTTPException(400, f"UNIT_FORMAT_INVALID_REQUEST: {exc}")
        persist(result, actor)
        return result

    return router


# Default mounting is fail-closed: no actor adapter means 503, never anonymous output.
router = create_unit_format_router()
