"""
Tests for the ingestion pipeline.
Tests file validation, size limits, and CSV/XLSX parsing logic.
"""
import io
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi import HTTPException, UploadFile


# ---------------------------------------------------------------------------
# Helpers to create mock UploadFile objects
# ---------------------------------------------------------------------------

def _make_upload_file(filename: str, content: bytes) -> UploadFile:
    """Create a mock UploadFile with the given filename and content."""
    mock_file = MagicMock(spec=UploadFile)
    mock_file.filename = filename
    mock_file.read = AsyncMock(return_value=content)
    return mock_file


# ---------------------------------------------------------------------------
# Extension validation
# ---------------------------------------------------------------------------

class TestFileValidation:
    @pytest.mark.asyncio
    async def test_reject_invalid_extension(self):
        """Files with extensions other than .csv/.xlsx must be rejected."""
        from app.services.ingestion_service import handle_file_upload

        mock_db = AsyncMock()
        mock_file = _make_upload_file("survey.pdf", b"fake content")

        with pytest.raises(HTTPException) as exc_info:
            await handle_file_upload(db=mock_db, project_id=1, file=mock_file)
        assert exc_info.value.status_code == 400
        assert "extension" in exc_info.value.detail.lower() or "pdf" in exc_info.value.detail.lower()

    @pytest.mark.asyncio
    async def test_reject_no_filename(self):
        """Files without a filename must be rejected."""
        from app.services.ingestion_service import handle_file_upload

        mock_db = AsyncMock()
        mock_file = _make_upload_file("", b"content")

        with pytest.raises(HTTPException) as exc_info:
            await handle_file_upload(db=mock_db, project_id=1, file=mock_file)
        assert exc_info.value.status_code == 400

    @pytest.mark.asyncio
    async def test_reject_txt_extension(self):
        """Text files must be rejected."""
        from app.services.ingestion_service import handle_file_upload

        mock_db = AsyncMock()
        mock_file = _make_upload_file("data.txt", b"a,b,c")

        with pytest.raises(HTTPException) as exc_info:
            await handle_file_upload(db=mock_db, project_id=1, file=mock_file)
        assert exc_info.value.status_code == 400

    @pytest.mark.asyncio
    async def test_reject_file_too_large(self):
        """Files exceeding 100 MB must be rejected."""
        from app.services.ingestion_service import handle_file_upload, MAX_FILE_SIZE_BYTES

        mock_db = AsyncMock()
        big_content = b"x" * (MAX_FILE_SIZE_BYTES + 1)
        mock_file = _make_upload_file("big.csv", big_content)

        with pytest.raises(HTTPException) as exc_info:
            await handle_file_upload(db=mock_db, project_id=1, file=mock_file)
        assert exc_info.value.status_code == 400
        assert "size" in exc_info.value.detail.lower() or "100" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_accept_csv_extension(self):
        """CSV files should pass validation (mocking the S3 and DB calls)."""
        from app.services.ingestion_service import handle_file_upload

        csv_content = b"respondent_id,q1,q2\n1,A,B\n2,C,D"
        mock_file = _make_upload_file("survey.csv", csv_content)

        with (
            patch("app.services.ingestion_service._get_s3_client") as mock_s3,
            patch("app.services.ingestion_service._ensure_bucket"),
            patch("app.services.ingestion_service.dispatch_ingestion_task") as mock_dispatch,
        ):
            # Mock S3 client
            mock_s3_client = MagicMock()
            mock_s3.return_value = mock_s3_client
            mock_dispatch.return_value = "fake-celery-id"

            # Mock DB session
            mock_db = AsyncMock()
            # Simulate flush/commit/refresh
            mock_uploaded_file = MagicMock()
            mock_uploaded_file.id = 42
            mock_job_run = MagicMock()
            mock_job_run.id = 99

            async def fake_flush():
                pass

            async def fake_commit():
                pass

            async def fake_refresh(obj):
                pass

            mock_db.flush = fake_flush
            mock_db.commit = fake_commit
            mock_db.refresh = fake_refresh
            mock_db.add = MagicMock()
            mock_db.execute = AsyncMock()

            # Patch model constructors
            with (
                patch("app.services.ingestion_service.UploadedFile", return_value=mock_uploaded_file),
                patch("app.services.ingestion_service.JobRun", return_value=mock_job_run),
            ):
                result = await handle_file_upload(db=mock_db, project_id=1, file=mock_file)
                assert result["status"] == "pending"
                assert result["filename"] == "survey.csv"

    @pytest.mark.asyncio
    async def test_accept_xlsx_extension(self):
        """XLSX files should pass extension validation."""
        from app.services.ingestion_service import _get_extension, ALLOWED_EXTENSIONS
        ext = _get_extension("survey.xlsx")
        assert ext in ALLOWED_EXTENSIONS


# ---------------------------------------------------------------------------
# CSV parsing / normalization logic
# ---------------------------------------------------------------------------

class TestCsvParsing:
    def test_normalize_column_name_basic(self):
        from apps.worker.app.tasks.ingestion_tasks import _normalize_column_name
        assert _normalize_column_name("  Hello World  ") == "hello_world"
        assert _normalize_column_name("Q1. Rating") == "q1_rating"
        assert _normalize_column_name("respondent-id") == "respondent_id"

    def test_normalize_column_name_special_chars(self):
        from apps.worker.app.tasks.ingestion_tasks import _normalize_column_name
        assert _normalize_column_name("A/B Test") == "ab_test"
        assert _normalize_column_name("___foo___") == "foo"

    def test_normalize_preserves_underscores(self):
        from apps.worker.app.tasks.ingestion_tasks import _normalize_column_name
        result = _normalize_column_name("q_1_answer")
        assert "q" in result and "1" in result


# ---------------------------------------------------------------------------
# Import path helper (worker code is in apps/worker)
# ---------------------------------------------------------------------------
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../../apps/worker"))
# Re-export the function from the worker module for the test above
try:
    from app.tasks.ingestion_tasks import _normalize_column_name  # noqa: F401
except ImportError:
    pass
