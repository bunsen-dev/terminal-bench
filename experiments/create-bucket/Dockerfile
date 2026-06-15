FROM localstack/localstack:4.3

RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/*

RUN apt-get update && apt-get install -y python3 python3-pip && rm -rf /var/lib/apt/lists/*
RUN pip3 install pytest boto3==1.38.42 botocore==1.38.42

WORKDIR /app

RUN printf '#!/bin/sh\nexec awslocal "$@"\n' > /usr/local/bin/aws \
    && chmod +x /usr/local/bin/aws
