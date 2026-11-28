from aiogram.fsm.state import State, StatesGroup


class AppointmentState(StatesGroup):
    """Qabulga yozilish bosqichlari"""
    problem = State()           # 1-bosqich: Muammoni tanlash (Inline)
    patient_name = State()      # 2-bosqich: Bemorning F.I.Sh
    phone_number = State()      # 3-bosqich: Telefon raqami
    appointment_date = State()  # 4-bosqich: Qabul sanasini tanlash (Kalendar)
    appointment_time = State()  # 5-bosqich: Qabul vaqtini tanlash


class AdminBroadcastState(StatesGroup):
    """Barcha foydalanuvchilarga xabar yuborish (Admin)"""
    waiting_for_message = State()


class AdminManageState(StatesGroup):
    """Yangi admin qo'shish va huquqlarni belgilash bosqichlari"""
    waiting_for_admin_user = State()
    selecting_permissions = State()


class PaymentReceiptState(StatesGroup):
    """Mijozdan to'lov cheki rasmini kutish holati"""
    waiting_for_receipt = State()


class DirectPaymentState(StatesGroup):
    """Instagram Direct / telefon orqali yozilgan bemordan telefon raqam so'rash holati"""
    waiting_for_phone = State()


class AdminCardState(StatesGroup):
    """Admin paneldan to'lov kartasini o'zgartirish holatlari"""
    waiting_for_card_number = State()
    waiting_for_card_holder = State()
