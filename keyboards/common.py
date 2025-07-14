from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from typing import Sequence
from services.api import CourseDTO


def start_kb() -> InlineKeyboardMarkup:
    """Клавиатура для начала регистрации"""
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="📝 Зарегистрироваться", callback_data="reg_start")]]
    )


def nav_kb(include_back: bool = True) -> InlineKeyboardMarkup:
    """Навигационная клавиатура"""
    buttons = []
    if include_back:
        buttons.append(InlineKeyboardButton(text="⬅️ Назад", callback_data="reg_back"))
    buttons.append(InlineKeyboardButton(text="Сначала", callback_data="reg_restart"))
    return InlineKeyboardMarkup(inline_keyboard=[buttons])


def confirm_kb() -> InlineKeyboardMarkup:
    """Клавиатура подтверждения"""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="✅ Подтвердить", callback_data="reg_confirm")],
            [InlineKeyboardButton(text="🔄 Сначала", callback_data="reg_restart")],
        ]
    )


def main_menu_kb() -> InlineKeyboardMarkup:
    """Главное меню"""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📚 Выбрать курс", callback_data="menu_choose_course")],
            [InlineKeyboardButton(text="ℹ️ Информация", callback_data="menu_info")],
        ]
    )


def back_menu_kb() -> InlineKeyboardMarkup:
    """Клавиатура возврата в меню"""
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="⬅️ Назад", callback_data="back_menu")]]
    )

def courses_kb(
    courses: Sequence[CourseDTO],
    add_other: bool = False,
) -> InlineKeyboardMarkup:
    """Клавиатура списка курсов"""
    rows = [
        [InlineKeyboardButton(text=f"{c.name} ({c.semester})", callback_data=f"course_{c.id}")]
        for c in courses
    ]

    nav = []
    if add_other:
        nav.append(InlineKeyboardButton(text="📚 Другие курсы", callback_data="courses_other"))
    nav.append(InlineKeyboardButton(text="⬅️ Назад", callback_data="back_menu"))
    rows.append(nav)

    return InlineKeyboardMarkup(inline_keyboard=rows)

def labs_kb(labs: Sequence[str], course_id: str) -> InlineKeyboardMarkup:
    """Клавиатура списка лабораторных"""
    rows = [
        [InlineKeyboardButton(text=lab, callback_data=f"lab_{course_id}_{lab}")]
        for lab in labs
    ]
    rows.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="courses_back")])
    return InlineKeyboardMarkup(inline_keyboard=rows)

def home_kb() -> InlineKeyboardMarkup:
    """Клавиатура возврата домой"""
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="🏠 Главное меню", callback_data="back_menu")]]
    )