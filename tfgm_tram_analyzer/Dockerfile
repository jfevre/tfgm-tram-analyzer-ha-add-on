ARG BUILD_FROM
FROM $BUILD_FROM

WORKDIR /app

COPY requirements.txt .
RUN pip3 install --no-cache-dir -r requirements.txt

COPY tram_analyzer.py .
COPY api.py .

COPY rootfs /
RUN chmod a+x /etc/services.d/tfgm-tram-analyzer/run \
    && chmod a+x /etc/services.d/tfgm-tram-analyzer/finish

ENV PYTHONUNBUFFERED=1

EXPOSE 5001
