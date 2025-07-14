from aiogram.fsm.state import StatesGroup, State


class Reg(StatesGroup):
    """Состояния процесса регистрации"""
    SURNAME = State()
    NAME = State()
    PATRONYMIC = State()
    GROUP = State()
    GITHUB = State()
    CONFIRM = State()