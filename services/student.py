import logging
from datetime import datetime
from models.student import Student, CourseRef
import json, aiosqlite

logger = logging.getLogger(__name__)

class StudentRepository:
    def __init__(self, db: aiosqlite.Connection):
        self._db = db

    async def get_by_chat(self, chat_id: int) -> Student | None:
        """Получение студента по chat_id"""
        logger.info(f"Getting student by chat_id {chat_id}")
        cur = await self._db.execute("SELECT * FROM students WHERE chat_id=?", (chat_id,))
        row = await cur.fetchone()
        await cur.close()
        if not row:
            logger.info(f"Student not found for chat_id {chat_id}")
            return None
        data = dict(row)
        data["courses"] = [CourseRef(**c) for c in json.loads(data["courses"] or "[]")]
        logger.info(f"Student found for chat_id {chat_id}: {data['surname']} {data['name']}")
        return Student(**data)

    async def save(self, student: Student) -> None:
        """Сохранение студента"""
        logger.info(f"Saving student {student.surname} {student.name} (chat_id: {student.chat_id})")
        
        # Проверяем, не существует ли уже студент с такими же данными
        existing = None
        if not student.id:  # Только для новых студентов
            existing = await self._check_existing_student(student)
        if existing:
            logger.warning(f"Student with same data already exists: {existing.surname} {existing.name} (chat_id: {existing.chat_id})")
            raise ValueError("Студент с такими же данными уже зарегистрирован в системе")
        
        now = datetime.utcnow().isoformat()
        courses_json = json.dumps([c.model_dump() for c in student.courses])
        if student.id:
            await self._db.execute(
                """
                UPDATE students
                   SET surname=?, name=?, patronymic=?, group_code=?, github=?, courses=?, updated_at=?
                 WHERE id=?
                """,
                (
                    student.surname,
                    student.name,
                    student.patronymic,
                    student.group_code,
                    student.github,
                    courses_json,
                    now,
                    student.id,
                ),
            )
            logger.info(f"Updated existing student {student.id}")
        else:
            await self._db.execute(
                """
                INSERT INTO students
                (chat_id, surname, name, patronymic, group_code, github, courses, created_at, updated_at)
                VALUES (?,?,?,?,?,?,?,?,?)
                """,
                (
                    student.chat_id,
                    student.surname,
                    student.name,
                    student.patronymic,
                    student.group_code,
                    student.github,
                    courses_json,
                    now,
                    now,
                ),
            )
            logger.info(f"Created new student for chat_id {student.chat_id}")
        await self._db.commit()

    async def _check_existing_student(self, student: Student) -> Student | None:
        """Проверка существования студента с такими же данными"""
        cur = await self._db.execute(
            """
            SELECT * FROM students 
            WHERE surname=? AND name=? AND group_code=? AND github=?
            """,
            (student.surname, student.name, student.group_code, student.github)
        )
        row = await cur.fetchone()
        await cur.close()
        
        if row:
            data = dict(row)
            data["courses"] = [CourseRef(**c) for c in json.loads(data["courses"] or "[]")]
            return Student(**data)
        return None

    async def all(self):
        """Получение всех студентов"""
        logger.info("Getting all students")
        cur = await self._db.execute("SELECT * FROM students")
        rows = await cur.fetchall()
        await cur.close()
        result = []
        for r in rows:
            data = dict(r)
            data["courses"] = [CourseRef(**c) for c in json.loads(data["courses"] or "[]")]
            result.append(Student(**data))
        logger.info(f"Retrieved {len(result)} students")
        return result

    async def by_group(self, group: str):
        """Получение студентов по группе"""
        logger.info(f"Getting students by group {group}")
        cur = await self._db.execute("SELECT * FROM students WHERE group_code=?", (group,))
        rows = await cur.fetchall()
        await cur.close()
        result = []
        for r in rows:
            data = dict(r)
            data["courses"] = [CourseRef(**c) for c in json.loads(data["courses"] or "[]")]
            result.append(Student(**data))
        logger.info(f"Retrieved {len(result)} students from group {group}")
        return result

    async def get_by_fio(self, group: str, fio: str) -> Student:
        """Получение студента по ФИО и группе"""
        logger.info(f"Getting student by FIO {fio} from group {group}")
        surname, name, *_ = fio.split()
        cur = await self._db.execute(
            "SELECT * FROM students WHERE group_code=? AND surname=? AND name=?",
            (group, surname, name),
        )
        row = await cur.fetchone()
        await cur.close()
        data = dict(row)
        data["courses"] = [CourseRef(**c) for c in json.loads(data["courses"] or "[]")]
        logger.info(f"Found student {surname} {name} in group {group}")
        return Student(**data)

    async def delete_by_index(self, group: str, idx: int):
        """Удаление студента по индексу в группе"""
        logger.info(f"Deleting student by index {idx} from group {group}")
        students = await self.by_group(group)
        target = students[idx]
        await self._db.execute("DELETE FROM students WHERE id=?", (target.id,))
        await self._db.commit()
        logger.info(f"Deleted student {target.surname} {target.name} from group {group}")

    async def delete_student(self, student_id: int):
        """Удаление студента по ID"""
        logger.info(f"Deleting student by ID {student_id}")
        await self._db.execute("DELETE FROM students WHERE id=?", (student_id,))
        await self._db.commit()
        logger.info(f"Deleted student with ID {student_id}")

    async def delete_group(self, group: str):
        """Удаление всех студентов группы"""
        logger.info(f"Deleting all students from group {group}")
        await self._db.execute("DELETE FROM students WHERE group_code=?", (group,))
        await self._db.commit()
        logger.info(f"Deleted all students from group {group}")