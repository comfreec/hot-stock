FROM python:3.11-slim

WORKDIR /app

# 한글 폰트 설치 (Nanum Gothic)
RUN apt-get update -qq && apt-get install -y --no-install-recommends \
    fonts-nanum fontconfig \
    && fc-cache -fv \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 7860

CMD ["streamlit", "run", "main_app.py", "--server.port=7860", "--server.address=0.0.0.0", "--server.headless=true", "--server.enableCORS=false"]
