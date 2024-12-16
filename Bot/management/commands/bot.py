from time import sleep

import telebot
from LavaAPI import LavaAPI
from django.core.management.base import BaseCommand
from django.utils import timezone
from telebot import types

from Bot.management.commands.config import token, link_faq, link_chat, link_warranty, provider_token, api_key_lava
from Bot.models import PromoCode, UsedPromo, Users, MainCategory, SubCategory, Product, PurchaseHistory

lava_api = LavaAPI(api_key_lava)
bot = telebot.TeleBot(token, parse_mode='html')

bot.delete_webhook()
user_states = {}
user_requested_amounts = {}  # словарь для отслеживания ожидающих платежей {user_id: (order_id, amount)}


def generate_main_menu_markup():
    markup = types.InlineKeyboardMarkup(row_width=2)
    items = [
        types.InlineKeyboardButton("Магазин", callback_data='shop'),
        types.InlineKeyboardButton("Кабинет", callback_data='cabinet'),
        types.InlineKeyboardButton("FAQ", callback_data='faq'),
        types.InlineKeyboardButton("Гарантии", callback_data='warranty'),
        types.InlineKeyboardButton("Отзывы", callback_data='reviews'),
        types.InlineKeyboardButton("Поддержка", callback_data='support')
    ]
    markup.add(*items)
    return markup


def generate_cabinet_menu_markup():
    markup = types.InlineKeyboardMarkup(row_width=1)
    items = [
        types.InlineKeyboardButton("Пополнить баланс", callback_data='recharge'),
        types.InlineKeyboardButton("Использовать промокод", callback_data='use_promo'),
        types.InlineKeyboardButton("История покупок", callback_data='purchase_history'),
        types.InlineKeyboardButton("Рассылки", callback_data='mailing'),
        types.InlineKeyboardButton("Назад", callback_data='back_to_menu')
    ]
    markup.add(*items)
    return markup


def generate_shop_menu_markup():
    markup = types.InlineKeyboardMarkup(row_width=1)
    categories = MainCategory.objects.all()
    for category in categories:
        markup.add(types.InlineKeyboardButton(category.name, callback_data=f'category_{category.id}'))
    markup.add(types.InlineKeyboardButton("Назад", callback_data='back_to_menu'))
    return markup


def generate_subcategories_menu_markup(main_category_id):
    markup = types.InlineKeyboardMarkup(row_width=1)
    subcategories = SubCategory.objects.filter(main_category__id=main_category_id)
    for subcategory in subcategories:
        markup.add(types.InlineKeyboardButton(subcategory.name, callback_data=f'subcategory_{subcategory.id}'))
    markup.add(types.InlineKeyboardButton("Назад", callback_data='back_to_shop_menu'))
    return markup


def generate_product_detail_markup(product_id):
    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(types.InlineKeyboardButton("Купить", callback_data=f'buy_{product_id}'))
    markup.add(types.InlineKeyboardButton("Назад", callback_data=f'product_back_{product_id}'))
    return markup


@bot.message_handler(commands=['start'])
def send_welcome(message):
    chat_id = message.chat.id

    # Отправляем картинку
    photo = open('images/your_image_path.jpg', 'rb')

    bot.send_photo(chat_id, photo, caption="Главное меню", reply_markup=generate_main_menu_markup())


def generate_payment_menu_markup():
    markup = types.InlineKeyboardMarkup(row_width=1)
    items = [
        types.InlineKeyboardButton("Систему1", callback_data='pay1'),
        types.InlineKeyboardButton("Lava", callback_data='pay2'),
        types.InlineKeyboardButton("Назад", callback_data='back_to_menu')
    ]
    markup.add(*items)
    return markup


def send_telegram_invoice(chat_id, amount):
    title = "Пополнение баланса"
    description = f"Пополнение баланса на {amount} рублей"
    prices = [types.LabeledPrice(label='Пополнение', amount=amount * 100)]
    bot.send_invoice(chat_id=chat_id,
                     title=title,
                     description=description,
                     invoice_payload="recharge_balance",
                     provider_token=provider_token,
                     currency="RUB",
                     prices=prices)


