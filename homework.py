import os
import requests
import time
import logging
import sys
import telegram

from dotenv import load_dotenv
from http import HTTPStatus

load_dotenv()


PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

RETRY_PERIOD = 600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}


HOMEWORK_VERDICTS = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}


logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
handler = logging.StreamHandler(stream=sys.stdout)
logger.addHandler(handler)
formatter = logging.Formatter(
    '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
handler.setFormatter(formatter)


def check_tokens():
    """Проверка доступности переменных окружения."""
    tokens = (PRACTICUM_TOKEN, TELEGRAM_TOKEN, TELEGRAM_CHAT_ID)
    for token in tokens:
        if token is None:
            logger.critical('Отсутствуют переменные окружения!')
            sys.exit()
    return True


def send_message(bot, message):
    """Отправка текстового сообщения в ТГ чат."""
    try:
        bot.send_message(TELEGRAM_CHAT_ID, message)
    except Exception as error:
        text = (f'Ошибка при отпраке сообщения в ТГ.'
                f'{error}')
        logger.error(text)
    else:
        logger.debug('Сообщение успешно отправлено.')


def get_api_answer(timestamp):
    """Получаем ответ от API Практикума."""
    params = {'from_date': timestamp}
    try:
        response = requests.get(ENDPOINT, headers=HEADERS, params=params)
    except requests.RequestException as error:
        logger.critical(f'Ошибка запроста к API {error}')
    if response.status_code != HTTPStatus.OK:
        raise Exception(
            f'Код ответа {response.status_code}.'
            f'Сервер {ENDPOINT} недоступен'
        )
    return response.json()


def check_response(response):
    """Проверка ответа API на соответствие документации."""
    if not isinstance(response, dict):
        raise TypeError('Ответ не является словарем.')
    if ('homeworks' not in response) and ('current_date' not in response):
        raise KeyError('Ответ не содержит необходимый ключ.')
    homeworks = response.get('homeworks')
    if not isinstance(homeworks, list):
        raise TypeError('Ключ "homeworks" не является списком.')
    return homeworks


def parse_status(homework):
    """Извлекаем информацию о статусе конкретной домашней работы."""
    homework_name = homework.get('homework_name')
    homework_status = homework.get('status')
    if 'homework_name' not in homework:
        raise KeyError('В ответе API нет ключа "homework_name"')
    if homework_status not in HOMEWORK_VERDICTS:
        raise KeyError(f'Неожиданный статус домашней работы -'
                       f'{homework_status}.')
    verdict = HOMEWORK_VERDICTS[homework_status]
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def main():
    """Основная логика работы бота."""
    check_tokens()
    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    timestamp = 0
    previous_message = ''

    while True:
        try:
            response = get_api_answer(timestamp)
            homeworks = check_response(response)
            timestamp = response.get('current_date', timestamp)
            if homeworks:
                message = parse_status(homeworks[0])
                if message != previous_message:
                    send_message(bot, message)
                    previous_message = message
            else:
                logger.debug('Новые статусы отсутствуют.')

        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            logger.error(message)
            if message != previous_message:
                send_message(bot, message)
                previous_message = message

        finally:
            time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    main()
