import io

import pytest
from openpyxl import Workbook

from app.sanctions.sources import au_dfat
from app.sanctions.sources.au_dfat import AustraliaDFATSource

HEADER = [
    "Reference", "Name of Individual or Entity", "Type", "Name Type", "Alias Strength",
    "Date of Birth", "Place of Birth", "Citizenship", "Address", "Additional Information",
    "Listing Information", "IMO Number", "Committees", "Control Date", "Instrument of Designation",
]


def _row(ref, name, typ, name_type, dob=None, pob=None, cit=None, addr=None, imo=None, committees=None):
    return [ref, name, typ, name_type, None, dob, pob, cit, addr, None, None, imo, committees, None, "Fictional Regs 2099"]


def _xlsx(header=HEADER, rows=None, sheet="Consolidated List - 1_1_2099", preface=0):
    wb = Workbook()
    ws = wb.active
    ws.title = sheet
    for _ in range(preface):
        ws.append(["Notice"])
    ws.append(header)
    for r in rows or []:
        ws.append(r)
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


ROWS = [
    _row(1, "ALPHA TESTER", "Individual", "Primary Name", "1970-01-01", "Testville, Examplestan", "Examplestan", "Capital, Examplestan", committees="Autonomous (Fiction)"),
    _row("1a", "Alfa Tester", "Individual", "Alias", "1970-01-01"),
    _row("1b", "ألفا", "Individual", "Original Script", "1970-01-01"),
    _row(2, "FICTIONAL TRADING LLC", "Entity", "Primary Name", addr="Example City, Otherland", committees="Autonomous (Fiction)"),
    _row("2a", "FT Trading", "Entity", "Alias"),
    _row(3, "MV NOT REAL", "Vessel", "Primary Name", imo=1234567),
    _row(4, None, "Entity", "Primary Name"),
]


def _records(raw):
    return {r.source_entity_id: r for r in AustraliaDFATSource().parse(raw)}


def test_groups_rows_by_reference():
    records = _records(_xlsx(rows=ROWS))
    assert set(records) == {"1", "2", "3"}  # reference 4 has no name -> skipped
    p = records["1"]
    assert p.source == "AU_DFAT"
    assert p.entity_type == "person"
    assert p.primary_name == "ALPHA TESTER"
    assert p.aliases == ["Alfa Tester", "ألفا"]
    assert p.date_of_birth == "1970-01-01"
    assert p.place_of_birth == "Testville, Examplestan"
    assert p.nationality == "Examplestan"
    assert p.addresses == [{"city": "Capital", "country": "Examplestan"}]
    assert p.country_of_residence == "Examplestan"
    assert p.programs == ["Autonomous (Fiction)"]


def test_entity_and_vessel():
    records = _records(_xlsx(rows=ROWS))
    e = records["2"]
    assert e.entity_type == "legal_entity"
    assert e.aliases == ["FT Trading"]
    assert e.date_of_birth is None
    v = records["3"]
    assert v.entity_type == "legal_entity"
    assert v.national_ids == [{"type": "IMO Number", "value": "1234567"}]


def test_header_row_found_after_preface_and_columns_mapped_by_text():
    shuffled = list(reversed(HEADER))
    rows = [list(reversed(r)) for r in ROWS]
    records = _records(_xlsx(header=shuffled, rows=rows, preface=3))
    assert records["1"].primary_name == "ALPHA TESTER"


def test_missing_required_column_raises():
    header = [h for h in HEADER if h != "Name Type"]
    rows = [[v for h, v in zip(HEADER, r) if h != "Name Type"] for r in ROWS]
    with pytest.raises(ValueError, match="name type"):
        list(AustraliaDFATSource().parse(_xlsx(header=header, rows=rows)))


def test_no_header_anywhere_raises():
    with pytest.raises(ValueError, match="no worksheet"):
        list(AustraliaDFATSource().parse(_xlsx(header=["foo", "bar"], rows=[[1, 2]])))


def test_parse_does_not_fetch(monkeypatch):
    def boom(*a, **k):
        raise AssertionError("network used")

    monkeypatch.setattr(au_dfat.requests, "get", boom)
    assert list(AustraliaDFATSource().parse(_xlsx(rows=ROWS)))
