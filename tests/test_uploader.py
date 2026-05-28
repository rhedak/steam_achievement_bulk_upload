"""Tests for steam_ach_upload — pure-Python logic only, no browser required."""

from __future__ import annotations

import csv
import sys
from io import StringIO
from pathlib import Path

import pytest

from steam_ach_upload.uploader import build_url, load_achievements, main

SAMPLE_CSV = Path(__file__).parent.parent / "sample" / "achievements.csv"


# ── build_url ────────────────────────────────────────────────────────────────

def test_build_url_contains_app_id():
    url = build_url("1234567")
    assert "1234567" in url


def test_build_url_is_steamworks():
    url = build_url("99")
    assert url.startswith("https://partner.steamgames.com/")


# ── load_achievements ────────────────────────────────────────────────────────

def test_load_achievements_returns_list(tmp_path):
    f = tmp_path / "achievements.csv"
    f.write_text(
        "API Name,Display Name (EN),Description (EN),Achieved Icon,Unachieved Icon\n"
        "ACH_TEST,Test,Test description.,done.png,locked.png\n",
        encoding="utf-8",
    )
    rows = load_achievements(f)
    assert isinstance(rows, list)
    assert len(rows) == 1


def test_load_achievements_fields(tmp_path):
    f = tmp_path / "achievements.csv"
    f.write_text(
        "API Name,Display Name (EN),Description (EN),Achieved Icon,Unachieved Icon\n"
        "ACH_FOO,Foo Achievement,Do something cool.,foo_done.png,foo_locked.png\n",
        encoding="utf-8",
    )
    rows = load_achievements(f)
    row = rows[0]
    assert row["API Name"] == "ACH_FOO"
    assert row["Display Name (EN)"] == "Foo Achievement"
    assert row["Description (EN)"] == "Do something cool."
    assert row["Achieved Icon"] == "foo_done.png"
    assert row["Unachieved Icon"] == "foo_locked.png"


def test_load_achievements_multiple_rows(tmp_path):
    f = tmp_path / "achievements.csv"
    rows_data = [
        ("ACH_A", "A", "Desc A", "a_done.png", "a_locked.png"),
        ("ACH_B", "B", "Desc B", "b_done.png", "b_locked.png"),
        ("ACH_C", "C", "Desc C", "c_done.png", "c_locked.png"),
    ]
    with open(f, "w", encoding="utf-8", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(["API Name", "Display Name (EN)", "Description (EN)", "Achieved Icon", "Unachieved Icon"])
        writer.writerows(rows_data)

    rows = load_achievements(f)
    assert len(rows) == 3
    assert rows[2]["API Name"] == "ACH_C"


def test_load_achievements_empty_csv(tmp_path):
    f = tmp_path / "achievements.csv"
    f.write_text(
        "API Name,Display Name (EN),Description (EN),Achieved Icon,Unachieved Icon\n",
        encoding="utf-8",
    )
    rows = load_achievements(f)
    assert rows == []


# ── sample CSV integrity ─────────────────────────────────────────────────────

def test_sample_csv_exists():
    assert SAMPLE_CSV.exists(), f"sample CSV not found at {SAMPLE_CSV}"


def test_sample_csv_has_required_columns():
    rows = load_achievements(SAMPLE_CSV)
    required = {"API Name", "Display Name (EN)", "Description (EN)", "Achieved Icon", "Unachieved Icon"}
    assert required.issubset(rows[0].keys())


def test_sample_csv_has_rows():
    rows = load_achievements(SAMPLE_CSV)
    assert len(rows) > 0


def test_sample_csv_no_empty_api_names():
    rows = load_achievements(SAMPLE_CSV)
    for row in rows:
        assert row["API Name"].strip(), f"Empty API Name in row: {row}"


# ── dry-run CLI path ─────────────────────────────────────────────────────────

def test_dry_run_output(tmp_path, capsys):
    f = tmp_path / "achievements.csv"
    f.write_text(
        "API Name,Display Name (EN),Description (EN),Achieved Icon,Unachieved Icon\n"
        "ACH_ONE,One,First.,done.png,locked.png\n"
        "ACH_TWO,Two,Second.,done.png,locked.png\n",
        encoding="utf-8",
    )
    sys.argv = ["steam-ach-upload", "1234567", str(f), "--dry-run"]
    main()
    out = capsys.readouterr().out
    assert "ACH_ONE" in out
    assert "ACH_TWO" in out


def test_dry_run_start_offset(tmp_path, capsys):
    f = tmp_path / "achievements.csv"
    f.write_text(
        "API Name,Display Name (EN),Description (EN),Achieved Icon,Unachieved Icon\n"
        "ACH_ONE,One,First.,done.png,locked.png\n"
        "ACH_TWO,Two,Second.,done.png,locked.png\n"
        "ACH_THREE,Three,Third.,done.png,locked.png\n",
        encoding="utf-8",
    )
    sys.argv = ["steam-ach-upload", "1234567", str(f), "--dry-run", "--start", "2"]
    main()
    out = capsys.readouterr().out
    assert "ACH_ONE" not in out
    assert "ACH_TWO" in out
    assert "ACH_THREE" in out


def test_missing_csv_exits(tmp_path):
    sys.argv = ["steam-ach-upload", "1234567", str(tmp_path / "nonexistent.csv")]
    with pytest.raises(SystemExit) as exc_info:
        main()
    assert exc_info.value.code != 0
