import datetime, aiosqlite, aiohttp
import contextlib
import logging

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.exceptions import TelegramBadRequest, TelegramNotFound
from services.admin import AdminAPI, AdminSessionRepo
from services.student import StudentRepository
from states.admin import AdminLogin, AdminMenu
from keyboards.admin import *

logger = logging.getLogger(__name__)
router = Router()
BOT_MSG_KEY = "__bot_msg_id"


async def _cleanup_prev(state: FSMContext, chat_id: int, bot):
    """Удаление предыдущего сообщения бота"""
    data = await state.get_data()
    msg_id = data.get(BOT_MSG_KEY)
    if msg_id:
        with contextlib.suppress(Exception):
            await bot.delete_message(chat_id, msg_id)

async def _send(state: FSMContext, obj, text: str, kb):
    """Отправка сообщения с обновлением состояния"""
    bot, chat_id = obj.bot, (obj.message.chat.id if isinstance(obj, CallbackQuery) else obj.chat.id)
    
    try:
        await _cleanup_prev(state, chat_id, bot)
        m = await bot.send_message(
            chat_id, 
            text, 
            reply_markup=kb,
            parse_mode="HTML",
            disable_web_page_preview=True
        )
        await state.update_data({BOT_MSG_KEY: m.message_id})
    except Exception as e:
        logger.error(f"Error in _send for chat {chat_id}: {e}")
        try:
            await bot.send_message(chat_id, text, reply_markup=kb, parse_mode="HTML")
        except Exception as fallback_error:
            logger.error(f"Fallback send also failed: {fallback_error}")


@router.message(F.text.lower() == "/admin")
async def admin_entry(msg: Message, state: FSMContext):
    """Вход в админ-панель"""
    logger.info(f"Admin entry attempt from user {msg.chat.id}")
    try:
        await msg.delete()
    except (TelegramBadRequest, TelegramNotFound):
        pass
    await state.clear()
    await state.set_state(AdminLogin.LOGIN)
    await _send(state, msg, "Введите логин", login_back_kb())


@router.message(AdminLogin.LOGIN)
async def admin_login_step(msg: Message, state: FSMContext):
    """Обработка ввода логина"""
    logger.info(f"Admin login step from user {msg.chat.id}")
    await msg.delete()
    await state.update_data(login=msg.text.strip())
    await state.set_state(AdminLogin.PASSWORD)
    await _send(state, msg, "Введите пароль", login_back_kb())


@router.message(AdminLogin.PASSWORD)
async def admin_password_step(msg: Message, state: FSMContext, db: aiosqlite.Connection):
    """Обработка ввода пароля"""
    logger.info(f"Admin password step from user {msg.chat.id}")
    await msg.delete()
    data = await state.get_data()
    login, pwd = data["login"], msg.text.strip()

    async with aiohttp.ClientSession() as s:
        api = AdminAPI(s)
        cookie = await api.login(login, pwd)

    if not cookie:
        logger.warning(f"Admin login failed for user {msg.chat.id}")
        await _send(state, msg, "❌ Неверные данные. Попробуйте ещё раз", login_back_kb())
        return

    repo = AdminSessionRepo(db)
    await repo.ensure_table()
    await repo.save_cookie(cookie)
    logger.info(f"Admin login successful for user {msg.chat.id}")

    await state.set_state(AdminMenu.MAIN)
    await _send(state, msg, "🔧 Админ-панель", admin_main_kb())


@router.callback_query(F.data == "admin_cancel")
async def admin_cancel(cb: CallbackQuery, state: FSMContext, db: aiosqlite.Connection):
    """Отмена операции в админ-панели"""
    logger.info(f"Admin cancel operation from user {cb.message.chat.id}")
    current_state = await state.get_state()
    
    if current_state == AdminMenu.CONFIRM:
        data = await state.get_data()
        if "cur_group" in data:
            group = data["cur_group"]
            repo = StudentRepository(db)
            students = sorted([f"{s.surname} {s.name} {s.patronymic or ''}".strip() for s in await repo.by_group(group)])
            await state.update_data(cur_group=group, students=students)
            await state.set_state(AdminMenu.STUDENTS)
            await _send(state, cb, f"👥 {group}: студенты", students_kb(students, group))
        elif "cur_course_id" in data:
            if await _ensure_admin(cb, db):
                repo = AdminSessionRepo(db)
                cookie_data = await repo.get_cookie()
                if cookie_data:
                    cookie, _ = cookie_data
                    async with aiohttp.ClientSession() as s:
                        courses = await AdminAPI(s).list_courses(cookie)
                    await state.set_state(AdminMenu.COURSES)
                    await _send(state, cb, "📚 Курсы:", courses_kb(courses))
                else:
                    await state.set_state(AdminMenu.MAIN)
                    await _send(state, cb, "🔧 Админ-панель", admin_main_kb())
            else:
                await state.set_state(AdminMenu.MAIN)
                await _send(state, cb, "🔧 Админ-панель", admin_main_kb())
        else:
            await state.set_state(AdminMenu.MAIN)
            await _send(state, cb, "🔧 Админ-панель", admin_main_kb())
    else:
        await state.clear()
        await cb.message.delete()
    
    await cb.answer()


