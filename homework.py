import os
import time
import telegram
import logging
import requests
import fails
import sys


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
    'rejected': 'Работа проверена: у ревьюера есть замечания.',
}


logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s, %(funcName)s, %(levelname)s, %(name)s, %(message)s',
)

logger = logging.getLogger(__name__)
log_handler = logging.StreamHandler()
logger.addHandler(log_handler)


def check_tokens():
    """Проверка доступности переменных окружения."""
    return all([PRACTICUM_TOKEN, TELEGRAM_TOKEN, TELEGRAM_CHAT_ID])


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
    params = {'from_date': timestamp}
    try:
        response = requests.get(
            ENDPOINT,
            headers=HEADERS,
            params=params,
        )
    except Exception:
        err_text = 'Ошибка при запросе к ENDPOINT'
        raise Exception(err_text)
    if response.status_code != HTTPStatus.OK:
        status_code = response.status_code
        err_text = f'Ошибка {status_code}'
        raise fails.StatusCodeFail(err_text)
    return response.json()


def check_response(response: dict) -> dict:
    """Проверка ответа API на соответствие документации."""
    if 'current_date' not in response:
        err_text = 'В ответе API нет домашки на текущую дату'
        raise TypeError(err_text)
    if 'homeworks' not in response:
        err_text = 'В ответе API нет домашек'
        raise TypeError(err_text)
    if not isinstance(response['homeworks'], list):
        err_text = 'В ответе API нет словаря с домашками'
        raise TypeError(err_text)
    return response


def parse_status(homework):
    """Извлечение статуса конкретной домашней работы."""
    if 'homework_name' not in homework:
        err_text = 'Такой домашки нет'
        raise KeyError(err_text)
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


def main():
    """Основная логика работы бота."""
    if not check_tokens():
        err_text = 'Отсутствует необходимая переменная'
        logger.critical(err_text)
        sys.exit(1)

    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    timestamp = int(0)
    some_status = None

    while True:
        try:
            response = get_api_answer(timestamp)
            homeworks = check_response(response)
            if not response['homeworks']:
                continue
            hw_status = homeworks['homeworks'][0]['status']
            if hw_status == some_status:
                logger.debug('Обновления статуса нет')
            else:
                some_status = hw_status
                message = parse_status(homeworks['homeworks'][0])
                send_message(bot, message)

        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            logger.error(message)
        finally:
            time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    main()
