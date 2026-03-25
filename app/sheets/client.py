
import gspread
from google.oauth2.service_account import Credentials
from loguru import logger
from app.config import settings

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]


def get_sheets_client() -> gspread.Client:
    try:
        creds = Credentials.from_service_account_file(
            settings.google_service_account_json,
            scopes=SCOPES
        )
        client = gspread.authorize(creds)
        logger.info("Google Sheets 클라이언트 연결 성공")
        return client
    except Exception as e:
        logger.error(f"Google Sheets 클라이언트 연결 실패: {e}")
        raise


def get_spreadsheet() -> gspread.Spreadsheet:
    try:
        client = get_sheets_client()
        spreadsheet = client.open_by_key(settings.spreadsheet_id)
        logger.info(f"스프레드시트 연결 성공: {spreadsheet.title}")
        return spreadsheet
    except Exception as e:
        logger.error(f"스프레드시트 연결 실패: {e}")
        raise