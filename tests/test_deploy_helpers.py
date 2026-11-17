"""Unit tests for deployment helpers (docker tools + solomon naming)."""

from vectra.tools.docker_tools import detect_exposed_port
from vectra.agents.solomon import _repo_slug, image_tag_for


class TestDetectExposedPort:
    def test_simple_expose(self):
        assert detect_exposed_port("FROM python:3.13\nEXPOSE 8000\nCMD []") == 8000

    def test_case_insensitive_and_indented(self):
        assert detect_exposed_port("  expose 5000\n") == 5000

    def test_no_expose(self):
        assert detect_exposed_port("FROM python:3.13\nCMD []") is None

    def test_first_of_multiple(self):
        assert detect_exposed_port("EXPOSE 3000\nEXPOSE 9000\n") == 3000

    def test_expose_in_comment_not_matched(self):
        assert detect_exposed_port("# EXPOSE 1234 is done later\n") is None


class TestRepoNaming:
    def test_slug_sanitised(self):
        assert _repo_slug(r"C:\work\My Cool_App!") == "my-cool-app"

    def test_slug_never_empty(self):
        # A name with no usable characters falls back to "app"
        assert _repo_slug("###") == "app"

    def test_image_tag_deterministic(self):
        assert image_tag_for(r"C:\repos\shop") == image_tag_for(r"C:\repos\shop")
        assert image_tag_for(r"C:\repos\shop") != image_tag_for(r"C:\repos\blog")

    def test_image_tag_format(self):
        tag = image_tag_for(r"C:\repos\shop")
        assert tag == "vectra-shop:latest"
