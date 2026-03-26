import gspread
from google.oauth2.service_account import Credentials
from loguru import logger
from app.config import settings

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

_client: gspread.Client | None = None


def get_sheets_client() -> gspread.Client:
    global _client
    if _client is None:
        creds = Credentials.from_service_account_file(
            settings.google_service_account_json, scopes=SCOPES
        )
        _client = gspread.authorize(creds)
        logger.info("Google Sheets 클라이언트 초기화 완료")
    return _client


def get_spreadsheet() -> gspread.Spreadsheet:
    try:
        return get_sheets_client().open_by_key(settings.spreadsheet_id)
    except Exception as e:
        logger.error(f"스프레드시트 연결 실패: {e}")
        # 연결 오류 -> 클라이언트 재초기화
        global _client
        _client = None
        raise
