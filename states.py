from aiogram.fsm.state import State, StatesGroup


class AppointmentState(StatesGroup):
    """Qabulga yozilish bosqichlari"""
    problem = State()           # 1-bosqich: Muammoni tanlash (Inline)
    patient_name = State()      # 2-bosqich: Bemorning F.I.Sh
    phone_number = State()      # 3-bosqich: Telefon raqami
    appointment_date = State()  # 4-bosqich: Qabul sanasini tanlash (Kalendar)
    appointment_time = State()  # 5-bosqich: Qabul vaqtini tanlash


class AnonymousQuestionState(StatesGroup):
    """Shifokorga savol berish bosqichi"""
    waiting_for_question = State()


class QuestionReplyState(StatesGroup):
    """Admin tomonidan foydalanuvchi savoliga javob yozish bosqichi"""
    waiting_for_reply = State()


class AdminBroadcastState(StatesGroup):
    """Barcha foydalanuvchilarga xabar yuborish (Admin)"""
    waiting_for_message = State()


class AdminManageState(StatesGroup):
    """Yangi admin qo'shish va huquqlarni belgilash bosqichlari"""
    waiting_for_admin_user = State()
    selecting_permissions = State()
