import logging

logger = logging.getLogger(__name__)


def isle(kayitlar):
    for k in kayitlar:
        logger.debug("İşleniyor: %s", k)
        k.kaydet()
