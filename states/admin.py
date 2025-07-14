from aiogram.fsm.state import StatesGroup, State


class AdminLogin(StatesGroup):
    """Состояния входа в админ-панель"""
    LOGIN = State()
    PASSWORD = State()


class AdminMenu(StatesGroup):
    """Состояния админ-панели"""
    MAIN = State()
    GROUPS = State()
    STUDENTS = State()
    STUDENT_INFO = State()
    COURSES = State()
    COURSE_INFO = State()
    EDIT = State()
    CONFIRM = State()