import secrets
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional
from fastapi import Cookie, Depends, Header, HTTPException, Request, status

from code.backend.db import db, utc_now_iso
from code.backend.shared.models import ActorContext

def get_session_info(token: str) -> Optional[Dict[str, Any]]:
    if not token:
        return None
    with db.transaction() as conn:
        cur = conn.cursor()
        cur.execute("""
        SELECT s.session_token, s.operator_id, s.created_at as session_created_at,
               o.display_name, o.role, o.status
        FROM local_sessions s
        JOIN local_operators o ON s.operator_id = o.operator_id
        WHERE s.session_token = ?
        """, (token,))
        row = cur.fetchone()
        if not row:
            return None
        return dict(row)


def create_operator_session(operator_id: str) -> str:
    token = secrets.token_hex(24)
    now = utc_now_iso()
    with db.transaction() as conn:
        conn.execute("""
        INSERT INTO local_sessions (session_token, operator_id, created_at, expires_at)
        VALUES (?, ?, ?, NULL);
        """, (token, operator_id, now))
    return token


def register_local_operator(display_name: str, role: str = "media_operator") -> Dict[str, Any]:
    clean_name = display_name.strip()
    if not clean_name:
        raise ValueError("操作人姓名/显示名称不能为空")
    
    operator_id = f"op_{uuid.uuid4().hex[:8]}"
    now = utc_now_iso()
    with db.transaction() as conn:
        conn.execute("""
        INSERT INTO local_operators (operator_id, display_name, role, registered_at, status)
        VALUES (?, ?, ?, ?, 'active');
        """, (operator_id, clean_name, role, now))
    
    session_token = create_operator_session(operator_id)
    return {
        "operator_id": operator_id,
        "display_name": clean_name,
        "role": role,
        "registered_at": now,
        "session_token": session_token,
    }


def list_local_operators() -> List[Dict[str, Any]]:
    with db.transaction() as conn:
        cur = conn.cursor()
        cur.execute("SELECT operator_id, display_name, role, registered_at, status FROM local_operators")
        return [dict(r) for r in cur.fetchall()]


def get_current_actor(request: Request) -> ActorContext:
    """
    Resolves the authenticated actor strictly from server sessions.
    Rejects spoofable client X-Actor-* headers in production.
    """
    token = None
    # 1. Cookie
    token = request.cookies.get("session_token")
    
    # 2. X-Session-Token header
    if not token:
        token = request.headers.get("X-Session-Token")
        
    # 3. Authorization: Bearer <token>
    if not token:
        auth_hdr = request.headers.get("Authorization", "")
        if auth_hdr.startswith("Bearer "):
            token = auth_hdr[7:].strip()

    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="未认证会话：请先在本机登记或登录真实操作人员身份，杜绝客户端随意自报身份。",
        )

    session = get_session_info(token)
    if not session:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="会话无效或已过期，请重新登录或登记本地操作人。",
        )

    is_denied = (session["status"] != "active") or (session["role"] == "human_denied")
    return ActorContext(
        actor_id=session["operator_id"],
        actor_type="human",
        actor_role=session["role"],
        allowed=not is_denied,
    )


def require_human_actor(actor: ActorContext, action_name: str = "操作") -> None:
    """
    Strictly checks that the actor is a human and has permission.
    Strictly forbids service_actor from confirming master or task.
    """
    if not actor.allowed or actor.actor_role == "human_denied":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"无权限执行{action_name}（主体受限或未授权）。",
        )

    if actor.actor_type == "service_actor":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"禁止工程服务/Agent服务主体代签或执行{action_name}，必须由真人操作员负责确认。",
        )


def require_permission(actor: ActorContext, action_name: str = "操作") -> None:
    """
    Checks that the actor is allowed.
    """
    if not actor.allowed or actor.actor_role == "human_denied":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"无权限执行{action_name}。",
        )