@router.callback_query(F.data == "admin_logout")
async def admin_logout(cb: CallbackQuery, db: aiosqlite.Connection):
    """Выход из админ-панели"""
    logger.info(f"Admin logout from user {cb.message.chat.id}")
    repo = AdminSessionRepo(db)
    cookie_data = await repo.get_cookie()
    if cookie_data:
        cookie, _ = cookie_data
        async with aiohttp.ClientSession() as s:
            await AdminAPI(s).logout(cookie)
    await repo.clear()
    await cb.message.delete()
    await cb.answer("✅ Сессия завершена")


async def _ensure_admin(cb: CallbackQuery, db: aiosqlite.Connection) -> bool:
    """Проверка аутентификации администратора"""
    repo = AdminSessionRepo(db)
    cookie_data = await repo.get_cookie()
    if not cookie_data:
        logger.warning(f"Admin session not found for user {cb.message.chat.id}")
        await cb.answer("⚠️ Нужно войти заново", show_alert=True)
        return False
    cookie, expires = cookie_data
    if datetime.datetime.fromisoformat(expires) <= datetime.datetime.utcnow():
        logger.warning(f"Admin session expired for user {cb.message.chat.id}")
        await repo.clear()
        await cb.answer("⏰ Сессия истекла", show_alert=True)
        return False
    return True


@router.callback_query(F.data == "admin_groups")
async def admin_groups(cb: CallbackQuery, db: aiosqlite.Connection, state: FSMContext):
    """Показать список групп"""
    logger.info(f"Admin viewing groups from user {cb.message.chat.id}")
    if not await _ensure_admin(cb, db):
        return
    repo = StudentRepository(db)
    groups = sorted({st.group_code for st in await repo.all()})
    await state.set_state(AdminMenu.GROUPS)
    await _send(state, cb, "👥 Группы:", groups_kb(groups))
    await cb.answer()


@router.callback_query(F.data.startswith("adm_group_"))
async def admin_group_open(cb: CallbackQuery, db: aiosqlite.Connection, state: FSMContext):
    """Открыть группу студентов"""
    group = "_".join(cb.data.split("_")[2:])
    logger.info(f"Admin viewing group {group} from user {cb.message.chat.id}")
    repo = StudentRepository(db)
    students = sorted([f"{s.surname} {s.name} {s.patronymic or ''}".strip() for s in await repo.by_group(group)])
    await state.update_data(cur_group=group, students=students)
    await state.set_state(AdminMenu.STUDENTS)
    await _send(state, cb, f"👥 {group}: студенты", students_kb(students, group))
    await cb.answer()


@router.callback_query(F.data == "admin_back_groups")
async def back_groups(cb: CallbackQuery, db: aiosqlite.Connection, state: FSMContext):
    """Возврат к списку групп"""
    logger.info(f"Admin back to groups from user {cb.message.chat.id}")
    repo = StudentRepository(db)
    groups = sorted({st.group_code for st in await repo.all()})
    await state.set_state(AdminMenu.GROUPS)
    await _send(state, cb, "👥 Группы:", groups_kb(groups))
    await cb.answer()


@router.callback_query(F.data.startswith("adm_back_students_"))
async def back_students(cb: CallbackQuery, db: aiosqlite.Connection, state: FSMContext):
    """Возврат к списку студентов группы"""
    group = "_".join(cb.data.split("_")[3:])
    logger.info(f"Admin back to students of group {group} from user {cb.message.chat.id}")
    repo = StudentRepository(db)
    students = sorted([f"{s.surname} {s.name} {s.patronymic or ''}".strip() for s in await repo.by_group(group)])
    await state.update_data(cur_group=group, students=students)
    await state.set_state(AdminMenu.STUDENTS)
    await _send(state, cb, f"👥 {group}: студенты", students_kb(students, group))
    await cb.answer()


