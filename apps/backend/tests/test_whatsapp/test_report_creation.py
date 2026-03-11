"""
Tests for create_sos_report() in the WhatsApp webhook handler.

Verifies that:
- media_url is stored as a Report column value (not only inside media_metadata)
- media_url is None when no photo is provided
- media_metadata contains ML classification fields when a classification is present
"""
import json
import uuid
from unittest.mock import MagicMock

from src.api.webhook import create_sos_report


def _make_db_mock():
    """Return a db session mock that captures the Report passed to db.add()."""
    db = MagicMock()

    def _fake_refresh(obj):
        # Simulate SQLAlchemy refresh by setting an id if not already set
        if not hasattr(obj, 'id') or obj.id is None:
            obj.id = uuid.uuid4()

    db.add = MagicMock()
    db.commit = MagicMock()
    db.refresh = MagicMock(side_effect=_fake_refresh)
    return db


def _make_classification(is_flood: bool, confidence: float = 0.85):
    """Build a minimal FloodClassification-like mock."""
    cls = MagicMock()
    cls.is_flood = is_flood
    cls.confidence = confidence
    cls.classification = "flood" if is_flood else "no_flood"
    cls.needs_review = not is_flood
    return cls


# =============================================================================
# TEST 1: media_url is set on the Report when a photo is provided
# =============================================================================

class TestReportHasMediaUrlWhenPhotoProvided:
    """create_sos_report() must populate Report.media_url from the media_url argument."""

    def test_report_has_media_url_when_photo_provided(self):
        """Report.media_url should equal the Twilio media URL passed in."""
        db = _make_db_mock()
        media_url = "https://api.twilio.com/2010-04-01/Accounts/AC123/Messages/SM123/Media/ME123"
        classification = _make_classification(is_flood=True)

        report = create_sos_report(
            db=db,
            latitude=28.6139,
            longitude=77.2090,
            phone="+919876543210",
            user=None,
            media_url=media_url,
            classification=classification,
        )

        assert report.media_url == media_url, (
            f"Expected report.media_url={media_url!r}, got {report.media_url!r}"
        )

    def test_report_media_url_persisted_to_db(self):
        """db.add() should be called with a Report that has media_url set."""
        db = _make_db_mock()
        media_url = "https://api.twilio.com/2010-04-01/Accounts/AC123/Messages/SM123/Media/ME456"

        create_sos_report(
            db=db,
            latitude=28.6139,
            longitude=77.2090,
            phone="+919876543210",
            user=None,
            media_url=media_url,
            classification=None,
        )

        db.add.assert_called_once()
        added_report = db.add.call_args[0][0]
        assert added_report.media_url == media_url, (
            f"Report passed to db.add() should have media_url={media_url!r}, "
            f"got {added_report.media_url!r}"
        )


# =============================================================================
# TEST 2: media_url is None when no photo is provided
# =============================================================================

class TestReportMediaUrlNoneWhenNoPhoto:
    """create_sos_report() must leave Report.media_url as None when media_url is not supplied."""

    def test_report_media_url_none_when_no_photo(self):
        """Report.media_url should be None for location-only reports."""
        db = _make_db_mock()

        report = create_sos_report(
            db=db,
            latitude=28.6139,
            longitude=77.2090,
            phone="+919876543210",
            user=None,
            media_url=None,
            classification=None,
        )

        assert report.media_url is None, (
            f"Expected report.media_url=None for no-photo report, got {report.media_url!r}"
        )

    def test_report_media_url_none_added_to_db(self):
        """db.add() should receive a Report with media_url=None when no photo is given."""
        db = _make_db_mock()

        create_sos_report(
            db=db,
            latitude=28.6139,
            longitude=77.2090,
            phone="+919876543210",
            user=None,
            media_url=None,
            classification=None,
        )

        db.add.assert_called_once()
        added_report = db.add.call_args[0][0]
        assert added_report.media_url is None, (
            f"Report passed to db.add() should have media_url=None, "
            f"got {added_report.media_url!r}"
        )


# =============================================================================
# TEST 3: media_metadata contains ML classification fields
# =============================================================================

class TestReportHasMediaMetadataWithClassification:
    """create_sos_report() must embed ML result fields inside media_metadata."""

    def test_flood_classification_stored_in_media_metadata(self):
        """media_metadata should contain ml_classification, ml_confidence, is_flood, needs_review, and media_url."""
        db = _make_db_mock()
        media_url = "https://api.twilio.com/2010-04-01/Accounts/AC123/Messages/SM123/Media/ME789"
        classification = _make_classification(is_flood=True, confidence=0.92)

        report = create_sos_report(
            db=db,
            latitude=28.6139,
            longitude=77.2090,
            phone="+919876543210",
            user=None,
            media_url=media_url,
            classification=classification,
        )

        assert report.media_metadata is not None, "media_metadata should not be None when classification is provided"
        metadata = json.loads(report.media_metadata) if isinstance(report.media_metadata, str) else report.media_metadata
        assert metadata["ml_classification"] == "flood"
        assert metadata["ml_confidence"] == 0.92
        assert metadata["is_flood"] is True
        assert metadata["needs_review"] is False
        assert metadata["media_url"] == media_url

    def test_no_flood_classification_stored_in_media_metadata(self):
        """media_metadata should reflect is_flood=False when classifier returns no flood."""
        db = _make_db_mock()
        media_url = "https://api.twilio.com/2010-04-01/Accounts/AC123/Messages/SM123/Media/ME999"
        classification = _make_classification(is_flood=False, confidence=0.70)

        report = create_sos_report(
            db=db,
            latitude=28.6139,
            longitude=77.2090,
            phone="+919876543210",
            user=None,
            media_url=media_url,
            classification=classification,
        )

        assert report.media_metadata is not None
        metadata = json.loads(report.media_metadata) if isinstance(report.media_metadata, str) else report.media_metadata
        assert metadata["is_flood"] is False
        assert metadata["needs_review"] is True

    def test_media_metadata_none_when_no_photo_no_classification(self):
        """media_metadata should be None for a pure location-only report."""
        db = _make_db_mock()

        report = create_sos_report(
            db=db,
            latitude=28.6139,
            longitude=77.2090,
            phone="+919876543210",
            user=None,
            media_url=None,
            classification=None,
        )

        assert report.media_metadata is None, (
            f"media_metadata should be None for location-only report, got {report.media_metadata!r}"
        )

    def test_media_metadata_set_when_photo_but_no_classification(self):
        """media_metadata should indicate ml_unavailable when photo provided but no classification."""
        db = _make_db_mock()
        media_url = "https://api.twilio.com/2010-04-01/Accounts/AC123/Messages/SM123/Media/ME000"

        report = create_sos_report(
            db=db,
            latitude=28.6139,
            longitude=77.2090,
            phone="+919876543210",
            user=None,
            media_url=media_url,
            classification=None,
        )

        assert report.media_metadata is not None
        metadata = json.loads(report.media_metadata) if isinstance(report.media_metadata, str) else report.media_metadata
        assert metadata.get("ml_unavailable") is True
        assert metadata["media_url"] == media_url
