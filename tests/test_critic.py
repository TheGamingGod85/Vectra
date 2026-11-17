"""Unit tests for the Critic agent's pure helper functions."""

from vectra.agents.critic import (
    _parse_issues,
    _deduplicate_issues,
    _static_prescan,
)


class TestParseIssues:
    def test_plain_json_array(self):
        raw = '[{"id": 1, "severity": "high", "category": "SQL Injection"}]'
        issues = _parse_issues(raw)
        assert len(issues) == 1
        assert issues[0]["category"] == "SQL Injection"

    def test_markdown_fenced_json(self):
        raw = '```json\n[{"id": 1, "category": "XSS"}]\n```'
        issues = _parse_issues(raw)
        assert len(issues) == 1
        assert issues[0]["category"] == "XSS"

    def test_dict_wrapping_array(self):
        raw = '{"issues": [{"id": 1}, {"id": 2}]}'
        assert len(_parse_issues(raw)) == 2

    def test_empty_response(self):
        assert _parse_issues("") == []
        assert _parse_issues("   ") == []

    def test_prose_around_array(self):
        raw = 'Here are the issues:\n[{"id": 1}]\nThat is all.'
        assert len(_parse_issues(raw)) == 1

    def test_garbage_returns_empty(self):
        assert _parse_issues("no json here at all") == []


class TestDeduplicateIssues:
    def test_same_file_same_category_different_snippet_both_kept(self):
        # Two DIFFERENT SQL injections in the same file must both survive.
        static = [
            {"file": "app.py", "category": "SQL Injection", "snippet": "query1"},
            {"file": "app.py", "category": "SQL Injection", "snippet": "query2"},
        ]
        merged = _deduplicate_issues(static, [])
        assert len(merged) == 2

    def test_exact_duplicate_removed(self):
        static = [{"file": "app.py", "category": "XSS", "snippet": "x = 1"}]
        llm = [{"file": "app.py", "category": "xss", "snippet": "x = 1"}]
        merged = _deduplicate_issues(static, llm)
        assert len(merged) == 1

    def test_ids_renumbered(self):
        static = [
            {"file": "a.py", "category": "A", "snippet": "s1", "id": 99},
            {"file": "b.py", "category": "B", "snippet": "s2", "id": 99},
        ]
        merged = _deduplicate_issues(static, [])
        assert [i["id"] for i in merged] == [1, 2]


class TestStaticPrescan:
    def test_hardcoded_secret_detected(self):
        manifest = {"app.py": 'password = "supersecret123"\n'}
        issues = _static_prescan(manifest)
        assert any(i["category"] == "Hardcoded Secret" for i in issues)

    def test_md5_word_boundary(self):
        # A function merely *ending* in md5 must not be flagged.
        manifest = {"app.py": "result = compute_checksum_not_md5ish(data)\n"}
        issues = _static_prescan(manifest)
        assert not any(i["category"] == "Weak Hashing" for i in issues)

    def test_real_md5_detected(self):
        manifest = {"app.py": "import hashlib\nh = hashlib.md5(data)\n"}
        issues = _static_prescan(manifest)
        assert any(i["category"] == "Weak Hashing" for i in issues)

    def test_test_files_skipped(self):
        manifest = {"test_app.py": 'password = "supersecret123"\n'}
        assert _static_prescan(manifest) == []

    def test_clean_code_no_issues(self):
        manifest = {"app.py": "def add(a, b):\n    return a + b\n"}
        assert _static_prescan(manifest) == []
