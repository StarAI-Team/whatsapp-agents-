FROM python:3.12.7-slim

WORKDIR ./app

COPY worker.sh .

COPY . .

RUN chmod a+x worker.sh

RUN pip3 install --upgrade pip

RUN pip install --no-cache-dir -r requirements.txt

EXPOSE 8000

CMD ["./worker.sh", "--host=0.0.0.0"]