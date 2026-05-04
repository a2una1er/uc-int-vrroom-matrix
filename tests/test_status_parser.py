"""
Tests for StatusParser.

Property-based tests use hypothesis.
All VRRoom API values are strings.
"""
from hypothesis import given, settings as h_settings
from hypothesis import strategies as st

from status_parser import DeviceStatus, ParseError, StatusParser


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def valid_status_dict(**overrides) -> dict:
    """Return a minimal valid status dict with string values."""
    base = {
        "portseltx0": "0",
        "portseltx1": "1",
        "rx0in5v": "1",
        "rx1in5v": "0",
        "rx2in5v": "1",
        "rx3in5v": "0",
    }
    base.update(overrides)
    return base


# ---------------------------------------------------------------------------
# Property 7: ParseError on missing required fields
# Feature: hdfury-vrroom-integration, Property 7: Parse-Fehler bei fehlenden Pflichtfeldern
# Validates: Requirement 2.8
# ---------------------------------------------------------------------------

@given(missing=st.sampled_from(["portseltx0", "portseltx1", "both"]))
@h_settings(max_examples=100)
def test_missing_required_fields_parse_error(missing):
    """Any dict without portseltx0 or portseltx1 must return ParseError (Req 2.8)."""
    data = valid_status_dict()
    if missing == "portseltx0":
        del data["portseltx0"]
    elif missing == "portseltx1":
        del data["portseltx1"]
    else:
        del data["portseltx0"]
        del data["portseltx1"]
    result = StatusParser().parse(data)
    assert isinstance(result, ParseError)


# ---------------------------------------------------------------------------
# Property 8: Round-trip serialization
# Feature: hdfury-vrroom-integration, Property 8: Round-Trip-Serialisierung
# Validates: Requirements 8.1, 8.2
# ---------------------------------------------------------------------------

@given(
    data=st.fixed_dictionaries({
        "portseltx0": st.integers(min_value=0, max_value=4).map(str),
        "portseltx1": st.integers(min_value=0, max_value=4).map(str),
        "rx0in5v": st.sampled_from(["0", "1"]),
        "rx1in5v": st.sampled_from(["0", "1"]),
        "rx2in5v": st.sampled_from(["0", "1"]),
        "rx3in5v": st.sampled_from(["0", "1"]),
    })
)
@h_settings(max_examples=100)
def test_round_trip_serialization(data):
    """serialize(parse(data)) == data for all valid string dicts (Req 8.1, 8.2)."""
    parser = StatusParser()
    status = parser.parse(data)
    assert not isinstance(status, ParseError), f"Unexpected ParseError: {status.message}"
    serialized = parser.serialize(status)
    assert serialized == data


# ---------------------------------------------------------------------------
# Property 9: Type and range invariant for TX values
# Feature: hdfury-vrroom-integration, Property 9: Typ- und Bereichsinvariante
# Validates: Requirement 8.3
# ---------------------------------------------------------------------------

@given(
    data=st.fixed_dictionaries({
        "portseltx0": st.integers(min_value=0, max_value=4).map(str),
        "portseltx1": st.integers(min_value=0, max_value=4).map(str),
        "rx0in5v": st.sampled_from(["0", "1"]),
        "rx1in5v": st.sampled_from(["0", "1"]),
        "rx2in5v": st.sampled_from(["0", "1"]),
        "rx3in5v": st.sampled_from(["0", "1"]),
    })
)
@h_settings(max_examples=100)
def test_tx_values_are_valid_integers(data):
    """After parse(), portseltx0/portseltx1 must be int in [0, 4] (Req 8.3)."""
    status = StatusParser().parse(data)
    assert isinstance(status, DeviceStatus)
    assert isinstance(status.portseltx0, int)
    assert isinstance(status.portseltx1, int)
    assert 0 <= status.portseltx0 <= 4
    assert 0 <= status.portseltx1 <= 4


# ---------------------------------------------------------------------------
# Property 10: ParseError on invalid string values
# Feature: hdfury-vrroom-integration, Property 10: Parse-Fehler bei ungültigem String-Wert
# Validates: Requirement 8.4
# ---------------------------------------------------------------------------

@given(
    tx0=st.one_of(
        st.integers().filter(lambda x: x < 0 or x > 4).map(str),
        st.text(min_size=1).filter(lambda s: not (s.isdigit() and int(s) in range(5))),
    )
)
@h_settings(max_examples=100)
def test_invalid_tx0_string_parse_error(tx0):
    """Invalid string for portseltx0 must return ParseError (Req 8.4)."""
    data = valid_status_dict(portseltx0=tx0)
    result = StatusParser().parse(data)
    assert isinstance(result, ParseError)


@given(rx_val=st.text().filter(lambda s: s not in ("0", "1")))
@h_settings(max_examples=100)
def test_invalid_signal_string_parse_error(rx_val):
    """Invalid string for rx*in5v (not '0' or '1') must return ParseError (Req 8.4)."""
    data = valid_status_dict(rx0in5v=rx_val)
    result = StatusParser().parse(data)
    assert isinstance(result, ParseError)


# ---------------------------------------------------------------------------
# Unit tests
# ---------------------------------------------------------------------------

def test_parse_valid_status():
    """Parse a typical VRRoom response correctly."""
    data = {
        "portseltx0": "2",
        "portseltx1": "1",
        "rx0in5v": "1",
        "rx1in5v": "0",
        "rx2in5v": "1",
        "rx3in5v": "0",
        "RX0": "some_value",
        "TX0": "other_value",
    }
    status = StatusParser().parse(data)
    assert isinstance(status, DeviceStatus)
    assert status.portseltx0 == 2
    assert status.portseltx1 == 1
    assert status.rx0in5v is True
    assert status.rx1in5v is False
    assert status.extra == {"RX0": "some_value", "TX0": "other_value"}


def test_parse_copy_mode():
    """Input value 4 (Copy-Mode) is valid (Req 4.3)."""
    data = valid_status_dict(portseltx0="4")
    status = StatusParser().parse(data)
    assert isinstance(status, DeviceStatus)
    assert status.portseltx0 == 4


def test_serialize_round_trip_with_extra():
    """Round-trip with extra fields preserves all data (Req 8.2)."""
    data = {
        "portseltx0": "3",
        "portseltx1": "0",
        "rx0in5v": "0",
        "rx1in5v": "1",
        "rx2in5v": "0",
        "rx3in5v": "1",
        "opmode": "matrix",
        "RX0": "4k60",
    }
    parser = StatusParser()
    status = parser.parse(data)
    assert not isinstance(status, ParseError)
    assert parser.serialize(status) == data