@router.callback_query(F.data == "empty_list")
async def empty_list_callback(cb: CallbackQuery):
    """Обработка пустого списка"""
    logger.info(f"Empty list callback from user {cb.message.chat.id}")
    await cb.answer("📭 Список пуст", show_alert=True)


@router.callback_query(F.data == "admin_back")
async def back_to_main(cb: CallbackQuery, state: FSMContext):
    """Возврат в главное меню админ-панели"""
    logger.info(f"Admin back to main menu from user {cb.message.chat.id}")
    await state.set_state(AdminMenu.MAIN)
    await _send(state, cb, "🔧 Админ-панель", admin_main_kb())
    await cb.answer()


@router.callback_query(F.data.startswith("adm_student_"))
async def admin_student(cb: CallbackQuery, db: aiosqlite.Connection, state: FSMContext):
    """Показать информацию о студенте"""
    parts = cb.data.split("_")
    idx = int(parts[-1])
    group = "_".join(parts[2:-1])
    students = (await state.get_data())["students"]
    fio = students[idx]
    logger.info(f"Admin viewing student {fio} from group {group}")

    repo = StudentRepository(db)
    student = await repo.get_by_fio(group, fio)
    text = (
        f"<b>👤 {fio}</b>\n"
        f"🎓 Группа: {student.group_code}\n🔗 GitHub: {student.github}\n"
        f"📚 Курсы: {', '.join(f'{c.name} ({c.semester})' for c in student.courses) or '—'}"
    )
    await state.set_state(AdminMenu.STUDENT_INFO)
    await state.update_data(sel_idx=idx)
    await _send(state, cb, text, student_info_kb(group, idx))
    await cb.answer()


@router.callback_query(F.data == "adm_del_st_yes_confirm")
async def del_student(cb: CallbackQuery, db: aiosqlite.Connection, state: FSMContext):
    """Удаление студента"""
    data = await state.get_data()
    
    if "cur_group" not in data or "del_student_idx" not in data:
        logger.error(f"Missing data for student deletion from user {cb.message.chat.id}")
        await cb.answer("❌ Ошибка: данные не найдены")
        return
    
    group = data["cur_group"]
    idx = data["del_student_idx"]
    
    repo = StudentRepository(db)
    students = await repo.by_group(group)
    
    if idx < len(students):
        target = students[idx]
        await repo.delete_student(target.id)
        logger.info(f"Admin deleted student {target.surname} {target.name} from group {group}")
        
        # Обновляем список студентов
        students = sorted([f"{s.surname} {s.name} {s.patronymic or ''}".strip() for s in await repo.by_group(group)])
        await state.update_data(cur_group=group, students=students)
        await state.set_state(AdminMenu.STUDENTS)
        await _send(state, cb, f"👥 {group}: студенты", students_kb(students, group))
    else:
        logger.error(f"Student index {idx} out of range for group {group}")
        await cb.answer("❌ Ошибка: студент не найден")
    
    await cb.answer()


@router.callback_query(F.data.startswith("adm_del_st_") & ~F.data.startswith("adm_del_st_yes_"))
async def confirm_del_student(cb: CallbackQuery, state: FSMContext):
    """Подтверждение удаления студента"""
    # Извлекаем данные из callback: adm_del_st_4231_0 -> group=4231, idx=0
    parts = cb.data.split("_")
    if len(parts) >= 5:
        group = parts[3]
        idx = int(parts[4])
    else:
        logger.error(f"Invalid callback data for student deletion: {cb.data}")
        await cb.answer("❌ Ошибка: неверные данные")
        return
    
    students = (await state.get_data())["students"]
    if idx < len(students):
        fio = students[idx]
        logger.info(f"Admin confirming deletion of student {fio} from group {group}")
        
        await state.update_data(del_student_idx=idx)
        await state.set_state(AdminMenu.CONFIRM)
        await _send(state, cb, f"❓ Удалить студента {fio}?", confirm_kb(f"adm_del_st_yes_confirm"))
    else:
        logger.error(f"Student index {idx} out of range")
        await cb.answer("❌ Ошибка: студент не найден")
    
    await cb.answer()


@router.callback_query(F.data.startswith("adm_del_group_") & ~F.data.startswith("adm_del_group_yes_"))
async def confirm_del_group(cb: CallbackQuery, state: FSMContext):
    """Подтверждение удаления группы"""
    # Извлекаем ID группы из callback данных
    # adm_del_group_4231 -> 4231
    group = cb.data.replace("adm_del_group_", "")
    logger.info(f"Admin confirming deletion of group {group}")
    
    await state.update_data(del_group=group)
    await state.set_state(AdminMenu.CONFIRM)
    await _send(state, cb, f"❓ Удалить группу {group}?", confirm_kb(f"adm_del_group_yes_{group}"))
    await cb.answer()