def send_lava_invoice(chat_id, amount):
    description = f"Оплата товара на сумму {amount} RUB"
    payment = lava_api.create_invoice(amount, description)
    markup = types.InlineKeyboardMarkup(row_width=1)
    buttons = [
        types.InlineKeyboardButton("Оплатить", url=f"{payment.url}"),
        # types.InlineKeyboardButton("Проверить оплату", callback_data='check_payment'),
        types.InlineKeyboardButton("Назад", callback_data='back_to_menu')
    ]
    markup.add(*buttons)
    new_photo = open('images/payment_image_path.jpg', 'rb')
    bot.send_photo(chat_id, new_photo,
                   caption=f"Счёт на {amount} рублей создан! Нажмите на кнопку ниже, чтобы оплатить.",
                   reply_markup=markup)
    ten_min = 10 * 60
    i = 0
    while True:
        if i >= ten_min:
            # Отправляем картинку
            photo = open('images/your_image_path.jpg', 'rb')

            bot.send_photo(chat_id, photo, caption="Время оплаты вышло! Попробуйте снова позже!",
                           reply_markup=generate_main_menu_markup())

            break
        else:
            if payment.is_paid():
                # Например:
                user = Users.objects.get(user_id=chat_id)
                user.balance += amount
                user.save()

                bot.send_message(chat_id, f"Оплата прошла успешно! Ваш баланс пополнен на {amount} рублей.")
                print("Payment is paid!")
                break
            i += 5
            sleep(5)


@bot.message_handler(func=lambda message: True)
def handle_all_messages(message):
    chat_id = message.chat.id
    user_state = user_states.get(chat_id)

    if user_state == 'AWAITING_RECHARGE_AMOUNT':
        try:
            amount = int(message.text)
            if 100 <= amount <= 10000:
                # Сохранение суммы в словаре
                user_requested_amounts[chat_id] = amount

                user_states[chat_id] = 'AWAITING_PAYMENT_CONFIRMATION'
                new_photo = open('images/payment_image_path.jpg', 'rb')
                bot.send_photo(chat_id, new_photo,
                               caption=f"Счёт на {amount} рублей создан! Жми по кнопке ниже, чтобы оплатить.",
                               reply_markup=generate_payment_menu_markup())
            else:
                bot.send_message(chat_id, "Сумма должна быть от 100₽ и до 10000₽. Попробуйте ещё раз.")
        except ValueError:
            bot.send_message(chat_id, "Пожалуйста, введите корректную сумму.")


@bot.callback_query_handler(func=lambda call: call.data in ['pay1', 'pay2'])
def handle_payment_callbacks(call):
    chat_id = call.message.chat.id
    amount = user_requested_amounts[chat_id]  # Словарь, где вы сохраняете сумму, которую пользователь хочет оплатить

    if call.data == 'pay1':
        send_telegram_invoice(chat_id, amount)
        bot.answer_callback_query(call.id, "Вы выбрали оплату через Систему1. Интеграция с системой...")
    elif call.data == 'pay2':
        send_lava_invoice(chat_id, amount)
        bot.answer_callback_query(call.id, "Вы выбрали оплату через Систему2. Интеграция с системой...")


@bot.message_handler(content_types=['successful_payment'])
def handle_successful_payment(message):
    chat_id = message.chat.id
    try:
        amount_received = message.successful_payment.total_amount / 100
        # Телеграм возвращает сумму в копейках (или центах), поэтому делите на 100

        # На этом этапе вы можете обновить баланс пользователя в вашей базе данных
        # Например:
        user = Users.objects.get(user_id=chat_id)
        user.balance += amount_received
        user.save()

        bot.send_message(chat_id, f"Оплата прошла успешно! Ваш баланс пополнен на {amount_received} рублей.")
    except Exception as e:
        bot.send_message(chat_id, "Произошла ошибка при обработке платежа. Пожалуйста, попробуйте снова позже.")
        print(f"Error occurred: {e}")  # Для вашего лога


