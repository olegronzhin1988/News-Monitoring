#!/bin/bash

# Rabbitmq-init.sh, forcefully changes user`s  pass after rabbitmq start
# Waiting for rabbitmq startup
until rabbitmqctl await_startup > /dev/null 2>&1; do
    sleep 1
done

# Waiting for user creation
until rabbitmqctl list_users | grep -q "^${RABBITMQ_DEFAULT_USER}\b"; do
    sleep 1
done

# Forcefully change password
rabbitmqctl change_password "${RABBITMQ_DEFAULT_USER}" "${RABBITMQ_DEFAULT_PASSWORD}"

echo "RabbitMQ password explicitly set for user ${RABBITMQ_DEFAULT_USER}"
