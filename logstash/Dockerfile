FROM docker.elastic.co/logstash/logstash:8.13.0

USER root

# NOTE: logstash-output-rabbitmq is already bundled in logstash-integration-rabbitmq
# (included with Logstash 8.x) — no install needed.


# # ── Download SQLite JDBC driver from Maven Central ──────────
# RUN mkdir -p /usr/share/logstash/drivers && \
#     curl -fsSL \
#       "https://repo1.maven.org/maven2/org/xerial/sqlite-jdbc/3.45.1.0/sqlite-jdbc-3.45.1.0.jar" \
#       -o /usr/share/logstash/drivers/sqlite-jdbc.jar && \
#     echo "SQLite JDBC driver downloaded ✓"



# ── Download MySQL Connector/J JDBC driver ──────────────────
RUN mkdir -p /usr/share/logstash/drivers && \
    curl -fsSL \
      "https://repo1.maven.org/maven2/com/mysql/mysql-connector-j/8.3.0/mysql-connector-j-8.3.0.jar" \
      -o /usr/share/logstash/drivers/mysql-connector-j.jar && \
    echo "MySQL JDBC driver downloaded ✓"

# ── Ensure data dir exists for JDBC state tracking ──────────
RUN mkdir -p /usr/share/logstash/data && \
    chown -R logstash:logstash /usr/share/logstash/data

# ── Remove the default sample pipeline ──────────────────────
RUN rm -f /usr/share/logstash/pipeline/logstash.conf

# ── Copy our config and pipeline ────────────────────────────
COPY config/logstash.yml /usr/share/logstash/config/logstash.yml
COPY pipeline/logstash.conf /usr/share/logstash/pipeline/logstash.conf

RUN chown logstash:logstash \
      /usr/share/logstash/config/logstash.yml \
      /usr/share/logstash/pipeline/logstash.conf

USER logstash
