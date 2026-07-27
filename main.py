"""UF Print — thin entry point."""

import logging
import sys
import traceback

from ufprint.bootstrap import (
    ensure_runtime_or_exit,
    setup_early_logging,
    setup_qt_environment,
)

setup_early_logging()
logging.info("=" * 50)
logging.info("UF Print Application Starting")
logging.info(f"Platform: {sys.platform}")
logging.info(f"Python: {sys.version}")
logging.info(f"Executable: {getattr(sys, 'executable', 'unknown')}")
if hasattr(sys, "_MEIPASS"):
    logging.info(f"MEIPASS: {sys._MEIPASS}")
logging.info("=" * 50)

ensure_runtime_or_exit()
setup_qt_environment()

try:
    from PyQt5.QtWidgets import QApplication
    from ufprint.app_window import CardPrintingApp

    logging.info("All imports completed successfully")
except Exception as e:
    logging.error(f"Import failed: {str(e)}\n{traceback.format_exc()}")
    sys.exit(1)


if __name__ == "__main__":
    try:
        app = QApplication(sys.argv)
        window = CardPrintingApp()
        window.show()
        logging.info("Application window shown successfully")
        sys.exit(app.exec())
    except Exception as e:
        setup_early_logging()
        logging.error(f"Fatal error: {str(e)}\n\nTraceback:\n{traceback.format_exc()}")
        try:
            import ctypes

            ctypes.windll.user32.MessageBoxW(
                0,
                f"Не удалось запустить программу:\n\n{str(e)}\n\nПодробности в app_debug.log",
                "Ошибка запуска",
                0x10,
            )
        except Exception:
            pass
        sys.exit(1)
