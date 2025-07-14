import logging
import aiohttp, datetime, aiosqlite
from settings import settings

logger = logging.getLogger(__name__)

COOKIE_SQL = """
CREATE TABLE IF NOT EXISTS admin_sessions (
    id INTEGER PRIMARY KEY,
    cookie TEXT,
    expires_at TEXT
)
"""

class AdminAPI:
    def __init__(self, session: aiohttp.ClientSession):
        self._session = session
        self._base = str(settings.server_base_url).rstrip("/")

    async def login(self, login: str, password: str) -> str | None:
        """Аутентификация администратора"""
        logger.info(f"Admin login attempt for user {login}")
        url = f"{self._base}/api/admin/login"
        async with self._session.post(url, json={"login": login, "password": password}) as r:
            if r.status == 200:
                cookie = r.cookies.get("admin_session")
                if cookie:
                    logger.info(f"Admin login successful for user {login}")
                    return cookie.value
                else:
                    logger.warning(f"Admin login failed - no cookie received for user {login}")
                    return None
            else:
                logger.warning(f"Admin login failed with status {r.status} for user {login}")
                return None

    async def logout(self, cookie: str) -> bool:
        """Выход из системы"""
        logger.info("Admin logout attempt")
        url = f"{self._base}/api/admin/logout"
        async with self._session.post(url, cookies={"admin_session": cookie}) as r:
            success = r.status == 200
            logger.info(f"Admin logout {'successful' if success else 'failed'}")
            return success

    async def check(self, cookie: str) -> bool:
        """Проверка аутентификации"""
        logger.debug("Checking admin authentication")
        url = f"{self._base}/api/admin/check-auth"
        async with self._session.get(url, cookies={"admin_session": cookie}) as r:
            valid = r.status == 200
            logger.debug(f"Admin auth check {'valid' if valid else 'invalid'}")
            return valid

    async def list_courses(self, cookie: str | None = None) -> list[dict]:
        """Получение списка курсов"""
        logger.info("Requesting admin courses list")
        url = f"{self._base}/courses"
        cookies = {"admin_session": cookie} if cookie else {}
        async with self._session.get(url, cookies=cookies) as r:
            courses = await r.json()
            logger.info(f"Retrieved {len(courses)} courses for admin")
            return courses

    async def get_course_info(self, cookie: str, course_id: str):
        """Получение информации о курсе"""
        logger.info(f"Requesting course info for course {course_id}")
        url = f"{self._base}/courses/{course_id}"
        cookies = {"admin_session": cookie} if cookie else {}
        async with self._session.get(url, cookies=cookies) as r:
            if r.status == 200:
                info = await r.json()
                logger.info(f"Retrieved course info for course {course_id}")
                return info
            else:
                logger.warning(f"Course info not found for course {course_id}")
                return None

    async def delete_course(self, cookie: str, course_id: str) -> bool:
        """Удаление курса"""
        logger.info(f"Deleting course {course_id}")
        url = f"{self._base}/courses/{course_id}"
        cookies = {"admin_session": cookie} if cookie else {}
        async with self._session.delete(url, cookies=cookies) as r:
            success = r.status == 200
            logger.info(f"Course {course_id} deletion {'successful' if success else 'failed'}")
            return success

    async def upload_course(self, cookie: str, file_url: str, filename: str) -> bool:
        """Загрузка нового курса"""
        logger.info(f"Uploading course file {filename}")
        url = f"{self._base}/courses/upload"
        cookies = {"admin_session": cookie} if cookie else {}
        
        # Download file from Telegram
        async with self._session.get(file_url) as file_resp:
            if file_resp.status != 200:
                logger.error(f"Failed to download file from {file_url}")
                return False
            
            file_data = await file_resp.read()
            form = aiohttp.FormData()
            form.add_field("file", file_data, filename=filename, content_type="application/x-yaml")
            
            async with self._session.post(url, data=form, cookies=cookies) as r:
                success = r.status == 200
                logger.info(f"Course upload {'successful' if success else 'failed'} for {filename}")
                return success


class AdminSessionRepo:
    def __init__(self, db: aiosqlite.Connection):
        self._db = db

    async def ensure_table(self):
        """Создание таблицы сессий"""
        logger.debug("Ensuring admin sessions table exists")
        await self._db.execute(COOKIE_SQL)
        await self._db.commit()

    async def get_cookie(self) -> tuple[str, str] | None:
        """Получение сохраненной сессии"""
        logger.debug("Getting admin session cookie")
        cur = await self._db.execute("SELECT cookie, expires_at FROM admin_sessions LIMIT 1")
        row = await cur.fetchone()
        await cur.close()
        if row:
            logger.debug("Admin session cookie found")
            return tuple(row)
        else:
            logger.debug("No admin session cookie found")
            return None

    async def save_cookie(self, cookie: str, ttl_sec: int = 3600):
        """Сохранение сессии"""
        logger.info("Saving admin session cookie")
        expires = (datetime.datetime.utcnow() + datetime.timedelta(seconds=ttl_sec)).isoformat()
        await self._db.execute("DELETE FROM admin_sessions")
        await self._db.execute("INSERT INTO admin_sessions(cookie, expires_at) VALUES(?,?)", (cookie, expires))
        await self._db.commit()

    async def clear(self):
        """Очистка сессий"""
        logger.info("Clearing admin session cookies")
        await self._db.execute("DELETE FROM admin_sessions")
        await self._db.commit()