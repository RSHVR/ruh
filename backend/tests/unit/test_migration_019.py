"""Shape tests for migration 019 (hybrid review search).

There is no live DB in the test suite, so the migration is guarded by shape only:
the SQL text declares the generated tsvector column + GIN index and a lexical RPC
using websearch_to_tsquery/ts_rank_cd, SECURITY DEFINER with an empty search_path,
and is idempotent. This locks the contract the app layer (search_reviews_lexical
call, RRF fusion) depends on.
"""

from pathlib import Path

MIGRATION = (
    Path(__file__).resolve().parents[2]
    / "supabase"
    / "migrations"
    / "019_hybrid_review_search.sql"
)


def _sql() -> str:
    return MIGRATION.read_text().lower()


def test_migration_file_exists():
    assert MIGRATION.is_file()


def test_adds_generated_tsvector_column():
    sql = _sql()
    assert "review_tsv" in sql
    assert "generated always as" in sql
    assert "to_tsvector('english', review_text)" in sql
    assert "stored" in sql


def test_creates_gin_index():
    sql = _sql()
    assert "using gin" in sql
    assert "review_tsv" in sql


def test_defines_lexical_rpc_with_native_fts_scorers():
    sql = _sql()
    assert "function search_reviews_lexical" in sql
    assert "websearch_to_tsquery" in sql
    assert "ts_rank_cd" in sql


def test_rpc_is_security_definer_with_empty_search_path():
    sql = _sql()
    assert "security definer" in sql
    assert "set search_path = ''" in sql
    # Table must be schema-qualified when search_path is empty.
    assert "public.review_chunks" in sql


def test_migration_is_idempotent():
    sql = _sql()
    assert "add column if not exists" in sql
    assert "create index if not exists" in sql
    assert "create or replace function" in sql
