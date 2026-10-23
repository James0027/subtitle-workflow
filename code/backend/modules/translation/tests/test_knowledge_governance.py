import json
import pytest

from code.backend.db import Database
from ..contract import KnowledgeItemCreate, KnowledgeItemUpdate
from ..knowledge import KnowledgeService, KnowledgeValidationError


def _versions(db, item_id):
    with db.transaction() as conn:
        return [dict(r) for r in conn.execute(
            "SELECT revision, action, actor_id FROM knowledge_versions WHERE item_id=? ORDER BY revision",
            (item_id,),
        )]


def _events(db, item_id):
    with db.transaction() as conn:
        rows = [dict(r) for r in conn.execute(
            "SELECT event_type, actor_id, actor_type, actor_role, payload FROM events "
            "WHERE event_type LIKE 'knowledge.%' ORDER BY rowid"
        )]
    return [r for r in rows if json.loads(r["payload"]).get("item_id") == item_id]


def test_knowledge_versions_table_created_by_migration(tmp_path):
    fresh = Database(db_path=tmp_path / "fresh.db")
    with fresh.transaction() as conn:
        names = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    assert "knowledge_versions" in names


def test_update_records_actor_and_archives(isolated_test_env):
    db = isolated_test_env["db"]
    svc = KnowledgeService(database=db)
    item = svc.create_item(
        KnowledgeItemCreate(source_text="甲", target_text="A", target_language="es-MX", target_market="MX"),
        actor_id="op_creator", actor_role="media_operator",
    )
    svc.update_item(
        item["item_id"], KnowledgeItemUpdate(target_text="B"),
        actor_id="op_editor", actor_role="media_operator",
    )
    versions = _versions(db, item["item_id"])
    # 相同内容不重复留档：create 已是 A，before_update 的 A 与它同 hash 被去重
    assert [v["action"] for v in versions] == ["create", "update"]
    assert versions[0]["actor_id"] == "op_creator"
    assert versions[1]["revision"] == 2
    assert versions[1]["actor_id"] == "op_editor"


def test_market_language_mismatch_rejected(isolated_test_env):
    svc = KnowledgeService(database=isolated_test_env["db"])
    with pytest.raises(KnowledgeValidationError, match="不匹配"):
        svc.create_item(KnowledgeItemCreate(source_text="错配", target_text="X", target_language="en", target_market="MX"))


def test_glossary_market_without_language_fills_standard_language(isolated_test_env):
    svc = KnowledgeService(database=isolated_test_env["db"])
    item = svc.create_item(KnowledgeItemCreate(source_text="自动补语言", target_text="Y", target_market="MX"))
    assert item["target_language"] == "es-MX"
    assert item["target_market"] == "MX"


def test_update_can_change_market_and_language(isolated_test_env):
    db = isolated_test_env["db"]
    svc = KnowledgeService(database=db)
    item = svc.create_item(KnowledgeItemCreate(source_text="改市场", target_text="A", target_language="es-MX", target_market="MX"))
    updated = svc.update_item(
        item["item_id"], KnowledgeItemUpdate(target_language="en", target_market="US"),
        actor_id="op_editor",
    )
    assert updated["target_language"] == "en"
    assert updated["target_market"] == "US"
    with pytest.raises(KnowledgeValidationError):
        svc.update_item(item["item_id"], KnowledgeItemUpdate(target_language="es-MX"))


def test_knowledge_mutations_emit_events(isolated_test_env):
    db = isolated_test_env["db"]
    svc = KnowledgeService(database=db)
    item = svc.create_item(
        KnowledgeItemCreate(source_text="事件", target_text="A", target_market="MX"),
        actor_id="op_human", actor_role="media_operator",
    )
    svc.update_item(item["item_id"], KnowledgeItemUpdate(is_locked=True), actor_id="op_human", actor_role="media_operator")
    svc.delete_item(item["item_id"], actor_id="op_human", actor_role="media_operator")

    events = _events(db, item["item_id"])
    assert [e["event_type"] for e in events] == ["knowledge.created", "knowledge.updated", "knowledge.deleted"]
    assert all(e["actor_id"] == "op_human" and e["actor_type"] == "human" for e in events)
    updated = json.loads(events[1]["payload"])
    assert updated["changed_fields"] == ["is_locked"]
    assert updated["revision"] >= 2
