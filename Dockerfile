# Usar uma imagem base oficial do Python
FROM python:3.11-slim

# Definir o diretório de trabalho no contêiner
WORKDIR /app

# Impedir que o Python armazene arquivos pyc em cache
ENV PYTHONDONTWRITEBYTECODE 1

# Garantir que a saída do Python seja exibida imediatamente
ENV PYTHONUNBUFFERED 1

# Copiar o arquivo de dependências
COPY requirements.txt .

# Instalar as dependências
RUN pip install --no-cache-dir -r requirements.txt

# Copiar o restante do código da aplicação
COPY . .

# Comando para executar a aplicação
CMD ["python", "main.py"]
