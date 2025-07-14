import aiohttp
import logging
from pydantic import BaseModel, parse_obj_as
from urllib.parse import quote
from aiohttp import ClientTimeout, ServerDisconnectedError

from settings import settings

logger = logging.getLogger(__name__)

class CourseDTO(BaseModel):
    id: int
    name: str
    semester: str
    logo: str | None = None
    email: str | None = None


class APIClient:
    def __init__(self, session: aiohttp.ClientSession):
        self._session = session
        self._base = str(settings.server_base_url).rstrip("/")

    async def get_courses(self) -> list[CourseDTO]:
        """Получение списка курсов"""
        url = f"{self._base}/courses"
        logger.info(f"Requesting courses from {url}")
        try:
            async with self._session.get(url, timeout=ClientTimeout(total=10)) as resp:
                resp.raise_for_status()
                data = await resp.json()
                courses = parse_obj_as(list[CourseDTO], data)
                logger.info(f"Retrieved {len(courses)} courses")
                return courses
        except Exception as e:
            logger.error(f"GET /courses failed: {e}")
            return []

    async def get_groups(self, course_id: str) -> list[str]:
        """Получение групп для курса"""
        url = f"{self._base}/courses/{course_id}/groups"
        logger.info(f"Requesting groups for course {course_id}")
        try:
            async with self._session.get(url, timeout=ClientTimeout(total=10)) as resp:
                if resp.status == 200:
                    groups = await resp.json()
                    logger.info(f"Retrieved {len(groups)} groups for course {course_id}")
                    return groups
        except Exception as e:
            logger.error(f"GET {url} failed: {e}")
        return []

    async def get_labs(self, course_id: str, group: str) -> list[str]:
        """Получение лабораторных для группы"""
        url = f"{self._base}/courses/{course_id}/groups/{group}/labs"
        logger.info(f"Requesting labs for course {course_id}, group {group}")
        try:
            async with self._session.get(url, timeout=ClientTimeout(total=10)) as resp:
                if resp.status == 200:
                    labs = await resp.json()
                    logger.info(f"Retrieved {len(labs)} labs for course {course_id}, group {group}")
                    return labs
        except Exception as e:
            logger.error(f"GET {url} failed: {e}")
        return []

    async def register_student(self, course_id: str, group: str, payload: dict) -> dict | None:
        """Регистрация студента на курс"""
        url = f"{self._base}/courses/{course_id}/groups/{group}/register"
        logger.info(f"Registering student for course {course_id}, group {group}")
        try:
            async with self._session.post(url, json=payload, timeout=ClientTimeout(total=10)) as resp:
                if resp.status == 200:
                    result = await resp.json()
                    logger.info(f"Student registration successful for course {course_id}")
                    return result
                result = {"status": "error", "code": resp.status, "message": await resp.text()}
                logger.error(f"Student registration failed for course {course_id}: {result}")
                return result
        except Exception as e:
            logger.error(f"POST {url} failed: {e}")
            return None

    async def grade_lab(self, course_id: str, group: str, lab_id: str, github: str) -> dict | None:
        """Проверка лабораторной работы"""
        url = (
            f"{self._base}/courses/{quote(str(course_id))}"
            f"/groups/{quote(group)}"
            f"/labs/{quote(lab_id)}/grade"
        )
        logger.info(f"Grading lab {lab_id} for course {course_id}, group {group}, github {github}")
        timeout = ClientTimeout(total=120)
        try:
            async with self._session.post(url, json={"github": github}, timeout=timeout) as resp:
                if resp.status == 200:
                    result = await resp.json()
                    logger.info(f"Lab grading completed for lab {lab_id}")
                    return result
                result = {"status": "error", "code": resp.status, "message": await resp.text()}
                logger.error(f"Lab grading failed for lab {lab_id}: {result}")
                return result
        except ServerDisconnectedError:
            logger.info(f"Lab grading pending for lab {lab_id}")
            return {"status": "pending", "message": "Нет ответа, проверка запущена ⏳"}
        except Exception as e:
            logger.error(f"POST {url} failed: {e}")
            return None

    async def get_course_info(self, course_id: str) -> dict | None:
        """Получение информации о курсе"""
        url = f"{self._base}/courses/{course_id}"
        logger.info(f"Requesting course info for course {course_id}")
        try:
            async with self._session.get(url, timeout=ClientTimeout(total=10)) as resp:
                if resp.status == 200:
                    info = await resp.json()
                    logger.info(f"Retrieved course info for course {course_id}")
                    return info
                logger.warning(f"Course info not found for course {course_id}")
                return None
        except Exception as e:
            logger.error(f"GET {url} failed: {e}")
            return None