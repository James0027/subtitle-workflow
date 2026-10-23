import json
import sqlite3
from pathlib import Path

db_path = Path("subtitle-project/subtitle-workflow/data/workflow.db")
quarantine_dir = Path("subtitle-project/subtitle-workflow/data/quarantine")
quarantine_dir.mkdir(parents=True, exist_ok=True)

conn = sqlite3.connect(str(db_path))
conn.row_factory = sqlite3.Row

# 1. Identify test records
test_tasks = [dict(r) for r in conn.execute(
    "SELECT * FROM tasks WHERE request_key LIKE 'test_%' OR task_id = 'TASK-20261022-098C17CC'"
).fetchall()]
test_task_ids = [t["task_id"] for t in test_tasks]

test_chunks = [dict(r) for r in conn.execute(
    "SELECT * FROM asr_chunks WHERE file_path = 'fake.wav' OR chunk_id IN ('chk_c1', 'chk_c2', 'chk_g1', 'chk_t1', 'chk_l1', 'chk_e1') OR task_id IN ({})".format(
        ",".join(f"'{tid}'" for tid in test_task_ids) if test_task_ids else "''"
    )
).fetchall()]

test_candidates = [dict(r) for r in conn.execute(
    "SELECT * FROM candidates WHERE chunk_id IN ('chk_c1', 'chk_c2', 'chk_g1', 'chk_t1', 'chk_l1', 'chk_e1') OR task_id IN ({})".format(
        ",".join(f"'{tid}'" for tid in test_task_ids) if test_task_ids else "''"
    )
).fetchall()]

test_runs = [dict(r) for r in conn.execute(
    "SELECT * FROM runs WHERE task_id IN ({})".format(
        ",".join(f"'{tid}'" for tid in test_task_ids) if test_task_ids else "''"
    )
).fetchall()]

test_operators = [dict(r) for r in conn.execute(
    "SELECT * FROM local_operators WHERE display_name = 'Test Translator' OR display_name LIKE 'test_%'"
).fetchall()]
test_operator_ids = [o["operator_id"] for o in test_operators]

test_sessions = [dict(r) for r in conn.execute(
    "SELECT * FROM local_sessions WHERE operator_id IN ({})".format(
        ",".join(f"'{oid}'" for oid in test_operator_ids) if test_operator_ids else "''"
    )
).fetchall()]

test_transcripts = [dict(r) for r in conn.execute(
    "SELECT * FROM source_transcripts WHERE task_id IN ({})".format(
        ",".join(f"'{tid}'" for tid in test_task_ids) if test_task_ids else "''"
    )
).fetchall()]

test_utterances = [dict(r) for r in conn.execute(
    "SELECT * FROM source_utterances WHERE task_id IN ({})".format(
        ",".join(f"'{tid}'" for tid in test_task_ids) if test_task_ids else "''"
    )
).fetchall()]

test_speakers = [dict(r) for r in conn.execute(
    "SELECT * FROM source_speakers WHERE task_id IN ({})".format(
        ",".join(f"'{tid}'" for tid in test_task_ids) if test_task_ids else "''"
    )
).fetchall()]

test_translations = [dict(r) for r in conn.execute(
    "SELECT * FROM translations WHERE task_id IN ({})".format(
        ",".join(f"'{tid}'" for tid in test_task_ids) if test_task_ids else "''"
    )
).fetchall()]

test_checks = [dict(r) for r in conn.execute(
    "SELECT * FROM translation_checks WHERE task_id IN ({})".format(
        ",".join(f"'{tid}'" for tid in test_task_ids) if test_task_ids else "''"
    )
).fetchall()]

test_history = [dict(r) for r in conn.execute(
    "SELECT * FROM translation_history WHERE task_id IN ({})".format(
        ",".join(f"'{tid}'" for tid in test_task_ids) if test_task_ids else "''"
    )
).fetchall()]

test_decisions = [dict(r) for r in conn.execute(
    "SELECT * FROM decisions WHERE task_id IN ({})".format(
        ",".join(f"'{tid}'" for tid in test_task_ids) if test_task_ids else "''"
    )
).fetchall()]

test_knowledge = [dict(r) for r in conn.execute(
    "SELECT * FROM knowledge_items WHERE source_text = '九转还魂丹'"
).fetchall()]

quarantine_data = {
    "quarantine_meta": {
        "timestamp": "2026-10-22T01:13:00Z",
        "description": "Quarantined test records mistakenly inserted into production workflow.db during initial test run",
        "isolation_mark": "SIMULATED_TEST_DATA",
    },
    "tasks": test_tasks,
    "asr_chunks": test_chunks,
    "candidates": test_candidates,
    "runs": test_runs,
    "local_operators": test_operators,
    "local_sessions": test_sessions,
    "source_transcripts": test_transcripts,
    "source_utterances": test_utterances,
    "source_speakers": test_speakers,
    "translations": test_translations,
    "translation_checks": test_checks,
    "translation_history": test_history,
    "decisions": test_decisions,
    "knowledge_items": test_knowledge,
}

backup_file = quarantine_dir / "quarantine_test_data_20261022.json"
backup_file.write_text(json.dumps(quarantine_data, ensure_ascii=False, indent=2), encoding="utf-8")
print(f"Backed up to {backup_file}:")
print(f"  tasks: {len(test_tasks)}")
print(f"  chunks: {len(test_chunks)}")
print(f"  candidates: {len(test_candidates)}")
print(f"  operators: {len(test_operators)}")

# Now safely remove ONLY these isolated test records
with conn:
    if test_task_ids:
        tid_ph = ",".join(f"'{tid}'" for tid in test_task_ids)
        conn.execute(f"DELETE FROM tasks WHERE task_id IN ({tid_ph})")
        conn.execute(f"DELETE FROM asr_chunks WHERE task_id IN ({tid_ph})")
        conn.execute(f"DELETE FROM candidates WHERE task_id IN ({tid_ph})")
        conn.execute(f"DELETE FROM runs WHERE task_id IN ({tid_ph})")
        conn.execute(f"DELETE FROM source_transcripts WHERE task_id IN ({tid_ph})")
        conn.execute(f"DELETE FROM source_utterances WHERE task_id IN ({tid_ph})")
        conn.execute(f"DELETE FROM source_speakers WHERE task_id IN ({tid_ph})")
        conn.execute(f"DELETE FROM translations WHERE task_id IN ({tid_ph})")
        conn.execute(f"DELETE FROM translation_checks WHERE task_id IN ({tid_ph})")
        conn.execute(f"DELETE FROM translation_history WHERE task_id IN ({tid_ph})")
        conn.execute(f"DELETE FROM decisions WHERE task_id IN ({tid_ph})")

    conn.execute("DELETE FROM asr_chunks WHERE file_path = 'fake.wav' OR chunk_id IN ('chk_c1', 'chk_c2', 'chk_g1', 'chk_t1', 'chk_l1', 'chk_e1')")
    conn.execute("DELETE FROM candidates WHERE chunk_id IN ('chk_c1', 'chk_c2', 'chk_g1', 'chk_t1', 'chk_l1', 'chk_e1')")
    conn.execute("DELETE FROM knowledge_items WHERE source_text = '九转还魂丹'")

    if test_operator_ids:
        oid_ph = ",".join(f"'{oid}'" for oid in test_operator_ids)
        conn.execute(f"DELETE FROM local_sessions WHERE operator_id IN ({oid_ph})")
        conn.execute(f"DELETE FROM local_operators WHERE operator_id IN ({oid_ph})")

print("Quarantine clean-up committed successfully.")
conn.close()