@router.callback_query(F.data.startswith("adm_del_group_yes_"))
async def del_group(cb: CallbackQuery, db: aiosqlite.Connection, state: FSMContext):
    """Удаление группы"""
    # Извлекаем ID группы из callback данных
    # adm_del_group_yes_4231 -> 4231
    group = cb.data.replace("adm_del_group_yes_", "")
    logger.info(f"Admin deleting group {group}")
    
    repo = StudentRepository(db)
    await repo.delete_group(group)
    
    await state.set_state(AdminMenu.GROUPS)
    groups = sorted({st.group_code for st in await repo.all()})
    await _send(state, cb, "👥 Группы:", groups_kb(groups))
    await cb.answer()


@router.callback_query(F.data == "admin_courses")
async def admin_courses(cb: CallbackQuery, state: FSMContext, db: aiosqlite.Connection):
    """Показать список курсов"""
    logger.info(f"Admin viewing courses from user {cb.message.chat.id}")
    if not await _ensure_admin(cb, db):
        return
    
    repo = AdminSessionRepo(db)
    cookie_data = await repo.get_cookie()
    if not cookie_data:
        logger.warning(f"Admin session not found for courses view")
        await cb.answer("⚠️ Нужно войти заново", show_alert=True)
        return
    
    cookie, _ = cookie_data
    async with aiohttp.ClientSession() as s:
        courses = await AdminAPI(s).list_courses(cookie)
    
    await state.set_state(AdminMenu.COURSES)
    await _send(state, cb, "📚 Курсы:", courses_kb(courses))
    await cb.answer()


@router.callback_query(F.data == "admin_back_courses")
async def back_courses(cb: CallbackQuery, state: FSMContext, db: aiosqlite.Connection):
    """Возврат к списку курсов"""
    logger.info(f"Admin back to courses from user {cb.message.chat.id}")
    if not await _ensure_admin(cb, db):
        return
    
    repo = AdminSessionRepo(db)
    cookie_data = await repo.get_cookie()
    if not cookie_data:
        logger.warning(f"Admin session not found for courses back")
        await cb.answer("⚠️ Нужно войти заново", show_alert=True)
        return
    
    cookie, _ = cookie_data
    async with aiohttp.ClientSession() as s:
        courses = await AdminAPI(s).list_courses(cookie)
    
    await state.set_state(AdminMenu.COURSES)
    await _send(state, cb, "📚 Курсы:", courses_kb(courses))
    await cb.answer()


@router.callback_query(F.data.startswith("adm_course_del_") & ~F.data.startswith("adm_course_del_yes_"))
async def confirm_course_del(cb: CallbackQuery, state: FSMContext, db: aiosqlite.Connection):
    """Подтверждение удаления курса"""
    # Извлекаем ID курса из callback данных
    # adm_course_del_1 -> 1
    course_id = cb.data.replace("adm_course_del_", "")
    logger.info(f"Admin confirming deletion of course {course_id}")
    
    await state.update_data(del_course_id=course_id)
    await state.set_state(AdminMenu.CONFIRM)
    await _send(state, cb, f"❓ Удалить курс {course_id}?", confirm_kb(f"adm_course_del_yes_{course_id}"))
    await cb.answer()


@router.callback_query(F.data.startswith("adm_course_del_yes_"))
async def do_course_del(cb: CallbackQuery, state: FSMContext, db: aiosqlite.Connection):
    """Удаление курса"""
    # Извлекаем ID курса из callback данных
    # adm_course_del_yes_1 -> 1
    course_id = cb.data.replace("adm_course_del_yes_", "")
    logger.info(f"Admin deleting course {course_id}")
    
    repo = AdminSessionRepo(db)
    cookie_data = await repo.get_cookie()
    if not cookie_data:
        logger.warning(f"Admin session not found for course deletion")
        await cb.answer("⚠️ Нужно войти заново", show_alert=True)
        return
    
    cookie, _ = cookie_data
    async with aiohttp.ClientSession() as s:
        api = AdminAPI(s)
        success = await api.delete_course(cookie, course_id)
    
    if success:
        logger.info(f"Course {course_id} deleted successfully")
        courses = await api.list_courses(cookie)
        await state.set_state(AdminMenu.COURSES)
        await _send(state, cb, "📚 Курсы:", courses_kb(courses))
    else:
        logger.error(f"Failed to delete course {course_id}")
        await cb.answer("❌ Ошибка удаления курса", show_alert=True)
    
    await cb.answer()


