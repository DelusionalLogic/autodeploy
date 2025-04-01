from docker.io/python:3.13.2-alpine3.21
RUN apk add --no-cache uv git openssh docker-compose \
	&& mkdir /data /app
COPY github-publickey /etc/ssh/ssh_known_hosts

COPY . /app
WORKDIR /app

ENV WORKDIR /data
CMD [ "uv", "run", "/app/main.py" ]
