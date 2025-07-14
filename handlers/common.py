import logging
from aiogram import Router, F
from aiogram.filters import CommandStart
from aiogram.types import Message, CallbackQuery
from aiogram.exceptions import TelegramBadRequest, TelegramNotFound
from aiogram.utils.markdown import bold
from html import escape as quote_html

import asyncio
import aiohttp

from keyboards.common import start_kb, main_menu_kb, back_menu_kb, home_kb
from keyboards.common import courses_kb, labs_kb
from services.student import StudentRepository
from services.api import APIClient
from utils.semester import current_semester
from models.student import CourseRef

logger = logging.getLogger(__name__)
router = Router()


@router.message(CommandStart())
async def cmd_start(message: Message, students_repo: StudentRepository):
    """Обработка команды /start"""
    logger.info(f"Start command from user {message.chat.id}")
    try:
        await message.delete()
    except (TelegramBadRequest, TelegramNotFound):
        pass
    student = await students_repo.get_by_chat(message.chat.id)

    if student:
        logger.info(f"User {message.chat.id} already registered")
        await message.answer("🏠 Главное меню", reply_markup=main_menu_kb())
    else:
        logger.info(f"New user {message.chat.id} needs registration")
        await message.answer(
            "👋 Добро пожаловать! Для работы необходимо зарегистрироваться",
            reply_markup=start_kb(),
        )


@router.callback_query(F.data == "menu_info")
async def show_info(cb: CallbackQuery, students_repo: StudentRepository):
    """Показать информацию о студенте"""
    logger.info(f"User {cb.message.chat.id} requested info")
    student = await students_repo.get_by_chat(cb.message.chat.id)
    if not student:
        logger.warning(f"User {cb.message.chat.id} not found in database")
        await cb.answer("❌ Нет данных")
        return
    txt = (
        f"<b>{student.surname} {student.name} {student.patronymic or ''}</b>\n"
        f"Группа: {student.group_code}\nGitHub: {student.github}"
    )
    await cb.message.delete()
    await cb.message.answer(txt, reply_markup=back_menu_kb())
    await cb.answer()


@router.callback_query(F.data == "back_menu")
async def back_to_menu(cb: CallbackQuery):
    """Возврат в главное меню"""
    logger.info(f"User {cb.message.chat.id} returned to main menu")
    await cb.message.delete()
    await cb.message.answer("🏠 Главное меню", reply_markup=main_menu_kb())
    await cb.answer()

@router.callback_query(F.data == "menu_choose_course")
async def choose_course(cb: CallbackQuery, api: APIClient):
    """Выбор курса"""
    logger.info(f"User {cb.message.chat.id} choosing course")
    await _show_active_courses(cb, api)

@router.callback_query(F.data == "courses_back")
async def courses_back(cb: CallbackQuery, api: APIClient):
    """Возврат к списку курсов"""
    logger.info(f"User {cb.message.chat.id} returned to courses list")
    await _show_active_courses(cb, api)

async def _show_active_courses(cb: CallbackQuery, api: APIClient) -> None:
    """Показать активные курсы"""
    logger.info(f"Showing active courses for user {cb.message.chat.id}")
    courses = await api.get_courses()
    sem = current_semester()

    active = [c for c in courses if c.semester == sem]
    other = [c for c in courses if c.semester != sem]

    await cb.message.delete()
    await cb.message.answer(
        f"<b>📚 Актуальные курсы\n({sem})</b>",
        reply_markup=courses_kb(active, add_other=bool(other)),
    )
    await cb.answer()

@router.callback_query(F.data == "courses_other")
async def courses_other(cb: CallbackQuery, api: APIClient):
    """Показать другие курсы"""
    logger.info(f"User {cb.message.chat.id} viewing other courses")
    courses = await api.get_courses()
    sem = current_semester()
    other = [c for c in courses if c.semester != sem]

    await cb.message.delete()
    await cb.message.answer(
        "<b>📚 Другие курсы</b>",
        reply_markup=courses_kb(other, add_other=False),
    )
    await cb.answer()

