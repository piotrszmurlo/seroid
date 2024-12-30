FROM python:3.12

WORKDIR /app
COPY . /app

RUN pip install -r requirements.txt

RUN chmod +x main_run.py
CMD python -u main_run.py
