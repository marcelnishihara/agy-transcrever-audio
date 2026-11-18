#!/usr/bin/env bash
# Script de instalacao e inicializacao rapida do transcrever-audio
set -e

echo "=== Instalando Skill agy-transcrever-audio (v0.0.1) ==="

# 1. Cria ambiente virtual se nao existir
if [ ! -d "venv" ]; then
    echo ">> Criando ambiente virtual Python (venv)..."
    python3 -m venv venv
fi

# 2. Ativa e instala dependencias
echo ">> Instalando dependencias minimas..."
./venv/bin/pip install --upgrade pip
./venv/bin/pip install -r requirements.txt

# 3. Configura .env a partir do .env.example se necessario
if [ ! -f ".env" ]; then
    echo ">> Criando arquivo .env a partir de .env.example..."
    cp .env.example .env
    echo "Lembre-se de configurar a sua OPENAI_API_KEY no arquivo .env!"
fi

echo ">> Validando instalacao..."
./venv/bin/python scripts/transcrever.py --check || true

echo "=== Instalacao concluida com sucesso! ==="
