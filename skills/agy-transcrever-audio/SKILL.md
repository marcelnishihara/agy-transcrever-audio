---
name: agy-transcrever-audio
description: "Skill para transcrição de áudios via OpenAI Whisper (gpt-transcribe), com identificação de locutores e geração sincronizada de legendas SRT (padrão) e arquivos TXT. Exige confirmação prévia expressa do usuário antes de processar chamadas pagas."
---

# Skill: agy-transcrever-audio (v0.0.1)

Esta skill automatiza a transcrição de episódios de podcast, aulas, entrevistas e gravações individuais, formatando os diálogos entre interlocutores e gerando legendas `.srt` sincronizadas com estrita segurança de custos na OpenAI.

---

## ⚡ SINTAXE DE PROMPT PARAMETRIZADO (SLASH COMMAND)

O usuário pode invocar a skill de forma rápida e concisa no chat utilizando a sintaxe posicional:

### Sintaxe Geral:
```text
/agy-transcrever-audio <audio> <preset_ou_contexto> [participantes...] [--formato srt|txt|ambos] [--output caminho]
```

### Exemplos Práticos no Chat:

1. **Chamada Concisa com Preset:**
   ```text
   /agy-transcrever-audio audios/episodio_01.mp3 modelo
   ```
2. **Chamada Completa com Contexto e Participantes Diretos:**
   ```text
   /agy-transcrever-audio entrevista.wav "Debate sobre educação pública e metodologias ativas" "Entrevistador: Fulano de Tal" "Convidado: Sicrano da Silva"
   ```
3. **Chamada com Opção de Formato e Saída Customizada:**
   ```text
   /agy-transcrever-audio aula.mp3 "Aula inaugural de história" "Professor: Fulano" --formato ambos --output legendas/aula_final.srt
   ```
4. **Listar Presets Existentes:**
   ```text
   /agy-transcrever-audio --list-presets
   ```
   *(Ou simplesmente: "Quais presets de transcrição temos disponíveis?")*
5. **Criar um Novo Preset no Chat:**
   ```text
   /agy-transcrever-audio --novo-preset <nome>
   ```
   *(Ou: "Crie um preset chamado 'seminario' com o tema inteligência artificial e os participantes Fulano e Sicrano" -> O assistente cria o arquivo `presets/<nome>.json` formatado e pronto para reuso).*
6. **Checagem Rápida:**
   ```text
   /agy-transcrever-audio --check
   ```

Quando o assistente receber essa sintaxe posicional, ele deve extrair os parâmetros automaticamente, executar a pré-checagem (`--dry-run`), apresentar a estimativa de custo e aguardar o "Sim" do usuário para prosseguir.

---

## 🧭 DIRETRIZES DE INTERAÇÃO COM O USUÁRIO

Sempre que o usuário solicitar a transcrição de um áudio, o assistente deve seguir este fluxo conversacional:

1. **Identificar o Arquivo de Áudio:**
   - Solicitar o caminho do arquivo (caso não tenha sido informado). O áudio pode estar em qualquer pasta do computador.
2. **Contexto e Participantes (Flexibilidade):**
   - Perguntar se o usuário deseja usar um preset (ex: criado a partir de `presets/modelo.json`) OU se prefere informar os interlocutores e o contexto diretamente no chat.
3. **Local e Nome do Arquivo de Saída:**
   - Informar que, **por padrão, as legendas (.srt) e o texto (.txt) serão salvos no mesmo diretório do arquivo de áudio** com o mesmo nome base (ex: `audio.mp3` ➔ `audio.srt`).
   - **Perguntar expressamente se o usuário deseja especificar outro diretório de saída ou renomear o arquivo resultante** (usando a flag `--output`).
4. **Pré-Checagem Obrigatória de Segurança (`--dry-run`):**
   - Executar a simulação:
     ```bash
     python scripts/transcrever.py --audio <CAMINHO_AUDIO> --preset <PRESET> --dry-run
     ```
   - Apresentar o resumo: Duração (minutos), Tamanho (MB) e Custo estimado na OpenAI (~$0.006/min). Se já existir cache local, destacar que o custo será **$0.00**.
5. **Confirmação Expressa:**
   - Aguardar autorização inequívoca do usuário antes de rodar o comando real de transcrição.

---

## 🛠️ Comandos Disponíveis (`scripts/transcrever.py`)

### 1. Verificação Gratuita de Credenciais e Ambiente
```bash
python scripts/transcrever.py --check
```

### 2. Listagem de Presets Disponíveis
```bash
python scripts/transcrever.py --list-presets
```

### 3. Transcrição com Preset (Simulação e Execução)
```bash
# Simulação sem custo:
python scripts/transcrever.py --audio audios/episodio.mp3 --preset modelo --dry-run

# Execução real:
python scripts/transcrever.py --audio audios/episodio.mp3 --preset modelo
```

### 4. Transcrição com Parâmetros Diretos e Saída Customizada
```bash
python scripts/transcrever.py \
  --audio /caminho/entrevista.wav \
  --contexto "Discussão sobre educação pública e tecnologias." \
  --participante "Entrevistador: Fulano de Tal" \
  --participante "Convidada: Sicrana da Silva" \
  --formato ambos \
  --output /caminho/saidas/entrevista_final.srt
```