@router.callback_query(F.data.startswith("course_"))
async def course_selected(
    cb: CallbackQuery,
    api: APIClient,
    students_repo: StudentRepository,
):
    """Обработка выбора курса"""
    course_id = cb.data.split("_", 1)[1]
    logger.info(f"User {cb.message.chat.id} selected course {course_id}")
    courses_all = await api.get_courses()
    course = next((c for c in courses_all if str(c.id) == course_id), None)
    if not course:
        logger.warning(f"Course {course_id} not found")
        await cb.answer("❌ Курс не найден", show_alert=True)
        return

    student = await students_repo.get_by_chat(cb.message.chat.id)
    if not student:
        logger.warning(f"User {cb.message.chat.id} not registered")
        await cb.answer("⚠️ Необходимо зарегистрироваться", show_alert=True)
        return

    if any(cr.name == course.name and cr.semester == course.semester for cr in student.courses):
        logger.info(f"User {cb.message.chat.id} already registered for course {course_id}")
        registered = True
    else:
        logger.info(f"Registering user {cb.message.chat.id} for course {course_id}")
        payload = {
            "name": student.name,
            "surname": student.surname,
            "patronymic": student.patronymic,
            "github": student.github,
        }
        result = await api.register_student(course_id, student.group_code, payload)
        if not result:
            logger.error(f"Failed to register user {cb.message.chat.id} for course {course_id}")
            await cb.answer("❌ Ошибка сервера", show_alert=True)
            return
        status = result.get("status")
        if status not in ("registered", "already_registered"):
            logger.error(f"Registration failed for user {cb.message.chat.id}, status: {status}")
            await cb.answer(result.get("message", "❌ Не удалось привязать курс"), show_alert=True)
            return

        student.courses.append(CourseRef(name=course.name, semester=course.semester))
        await students_repo.save(student)
        logger.info(f"User {cb.message.chat.id} successfully registered for course {course_id}")
        registered = True

    if registered:
        groups = await api.get_groups(course_id)
        if student.group_code not in groups:
            logger.warning(f"Course {course_id} not available for group {student.group_code}")
            await cb.answer("⚠️ Этот курс не для твоей группы", show_alert=True)
            return

        labs = await api.get_labs(course_id, student.group_code)
        if not labs:
            logger.info(f"No labs available for course {course_id}, group {student.group_code}")
            await cb.answer("📭 Для твоей группы лабораторных нет", show_alert=True)
            return

        # Получение информации о курсе
        course_info = await api.get_course_info(course_id)
        
        if course_info:
            name = course_info.get('name', 'Неизвестно')
            semester = course_info.get('semester', 'Неизвестно')
            github_org = course_info.get('github-organization', 'Не указан')
            spreadsheet_id = course_info.get('google-spreadsheet', 'Не указан')
            
            github_link = f"https://github.com/{github_org}" if github_org != 'Не указан' else 'Не указан'
            spreadsheet_link = f"https://docs.google.com/spreadsheets/d/{spreadsheet_id}" if spreadsheet_id != 'Не указан' else 'Не указан'
            
            course_text = (
                f"<b>📚 {name} ({semester})</b>\n"
                f"🔗 GitHub: <a href=\"{github_link}\">{github_org}</a>\n"
                f"📊 Таблица: <a href=\"{spreadsheet_link}\">{spreadsheet_id}</a>\n\n"
                f"<b>🧪 Группа {student.group_code} лабораторные</b>"
            )
        else:
            course_text = f"<b>🧪 Группа {student.group_code} лабораторные</b>"
        
        logger.info(f"Showing labs for user {cb.message.chat.id}, course {course_id}")
        await cb.message.delete()
        await cb.message.answer(
            course_text,
            reply_markup=labs_kb(labs, course_id),
            parse_mode="HTML",
            disable_web_page_preview=True
        )
        await cb.answer()

@router.callback_query(F.data.startswith("lab_"))
async def lab_selected(
    cb: CallbackQuery,
    students_repo: StudentRepository,
):
    """Обработка выбора лабораторной"""
    _, course_id, lab_id = cb.data.split("_", 2)
    logger.info(f"User {cb.message.chat.id} selected lab {lab_id} for course {course_id}")
    student = await students_repo.get_by_chat(cb.message.chat.id)
    if not student:
        logger.warning(f"User {cb.message.chat.id} not registered")
        await cb.answer("⚠️ Сначала зарегистрируйся", show_alert=True)
        return

    await cb.message.delete()
    wait_msg = await cb.message.answer("⏳ Проверка запущена…")

    async def poll():
        """Опрос результатов проверки"""
        logger.info(f"Starting lab grading for user {cb.message.chat.id}, lab {lab_id}")
        while True:
            async with aiohttp.ClientSession() as sess:
                res = await APIClient(sess).grade_lab(
                    course_id,
                    student.group_code,
                    lab_id,
                    student.github,
                )
            if not res:
                logger.error(f"Lab grading failed for user {cb.message.chat.id}, lab {lab_id}")
                txt = "❌ Ошибка сервера"
                await wait_msg.edit_text(txt, reply_markup=home_kb())
                return

            if res.get("status") == "pending":
                logger.info(f"Lab grading pending for user {cb.message.chat.id}, lab {lab_id}")
                await asyncio.sleep(15)
                continue

            if res.get("status") == "updated":
                logger.info(f"Lab grading completed for user {cb.message.chat.id}, lab {lab_id}")
                symbol = res.get("result", "✗")
                msg = res.get("message", "")
                passed = res.get("passed", "")
                checks = "\n".join(res.get("checks", []))
                text = (
                    f"{bold('Результат')}: {symbol}\n"
                    f"{quote_html(msg)}\n\n"
                    f"{bold('Тесты')}: {passed}\n\n"
                    f"{checks}"
                )
                await wait_msg.edit_text(text, reply_markup=home_kb())
                return

            err = res.get("message", "❌ Не удалось запустить проверку")
            logger.error(f"Lab grading error for user {cb.message.chat.id}, lab {lab_id}: {err}")
            await wait_msg.edit_text(quote_html(err), reply_markup=home_kb())
            return

    asyncio.create_task(poll())
    await cb.answer()