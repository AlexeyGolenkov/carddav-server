FROM python:3

WORKDIR /

COPY . .
RUN pip install --upgrade pip
RUN pip install -r requirements.txt

EXPOSE 8000

CMD echo 'Server is ready to use!' & ./ngrok start -config config.yml cds & python3 -m CDserver < log_info
