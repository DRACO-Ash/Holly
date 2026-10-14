from datetime import datetime, timezone

from app.services.notification_ingest import _map_udl_record


def _real_tacrep_notso_record() -> dict:
    """A synthetic record in the shape UDL serves for msgType=TACREP_NOTSO. Every identifier,
    name, satellite and link is invented; none is taken from a real record."""
    return {
        "createdAt": "2026-06-05T04:55:45.975Z",
        "dataMode": "TEST",
        "msgType": "TACREP_NOTSO",
        "createdBy": "system.example",
        "id": "00000000-0000-4000-8000-000000000001",
        "source": "TEST",
        "classificationMarking": "U",
        "origNetwork": "TEST",
        "msgBody": {
            "Status": "OPEN",
            "Event_Class": "ID: 0001 / Photometric Change / TEST-SAT (99999) / GEO",
            "Template_Name": "NOTSO",
            "NOTSO_Image_Metadata": (
                '[{"caption":"","filename":"TEST-SAT / Lightcurve / Example","'
                'id":"00000000-0000-4000-8000-000000000004","url":'
                '"https://images.example/lightcurve.png"}]'
            ),
            "Email_Subject": (
                "NOTSO - ID: 0001 / Photometric Change / TEST-SAT (99999) / GEO - "
                "0001_05Jun-0448Z - TACREP Notification"
            ),
            "Event_Id": "00000000-0000-4000-8000-000000000002",
            "Event_Type": "other",
            "UDL_Classification": "U",
            "Remarks": "Photometric change observed during JDAY 154.",
            "Classification": "U",
            "UDL_Data_Mode": "TEST",
            "Event_Description": "JDay 156 at 0430z; photometric change detected on TEST-SAT.",
            "Company_Name": "Example Analyst",
            "previewText": "preview text",
            "SatIds": ["99999"],
            "Orbital_Regime": ["N/A"],
            "Publish_To_UDL": "True",
            "Publish_Date": "2026-06-05T04:48:44.453004Z",
            "NOTSO_Link": "https://notso.example/notso/00000000-0000-4000-8000-000000000003",
            "NOTSO": "0001_05Jun-0448Z",
        },
    }


def test_map_udl_record_extracts_top_level_envelope() -> None:
    mapped = _map_udl_record(_real_tacrep_notso_record())
    assert mapped is not None
    assert mapped["udl_id"] == "00000000-0000-4000-8000-000000000001"
    assert mapped["msg_type"] == "TACREP_NOTSO"
    assert mapped["data_mode"] == "TEST"
    assert mapped["source"] == "TEST"
    assert mapped["classification_marking"] == "U"
    assert mapped["created_by"] == "system.example"
    assert mapped["orig_network"] == "TEST"
    assert mapped["udl_created_at"] == datetime(2026, 6, 5, 4, 55, 45, 975000, tzinfo=timezone.utc)


def test_map_udl_record_extracts_msg_body_fields() -> None:
    mapped = _map_udl_record(_real_tacrep_notso_record())
    assert mapped is not None
    assert mapped["notso_identifier"] == "0001_05Jun-0448Z"
    assert mapped["notice_id"] == "0001_05Jun-0448Z"
    assert mapped["event_class"] == "ID: 0001 / Photometric Change / TEST-SAT (99999) / GEO"
    assert mapped["subject"] == "ID: 0001 / Photometric Change / TEST-SAT (99999) / GEO"
    assert mapped["event_type"] == "other"
    assert mapped["event_id"] == "00000000-0000-4000-8000-000000000002"
    assert mapped["status"] == "OPEN"
    assert mapped["description"] == "JDay 156 at 0430z; photometric change detected on TEST-SAT."
    assert mapped["company_name"] == "Example Analyst"
    assert mapped["notso_link"].startswith("https://notso.example/")
    assert mapped["publish_date"] == datetime(2026, 6, 5, 4, 48, 44, 453004, tzinfo=timezone.utc)


def test_map_udl_record_handles_sat_ids_single_value() -> None:
    mapped = _map_udl_record(_real_tacrep_notso_record())
    assert mapped is not None
    assert mapped["sat_ids"] == ["99999"]
    assert mapped["sat_no"] == 99999


def test_map_udl_record_handles_sat_ids_multiple() -> None:
    record = _real_tacrep_notso_record()
    record["msgBody"]["SatIds"] = ["99998", "99999"]
    mapped = _map_udl_record(record)
    assert mapped is not None
    assert mapped["sat_ids"] == ["99998", "99999"]
    assert "sat_no" not in mapped


def test_map_udl_record_handles_non_numeric_sat_id() -> None:
    record = _real_tacrep_notso_record()
    record["msgBody"]["SatIds"] = ["UNCAT-001"]
    mapped = _map_udl_record(record)
    assert mapped is not None
    assert mapped["sat_ids"] == ["UNCAT-001"]
    assert "sat_no" not in mapped


def test_map_udl_record_preserves_raw_payload() -> None:
    record = _real_tacrep_notso_record()
    mapped = _map_udl_record(record)
    assert mapped is not None
    assert mapped["raw"] is record
    assert mapped["raw"]["msgBody"]["Template_Name"] == "NOTSO"


def test_map_udl_record_returns_none_when_id_missing() -> None:
    record = _real_tacrep_notso_record()
    del record["id"]
    assert _map_udl_record(record) is None


def test_map_udl_record_handles_missing_msg_body() -> None:
    record = {
        "id": "x",
        "msgType": "OTHER_TYPE",
        "dataMode": "REAL",
    }
    mapped = _map_udl_record(record)
    assert mapped is not None
    assert mapped["udl_id"] == "x"
    assert mapped["msg_type"] == "OTHER_TYPE"
    assert "notso_identifier" not in mapped
    assert "status" not in mapped


def test_map_udl_record_falls_back_to_flat_aliases() -> None:
    record = {
        "id": "legacy",
        "msgType": "OPERATIONAL",
        "noticeId": "OPS-2026-001",
        "subject": "Flat-shaped subject",
        "text": "Flat-shaped description",
        "effectiveFrom": "2026-05-20T00:00:00.000Z",
        "satNo": "25544",
    }
    mapped = _map_udl_record(record)
    assert mapped is not None
    assert mapped["notice_id"] == "OPS-2026-001"
    assert mapped["subject"] == "Flat-shaped subject"
    assert mapped["description"] == "Flat-shaped description"
    assert mapped["effective_from"] == datetime(2026, 5, 20, 0, 0, 0, tzinfo=timezone.utc)
    assert mapped["sat_no"] == 25544
