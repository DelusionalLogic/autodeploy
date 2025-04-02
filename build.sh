#!/bin/bash

set -euo pipefail

if [[ -z "${VERSION+x}" ]]; then
	echo "no VERSION provided"
	exit 1
fi

image_id="ghcr.io/delusionallogic/autodeploy"

docker build --annotation "org.opencontainers.image.source=https://github.com/delusionallogic/autodeploy" --tag "$image_id:$VERSION" .
docker tag "$image_id:$VERSION" "$image_id:latest"
docker push "$image_id:$VERSION"
docker push "$image_id:latest"
