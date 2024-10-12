FROM python:3.12

WORKDIR /code

COPY pyproject.toml poetry.lock .
RUN pip install poetry && poetry install --only main --no-root --no-directory
COPY src/ ./src
RUN poetry install --only main

CMD ["fastapi", "run", "src/main.py", "--port", "80"]
