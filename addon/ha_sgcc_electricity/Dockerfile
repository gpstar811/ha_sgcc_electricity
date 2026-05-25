ARG BUILD_FROM=ghcr.io/gpstar811/ha_sgcc_electricity:latest
FROM ${BUILD_FROM}

COPY run.sh /run.sh
RUN chmod a+x /run.sh

CMD ["/run.sh"]
