import hashlib
import json
import re
import uuid
from typing import Any, Dict, List, Optional
from code.backend.db import Database, db, utc_now_iso
from code.backend.modules.translation.contract import KnowledgeItemCreate, KnowledgeItemUpdate

# 市场 -> 目标语言的标准映射；用于服务端校验，避免"MX 市场 + en 语言"这类自相矛盾条目静默落库。
MARKET_LANGUAGES = {
    "MX": "es-MX",
    "US": "en",
    "LATAM": "es",
    "ES": "es",
    "BR": "pt",
    "ID": "id",
}
LANGUAGE_CODE = re.compile(r"^[A-Za-z]{2,3}(?:-[A-Za-z0-9]{2,8})*$")


class KnowledgeValidationError(ValueError):
    """知识条目业务校验失败；由接口层映射为 HTTP 400。"""


class KnowledgeService:
    def __init__(self, database: Optional[Database] = None):
        self._db = database

    @property
    def db(self) -> Database:
        return self._db if self._db is not None else db

    @db.setter
    def db(self, value: Database):
        self._db = value

    @staticmethod
    def _archive(conn, item, action, actor_id=None):
        """Append immutable content snapshots; historical runs also embed exact context."""
        conn.execute("""CREATE TABLE IF NOT EXISTS knowledge_versions(
            item_id TEXT NOT NULL, revision INTEGER NOT NULL, content_hash TEXT NOT NULL,
            snapshot TEXT NOT NULL, action TEXT NOT NULL, actor_id TEXT, created_at TEXT NOT NULL,
            PRIMARY KEY(item_id,revision))""")
        payload=dict(item)
        payload['is_locked']=bool(payload.get('is_locked'))
        if action=='delete': payload['deleted']=True
        encoded=json.dumps(payload,sort_keys=True,ensure_ascii=False)
        digest=hashlib.sha256(encoded.encode()).hexdigest()
        last=conn.execute("SELECT revision,content_hash FROM knowledge_versions WHERE item_id=? ORDER BY revision DESC LIMIT 1",(payload['item_id'],)).fetchone()
        if last and last['content_hash']==digest:
            return last['revision']
        revision=last['revision']+1 if last else 1
        conn.execute(
            "INSERT INTO knowledge_versions (item_id,revision,content_hash,snapshot,action,actor_id,created_at) VALUES (?,?,?,?,?,?,?)",
            (payload['item_id'],revision,digest,encoded,action,actor_id,utc_now_iso()),
        )
        return revision

    @staticmethod
    def _language_matches(language: str, expected: str) -> bool:
        """语言兼容判断：主语言必须一致；两边都带地区时才比较地区。

        允许市场 MX 配 es 或 es-MX（同一主语言），但拒绝 MX 配 en 或 es-ES。
        """
        lang_parts = language.replace("_", "-").split("-")
        exp_parts = expected.replace("_", "-").split("-")
        if lang_parts[0].casefold() != exp_parts[0].casefold():
            return False
        lang_region = lang_parts[1].casefold() if len(lang_parts) > 1 else None
        exp_region = exp_parts[1].casefold() if len(exp_parts) > 1 else None
        if lang_region and exp_region:
            return lang_region == exp_region
        return True

    @staticmethod
    def _normalize_scope(category: str, language: Optional[str], market: Optional[str]):
        """校验并归一化目标语言/市场。

        - 已知市场（MX/US/LATAM/ES/BR/ID）必须与标准语言同主语言；术语缺语言时自动补标准语言。
        - 未知市场代码保留原样（便于后续新增市场），但语言格式仍须合法。
        - 角色/场景不强制绑定语言，允许为空。
        """
        lang = language.strip() if isinstance(language, str) and language.strip() else None
        mkt = market.strip().upper() if isinstance(market, str) and market.strip() else None
        if lang is not None and not LANGUAGE_CODE.match(lang):
            raise KnowledgeValidationError(f"目标语言代码不合法: {lang}")
        if mkt in MARKET_LANGUAGES:
            expected = MARKET_LANGUAGES[mkt]
            if lang is None and category == "glossary":
                lang = expected
            elif lang is not None and not KnowledgeService._language_matches(lang, expected):
                raise KnowledgeValidationError(
                    f"目标市场 {mkt} 与目标语言 {lang} 不匹配，应为 {expected}（同主语言可接受）"
                )
        return lang, mkt

    @staticmethod
    def _emit_event(conn, event_type: str, actor_id: Optional[str], actor_role: Optional[str],
                    payload: Dict[str, Any], task_id: Optional[str] = None) -> str:
        """写入既有 events 表，使知识变更进入统一审计流（不复用 ReviewDecision）。"""
        now = utc_now_iso()
        event_id = f"evt_{uuid.uuid4().hex[:12]}"
        conn.execute(
            """INSERT INTO events (
                event_id, event_type, event_at, received_at, task_id,
                media_id, run_id, actor_id, actor_type, actor_role,
                operation_id, dedup_key, payload, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);""",
            (
                event_id, event_type, now, now, task_id,
                None, None, actor_id or "system",
                "human" if actor_id else "service_actor", actor_role or "operator",
                f"op_{uuid.uuid4().hex[:8]}", f"dedup_{event_id}",
                json.dumps(payload, ensure_ascii=False), now,
            ),
        )
        return event_id

    def _event_payload(self, item: Dict[str, Any], revision: int, changed_fields: Optional[List[str]] = None) -> Dict[str, Any]:
        return {
            "item_id": item["item_id"],
            "project_id": item["project_id"],
            "category": item["category"],
            "status": item["status"],
            "is_locked": bool(item.get("is_locked")),
            "target_market": item.get("target_market"),
            "target_language": item.get("target_language"),
            "revision": revision,
            "changed_fields": changed_fields or [],
        }

    def create_item(self, item: KnowledgeItemCreate, actor_id: Optional[str] = None,
                    actor_role: Optional[str] = None) -> Dict[str, Any]:
        item_id = f"k_{uuid.uuid4().hex[:12]}"
        now = utc_now_iso()
        language, market = self._normalize_scope(item.category, item.target_language, item.target_market)
        with self.db.transaction() as conn:
            conn.execute("""
            INSERT INTO knowledge_items (
                item_id, project_id, task_id, category, source_text,
                target_text, target_language, target_market, is_locked,
                status, scope, evidence, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
            """, (
                item_id, item.project_id, item.task_id, item.category, item.source_text.strip(),
                item.target_text.strip() if item.target_text else None,
                language, market, 1 if item.is_locked else 0,
                item.status, item.scope, item.evidence, now, now
            ))
            row=conn.execute("SELECT * FROM knowledge_items WHERE item_id=?",(item_id,)).fetchone()
            revision = self._archive(conn,row,"create",actor_id)
            self._emit_event(conn, "knowledge.created", actor_id, actor_role,
                             self._event_payload(dict(row), revision), item.task_id)
        return self.get_item(item_id)

    def get_item(self, item_id: str) -> Optional[Dict[str, Any]]:
        with self.db.transaction() as conn:
            cur = conn.cursor()
            cur.execute("SELECT * FROM knowledge_items WHERE item_id = ?", (item_id,))
            row = cur.fetchone()
            if not row:
                return None
            res = dict(row)
            res["is_locked"] = bool(res["is_locked"])
            return res

    def list_items(
        self,
        project_id: str = "PRJ-DEFAULT",
        category: Optional[str] = None,
        scope: Optional[str] = None,
        only_confirmed: bool = False,
    ) -> List[Dict[str, Any]]:
        with self.db.transaction() as conn:
            cur = conn.cursor()
            query = "SELECT * FROM knowledge_items WHERE project_id = ?"
            params: List[Any] = [project_id]

            if category:
                query += " AND category = ?"
                params.append(category)
            if scope:
                query += " AND scope = ?"
                params.append(scope)
            if only_confirmed:
                query += " AND status = 'CONFIRMED'"

            query += " ORDER BY created_at DESC"
            cur.execute(query, tuple(params))
            items = []
            for r in cur.fetchall():
                d = dict(r)
                d["is_locked"] = bool(d["is_locked"])
                items.append(d)
            return items

    def update_item(self, item_id: str, updates: KnowledgeItemUpdate,
                    actor_id: Optional[str] = None, actor_role: Optional[str] = None) -> Optional[Dict[str, Any]]:
        now = utc_now_iso()
        touched = updates.model_fields_set
        with self.db.transaction() as conn:
            cur = conn.cursor()
            cur.execute("SELECT * FROM knowledge_items WHERE item_id = ?", (item_id,))
            old=cur.fetchone()
            if not old:
                return None
            old_d = dict(old)
            new_lang = updates.target_language if "target_language" in touched else old_d["target_language"]
            new_market = updates.target_market if "target_market" in touched else old_d["target_market"]
            language, market = self._normalize_scope(old_d["category"], new_lang, new_market)

            fields = ["updated_at = ?"]
            params: List[Any] = [now]
            changed: List[str] = []

            if updates.source_text is not None:
                fields.append("source_text = ?")
                params.append(updates.source_text.strip())
                changed.append("source_text")
            if updates.target_text is not None:
                fields.append("target_text = ?")
                params.append(updates.target_text.strip())
                changed.append("target_text")
            if updates.is_locked is not None:
                fields.append("is_locked = ?")
                params.append(1 if updates.is_locked else 0)
                changed.append("is_locked")
            if updates.status is not None:
                fields.append("status = ?")
                params.append(updates.status)
                changed.append("status")
            if "target_language" in touched or language != old_d["target_language"]:
                fields.append("target_language = ?")
                params.append(language)
                changed.append("target_language")
            if "target_market" in touched or market != old_d["target_market"]:
                fields.append("target_market = ?")
                params.append(market)
                changed.append("target_market")

            if changed:
                self._archive(conn, old, "before_update", actor_id)
                params.append(item_id)
                conn.execute(f"UPDATE knowledge_items SET {', '.join(fields)} WHERE item_id = ?", tuple(params))
                row=conn.execute("SELECT * FROM knowledge_items WHERE item_id=?",(item_id,)).fetchone()
                revision = self._archive(conn,row,"update",actor_id)
                self._emit_event(conn, "knowledge.updated", actor_id, actor_role,
                                 self._event_payload(dict(row), revision, changed), row["task_id"])

        return self.get_item(item_id)

    def delete_item(self, item_id: str, actor_id: Optional[str] = None,
                    actor_role: Optional[str] = None) -> bool:
        with self.db.transaction() as conn:
            cur = conn.cursor()
            old=cur.execute("SELECT * FROM knowledge_items WHERE item_id=?",(item_id,)).fetchone()
            if old:
                self._archive(conn,old,"before_delete",actor_id)
                revision = self._archive(conn,old,"delete",actor_id)
                self._emit_event(conn, "knowledge.deleted", actor_id, actor_role,
                                 self._event_payload(dict(old), revision), old["task_id"])
            cur.execute("DELETE FROM knowledge_items WHERE item_id = ?", (item_id,))
            return cur.rowcount > 0

    def query_locked_terms_for_units(
        self,
        project_id: str,
        units_text: List[str],
        target_language: Optional[str] = None,
        target_market: Optional[str] = None,
        task_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Structured retrieval: extracts locked terms relevant to the dialogue texts without dumping the whole DB.
        """
        all_terms = self.list_items(project_id=project_id, category="glossary", only_confirmed=True)
        # Filter locked terms
        locked = [t for t in all_terms if t.get("is_locked")]
        combined_text = " ".join(units_text)

        hits: List[Dict[str, Any]] = []
        for term in locked:
            if not self._applies(term, target_language, target_market, task_id):
                continue
            src = term.get("source_text", "")
            if not src:
                continue
            # Literal or case-insensitive match
            if src.lower() in combined_text.lower():
                hits.append({
                    "term_id": term["item_id"],
                    "source_term": src,
                    "target_term": term.get("target_text") or "",
                    "target_language": term.get("target_language"),
                    "target_market": term.get("target_market"),
                    "is_locked": True,
                    "context_ref": self.snapshot_ref(term),
                })
        grouped = {}
        for hit in hits:
            grouped.setdefault(hit["source_term"].casefold(),set()).add(hit["target_term"].casefold())
        if any(len(values)>1 for values in grouped.values()):
            raise ValueError("适用锁词互相冲突，请先人工确认译法")
        return hits

    @staticmethod
    def _applies(item, language=None, market=None, task_id=None):
        for field, requested in (("target_language",language),("target_market",market)):
            specified = item.get(field)
            if specified and (not requested or specified.casefold()!=requested.casefold()):
                return False
        if item.get("scope") != "project" and (not task_id or item.get("task_id") != task_id):
            return False
        return True

    @staticmethod
    def snapshot_ref(item):
        payload={k:v for k,v in item.items() if k not in ("context_ref",)}
        digest=hashlib.sha256(json.dumps(payload,sort_keys=True,ensure_ascii=False).encode()).hexdigest()
        return {"item_id":item["item_id"],"content_hash":digest,"snapshot":payload}

    def query_characters(self, project_id, units_text=None, character_refs=None, task_id=None,
                         target_language=None,target_market=None):
        text=" ".join(units_text or [])
        refs=set(character_refs or [])
        selected=[]
        for item in self.list_items(project_id=project_id,category="character",only_confirmed=True):
            if not self._applies(item,target_language,target_market,task_id):
                continue
            if item["item_id"] not in refs and item["source_text"] not in refs and item["source_text"].casefold() not in text.casefold():
                continue
            item["context_ref"]=self.snapshot_ref(item)
            selected.append(item)
        return selected

    def query_confirmed_history(self, project_id, task_id, units_text, target_language, target_market, limit=8):
        """Exact-source memory only; same work or same task, current confirmed revisions."""
        if not units_text:
            return []
        with self.db.transaction() as conn:
            rows=conn.execute("""SELECT t.*,s.text AS source_text FROM translations t
                JOIN source_utterances s ON s.task_id=t.task_id AND s.unit_id=t.unit_id AND s.transcript_revision=t.source_revision
                JOIN tasks tt ON tt.task_id=t.task_id JOIN tasks ct ON ct.task_id=?
                LEFT JOIN media tm ON tm.media_id=tt.media_id LEFT JOIN media cm ON cm.media_id=ct.media_id
                WHERE tt.project_id=? AND t.target_language=? AND t.target_market=?
                AND (t.task_id=ct.task_id OR (tm.title_id IS NOT NULL AND tm.title_id=cm.title_id))
                AND t.status IN ('CONFIRMED','MANUAL_LOCKED') AND t.confirmed_by IS NOT NULL
                AND t.source_revision=(SELECT MAX(revision) FROM source_transcripts WHERE task_id=t.task_id)
                AND EXISTS (SELECT 1 FROM source_transcripts st WHERE st.task_id=t.task_id AND st.revision=t.source_revision AND st.status='CONFIRMED')
                AND t.translation_revision=(SELECT MAX(t2.translation_revision) FROM translations t2 WHERE t2.task_id=t.task_id AND t2.unit_id=t.unit_id AND t2.source_revision=t.source_revision)
                ORDER BY t.updated_at DESC""",(task_id,project_id,target_language,target_market)).fetchall()
        wanted=set(units_text)
        result=[]
        for row in rows:
            item=dict(row)
            if item['source_text'] not in wanted:
                continue
            result.append({"translation_id":item['translation_id'],"revision":item['translation_revision'],
                "task_id":item['task_id'],"unit_id":item['unit_id'],"source_revision":item['source_revision'],
                "source_text":item['source_text'],"translation":item['text']})
            if len(result)>=limit:
                break
        return result


knowledge_service = KnowledgeService()