@router.callback_query(F.data == "adm_course_add")
async def add_course_start(cb: CallbackQuery, state: FSMContext, db: aiosqlite.Connection):
    """Начало добавления курса"""
    logger.info(f"Admin starting course addition from user {cb.message.chat.id}")
    if not await _ensure_admin(cb, db):
        return
    
    await state.set_state(AdminMenu.EDIT)
    await _send(state, cb, "📤 Отправьте файл курса", InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="⬅️ Назад", callback_data="admin_back_courses")]]
    ))
    await cb.answer()


@router.callback_query(F.data.startswith("adm_course_"))
async def course_info(cb: CallbackQuery, state: FSMContext, db: aiosqlite.Connection):
    """Информация о курсе"""
    course_id = cb.data.split("_")[-1]
    logger.info(f"Admin viewing course {course_id} info")
    
    repo = AdminSessionRepo(db)
    cookie_data = await repo.get_cookie()
    if not cookie_data:
        logger.warning(f"Admin session not found for course info")
        await cb.answer("⚠️ Нужно войти заново", show_alert=True)
        return
    
    cookie, _ = cookie_data
    async with aiohttp.ClientSession() as s:
        api = AdminAPI(s)
        course_info = await api.get_course_info(cookie, course_id)
    
    if course_info:
        name = course_info.get('name', 'Неизвестно')
        semester = course_info.get('semester', 'Неизвестно')
        github_org = course_info.get('github-organization', 'Не указан')
        spreadsheet_id = course_info.get('google-spreadsheet', 'Не указан')
        
        github_link = f"https://github.com/{github_org}" if github_org != 'Не указан' else 'Не указан'
        spreadsheet_link = f"https://docs.google.com/spreadsheets/d/{spreadsheet_id}" if spreadsheet_id != 'Не указан' else 'Не указан'
        
        text = (
            f"<b>📚 {name} ({semester})</b>\n"
            f"🔗 GitHub: <a href=\"{github_link}\">{github_org}</a>\n"
            f"📊 Таблица: <a href=\"{spreadsheet_link}\">{spreadsheet_id}</a>"
        )
    else:
        text = f"<b>📚 Курс {course_id}</b>\nИнформация недоступна"
    
    await state.set_state(AdminMenu.COURSE_INFO)
    await state.update_data(cur_course_id=course_id)
    await _send(state, cb, text, course_actions_kb(course_id))
    await cb.answer()


@router.message(AdminMenu.EDIT, F.document)
async def upload_new_course(msg: Message, state: FSMContext, db: aiosqlite.Connection):
    """Загрузка нового курса"""
    logger.info(f"Admin uploading course file from user {msg.chat.id}")
    if not await _ensure_admin(msg, db):
        return
    
    repo = AdminSessionRepo(db)
    cookie_data = await repo.get_cookie()
    if not cookie_data:
        logger.warning(f"Admin session not found for course upload")
        await msg.answer("⚠️ Нужно войти заново")
        return
    
    cookie, _ = cookie_data
    file_id = msg.document.file_id
    file_info = await msg.bot.get_file(file_id)
    file_url = f"https://api.telegram.org/file/bot{msg.bot.token}/{file_info.file_path}"
    
    async with aiohttp.ClientSession() as s:
        api = AdminAPI(s)
        success = await api.upload_course(cookie, file_url, msg.document.file_name)
    
    if success:
        logger.info(f"Course uploaded successfully by user {msg.chat.id}")
        courses = await api.list_courses(cookie)
        await state.set_state(AdminMenu.COURSES)
        await _send(state, msg, "📚 Курсы:", courses_kb(courses))
    else:
        logger.error(f"Course upload failed for user {msg.chat.id}")
        await msg.answer("❌ Ошибка загрузки курса")
    
    await msg.delete()


@router.message(AdminMenu.EDIT)
async def cancel_course_upload(msg: Message, state: FSMContext, db: aiosqlite.Connection):
    """Отмена загрузки курса"""
    logger.info(f"Admin cancelled course upload from user {msg.chat.id}")
    await msg.delete()
    await state.set_state(AdminMenu.COURSES)
    
    repo = AdminSessionRepo(db)
    cookie_data = await repo.get_cookie()
    if cookie_data:
        cookie, _ = cookie_data
        async with aiohttp.ClientSession() as s:
            courses = await AdminAPI(s).list_courses(cookie)
        await _send(state, msg, "📚 Курсы:", courses_kb(courses))
    else:
        await _send(state, msg, "🔧 Админ-панель", admin_main_kb())