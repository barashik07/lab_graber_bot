from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from typing import Sequence

def login_back_kb() -> InlineKeyboardMarkup:
    """Клавиатура отмены входа"""
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="❌ Отмена", callback_data="admin_cancel")]]
    )


def admin_main_kb() -> InlineKeyboardMarkup:
    """Главное меню админ-панели"""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📚 Курсы", callback_data="admin_courses")],
            [InlineKeyboardButton(text="👥 Студенты", callback_data="admin_groups")],
            [InlineKeyboardButton(text="🚪 Выход", callback_data="admin_logout")],
        ]
    )


def groups_kb(groups: Sequence[str]) -> InlineKeyboardMarkup:
    """Клавиатура списка групп"""
    if not groups:
        rows = [[InlineKeyboardButton(text="📭 Пусто", callback_data="empty_list")]]
    else:
        rows = [[InlineKeyboardButton(text=g, callback_data=f"adm_group_{g}")] for g in groups]
    
    rows.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="admin_back")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def students_kb(students: Sequence[str], group: str) -> InlineKeyboardMarkup:
    """Клавиатура списка студентов группы"""
    if not students:
        rows = [[InlineKeyboardButton(text="📭 Пусто", callback_data="empty_list")]]
    else:
        rows = [
            [InlineKeyboardButton(text=fio, callback_data=f"adm_student_{group}_{idx}")]
            for idx, fio in enumerate(students)
        ]
    
    rows.append(
        [
            InlineKeyboardButton(text="🗑️ Удалить группу", callback_data=f"adm_del_group_{group}"),
            InlineKeyboardButton(text="⬅️ Назад", callback_data="admin_back_groups"),
        ]
    )
    return InlineKeyboardMarkup(inline_keyboard=rows)


def student_info_kb(group: str, idx: int) -> InlineKeyboardMarkup:
    """Клавиатура информации о студенте"""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🗑️ Удалить студента", callback_data=f"adm_del_st_{group}_{idx}")],
            [InlineKeyboardButton(text="⬅️ Назад", callback_data=f"adm_back_students_{group}")],
        ]
    )


def confirm_kb(yes_cb: str, no_cb: str = "admin_cancel") -> InlineKeyboardMarkup:
    """Клавиатура подтверждения"""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="✅ Подтвердить", callback_data=yes_cb)],
            [InlineKeyboardButton(text="❌ Отмена", callback_data=no_cb)],
        ]
    )

def courses_kb(courses: list[dict]) -> InlineKeyboardMarkup:
    """Клавиатура списка курсов"""
    if not courses:
        rows = [[InlineKeyboardButton(text="📭 Пусто", callback_data="empty_list")]]
    else:
        rows = [
            [InlineKeyboardButton(
                text=f"{c['name']} ({c['semester']})", 
                callback_data=f"adm_course_{c['id']}"
            )] 
            for c in courses
        ]
    
    rows.append(
        [
            InlineKeyboardButton(text="➕ Добавить", callback_data="adm_course_add"),
            InlineKeyboardButton(text="⬅️ Назад", callback_data="admin_back"),
        ]
    )
    return InlineKeyboardMarkup(inline_keyboard=rows)


def course_actions_kb(cid: str) -> InlineKeyboardMarkup:
    """Клавиатура действий с курсом"""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🗑️ Удалить", callback_data=f"adm_course_del_{cid}")],
            [InlineKeyboardButton(text="⬅️ Назад", callback_data="admin_back_courses")],
        ]
    )