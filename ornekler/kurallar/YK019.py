import logging

logger = logging.getLogger(__name__)


def isle(kayitlar):
    for k in kayitlar:
        logger.debug(f"İşleniyor: {k}")
        k.kaydet()
