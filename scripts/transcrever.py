"""Modulo de transcricao e geracao de legendas via OpenAI Whisper.

Este script processa um unico arquivo de audio por execucao,
utiliza contexto semantico customizado e identificacao de participantes,
gerando saidas nos formatos SRT, TXT ou ambos em estrita conformidade PEP 8.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Dict, List, Tuple

from dotenv import load_dotenv
from openai import (
    APIConnectionError,
    AuthenticationError,
    OpenAI,
    RateLimitError,
)

load_dotenv()


def verificar_ambiente_e_credenciais() -> None:
    """Valida ambiente virtual, bibliotecas, FFmpeg e chave da OpenAI."""
    print("Executando checagem completa de ambiente e credenciais...")

    # 1. Checagem do Ambiente Virtual (venv)
    em_venv = (
        hasattr(sys, "real_prefix")
        or (hasattr(sys, "base_prefix") and sys.base_prefix != sys.prefix)
    )
    if not em_venv:
        print(
            "\nAviso de ambiente: O script nao esta rodando em um venv "
            "ativo.\n"
            "Recomenda-se ativar o ambiente com: 'source venv/bin/activate'."
        )

    # 2. Checagem das bibliotecas Python requeridas
    dependencias_faltando: List[str] = []
    try:
        import openai  # noqa: F401
    except ImportError:
        dependencias_faltando.append("openai")

    try:
        import dotenv  # noqa: F401
    except ImportError:
        dependencias_faltando.append("python-dotenv")

    if dependencias_faltando:
        libs = ", ".join(dependencias_faltando)
        print(
            f"\nDependencias ausentes detectadas: {libs}.\n"
            "Como resolver: Execute no terminal:\n"
            "pip install -r requirements.txt"
        )
        sys.exit(1)

    # 3. Checagem do FFmpeg / ffprobe local
    ffmpeg_instalado = False
    try:
        res = subprocess.run(
            ["ffprobe", "-version"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=True,
        )
        ffmpeg_instalado = bool(res.stdout)
    except (subprocess.SubprocessError, FileNotFoundError):
        ffmpeg_instalado = False

    if not ffmpeg_instalado:
        print(
            "\nFalta uma dependencia do sistema operacional (FFmpeg).\n"
            "O utilitario ffprobe nao foi encontrado no sistema, impedindo "
            "o calculo de duracao e sincronizacao de legendas.\n"
            "Como resolver:\n"
            "- Linux (Ubuntu/Debian) : sudo apt install ffmpeg\n"
            "- macOS (Homebrew)      : brew install ffmpeg\n"
            "- Windows (Winget)      : winget install Gyan.FFmpeg"
        )
        sys.exit(1)

    # 4. Checagem da variavel de ambiente
    load_dotenv()
    chave_api = os.getenv("OPENAI_API_KEY")

    if not chave_api or not chave_api.strip() or chave_api == "sk-...":
        print(
            "\nFalha de autenticacao na OpenAI.\n"
            "A chave configurada no .env e invalida, foi revogada ou nao foi "
            "encontrada no ambiente.\n"
            "Como resolver: Gere uma nova chave em "
            "https://platform.openai.com/api-keys e atualize a variavel "
            "OPENAI_API_KEY no seu arquivo .env."
        )
        sys.exit(1)

    # 5. Validacao sem custos na API (List Models)
    try:
        cliente = OpenAI(api_key=chave_api)
        # client.models.list() e chamada de metadados gratuita (zero tokens)
        cliente.models.list()

        print(
            "\nTudo pronto! Ambiente e credenciais validados com sucesso!\n"
            "- Ambiente Virtual e Bibliotecas Python : OK\n"
            "- Suporte Multimidia Local (FFmpeg)    : OK\n"
            "- Autenticacao na API da OpenAI         : OK\n\n"
            "O modelo Whisper esta operacional para transcricoes.\n"
            "Nota sobre saldo: A OpenAI nao fornece saldo restante via API "
            "por seguranca. Para checar seus creditos em dolares, acesse:\n"
            "https://platform.openai.com/settings/organization/billing/"
            "overview"
        )
    except AuthenticationError:
        print(
            "\nFalha de autenticacao na OpenAI.\n"
            "A chave configurada no .env e invalida, foi revogada ou "
            "expirou.\n"
            "Como resolver: Gere uma nova chave no painel "
            "https://platform.openai.com/api-keys e atualize a variavel "
            "OPENAI_API_KEY no seu arquivo .env."
        )
        sys.exit(1)
    except RateLimitError as erro:
        mensagem = str(erro).lower()
        if "quota" in mensagem or "billing" in mensagem:
            print(
                "\nChave reconhecida, mas os creditos da conta estao "
                "esgotados.\n"
                "A OpenAI recusou o acesso por ausencia de saldo pre-pago ou "
                "limite mensal atingido (insufficient_quota).\n"
                "Como resolver: Adicione creditos pre-pagos a sua conta em "
                "https://platform.openai.com/settings/organization/"
                "billing/overview antes de transcrever novos audios."
            )
        else:
            print(
                f"\nLimite de taxa ou cota momentaneamente atingido: {erro}.\n"
                "Aguarde alguns instantes antes de enviar novas requisicoes."
            )
        sys.exit(1)
    except APIConnectionError:
        print(
            "\nErro de conexao com os servidores da OpenAI.\n"
            "Nao foi possivel estabelecer contato com a API da OpenAI. "
            "Verifique sua conexao de rede e tente novamente."
        )
        sys.exit(1)
    except Exception as e:
        print(
            f"\nRetorno inesperado da API ao validar chave: {e}\n"
            "Verifique o painel em https://platform.openai.com/ para detalhes."
        )
        sys.exit(1)


def obter_duracao_audio(caminho_audio: Path) -> float:
    """Obtem a duracao do audio em segundos utilizando ffprobe."""
    comando = [
        "ffprobe",
        "-v",
        "error",
        "-show_entries",
        "format=duration",
        "-of",
        "default=noprint_wrappers=1:nokey=1",
        str(caminho_audio),
    ]
    try:
        resultado = subprocess.run(
            comando,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=True,
        )
        return float(resultado.stdout.strip())
    except (subprocess.SubprocessError, ValueError):
        return 0.0


def carregar_dados_preset(
    identificador_preset: str | Path,
) -> Tuple[str, List[Dict[str, str]]]:
    """Carrega contexto e participantes a partir de preset local ou nativo."""
    caminho = Path(identificador_preset)

    # Se nao for caminho direto com .json, busca por nome na pasta presets
    if not caminho.is_file():
        nome = str(identificador_preset)
        if not nome.endswith(".json"):
            nome = f"{nome}.json"

        # 1. Busca no diretorio de execucao local
        candidato_local = Path("presets") / nome
        if candidato_local.is_file():
            caminho = candidato_local
        else:
            # 2. Busca na pasta presets relativa ao proprio script (plugin)
            diretorio_script = Path(__file__).resolve().parent.parent
            candidato_plugin = diretorio_script / "presets" / nome
            if candidato_plugin.is_file():
                caminho = candidato_plugin
            else:
                raise FileNotFoundError(
                    f"Preset '{identificador_preset}' nao encontrado em "
                    f"'{candidato_local}' nem em '{candidato_plugin}'."
                )

    with caminho.open("r", encoding="utf-8") as arquivo:
        dados = json.load(arquivo)

    contexto = dados.get("contexto", "").strip()
    participantes_brutos = dados.get("participantes", [])
    participantes = []

    for item in participantes_brutos:
        if isinstance(item, dict):
            papel = item.get("papel", "Participante")
            nome = item.get("nome", "Desconhecido")
            participantes.append({"papel": papel, "nome": nome})
        elif isinstance(item, str):
            partes = item.split(":", 1)
            papel = partes[0].strip() if len(partes) > 1 else "Participante"
            nome = partes[-1].strip()
            participantes.append({"papel": papel, "nome": nome})

    return contexto, participantes


def listar_presets_disponiveis() -> None:
    """Lista todos os arquivos de presets encontrados."""
    pastas = [
        Path("presets"),
        Path(__file__).resolve().parent.parent / "presets",
    ]
    presets_encontrados: Dict[str, Path] = {}

    for pasta in pastas:
        if pasta.is_dir():
            for arquivo in pasta.glob("*.json"):
                if arquivo.name not in presets_encontrados:
                    presets_encontrados[arquivo.stem] = arquivo

    print("\nPresets disponiveis:")
    if not presets_encontrados:
        print("  (Nenhum preset encontrado na pasta 'presets/')")
    else:
        for nome, caminho in sorted(presets_encontrados.items()):
            try:
                with caminho.open("r", encoding="utf-8") as f:
                    conteudo = json.load(f)
                desc = conteudo.get("descricao", "Sem descricao")
            except Exception:
                desc = "Arquivo de configuracao"
            print(f"  - {nome:15} : {desc} ({caminho})")
    print()


def formatar_timestamp_srt(segundos: float) -> str:
    """Formata valor em segundos no padrao SubRip (HH:MM:SS,mmm)."""
    horas = int(segundos // 3600)
    minutos = int((segundos % 3600) // 60)
    segs = int(segundos % 60)
    milisegundos = int(round((segundos - int(segundos)) * 1000))
    if milisegundos >= 1000:
        milisegundos = 999
    return f"{horas:02d}:{minutos:02d}:{segs:02d},{milisegundos:03d}"


def converter_dialogo_para_srt(
    texto_dialogo: str, duracao_total: float, caminho_saida_srt: Path
) -> None:
    """Converte texto com interlocutores em arquivo de legenda SRT."""
    paragrafos = [
        p.strip() for p in texto_dialogo.split("\n\n") if p.strip()
    ]
    blocos_legenda: List[str] = []
    ultimo_locutor: str | None = None

    for paragrafo in paragrafos:
        match_locutor = re.match(r"^\*\*(.*?)\*\*:?\s*(.*)", paragrafo)
        if match_locutor:
            locutor = match_locutor.group(1).rstrip(":").strip()
            fala = match_locutor.group(2).strip()
        else:
            locutor = None
            fala = paragrafo

        frases = re.split(r"(?<=[.?!])\s+", fala)
        for frase in frases:
            frase_limpa = frase.strip()
            if not frase_limpa:
                continue

            if len(frase_limpa) > 75:
                clausulas = re.split(r"(?<=[,;])\s+", frase_limpa)
                acumulado = ""
                for clausula in clausulas:
                    if len(acumulado) + len(clausula) < 75:
                        espaco = " " if acumulado else ""
                        acumulado += f"{espaco}{clausula}"
                    else:
                        if acumulado:
                            tag = (
                                f"[{locutor}] "
                                if locutor != ultimo_locutor
                                else ""
                            )
                            blocos_legenda.append(f"{tag}{acumulado}")
                            ultimo_locutor = locutor
                        acumulado = clausula
                if acumulado:
                    tag = (
                        f"[{locutor}] "
                        if locutor != ultimo_locutor
                        else ""
                    )
                    blocos_legenda.append(f"{tag}{acumulado}")
                    ultimo_locutor = locutor
            else:
                tag = (
                    f"[{locutor}] "
                    if locutor != ultimo_locutor
                    else ""
                )
                blocos_legenda.append(f"{tag}{frase_limpa}")
                ultimo_locutor = locutor

    total_caracteres = sum(len(b) for b in blocos_legenda) or 1
    tempo_atual = 0.5
    duracao_efetiva = max(duracao_total, 2.0)

    with caminho_saida_srt.open("w", encoding="utf-8") as arquivo_srt:
        for indice, bloco in enumerate(blocos_legenda, start=1):
            razao = len(bloco) / total_caracteres
            duracao_bloco = max(1.8, razao * (duracao_efetiva - 2.0))
            tempo_fim = min(duracao_efetiva, tempo_atual + duracao_bloco)
            ts_inicio = formatar_timestamp_srt(tempo_atual)
            ts_fim = formatar_timestamp_srt(tempo_fim)

            arquivo_srt.write(
                f"{indice}\n{ts_inicio} --> {ts_fim}\n{bloco}\n\n"
            )
            tempo_atual = tempo_fim + 0.1


def processar_transcricao(
    caminho_audio: Path,
    contexto: str,
    participantes: List[Dict[str, str]],
    formato: str,
    saida_customizada: Path | None = None,
) -> None:
    """Executa a transcricao e geracao das saidas especificadas."""
    cliente = OpenAI()

    # Definicao do destino e nome base dos arquivos de saida
    if saida_customizada:
        if saida_customizada.suffix:
            # O usuario especificou um arquivo completo (ex: /caminho/meu.srt)
            nome_base = saida_customizada.stem
            pasta_saida = saida_customizada.parent
        else:
            # O usuario especificou apenas um diretorio de saida
            nome_base = caminho_audio.stem
            pasta_saida = saida_customizada
    else:
        # Padrao: exatamente a mesma pasta e mesmo nome base do audio
        nome_base = caminho_audio.stem
        pasta_saida = caminho_audio.parent

    pasta_saida.mkdir(parents=True, exist_ok=True)
    caminho_txt = pasta_saida / f"{nome_base}.txt"
    caminho_srt = pasta_saida / f"{nome_base}.srt"

    # Verificacao de cache local para evitar custos repetidos
    if caminho_txt.is_file():
        print(f"[Cache] Utilizando transcricao pre-existente: {caminho_txt}")
        with caminho_txt.open("r", encoding="utf-8") as f:
            texto_formatado = f.read()
    else:
        print("[1/2] Enviando audio para Whisper (OpenAI: gpt-transcribe)...")
        with caminho_audio.open("rb") as f_audio:
            resposta_audio = cliente.audio.transcriptions.create(
                model="gpt-transcribe",
                file=f_audio,
                prompt=contexto,
            )

        texto_bruto = resposta_audio.text
        print(f"Transcricao bruta obtida ({len(texto_bruto)} caracteres).")

        descricao_participantes = "\n".join(
            f"- {p['papel']}: {p['nome']}" for p in participantes
        )
        prompt_sistema = (
            "Estruture o dialogo entre os participantes da entrevista.\n"
            "Use estritamente o formato:\n"
            "'**Nome do Participante:** [fala do participante]'\n"
            "Mantenha 100% da fidelidade ao texto original falado."
        )
        prompt_usuario = (
            f"Participantes:\n{descricao_participantes}\n\n"
            f"Contexto:\n{contexto}\n\n"
            f"Texto Transcrito:\n{texto_bruto}"
        )

        print("[Formatacao] Estruturando interlocutores...")
        resposta_chat = cliente.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": prompt_sistema},
                {"role": "user", "content": prompt_usuario},
            ],
            temperature=0.1,
        )
        texto_formatado = (
            resposta_chat.choices[0].message.content or ""
        ).strip()

    # 1. Geracao do formato textual (.txt) apenas quando solicitado
    if formato in ("txt", "ambos"):
        with caminho_txt.open("w", encoding="utf-8") as f:
            f.write(texto_formatado + "\n")
        print(f"[Salvo] Transcricao textual gravada: {caminho_txt}")

    # 2. Geracao do formato SRT (.srt) quando solicitado (padrao ou ambos)
    if formato in ("srt", "ambos"):
        print("[2/2] Gerando arquivo de legendas SRT sincronizadas...")
        duracao = obter_duracao_audio(caminho_audio)
        converter_dialogo_para_srt(texto_formatado, duracao, caminho_srt)
        print(f"[Salvo] Legenda gravada: {caminho_srt}")


def exibir_pre_checagem(
    caminho_audio: Path,
    contexto: str,
    participantes: List[Dict[str, str]],
    formato: str,
) -> None:
    """Exibe diagnostico e resumo antes de solicitar confirmacao."""
    duracao = obter_duracao_audio(caminho_audio)
    minutos = duracao / 60.0
    tamanho_mb = caminho_audio.stat().st_size / (1024 * 1024)
    estimativa_custo_usd = minutos * 0.006

    print("\n" + "=" * 65)
    print("RESUMO DA PRE-EXECUCAO (CONFIRMACAO DE RECURSOS)")
    print("=" * 65)
    print(f"Arquivo de audio   : {caminho_audio.name}")
    print(f"Caminho completo   : {caminho_audio.resolve()}")
    print(f"Tamanho do arquivo : {tamanho_mb:.2f} MB")
    print(f"Duracao estimada   : {duracao:.2f} s (~{minutos:.1f} min)")
    print(f"Custo est. Whisper : ~${estimativa_custo_usd:.3f} USD")
    print(f"Formato desejado   : {formato.upper()}")
    print(f"Interlocutores ({len(participantes)}):")
    for p in participantes:
        print(f"  - [{p['papel']}] {p['nome']}")
    print(f"Contexto semantico : {contexto[:120]}...")
    print("=" * 65 + "\n")


def parse_argumentos() -> argparse.Namespace:
    """Configura e valida os argumentos passados via CLI."""
    parser = argparse.ArgumentParser(
        description="Skill de Transcricao e Geracao de Legendas SRT."
    )
    parser.add_argument(
        "--audio",
        "-a",
        type=Path,
        default=None,
        help="Caminho do unico arquivo de audio a ser processado.",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Valida a chave da OpenAI e o ambiente sem custos.",
    )
    parser.add_argument(
        "--contexto",
        "-c",
        type=str,
        default=None,
        help="Contexto semantico do episodio.",
    )
    parser.add_argument(
        "--participante",
        "-p",
        action="append",
        default=[],
        help="Participante no formato 'Papel: Nome'. Aceita repeticao.",
    )
    parser.add_argument(
        "--preset",
        type=str,
        default=None,
        help="Nome ou caminho do preset JSON (ex: 'meu_preset' ou 'modelo').",
    )
    parser.add_argument(
        "--list-presets",
        action="store_true",
        help="Lista todos os presets disponiveis no ambiente.",
    )
    parser.add_argument(
        "--output",
        "-o",
        type=Path,
        default=None,
        help="Caminho alternativo de saida (diretorio ou nome customizado).",
    )
    parser.add_argument(
        "--formato",
        "-f",
        choices=["srt", "txt", "ambos"],
        default="srt",
        help="Formato de saida gerado. Padrao: srt.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Exibe apenas o resumo com estimativa de custo e encerra.",
    )
    return parser.parse_args()


def main() -> None:
    """Funcao principal de entrada do script CLI."""
    args = parse_argumentos()

    if args.list_presets:
        listar_presets_disponiveis()
        return

    if args.check:
        verificar_ambiente_e_credenciais()
        return

    caminho_audio: Path | None = args.audio
    if not caminho_audio:
        print(
            "Erro: O parametro --audio e obrigatorio para transcricao. "
            "Use --check para apenas validar o ambiente.",
            file=sys.stderr,
        )
        sys.exit(1)

    if not caminho_audio.is_file():
        print(
            f"Erro: Arquivo de audio nao encontrado: {caminho_audio}",
            file=sys.stderr,
        )
        sys.exit(1)

    contexto = args.contexto or ""
    participantes: List[Dict[str, str]] = []

    # Processamento de Preset ou Argumentos Diretos
    if args.preset:
        ctx_preset, part_preset = carregar_dados_preset(args.preset)
        if not contexto:
            contexto = ctx_preset
        if not participantes:
            participantes = part_preset

    for item in args.participante:
        partes = item.split(":", 1)
        papel = partes[0].strip() if len(partes) > 1 else "Participante"
        nome = partes[-1].strip()
        participantes.append({"papel": papel, "nome": nome})

    if not contexto:
        print(
            "Erro: O parametro de contexto e obrigatorio "
            "(via --contexto ou --preset).",
            file=sys.stderr,
        )
        sys.exit(1)

    if not participantes:
        print(
            "Erro: Ao menos um participante deve ser informado "
            "(via --participante ou --preset).",
            file=sys.stderr,
        )
        sys.exit(1)

    if args.dry_run:
        exibir_pre_checagem(
            caminho_audio, contexto, participantes, args.formato
        )
        print("Modo dry-run concluido. Nenhuma cobranca foi realizada.")
        return

    processar_transcricao(
        caminho_audio, contexto, participantes, args.formato, args.output
    )


if __name__ == "__main__":
    main()
