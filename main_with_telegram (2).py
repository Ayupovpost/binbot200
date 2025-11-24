import requests
import time
import os
from dotenv import load_dotenv
from datetime import datetime

# Загрузка настроек из .env
load_dotenv()

GROWTH_THRESHOLD = float(os.getenv('GROWTH_THRESHOLD', 250))
CHECK_INTERVAL = int(os.getenv('CHECK_INTERVAL', 60))
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

# URL для получения тикеров фьючерсов USD-M
BINANCE_FUTURES_API = "https://fapi.binance.com/fapi/v1/ticker/24hr"
BINANCE_EXCHANGE_INFO = "https://fapi.binance.com/fapi/v1/exchangeInfo"

def send_telegram_message(message):
    """Отправляет сообщение в Telegram"""
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("⚠️ Telegram не настроен. Пропускаю отправку сообщения.")
        return False
    
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        data = {
            "chat_id": TELEGRAM_CHAT_ID,
            "text": message,
            "parse_mode": "HTML"
        }
        response = requests.post(url, data=data, timeout=10)
        response.raise_for_status()
        print("✅ Сообщение отправлено в Telegram")
        return True
    except Exception as e:
        print(f"❌ Ошибка при отправке в Telegram: {e}")
        return False

def get_trading_symbols():
    """Возвращает множество символов, которые имеют статус TRADING"""
    try:
        response = requests.get(BINANCE_EXCHANGE_INFO)
        response.raise_for_status()
        data = response.json()
        
        trading_symbols = set()
        for symbol_info in data['symbols']:
            if symbol_info['status'] == 'TRADING':
                trading_symbols.add(symbol_info['symbol'])
        return trading_symbols
    except Exception as e:
        print(f"Ошибка при получении информации об обмене: {e}")
        return set()

def get_top_gainers():
    try:
        # Сначала получаем список торгуемых пар
        trading_symbols = get_trading_symbols()
        
        response = requests.get(BINANCE_FUTURES_API)
        response.raise_for_status()
        data = response.json()
        
        gainers = []
        for ticker in data:
            symbol = ticker['symbol']
            
            # Фильтруем только пары к USDT
            if not symbol.endswith('USDT'):
                continue
            
            # Проверяем, торгуется ли пара
            if trading_symbols and symbol not in trading_symbols:
                continue
                
            try:
                price_change_percent = float(ticker['priceChangePercent'])
            except (ValueError, KeyError):
                continue
                
            if price_change_percent > GROWTH_THRESHOLD:
                gainers.append({
                    'symbol': symbol,
                    'price_change': price_change_percent,
                    'last_price': ticker['lastPrice'],
                    'volume': ticker.get('volume', 'N/A')
                })
        
        return gainers
    except Exception as e:
        print(f"Ошибка при получении данных: {e}")
        return []

def format_telegram_message(gainers):
    """Форматирует сообщение для Telegram"""
    message = f"🚀 <b>НАЙДЕНЫ МОНЕТЫ С РОСТОМ &gt; {GROWTH_THRESHOLD}%!</b>\n\n"
    
    for coin in gainers:
        message += f"💰 <b>{coin['symbol']}</b>\n"
        message += f"📈 Рост: <b>+{coin['price_change']:.2f}%</b>\n"
        message += f"💵 Цена: {coin['last_price']}\n"
        message += f"📊 Объем: {coin['volume']}\n"
        message += f"🔗 <a href='https://www.binance.com/ru/futures/{coin['symbol']}'>Открыть на Binance</a>\n"
        message += "─────────────────\n"
    
    message += f"\n⏰ Время: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
    return message

def main():
    print(f"🤖 Бот запущен. Мониторинг фьючерсов с ростом > {GROWTH_THRESHOLD}%...")
    print(f"⏱️ Интервал проверки: {CHECK_INTERVAL} сек.")
    
    # Проверка настройки Telegram
    if TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID:
        print("✅ Telegram настроен. Уведомления будут отправляться.")
        # Отправляем тестовое сообщение при запуске
        send_telegram_message("🤖 <b>Бот запущен!</b>\n\nМониторинг Binance активирован.")
    else:
        print("⚠️ Telegram не настроен. Уведомления будут только в консоли.")
        print("💡 Добавьте TELEGRAM_BOT_TOKEN и TELEGRAM_CHAT_ID в файл .env")
    
    print("-" * 50)
    
    # Храним уже отправленные уведомления, чтобы не спамить
    seen_alerts = {}
    ALERT_COOLDOWN = 3600  # 1 час в секундах

    while True:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print(f"\n[{timestamp}] 🔍 Проверка рынка...")
        
        gainers = get_top_gainers()
        
        if gainers:
            print(f"\n!!! НАЙДЕНЫ МОНЕТЫ С РОСТОМ > {GROWTH_THRESHOLD}% !!!")
            
            # Фильтруем новые алерты (не отправленные недавно)
            new_gainers = []
            current_time = time.time()
            
            for coin in gainers:
                symbol = coin['symbol']
                last_alert_time = seen_alerts.get(symbol, 0)
                
                # Отправляем только если прошло достаточно времени с последнего алерта
                if current_time - last_alert_time > ALERT_COOLDOWN:
                    new_gainers.append(coin)
                    seen_alerts[symbol] = current_time
                    print(f"🚀 {coin['symbol']}: +{coin['price_change']:.2f}% (Цена: {coin['last_price']})")
                else:
                    print(f"⏭️ {coin['symbol']}: +{coin['price_change']:.2f}% (уже отправлено)")
            
            # Отправляем в Telegram только новые алерты
            if new_gainers:
                telegram_message = format_telegram_message(new_gainers)
                send_telegram_message(telegram_message)
            
            print("-" * 50)
        else:
            print("✅ Нет монет, удовлетворяющих условию.")
        
        # Очищаем старые записи из seen_alerts
        current_time = time.time()
        seen_alerts = {
            symbol: alert_time 
            for symbol, alert_time in seen_alerts.items() 
            if current_time - alert_time < ALERT_COOLDOWN
        }
            
        time.sleep(CHECK_INTERVAL)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n🛑 Бот остановлен пользователем.")
        if TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID:
            send_telegram_message("🛑 <b>Бот остановлен</b>\n\nМониторинг Binance деактивирован.")
    except Exception as e:
        error_msg = f"❌ Критическая ошибка: {e}"
        print(error_msg)
        if TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID:
            send_telegram_message(f"❌ <b>Ошибка бота!</b>\n\n{e}")
