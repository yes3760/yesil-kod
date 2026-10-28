def raporlari_indir(s3, anahtarlar):
    return [s3.get_object(Bucket="raporlar", Key=k)["Body"].read() for k in anahtarlar]
