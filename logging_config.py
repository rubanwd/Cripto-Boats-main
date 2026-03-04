import logging

logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s %(levelname)s %(message)s',
                    handlers=[
                        logging.FileHandler('trading_bot_derivatives.log', encoding='utf-8'),
                        logging.StreamHandler()
                    ])
