import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Generator, List, Optional

from config.settings import DB_PATH

def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


class Database:
    def __init__(self, db_path: Path = DB_PATH):
        self.db_path = Path(db_path).resolve()
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.init_db()

    def get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path), timeout=30.0)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON;")
        conn.execute("PRAGMA journal_mode = WAL;")
        return conn

    @contextmanager
    def transaction(self) -> Generator[sqlite3.Connection, None, None]:
        conn = self.get_connection()
        try:
            conn.execute("BEGIN IMMEDIATE;")
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def init_db(self) -> None:
        with self.transaction() as conn:
            conn.execute("""
            CREATE TABLE IF NOT EXISTS schema_migrations (
                version INTEGER PRIMARY KEY,
                applied_at TEXT NOT NULL
            );
            """)

            # Local Operators & Sessions
            conn.execute("""
            CREATE TABLE IF NOT EXISTS local_operators (
                operator_id TEXT PRIMARY KEY,
                display_name TEXT NOT NULL,
                role TEXT NOT NULL DEFAULT 'media_operator',
                registered_at TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'active'
            );
            """)

            conn.execute("""
            CREATE TABLE IF NOT EXISTS local_sessions (
                session_token TEXT PRIMARY KEY,
                operator_id TEXT NOT NULL,
                created_at TEXT NOT NULL,
                expires_at TEXT,
                FOREIGN KEY (operator_id) REFERENCES local_operators(operator_id)
            );
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_sessions_token ON local_sessions(session_token);")

            # Projects
            conn.execute("""
            CREATE TABLE IF NOT EXISTS projects (
                project_id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            """)

            # Assets
            conn.execute("""
            CREATE TABLE IF NOT EXISTS assets (
                asset_id TEXT PRIMARY KEY,
                project_id TEXT NOT NULL,
                media_id TEXT,
                kind TEXT NOT NULL,
                origin TEXT NOT NULL,
                source_uri TEXT NOT NULL,
                rights_ref TEXT NOT NULL,
                checksum_sha256 TEXT NOT NULL,
                size_bytes INTEGER NOT NULL,
                mime_type TEXT NOT NULL,
                supplied_version TEXT,
                parent_asset_ids TEXT NOT NULL,
                transform TEXT,
                availability TEXT NOT NULL,
                inspection TEXT,
                privacy TEXT NOT NULL,
                revision INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL,
                created_by TEXT NOT NULL
            );
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_assets_project ON assets(project_id);")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_assets_checksum ON assets(checksum_sha256);")

            # Media (Master)
            conn.execute("""
            CREATE TABLE IF NOT EXISTS media (
                media_id TEXT PRIMARY KEY,
                project_id TEXT NOT NULL,
                title_id TEXT NOT NULL,
                episode_id TEXT NOT NULL,
                master_video_asset_id TEXT,
                primary_audio_asset_id TEXT,
                duration_ms INTEGER,
                frame_rate TEXT,
                master_status TEXT NOT NULL,
                match_checks TEXT NOT NULL,
                confirmed_by TEXT,
                confirmed_at TEXT,
                supersedes_media_id TEXT,
                content_dimensions TEXT NOT NULL,
                revision INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL,
                created_by TEXT NOT NULL
            );
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_media_project ON media(project_id);")

            # Tasks
            conn.execute("""
            CREATE TABLE IF NOT EXISTS tasks (
                task_id TEXT PRIMARY KEY,
                project_id TEXT NOT NULL,
                task_revision INTEGER NOT NULL DEFAULT 1,
                request_key TEXT NOT NULL,
                media_id TEXT,
                parent_task_id TEXT,
                task_type TEXT NOT NULL,
                execution_mode TEXT NOT NULL,
                execution_policy TEXT NOT NULL,
                purpose TEXT,
                owner_id TEXT,
                source_locale TEXT NOT NULL,
                processing_route TEXT NOT NULL,
                input_asset_ids TEXT NOT NULL,
                range TEXT NOT NULL,
                target_variants TEXT NOT NULL,
                target_scope_status TEXT NOT NULL,
                output_spec TEXT NOT NULL,
                delivery_units TEXT NOT NULL,
                module_plan TEXT NOT NULL,
                missing_items TEXT NOT NULL,
                readiness TEXT NOT NULL,
                task_status TEXT NOT NULL,
                confirmed_by TEXT,
                confirmed_at TEXT,
                created_at TEXT NOT NULL,
                created_by TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                CONSTRAINT uq_project_request_key UNIQUE (project_id, request_key)
            );
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_tasks_project ON tasks(project_id);")

            # Runs
            conn.execute("""
            CREATE TABLE IF NOT EXISTS runs (
                run_id TEXT PRIMARY KEY,
                task_id TEXT NOT NULL,
                task_revision INTEGER NOT NULL,
                trace_id TEXT NOT NULL,
                authorization_ref TEXT,
                permission_check_ref TEXT,
                module TEXT NOT NULL,
                input_refs TEXT NOT NULL,
                input_revision INTEGER NOT NULL,
                idempotency_key TEXT NOT NULL,
                attempt_no INTEGER NOT NULL DEFAULT 1,
                attempts TEXT NOT NULL,
                run_status TEXT NOT NULL,
                stop_reason TEXT,
                context_manifest TEXT NOT NULL,
                manifest_hash TEXT NOT NULL,
                steps TEXT NOT NULL,
                started_at TEXT,
                ended_at TEXT,
                usage TEXT NOT NULL,
                controls TEXT NOT NULL,
                output_refs TEXT NOT NULL,
                failure TEXT,
                created_at TEXT NOT NULL,
                created_by TEXT NOT NULL
            );
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_runs_task ON runs(task_id);")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_runs_idempotency ON runs(idempotency_key);")

            # Events
            conn.execute("""
            CREATE TABLE IF NOT EXISTS events (
                event_id TEXT PRIMARY KEY,
                event_type TEXT NOT NULL,
                event_at TEXT NOT NULL,
                received_at TEXT NOT NULL,
                task_id TEXT,
                media_id TEXT,
                run_id TEXT,
                actor_id TEXT NOT NULL,
                actor_type TEXT NOT NULL,
                actor_role TEXT NOT NULL,
                operation_id TEXT NOT NULL,
                dedup_key TEXT NOT NULL,
                payload TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_events_task ON events(task_id);")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_events_dedup ON events(dedup_key);")

            # Decisions
            conn.execute("""
            CREATE TABLE IF NOT EXISTS decisions (
                decision_id TEXT PRIMARY KEY,
                task_id TEXT,
                media_id TEXT,
                decision_type TEXT NOT NULL,
                action TEXT NOT NULL,
                actor_id TEXT NOT NULL,
                actor_role TEXT NOT NULL,
                target_ref TEXT NOT NULL,
                payload TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            """)

            # ASR Chunks (T2.1: Fixed 10s audio slices with real tail duration)
            conn.execute("""
            CREATE TABLE IF NOT EXISTS asr_chunks (
                chunk_id TEXT PRIMARY KEY,
                task_id TEXT NOT NULL,
                slice_run_id TEXT,
                chunk_index INTEGER NOT NULL,
                start_ms INTEGER NOT NULL,
                end_ms INTEGER NOT NULL,
                offset_ms INTEGER NOT NULL,
                duration_ms INTEGER NOT NULL,
                checksum_sha256 TEXT NOT NULL,
                file_path TEXT NOT NULL,
                quality_stats TEXT NOT NULL,
                status TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            """)
            try:
                conn.execute("ALTER TABLE asr_chunks ADD COLUMN slice_run_id TEXT;")
            except Exception:
                pass
            conn.execute("CREATE INDEX IF NOT EXISTS idx_asr_chunks_task ON asr_chunks(task_id);")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_asr_chunks_slice_run ON asr_chunks(slice_run_id);")

            # Candidates (T2.1: Transcribed text, timing, and proposed revisions)
            conn.execute("""
            CREATE TABLE IF NOT EXISTS candidates (
                candidate_id TEXT PRIMARY KEY,
                task_id TEXT NOT NULL,
                run_id TEXT,
                segment_id TEXT,
                chunk_id TEXT,
                candidate_revision INTEGER NOT NULL DEFAULT 1,
                input_revision INTEGER NOT NULL DEFAULT 1,
                target_variant_key TEXT NOT NULL DEFAULT 'source',
                module TEXT NOT NULL DEFAULT 'asr_alignment',
                candidate_kind TEXT NOT NULL,
                candidate_index INTEGER NOT NULL DEFAULT 0,
                proposed TEXT NOT NULL,
                candidate_status TEXT NOT NULL DEFAULT 'AI_PROPOSED',
                confidence TEXT NOT NULL,
                overlap_info TEXT,
                entity_info TEXT,
                uncertainties TEXT,
                evidence TEXT,
                supersedes_candidate_id TEXT,
                content_hash TEXT NOT NULL,
                is_simulated INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL
            );
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_candidates_task ON candidates(task_id);")

            # Issues (T2.1: Quality doubts, boundary cuts, overlap risks, unconfirmed entities)
            conn.execute("""
            CREATE TABLE IF NOT EXISTS issues (
                issue_id TEXT PRIMARY KEY,
                task_id TEXT NOT NULL,
                run_id TEXT,
                candidate_id TEXT,
                segment_id TEXT,
                chunk_id TEXT,
                category TEXT NOT NULL,
                severity TEXT NOT NULL,
                confidence TEXT NOT NULL,
                detail TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'OPEN',
                created_at TEXT NOT NULL
            );
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_issues_task ON issues(task_id);")

            # Source Transcripts (Task A & Gate 1)
            conn.execute("""
            CREATE TABLE IF NOT EXISTS source_transcripts (
                transcript_id TEXT PRIMARY KEY,
                task_id TEXT NOT NULL,
                revision INTEGER NOT NULL DEFAULT 1,
                status TEXT NOT NULL DEFAULT 'AI_PROPOSED',
                source_language TEXT NOT NULL DEFAULT 'zh-CN',
                run_id TEXT,
                confirmed_by TEXT,
                confirmed_at TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                CONSTRAINT uq_transcripts_task_rev UNIQUE (task_id, revision)
            );
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_transcripts_task ON source_transcripts(task_id);")

            # Source Utterances (Units of source dialogue)
            conn.execute("""
            CREATE TABLE IF NOT EXISTS source_utterances (
                unit_id TEXT NOT NULL,
                task_id TEXT NOT NULL,
                transcript_revision INTEGER NOT NULL DEFAULT 1,
                unit_index INTEGER NOT NULL,
                speaker_id TEXT,
                character_ref TEXT,
                text TEXT NOT NULL,
                source_spans TEXT NOT NULL,
                start_ms INTEGER,
                end_ms INTEGER,
                timing_precision TEXT NOT NULL DEFAULT 'chunk_fallback',
                uncertainties TEXT,
                status TEXT NOT NULL DEFAULT 'AI_PROPOSED',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                PRIMARY KEY (task_id, transcript_revision, unit_id)
            );
            """)
            # Preserve every extant row while migrating the original global unit-id key.
            unit_pk = [r['name'] for r in conn.execute('PRAGMA table_info(source_utterances)') if r['pk']]
            if unit_pk == ['unit_id']:
                schema = conn.execute("SELECT sql FROM sqlite_master WHERE name='source_utterances'").fetchone()[0]
                schema = schema.replace('unit_id TEXT PRIMARY KEY,', 'unit_id TEXT NOT NULL,')
                closing = schema.rfind(')')
                schema = schema[:closing] + ', PRIMARY KEY (task_id, transcript_revision, unit_id)' + schema[closing:]
                conn.execute('ALTER TABLE source_utterances RENAME TO source_utterances_legacy')
                conn.execute(schema)
                conn.execute('INSERT INTO source_utterances SELECT * FROM source_utterances_legacy')
                conn.execute('DROP TABLE source_utterances_legacy')
            conn.execute("CREATE INDEX IF NOT EXISTS idx_utterances_task_rev ON source_utterances(task_id, transcript_revision);")

            # Source Speakers
            conn.execute("""
            CREATE TABLE IF NOT EXISTS source_speakers (
                speaker_id TEXT NOT NULL,
                task_id TEXT NOT NULL,
                transcript_revision INTEGER NOT NULL DEFAULT 1,
                display_name TEXT NOT NULL,
                character_ref TEXT,
                evidence_refs TEXT,
                uncertainties TEXT,
                created_at TEXT NOT NULL,
                PRIMARY KEY (task_id, transcript_revision, speaker_id)
            );
            """)

            speaker_pk = [r['name'] for r in conn.execute('PRAGMA table_info(source_speakers)') if r['pk']]
            if speaker_pk == ['speaker_id']:
                schema = conn.execute("SELECT sql FROM sqlite_master WHERE name='source_speakers'").fetchone()[0]
                schema = schema.replace('speaker_id TEXT PRIMARY KEY,', 'speaker_id TEXT NOT NULL,')
                closing = schema.rfind(')')
                schema = schema[:closing] + ', PRIMARY KEY (task_id, transcript_revision, speaker_id)' + schema[closing:]
                conn.execute('ALTER TABLE source_speakers RENAME TO source_speakers_legacy')
                conn.execute(schema)
                conn.execute('INSERT INTO source_speakers SELECT * FROM source_speakers_legacy')
                conn.execute('DROP TABLE source_speakers_legacy')

            # Knowledge Items (Terms, Characters, Scenes, Locked words)
            conn.execute("""
            CREATE TABLE IF NOT EXISTS knowledge_items (
                item_id TEXT PRIMARY KEY,
                project_id TEXT NOT NULL,
                task_id TEXT,
                category TEXT NOT NULL,
                source_text TEXT NOT NULL,
                target_text TEXT,
                target_language TEXT,
                target_market TEXT,
                is_locked INTEGER NOT NULL DEFAULT 0,
                status TEXT NOT NULL DEFAULT 'CONFIRMED',
                scope TEXT NOT NULL DEFAULT 'project',
                evidence TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_knowledge_project ON knowledge_items(project_id, category);")

            # Knowledge Versions (immutable snapshot history; creation kept here so read-only
            # version queries do not depend on a first write having happened)
            conn.execute("""
            CREATE TABLE IF NOT EXISTS knowledge_versions (
                item_id TEXT NOT NULL,
                revision INTEGER NOT NULL,
                content_hash TEXT NOT NULL,
                snapshot TEXT NOT NULL,
                action TEXT NOT NULL,
                actor_id TEXT,
                created_at TEXT NOT NULL,
                PRIMARY KEY(item_id, revision)
            );
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_knowledge_versions_item ON knowledge_versions(item_id);")

            # Translations (Task B & Gate 2)
            conn.execute("""
            CREATE TABLE IF NOT EXISTS translations (
                translation_id TEXT PRIMARY KEY,
                task_id TEXT NOT NULL,
                unit_id TEXT NOT NULL,
                source_revision INTEGER NOT NULL,
                translation_revision INTEGER NOT NULL DEFAULT 1,
                target_language TEXT NOT NULL,
                target_market TEXT NOT NULL,
                text TEXT NOT NULL,
                brief_paraphrase TEXT,
                term_hits TEXT,
                status TEXT NOT NULL DEFAULT 'AI_PROPOSED',
                is_locked INTEGER NOT NULL DEFAULT 0,
                run_id TEXT,
                confirmed_by TEXT,
                confirmed_at TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_translations_task ON translations(task_id, source_revision);")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_translations_unit ON translations(unit_id);")

            # Translation Checks (Task C)
            conn.execute("""
            CREATE TABLE IF NOT EXISTS translation_checks (
                check_id TEXT PRIMARY KEY,
                task_id TEXT NOT NULL,
                unit_id TEXT NOT NULL,
                translation_id TEXT NOT NULL,
                category TEXT NOT NULL,
                severity TEXT NOT NULL,
                source_span TEXT,
                target_span TEXT,
                evidence_refs TEXT,
                detail TEXT NOT NULL,
                suggestion TEXT,
                uncertainty TEXT,
                status TEXT NOT NULL DEFAULT 'OPEN',
                created_at TEXT NOT NULL
            );
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_checks_unit ON translation_checks(unit_id);")

            # Translation Revision History (for Rollback & Audit)
            conn.execute("""
            CREATE TABLE IF NOT EXISTS translation_history (
                history_id TEXT PRIMARY KEY,
                task_id TEXT NOT NULL,
                unit_id TEXT NOT NULL,
                translation_id TEXT NOT NULL,
                revision INTEGER NOT NULL,
                text TEXT NOT NULL,
                status TEXT NOT NULL,
                actor_id TEXT NOT NULL,
                action TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_trans_hist_unit ON translation_history(unit_id);")

            # Compliance Artifacts (P1: Persistent delivery artifacts & signed records)
            conn.execute("""
            CREATE TABLE IF NOT EXISTS compliance_artifacts (
                task_id TEXT NOT NULL,
                artifact_id TEXT NOT NULL,
                format TEXT NOT NULL,
                content TEXT NOT NULL,
                artifact_sha256 TEXT NOT NULL,
                status TEXT NOT NULL,
                validation_id TEXT,
                validation_result_json TEXT,
                round_trip_result_json TEXT,
                signoff_json TEXT,
                manifest_json TEXT NOT NULL,
                translation_revision TEXT NOT NULL,
                rule_version TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                PRIMARY KEY (task_id, artifact_id)
            );
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_compliance_artifacts_task ON compliance_artifacts(task_id);")

            # Unit Format Runs (P1: Persistent candidates & localization history)
            conn.execute("""
            CREATE TABLE IF NOT EXISTS unit_format_runs (
                run_id TEXT PRIMARY KEY,
                task_id TEXT NOT NULL,
                task_revision INTEGER NOT NULL,
                target_language TEXT NOT NULL,
                target_market TEXT NOT NULL,
                candidates_json TEXT NOT NULL,
                manifest_json TEXT NOT NULL,
                status TEXT NOT NULL,
                actor_id TEXT,
                created_at TEXT NOT NULL
            );
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_unit_format_runs_task ON unit_format_runs(task_id);")

            # Oral Review Runs (P1: Persistent readability & rhythm metrics)
            conn.execute("""
            CREATE TABLE IF NOT EXISTS oral_review_runs (
                run_id TEXT PRIMARY KEY,
                task_id TEXT NOT NULL,
                request_id TEXT NOT NULL,
                overall_status TEXT NOT NULL,
                items_json TEXT NOT NULL,
                manifest_json TEXT NOT NULL,
                actor_id TEXT,
                created_at TEXT NOT NULL
            );
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_oral_review_runs_task ON oral_review_runs(task_id);")


            # Ensure default project exists
            conn.execute("""
            INSERT OR IGNORE INTO projects (project_id, name, created_at)
            VALUES (?, ?, ?);
            """, ("PRJ-DEFAULT", "快手短剧字幕默认项目", utc_now_iso()))


db = Database()
