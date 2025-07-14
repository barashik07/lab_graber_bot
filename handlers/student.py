import logging
from aiogram import Router, F
from aiogram.types import CallbackQuery, Message
from aiogram.fsm.context import FSMContext
from aiogram.exceptions import TelegramNotFound, TelegramBadRequest, TelegramForbiddenError

from states.reg import Reg
from keyboards.common import nav_kb, confirm_kb, main_menu_kb
from keyboards.common import start_kb
from services.student import StudentRepository, Student

logger = logging.getLogger(__name__)
router = Router()

PROMPTS = {
    Reg.SURNAME: "Введи фамилию",
    Reg.NAME: "Введи имя",
    Reg.PATRONYMIC: "Введи отчество\n(если нет — напиши «-»)",
    Reg.GROUP: "Введи группу",
    Reg.GITHUB: "Введи GitHub",
}
ORDER = [Reg.SURNAME, Reg.NAME, Reg.PATRONYMIC, Reg.GROUP, Reg.GITHUB]
PREV = {ORDER[i + 1]: ORDER[i] for i in range(len(ORDER) - 1)}

BOT_MSG_KEY = "__bot_msg_id"


def normalize_fio(text: str) -> str:
    """Приведение ФИО к нормальному формату"""
    return text.strip().title()


async def _cleanup_prev(state: FSMContext, chat_id: int, bot):
    """Удаление предыдущего сообщения бота"""
    data = await state.get_data()
    msg_id = data.get(BOT_MSG_KEY)
    if msg_id:
        try:
            await bot.delete_message(chat_id, msg_id)
        except (TelegramNotFound, TelegramBadRequest, TelegramForbiddenError):
            pass


async def _send(state: FSMContext, message_or_cb, text: str, kb):
    """Отправка сообщения с обновлением состояния"""
    bot = message_or_cb.bot
    if isinstance(message_or_cb, CallbackQuery):
        chat_id = message_or_cb.message.chat.id
    else:
        chat_id = message_or_cb.chat.id
    
    try:
        await _cleanup_prev(state, chat_id, bot)
        sent = await bot.send_message(chat_id, text, reply_markup=kb)
        await state.update_data({BOT_MSG_KEY: sent.message_id})
    except Exception as e:
        logger.error(f"Error in _send for chat {chat_id}: {e}")
        # Fallback: отправляем сообщение без обновления состояния
        try:
            await bot.send_message(chat_id, text, reply_markup=kb)
        except Exception as fallback_error:
            logger.error(f"Fallback send also failed: {fallback_error}")


@router.callback_query(F.data == "reg_start")
async def reg_start(cb: CallbackQuery, state: FSMContext):
    """Начало регистрации"""
    logger.info(f"User {cb.message.chat.id} started registration")
    await state.clear()
    await state.set_state(Reg.SURNAME)

    await cb.message.delete()
    await _send(state, cb, PROMPTS[Reg.SURNAME], nav_kb(include_back=False))
    await cb.answer()


@router.message(Reg.SURNAME, F.text)
@router.message(Reg.NAME, F.text)
@router.message(Reg.PATRONYMIC, F.text)
@router.message(Reg.GROUP, F.text)
@router.message(Reg.GITHUB, F.text)
async def reg_steps(message: Message, state: FSMContext):
    """Обработка шагов регистрации"""
    await message.delete()

    cur_state = await state.get_state()
    text = message.text.strip()
    logger.info(f"User {message.chat.id} entered {cur_state}: {text}")

    if cur_state in [Reg.SURNAME.state, Reg.NAME.state, Reg.PATRONYMIC.state]:
        text = normalize_fio(text)

    data = await state.get_data()
    data[cur_state] = text
    await state.update_data(data)

    cur = next(s for s in ORDER if s.state == cur_state)
    if cur != Reg.GITHUB:
        nxt = ORDER[ORDER.index(cur) + 1]
        await state.set_state(nxt)
        await _send(state, message, PROMPTS[nxt], nav_kb())
        return

    await state.set_state(Reg.CONFIRM)
    s = data
    summary = (
        f"<b>{s[Reg.SURNAME.state]} {s[Reg.NAME.state]} {s[Reg.PATRONYMIC.state]}</b>\n"
        f"Группа: {s[Reg.GROUP.state]}\nGitHub: {s[Reg.GITHUB.state]}"
    )
    logger.info(f"User {message.chat.id} completed registration form")
    await _send(state, message, summary, confirm_kb())


@router.callback_query(F.data == "reg_back")
async def reg_back(cb: CallbackQuery, state: FSMContext):
    """Возврат к предыдущему шагу регистрации"""
    logger.info(f"User {cb.message.chat.id} going back in registration")
    cur_state = await state.get_state()
    prev = PREV.get(next(s for s in ORDER if s.state == cur_state))
    if not prev:
        await cb.answer()
        return

    await cb.message.delete()
    data = await state.get_data()
    data.pop(BOT_MSG_KEY, None)
    await state.update_data(data)

    await state.set_state(prev)
    await _send(
        state,
        cb,
        PROMPTS[prev],
        nav_kb(include_back=prev != Reg.SURNAME),
    )
    await cb.answer()


@router.callback_query(F.data == "reg_restart")
async def reg_restart(cb: CallbackQuery, state: FSMContext):
    """Перезапуск регистрации"""
    logger.info(f"User {cb.message.chat.id} restarted registration")
    await state.clear()

    await cb.message.delete()
    await _cleanup_prev(state, cb.message.chat.id, cb.bot)
    sent = await cb.message.answer(
        "Начнём заново. Жми «Зарегистрироваться»",
        reply_markup=start_kb(),
    )
    await state.update_data({BOT_MSG_KEY: sent.message_id})
    await cb.answer()


@router.callback_query(F.data == "reg_confirm")
async def reg_confirm(cb: CallbackQuery, state: FSMContext, students_repo: StudentRepository):
    """Подтверждение регистрации"""
    logger.info(f"User {cb.message.chat.id} confirming registration")
    data = await state.get_data()
    await state.clear()

    student = Student(
        chat_id=cb.message.chat.id,
        surname=data[Reg.SURNAME.state],
        name=data[Reg.NAME.state],
        patronymic=None if data[Reg.PATRONYMIC.state] == "-" else data[Reg.PATRONYMIC.state],
        group_code=data[Reg.GROUP.state],
        github=data[Reg.GITHUB.state],
    )
    
    try:
        await students_repo.save(student)
        logger.info(f"User {cb.message.chat.id} successfully registered")

        await cb.message.delete()
        await cb.message.answer("✅ Регистрация завершена\n\n🏠 Главное меню", reply_markup=main_menu_kb())
    except ValueError as e:
        logger.warning(f"Registration failed for user {cb.message.chat.id}: {e}")
        await cb.message.delete()
        await cb.message.answer(
            "❌ Студент с такими же данными уже зарегистрирован в системе.\n\n"
            "Если это ваши данные, но вы используете другой Telegram аккаунт, "
            "пожалуйста, обратитесь к администратору.",
            reply_markup=start_kb()
        )
    except Exception as e:
        logger.error(f"Unexpected error during registration for user {cb.message.chat.id}: {e}")
        await cb.message.delete()
        await cb.message.answer(
            "❌ Произошла ошибка при регистрации. Попробуйте позже.",
            reply_markup=start_kb()
        )
    
    await cb.answer()