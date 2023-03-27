import os
import time
import telegram
import logging
import requests


from dotenv import load_dotenv
from http import HTTPStatus

load_dotenv()


PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

RETRY_PERIOD = 600
TEST_TIME = 2629743
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}


HOMEWORK_VERDICTS = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}


logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s, %(fucName)s, %(levelname)s, %(name)s, %(message)s'
)

logger = logging.getLogger(__name__)
log_handler = logging.StreamHandler()
logger.addHandler(log_handler)


def check_tokens():
    """Проверка доступности переменных окружения."""
    if all([PRACTICUM_TOKEN, TELEGRAM_TOKEN, TELEGRAM_CHAT_ID]):
        return True


def send_message(bot: telegram.Bot, message: str) -> None:
    """Отправка сообщений в Telegram чат."""
    logger.info('Отправка сообщения')
    try:
        bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=message)
    except Exception:
        err_text = 'Ошибка отправки сообщения'
        logger.error(err_text)
    logger.debug('Сообщение отправлено')


def get_api_answer(timestamp: int) -> dict:
    """Создание зпроса к эндпоинту API-сервиса."""
    if not timestamp == 0:
        timestamp = int(time.time() - TEST_TIME)
    params = {'from_date': timestamp}
    try:
        response = requests.get(
            ENDPOINT,
            headers=HEADERS,
            params=params,
        )
    except Exception:
        err_text = 'Ошибка при запросе к ENDPOINT'
        logger.error(err_text)
    if response.status_code != HTTPStatus.OK:
        status_code = response.status_code
        err_text = f'Ошибка {status_code}'
        raise Exception(err_text)
    try:
        return response.json()
    except Exception:
        err_text = 'Ошибка изменения типа данных'
        logger.error(err_text)


def check_response(response: dict) -> dict:
    """Проверка ответа API на соответствие документации."""
    if (
        'current_date' in response
        and 'homeworks' in response
        and isinstance(response['homeworks'], list)
    ):
        return response
    else:
        err_text = 'Ошибка соответствия'
        logger.error(err_text)
        raise TypeError(err_text)


def parse_status(homework):
    """Извлечение статуса конкретной домашней работы."""
    if 'homework_name' in homework:
        homework_name = homework['homework_name']
        status = homework['status']
        if status not in HOMEWORK_VERDICTS:
            err_text = 'Неизвестный статус домашней работы'
            raise Exception(err_text)
        else:
            verdict = HOMEWORK_VERDICTS.get(status)
            return (
                f'Изменился статус проверки '
                f'работы "{homework_name}". {verdict}'
            )
    err_text = 'Хрень!!!!'
    logger.error(err_text)
    raise KeyError(err_text)


def main():
    """Основная логика работы бота."""
    if not check_tokens():
        err_text = 'Отсутствует необходимая переменная'
        logger.critical(err_text)
        raise Exception(err_text)

    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    timestamp = int(0)
    some_status = None
    some_error = None

    while True:
        try:
            response = get_api_answer(timestamp)
        except Exception as incorrect_resp:
            if str(incorrect_resp) != some_error:
                some_error = str(incorrect_resp)
                send_message(bot, incorrect_resp)
            logger.error(incorrect_resp)
            time.sleep(RETRY_PERIOD)
            continue
        try:
            homeworks = check_response(response)
            print(homeworks)
            hw_status = homeworks['homeworks'][0]['status']
            if hw_status == some_status:
                logger.debug('Обновления статуса нет')
            else:
                some_status = hw_status
                message = parse_status(homeworks['homeworks'][0])
                send_message(bot, message)
            time.sleep(RETRY_PERIOD)

        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            if some_error != str(error):
                some_error = str(error)
                send_message(bot, message)
            logger.error(message)
        time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    main()
