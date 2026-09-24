"""Calendar versions: `VERSION` names the last release, and the tag agrees.

The release rule (CLAUDE.md, *Releases*): the release commit bumps `VERSION`
and is tagged `v<VERSION>`. So wherever a release tag is reachable, the
nearest one must equal `v` + `VERSION`; a cut tagged without the bump, or
bumped without the tag, fails here. Skipped where there is no git or no tag
(a scratch copy, a clone without tags), because there is nothing to compare.
"""

import re
import subprocess

import pytest

from src import version as v


def test_the_version_file_is_a_calendar_version():
    assert re.fullmatch(r"\d{4}\.(0[1-9]|1[0-2])\.[1-9]\d*", v.APP_VERSION), v.APP_VERSION


def test_the_version_file_is_read_stripped_and_never_raises(tmp_path):
    p = tmp_path / "VERSION"
    p.write_text("2026.10.1\r\n", encoding="utf-8")
    assert v.read_version(str(p)) == "2026.10.1"
    assert v.read_version(str(tmp_path / "missing")) == "unknown"
    p.write_text("  \n", encoding="utf-8")
    assert v.read_version(str(p)) == "unknown"


def test_no_git_repository_means_no_build_label(tmp_path):
    assert v.read_build(str(tmp_path)) is None


def _nearest_release_tag():
    try:
        out = subprocess.run(
            ["git", "describe", "--tags", "--abbrev=0", "--match", "v[0-9]*"],
            cwd=v._REPO_ROOT, capture_output=True, text=True, timeout=5,
        )
    except Exception:
        return None
    return out.stdout.strip() if out.returncode == 0 else None


def test_the_nearest_release_tag_is_the_version_file():
    tag = _nearest_release_tag()
    if not tag:
        pytest.skip("no git, or no release tag reachable from this checkout")
    assert tag == f"v{v.APP_VERSION}", (
        f"VERSION says {v.APP_VERSION} but the nearest release tag is {tag}: "
        "bump VERSION in the release commit, then tag that commit"
    )


def test_the_build_label_names_the_release_it_is_on_or_past():
    if not _nearest_release_tag():
        pytest.skip("no release tag reachable from this checkout")
    assert v.APP_BUILD == f"v{v.APP_VERSION}" or v.APP_BUILD.startswith(f"v{v.APP_VERSION}-")


@pytest.mark.asyncio
async def test_bot_info_reports_the_version():
    from src.routers.identity import BotInfoOut, bot_info

    info = await bot_info()
    assert info["version"] == v.APP_VERSION
    assert info.get("build") == v.APP_BUILD  # absent when there is no git
    BotInfoOut(**info)  # the response model accepts it