@bot.pre_checkout_query_handler(func=lambda query: True)
def handle_pre_checkout_query(pre_checkout_query):
    bot.answer_pre_checkout_query(pre_checkout_query.id, ok=True)


@bot.callback_query_handler(func=lambda call: "accept_" in call.data)
def handle_accept(call):
    user_id, product_id = map(int, call.data.split('_')[1:])
    user = Users.objects.get(user_id=user_id)
    product = Product.objects.get(id=product_id)

    msg = bot.send_message(call.from_user.id, "Введите текст для отправки пользователю:")
    bot.register_next_step_handler(msg, send_text_to_user, user, product)


@bot.callback_query_handler(func=lambda call: "cancel_" in call.data)
def handle_cancel(call):
    user_id, product_id = map(int, call.data.split('_')[1:])
    # user = Users.objects.get(user_id=user_id)

    bot.send_message(user_id, "Ваш заказ был отменен.")
    bot.answer_callback_query(call.id, "Заказ отменен.")


def send_text_to_user(message, user, product):
    bot.send_message(user.user_id, message.text)
    user.balance -= product.price  # Здесь нужна некая логика конвертации, если balance и price имеют разные типы данных
    user.save()

    # Запись в историю покупок
    PurchaseHistory.objects.create(user=user, product=product.name, price=product.price)


@bot.callback_query_handler(func=lambda call: call.data.startswith('buy_'))
def handle_buy(call):
    product_id = int(call.data.split('_')[1])
    product = Product.objects.get(id=product_id)

    admin_id = 12345678  # Замените на ваш Telegram ID
    admin_name = '@NAME'  # Замените на ваш Telegram User Name

    markup = telebot.types.InlineKeyboardMarkup()
    accept_button = telebot.types.InlineKeyboardButton(text="Предоставить товар",
                                                       callback_data=f"accept_{call.from_user.id}_{product_id}")
    cancel_button = telebot.types.InlineKeyboardButton(text="Отменить",
                                                       callback_data=f"cancel_{call.from_user.id}_{product_id}")
    markup.add(accept_button, cancel_button)

    bot.send_message(admin_id,
                     f"Заказ от @{call.from_user.username} "
                     f"(ID: {call.from_user.id})\nТовар: {product.name}\nЦена: {product.price}",
                     reply_markup=markup)
    bot.answer_callback_query(call.id, f"Заказ принят. Для уточнения с вами свяжется администратор {admin_name}!\n"
                                       f"В случае задержки свяжитесь с администратором сами!")


def process_promocode(message):
    chat_id = message.chat.id
    user_code = message.text

    try:
        proms = PromoCode.objects.get(code=user_code)
        user = Users.objects.get(user_id=chat_id)

        if UsedPromo.objects.filter(user=user, promo=proms).exists():
            bot.send_message(chat_id, "Вы уже использовали этот промокод.")
            return

        if proms.expiration_date and proms.expiration_date < timezone.now():
            bot.send_message(chat_id, "Промокод истек.")
            return

        UsedPromo.objects.create(user=user, promo=proms)
        bot.send_message(chat_id, f"Промокод успешно активирован! Ваша скидка: {proms.discount * 100}%")
    except PromoCode.DoesNotExist:
        bot.send_message(chat_id, "Неверный промокод.")
    except Exception as e:
        print(e)
        bot.send_message(chat_id, "Произошла ошибка. Попробуйте еще раз.")


@bot.callback_query_handler(func=lambda call: call.data == 'use_promo')
def ask_promocode(call):
    chat_id = call.message.chat.id
    bot.send_message(chat_id, "Введите промокод:")
    bot.register_next_step_handler(call.message, process_promocode)


