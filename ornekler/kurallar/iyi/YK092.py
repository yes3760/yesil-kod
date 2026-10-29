from concurrent.futures import ThreadPoolExecutor


def raporlari_indir(s3, anahtarlar):
    def indir(anahtar):
        return s3.get_object(Bucket="raporlar", Key=anahtar)["Body"].read()

    with ThreadPoolExecutor(max_workers=16) as havuz:
        return list(havuz.map(indir, anahtarlar))
