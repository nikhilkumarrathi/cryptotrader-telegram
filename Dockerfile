# We will use Ubuntu for our image
FROM continuumio/anaconda3:5.3.0
COPY requirements.txt /
RUN pip install -r /requirements.txt

COPY . /app
WORKDIR /app

CMD [ "python", "bot.py" ]