@bot.callback_query_handler(func=lambda call: True)
def callback_inline(call):
    try:
        if call.message:
            chat_id = call.message.chat.id
            message_id = call.message.message_id

            if call.data == 'faq':
                # Редактирование фотографии и подписи
                new_photo = open('images/faq_image_path.jpg', 'rb')
                new_markup = types.InlineKeyboardMarkup()
                new_markup.add(types.InlineKeyboardButton("Назад", callback_data='back_to_menu'))
                bot.edit_message_media(media=types.InputMedia(type='photo', media=new_photo),
                                       chat_id=chat_id,
                                       message_id=message_id)
                bot.edit_message_caption(caption=f"Ответы на <a href='{link_faq}'>Часто задаваемые вопросы</a>",
                                         chat_id=chat_id,
                                         message_id=message_id,
                                         reply_markup=new_markup,
                                         # parse_mode='html'
                                         )
            elif call.data == 'back_to_menu':
                # Возвращение к главному меню
                back_photo = open('images/your_image_path.jpg', 'rb')
                bot.edit_message_media(media=types.InputMedia(type='photo', media=back_photo),
                                       chat_id=chat_id,
                                       message_id=message_id)
                bot.edit_message_caption(caption="Главное меню",
                                         chat_id=chat_id,
                                         message_id=message_id,
                                         reply_markup=generate_main_menu_markup(),
                                         # parse_mode='html'
                                         )

            elif call.data == 'shop':
                new_photo = open('images/shop_image_path.jpg', 'rb')
                bot.edit_message_media(media=types.InputMedia(type='photo', media=new_photo),
                                       chat_id=chat_id,
                                       message_id=message_id)
                bot.edit_message_caption(caption="Выбери категорию",
                                         chat_id=chat_id,
                                         message_id=message_id,
                                         reply_markup=generate_shop_menu_markup())
            elif call.data.startswith('category_'):
                category_id = int(call.data.split('_')[1])
                new_photo = open('images/subcategory_image_path.jpg', 'rb')
                bot.edit_message_media(media=types.InputMedia(type='photo', media=new_photo),
                                       chat_id=chat_id,
                                       message_id=message_id)
                bot.edit_message_caption(caption="Выбери подкатегорию",
                                         chat_id=chat_id,
                                         message_id=message_id,
                                         reply_markup=generate_subcategories_menu_markup(category_id))
            elif call.data == 'cabinet':
                # Получаем или создаем пользователя в базе данных
                user, created = Users.objects.get_or_create(user_id=str(chat_id))

                cabinet_info = f"""Ваш ID профиля: {user.user_id}
            Количество пополнений: {user.count_deposits}
            Количество заказов: {user.count_orders}

            Баланс: {user.balance}₽"""

                # Редактируем сообщение для отображения информации о кабинете
                new_photo = open('images/cabinet_image_path.jpg', 'rb')
                bot.edit_message_media(media=types.InputMedia(type='photo', media=new_photo),
                                       chat_id=chat_id,
                                       message_id=message_id)
                bot.edit_message_caption(caption=cabinet_info,
                                         chat_id=chat_id,
                                         message_id=message_id,
                                         reply_markup=generate_cabinet_menu_markup())

            elif call.data == 'warranty':
                # Редактирование фотографии и подписи
                new_photo = open('images/warranty_image_path.jpg', 'rb')
                new_markup = types.InlineKeyboardMarkup()
                new_markup.add(types.InlineKeyboardButton("Назад", callback_data='back_to_menu'))
                bot.edit_message_media(media=types.InputMedia(type='photo', media=new_photo),
                                       chat_id=chat_id,
                                       message_id=message_id)
                msg = (f"Максимально надёжно, без банов и скама\n"
                       f"<a href='{link_warranty}'>Ознакомиться с гарантиями</a>")
                bot.edit_message_caption(caption=msg,
                                         chat_id=chat_id,
                                         message_id=message_id,
                                         reply_markup=new_markup,
                                         # parse_mode='html'
                                         )
            elif call.data == 'reviews':
                # Редактирование фотографии и подписи
                new_photo = open('images/reviews_image_path.jpg', 'rb')
                new_markup = types.InlineKeyboardMarkup()
                new_markup.add(types.InlineKeyboardButton("Назад", callback_data='back_to_menu'))
                bot.edit_message_media(media=types.InputMedia(type='photo', media=new_photo),
                                       chat_id=chat_id,
                                       message_id=message_id)
                msg = (f"Отдельный чат с отзывами, писать в чат могут те, кто оформил заказ.\n"
                       f"<a href='{link_chat}'>Чатик с отзывами</a>")
                bot.edit_message_caption(caption=msg,
                                         chat_id=chat_id,
                                         message_id=message_id,
                                         reply_markup=new_markup,
                                         # parse_mode='html'
                                         )
            elif call.data == 'support':
                # Редактирование фотографии и подписи
                new_photo = open('images/support_image_path.jpg', 'rb')
                new_markup = types.InlineKeyboardMarkup(row_width=1)
                new_markup.add(
                    types.InlineKeyboardButton("Создать тикет", callback_data='back_to_menu'),
                    types.InlineKeyboardButton("В главное меню", callback_data='back_to_menu'),
                )
                bot.edit_message_media(media=types.InputMedia(type='photo', media=new_photo),
                                       chat_id=chat_id,
                                       message_id=message_id)
                msg = (f"Тут ты можешь задать свой вопрос в поддержку, "
                       f"но перед этим ознакомься с нашим <a href='{link_faq}'>FAQ</a>\n\n"
                       f"Время работы поддержки: 9:00-22:00 МСК\n"
                       f"Отвечаем в порядке очереди\n"
                       )
                bot.edit_message_caption(caption=msg,
                                         chat_id=chat_id,
                                         message_id=message_id,
                                         reply_markup=new_markup,
                                         # parse_mode='html'
                                         )
            elif call.data == 'recharge':
                user_states[chat_id] = 'AWAITING_RECHARGE_AMOUNT'
                new_photo = open('images/recharge_image_path.jpg', 'rb')
                bot.edit_message_media(media=types.InputMedia(type='photo', media=new_photo),
                                       chat_id=chat_id,
                                       message_id=message_id)
                markup = types.InlineKeyboardMarkup(row_width=1)
                markup.add(types.InlineKeyboardButton("В главное меню", callback_data='back_to_shop_menu'))
                bot.edit_message_caption(caption="Введи сумму для пополнения от 100₽ и до 10000₽",
                                         chat_id=chat_id,
                                         message_id=message_id,
                                         reply_markup=markup)
            elif call.data.startswith('product_'):
                # Редактируем сообщение для отображения информации о кабинете
                new_photo = open('images/towar_image.jpg', 'rb')
                bot.edit_message_media(media=types.InputMedia(type='photo', media=new_photo),
                                       chat_id=chat_id,
                                       message_id=message_id)
                product_id = int(call.data.split('_')[1])
                product = Product.objects.get(id=product_id)
                user = Users.objects.get(user_id=chat_id)

                # Проверка на наличие активного промокода у пользователя
                active_promo = UsedPromo.objects.filter(user=user, used=False).first()
                if active_promo:
                    discount = active_promo.promo.discount
                    discounted_price = product.price * (1 - discount)
                    product_info = f"Товар: {product.name}\nЦена со скидкой: {discounted_price}₽\n\nОписание: {product.description}"
                else:
                    product_info = f"Товар: {product.name}\nЦена: {product.price}₽\n\nОписание: {product.description}"

                markup = generate_product_detail_markup(product_id)
                bot.edit_message_caption(chat_id=call.message.chat.id, message_id=call.message.message_id,
                                         caption=product_info, reply_markup=markup, parse_mode='HTML')
    except Exception as e:
        print(repr(e))


class Command(BaseCommand):
    help = 'бот'

    def handle(self, *args, **options):
        bot.infinity_polling()
