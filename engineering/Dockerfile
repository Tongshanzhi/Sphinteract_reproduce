ARG PYTHON_IMAGE=public.ecr.aws/docker/library/python:3.11-slim
FROM ${PYTHON_IMAGE}
WORKDIR /app
COPY engineering /app/engineering
COPY KaggleDBQA-main /app/KaggleDBQA-main
COPY databases /app/databases
COPY kaggle_dataset.csv /app/kaggle_dataset.csv
RUN pip install --no-cache-dir openai pandas numpy
ENV PROJECT_ROOT=/app
CMD ["python","-m","engineering.pipeline"]
