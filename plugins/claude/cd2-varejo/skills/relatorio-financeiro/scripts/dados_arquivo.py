#!/usr/bin/env python3
"""Leitor de arquivo exportado pelo ERP: coloca o arquivo num SQLite temporario.

So biblioteca padrao. Entende CSV (Windows-1252 ou UTF-8, ponto e virgula, virgula,
tab ou barra vertical) e XLSX (primeira planilha). Numero 1.234,56 e data dd/mm/aaaa
viram valor e data ISO. Linhas de subtotal e total geral vao para a tabela
<tabela>__totais e nunca somam na principal. CPF e mascarado ao carregar.

Uso:
  python3 dados_arquivo.py carregar --base B.sqlite ARQ [ARQ ...]
  python3 dados_arquivo.py consultar --base B.sqlite --sql "SELECT ..." [--limite 500]
  python3 dados_arquivo.py apagar --base B.sqlite

Erro: codigo de saida 2 e {"errors": [...]} em portugues.
"""
import argparse
import csv
import datetime
import io
import json
import re
import sqlite3
import sys
import unicodedata
import urllib.parse
import zipfile
import zlib
from pathlib import Path
from xml.etree import ElementTree as ET

LIMITE_BYTES = 200 * 1024 * 1024
LIMITE_XML_BYTES = 50 * 1024 * 1024
MAX_COLUNAS_XLSX = 16384
ASSINATURA_SQLITE = b"SQLite format 3\x00"
_ERROS_ZIP = (zipfile.BadZipFile, zlib.error, NotImplementedError, RuntimeError, OSError, EOFError)
LIMITE_LINHAS_PADRAO = 500
_DELIMITADORES = [";", "\t", "|", ","]
_RE_TOTAL = re.compile(
    r"^\s*(sub\s*-?\s*total(\s+.*)?|total|totais|soma|total\s+geral|total\s+d[aoe]s?\b.*)\s*:?\s*$",
    re.IGNORECASE)
_RE_CPF = re.compile(r"^\d{3}\.\d{3}\.\d{3}-\d{2}$")
_RE_DATA_BR = re.compile(r"^(\d{1,2})[/.-](\d{1,2})[/.-](\d{4}|\d{2})(?:[ T](\d{1,2}):(\d{2})(?::(\d{2}))?)?$")
_RE_DATA_ISO = re.compile(r"^(\d{4})-(\d{2})-(\d{2})(?:[ T](\d{1,2}):(\d{2})(?::(\d{2}))?)?$")
_RE_AGRUPADO = re.compile(r"^\d{1,3}(\.\d{3})+$")
_RE_TRES_CASAS = re.compile(r"^\d{1,3}\.\d{3}$")
_RE_MILHAR_MULTIPLO = re.compile(r"^\d{1,3}(\.\d{3}){2,}$")
_RE_CPF_SOLTO = re.compile(r"\b\d{3}\.\d{3}\.\d{3}-\d{2}\b")
_RE_CODIGO = re.compile(r"^(0\d+|\d{12,})$")


class ErroDados(Exception):
    """Erro para a pessoa: lista de mensagens em portugues."""

    def __init__(self, *erros):
        super().__init__("; ".join(erros))
        self.erros = list(erros)


def _sem_acento(texto: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFKD", texto) if not unicodedata.combining(c))


def _aspas(nome: str) -> str:
    return '"' + nome.replace('"', '""') + '"'


# --- leitura de CSV -------------------------------------------------------------------------------------

def detectar_csv(dados: bytes) -> tuple[str, str]:
    """Devolve (texto, delimitador). UTF-8 (com ou sem BOM) ou, se nao fechar, Windows-1252."""
    if dados.startswith(b"\xef\xbb\xbf"):
        dados = dados[3:]
    try:
        texto = dados.decode("utf-8")
    except UnicodeDecodeError:
        texto = dados.decode("cp1252", errors="replace")
    amostra = [l for l in texto.splitlines() if l.strip()][:20]
    melhor, melhor_nota = ",", (-1, 0, 0, 0)
    for prioridade, d in enumerate(_DELIMITADORES):
        try:
            larguras = [len(l) for l in csv.reader(amostra, delimiter=d)]
        except csv.Error:
            continue
        if not larguras:
            continue
        moda = max(set(larguras), key=lambda w: (larguras.count(w), w))
        nota = (1 if moda > 1 else 0, larguras.count(moda), moda, -prioridade)
        if nota > melhor_nota:
            melhor, melhor_nota = d, nota
    return texto, melhor


def _ler_csv(caminho: Path) -> list[list[str]]:
    texto, delim = detectar_csv(caminho.read_bytes())
    try:
        return [list(l) for l in csv.reader(io.StringIO(texto, newline=""), delimiter=delim)]
    except csv.Error as e:
        raise ErroDados(f"{caminho.name}: não consegui ler o CSV ({e}).")


# --- leitura de XLSX ------------------------------------------------------------------------------------

_FORMATOS_DATA = set(range(14, 23)) | set(range(27, 37)) | set(range(45, 48)) | set(range(50, 59))


def _xml(zf: zipfile.ZipFile, nome: str):
    with zf.open(nome) as f:
        bruto = f.read(LIMITE_XML_BYTES + 1)
    if len(bruto) > LIMITE_XML_BYTES:
        raise ErroDados("A planilha é grande demais para carregar. Exporte um período menor ou salve como CSV.")
    if b"<!DOCTYPE" in bruto[:2048].upper() or b"<!ENTITY" in bruto[:4096].upper():
        raise ErroDados("A planilha tem um formato que não aceitamos. Salve de novo como XLSX ou CSV.")
    return ET.fromstring(bruto)


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _filhos(no, nome):
    return [c for c in no if _local(c.tag) == nome]


def _texto_si(si) -> str:
    """Texto de um item de sharedStrings, somando os trechos e pulando o fonetico (rPh)."""
    partes = []

    def andar(no):
        for filho in no:
            nome = _local(filho.tag)
            if nome == "rPh":
                continue
            if nome == "t":
                partes.append(filho.text or "")
            else:
                andar(filho)

    andar(si)
    return "".join(partes)


def _formato_e_data(codigo: str) -> bool:
    limpo = re.sub(r'"[^"]*"|\[[^\]]*\]|\\.', "", codigo.lower())
    return bool(re.search(r"[dy]", limpo))


def _estilos_data(zf: zipfile.ZipFile) -> list[bool]:
    if "xl/styles.xml" not in zf.namelist():
        return []
    raiz = _xml(zf, "xl/styles.xml")
    custom = {}
    for nf in raiz.iter():
        if _local(nf.tag) == "numFmt":
            custom[int(nf.get("numFmtId", "0"))] = nf.get("formatCode", "")
    resultado = []
    for xfs in _filhos(raiz, "cellXfs"):
        for xf in _filhos(xfs, "xf"):
            fid = int(xf.get("numFmtId", "0"))
            resultado.append(fid in _FORMATOS_DATA or (fid in custom and _formato_e_data(custom[fid])))
    return resultado


def _planilhas(zf: zipfile.ZipFile) -> list[tuple[str, str]]:
    """[(nome, caminho dentro do zip)] na ordem do livro."""
    nomes = zf.namelist()
    if "xl/workbook.xml" not in nomes:
        raise ErroDados("O arquivo XLSX não parece uma planilha válida. Salve de novo como XLSX ou CSV.")
    livro = _xml(zf, "xl/workbook.xml")
    alvos = {}
    if "xl/_rels/workbook.xml.rels" in nomes:
        for rel in _xml(zf, "xl/_rels/workbook.xml.rels"):
            alvos[rel.get("Id")] = rel.get("Target", "")
    saida = []
    for sh in livro.iter():
        if _local(sh.tag) != "sheet":
            continue
        rid = next((v for k, v in sh.attrib.items() if _local(k) == "id"), None)
        alvo = alvos.get(rid, "")
        alvo = alvo.lstrip("/")
        caminho = alvo if alvo.startswith("xl/") else "xl/" + alvo
        saida.append((sh.get("name", ""), caminho))
    if not saida or saida[0][1] not in nomes:
        if "xl/worksheets/sheet1.xml" in nomes:
            return [(saida[0][0] if saida else "Planilha1", "xl/worksheets/sheet1.xml")] + saida[1:]
        raise ErroDados("Não achei dados na planilha. Salve como CSV e tente de novo.")
    return saida


def _coluna_indice(ref: str) -> int:
    letras = re.match(r"[A-Za-z]+", ref or "")
    if not letras:
        return -1
    n = 0
    for c in letras.group(0).upper():
        n = n * 26 + (ord(c) - 64)
    if n > MAX_COLUNAS_XLSX:
        raise ErroDados("A planilha tem referência de coluna fora do limite do Excel. "
                        "Salve de novo como XLSX ou como CSV.")
    return n - 1


def _numero_br(valor: str) -> str:
    """Numero do XLSX (ponto decimal) escrito com virgula, que o resto do leitor entende."""
    try:
        f = float(valor)
    except ValueError:
        return valor
    if f == int(f) and abs(f) < 1e15:
        return str(int(f))
    return repr(f).replace(".", ",")


def _data_serial(valor: str) -> str:
    f = float(valor)
    base = datetime.datetime(1899, 12, 30) + datetime.timedelta(days=f)
    if f == int(f):
        return base.date().isoformat()
    return base.replace(microsecond=0).isoformat(sep=" ")


def ler_xlsx(caminho: Path) -> list[list[str]]:
    """Linhas da primeira planilha como texto. Datas viram ISO; numeros usam virgula decimal."""
    try:
        zf = zipfile.ZipFile(caminho)
    except _ERROS_ZIP:
        raise ErroDados(f"{caminho.name}: não consegui abrir como XLSX. Salve de novo como XLSX ou como CSV.")
    with zf:
        try:
            planilhas = _planilhas(zf)
            compartilhadas = []
            if "xl/sharedStrings.xml" in zf.namelist():
                compartilhadas = [_texto_si(si) for si in _xml(zf, "xl/sharedStrings.xml") if _local(si.tag) == "si"]
            estilos = _estilos_data(zf)
            folha = _xml(zf, planilhas[0][1])
        except (ET.ParseError, KeyError, ValueError) + _ERROS_ZIP:
            raise ErroDados(f"{caminho.name}: a planilha está com defeito. Salve de novo como XLSX ou como CSV.")
    try:
        return _linhas_da_folha(folha, compartilhadas, estilos)
    except _ERROS_ZIP:
        raise ErroDados(f"{caminho.name}: a planilha está com defeito. Salve de novo como XLSX ou como CSV.")


def _linhas_da_folha(folha, compartilhadas, estilos) -> list[list[str]]:
    linhas = []
    for row in folha.iter():
        if _local(row.tag) != "row":
            continue
        celulas = {}
        proxima = 0
        for c in row:
            if _local(c.tag) != "c":
                continue
            idx = _coluna_indice(c.get("r", ""))
            idx = proxima if idx < 0 else idx
            proxima = idx + 1
            tipo = c.get("t", "n")
            v = next((x.text or "" for x in c if _local(x.tag) == "v"), "")
            if tipo == "s":
                try:
                    texto = compartilhadas[int(v)]
                except (ValueError, IndexError):
                    texto = ""
            elif tipo == "inlineStr":
                texto = "".join(t.text or "" for t in c.iter() if _local(t.tag) == "t")
            elif tipo == "b":
                texto = "1" if v == "1" else "0"
            elif tipo in ("str", "e"):
                texto = v
            else:
                estilo = int(c.get("s", "0") or 0)
                if v == "":
                    texto = ""
                elif estilo < len(estilos) and estilos[estilo]:
                    try:
                        texto = _data_serial(v)
                    except (ValueError, OverflowError):
                        texto = v
                else:
                    texto = _numero_br(v)
            celulas[idx] = texto
        if celulas:
            largura = max(celulas) + 1
            linhas.append([celulas.get(i, "") for i in range(largura)])
    return linhas


# --- normalizacao ---------------------------------------------------------------------------------------

def normalizar_numero(texto: str, ponto_milhar: bool | None = None) -> float | None:
    """Converte 1.234,56, (R$ 1.234,50), 12,5- em float. None se nao for numero.

    ponto_milhar: True trata ponto como milhar, False como decimal, None decide pelo valor.
    """
    t = str(texto).strip()
    if not t:
        return None
    negativo = False
    t = re.sub(r"R\$|%|\s| ", "", t)
    if t.startswith("(") and t.endswith(")"):
        negativo, t = True, t[1:-1]
    if t.endswith("-"):
        negativo, t = not negativo, t[:-1]
    elif t.startswith("-"):
        negativo, t = not negativo, t[1:]
    elif t.startswith("+"):
        t = t[1:]
    if not re.fullmatch(r"[\d.,]*\d[\d.,]*", t):
        return None
    pontos, virgulas = t.count("."), t.count(",")
    if virgulas and pontos:
        decimal = "," if t.rfind(",") > t.rfind(".") else "."
        outro = "." if decimal == "," else ","
        if t.count(decimal) != 1:
            return None
        t = t.replace(outro, "").replace(decimal, ".")
    elif virgulas:
        if virgulas != 1:
            return None
        t = t.replace(",", ".")
    elif pontos:
        if ponto_milhar is False:
            if pontos != 1:
                return None
        elif ponto_milhar is True and _RE_AGRUPADO.match(t):
            t = t.replace(".", "")
        elif pontos > 1:
            if not _RE_AGRUPADO.match(t):
                return None
            t = t.replace(".", "")
    try:
        valor = float(t)
    except ValueError:
        return None
    return -valor if negativo else valor


def normalizar_data(texto: str) -> str | None:
    """dd/mm/aaaa (ou aa, com / - .) e ISO viram aaaa-mm-dd; com hora, aaaa-mm-dd hh:mm:ss."""
    t = str(texto).strip()
    m = _RE_DATA_BR.match(t)
    if m:
        dia, mes, ano = int(m.group(1)), int(m.group(2)), m.group(3)
        ano = int(ano) + 2000 if len(ano) == 2 else int(ano)
        resto = m.groups()[3:]
    else:
        m = _RE_DATA_ISO.match(t)
        if not m:
            return None
        ano, mes, dia = int(m.group(1)), int(m.group(2)), int(m.group(3))
        resto = m.groups()[3:]
    try:
        data = datetime.date(ano, mes, dia)
    except ValueError:
        return None
    if resto[0] is None:
        return data.isoformat()
    try:
        hora = datetime.time(int(resto[0]), int(resto[1]), int(resto[2] or 0))
    except ValueError:
        return None
    return f"{data.isoformat()} {hora.isoformat()}"


def e_linha_total(celulas: list[str]) -> bool:
    """Subtotal, total geral e similares: rotulo nas 3 primeiras celulas e ao menos um numero."""
    rotulo = any(_RE_TOTAL.match(_sem_acento(str(c))) for c in celulas[:3])
    if not rotulo:
        return False
    return any(normalizar_numero(str(c)) is not None for c in celulas)


def nome_seguro(texto: str, usados: set[str]) -> str:
    """Nome de tabela ou coluna: minusculo, sem acento, so a-z0-9_, unico dentro de usados."""
    base = re.sub(r"[^a-z0-9]+", "_", _sem_acento(str(texto)).lower()).strip("_") or "col"
    if base[0].isdigit():
        base = "c_" + base
    if base.startswith("sqlite_"):
        base = "t_" + base
    nome, n = base, 2
    while nome in usados:
        nome = f"{base}_{n}"
        n += 1
    usados.add(nome)
    return nome


def _mascarar_cpf(valor: str) -> str:
    d = re.sub(r"\D", "", valor)
    return f"***.{d[3:6]}.{d[6:9]}-**"


def _mascarar_celula(celula: str, cabecalho: str) -> tuple[str, int]:
    """Mascara CPF na celula: coluna cpf com 11 digitos, ou CPF pontuado em qualquer trecho do texto."""
    if "cpf" in _sem_acento(cabecalho).lower() and re.fullmatch(r"\d{11}", celula):
        return _mascarar_cpf(celula), 1
    return _RE_CPF_SOLTO.subn(lambda m: _mascarar_cpf(m.group(0)), celula)


# --- carga ----------------------------------------------------------------------------------------------

def _ler_arquivo(caminho: Path, avisos: list[str]) -> list[list[str]]:
    if not caminho.is_file():
        raise ErroDados(f"Não achei o arquivo {caminho.name}. Confira o caminho.")
    if caminho.stat().st_size > LIMITE_BYTES:
        mb = LIMITE_BYTES // (1024 * 1024)
        raise ErroDados(f"{caminho.name} é grande demais (limite de {mb} MB). Exporte um período menor.")
    ext = caminho.suffix.lower()
    with caminho.open("rb") as f:
        assinatura = f.read(4)
    if ext == ".xls" or assinatura == b"\xd0\xcf\x11\xe0":
        raise ErroDados(f"{caminho.name} está no formato antigo do Excel (.xls). "
                        "Abra no Excel e salve como CSV ou XLSX, depois tente de novo.")
    if ext == ".xlsx" or assinatura[:2] == b"PK":
        try:
            with zipfile.ZipFile(caminho) as zf:
                outras = [n for n, _ in _planilhas(zf)[1:]]
        except (ET.ParseError, KeyError, ErroDados) + _ERROS_ZIP:
            outras = []
        linhas = ler_xlsx(caminho)
        if outras:
            with zipfile.ZipFile(caminho) as zf:
                primeira = _planilhas(zf)[0][0]
            avisos.append(f"{caminho.name} tem {len(outras) + 1} planilhas. Carreguei só a primeira "
                          f"({primeira}); salve as outras separadas se precisar delas.")
        return linhas
    if ext in (".csv", ".txt", ".tsv", ".prn", ""):
        return _ler_csv(caminho)
    raise ErroDados(f"{caminho.name}: formato {ext} não suportado. Envie CSV ou XLSX.")


def _limpo(valor: str) -> str:
    return re.sub(r"R\$|\s|\u00a0|[()+-]", "", valor)


def _inferir_coluna(nome_original: str, valores: list[str], avisos: list[str], arquivo: str):
    """Devolve (tipo, conversor). Valores sao os nao vazios, ja sem CPF.

    Coluna e numero quando ao menos 80% dos valores convertem; o resto vira vazio (NULL) com aviso.
    """
    if not valores:
        return "texto", None
    if all(normalizar_data(v) is not None for v in valores):
        return "data", lambda v: normalizar_data(v)
    if any(_RE_CODIGO.match(v.strip()) for v in valores):
        return "texto", None
    tem_virgula = any("," in v for v in valores)
    ponto_milhar = None
    if tem_virgula or any(_RE_MILHAR_MULTIPLO.match(_limpo(v)) for v in valores):
        ponto_milhar = True
    else:
        ambiguos = [v for v in valores if _RE_TRES_CASAS.match(_limpo(v))]
        if ambiguos:
            ponto_milhar = False
            avisos.append(
                f"Na coluna \"{nome_original}\" de {arquivo} há valores como {ambiguos[0]} (3 casas depois do "
                f"ponto) e nenhum valor da coluna tem vírgula. Tratei o ponto como decimal "
                f"({ambiguos[0]} = {normalizar_numero(ambiguos[0], False):g}). "
                "Se for milhar, confirme com a pessoa que exportou.")
    numeros = [normalizar_numero(v, ponto_milhar) for v in valores]
    boas = [n for n in numeros if n is not None]
    if not boas or len(boas) / len(numeros) < 0.8:
        return "texto", None
    falhas = [v for v, n in zip(valores, numeros) if n is None]
    if falhas:
        amostra = ", ".join(f"\"{v}\"" for v in falhas[:5])
        avisos.append(f"Na coluna \"{nome_original}\" de {arquivo}, {len(falhas)} valor(es) não são número e "
                      f"ficaram vazios: {amostra}.")
    if all(n == int(n) for n in boas):
        return "inteiro", lambda v: _como_inteiro(normalizar_numero(v, ponto_milhar))
    return "real", lambda v: normalizar_numero(v, ponto_milhar)


def _como_inteiro(n):
    return None if n is None else int(n)


def _estatisticas(tipo: str, valores: list):
    if not valores:
        return None, None, 0
    distintos = len(set(valores))
    if tipo in ("inteiro", "real", "data"):
        return min(valores), max(valores), distintos
    return None, None, distintos


def _carregar_um(con, caminho: Path, tabela: str, avisos: list[str]) -> dict:
    linhas = _ler_arquivo(caminho, avisos)
    linhas = [[str(c).strip() for c in l] for l in linhas]
    nao_vazias = [l for l in linhas if any(c for c in l)]
    if not nao_vazias:
        raise ErroDados(f"{caminho.name} está vazio.")
    candidato = next((i for i, l in enumerate(linhas) if sum(1 for c in l if c) >= 2), None)
    if candidato is None:
        candidato = next(i for i, l in enumerate(linhas) if any(l))
    cabecalho = linhas[candidato]
    largura = len(cabecalho)
    while largura > 1 and not cabecalho[largura - 1]:
        largura -= 1
    cabecalho = cabecalho[:largura]
    usados: set[str] = set()
    nomes = [nome_seguro(h or f"coluna_{i + 1}", usados) for i, h in enumerate(cabecalho)]
    originais = [h or f"coluna_{i + 1}" for i, h in enumerate(cabecalho)]
    dados = []
    for l in linhas[candidato + 1:]:
        if not any(l):
            continue
        l = (l + [""] * largura)[:largura]
        dados.append(l)

    # cabecalho repetido (paginacao do ERP)
    chave = [c.lower() for c in cabecalho]
    sem_repetidos = [l for l in dados if [c.lower() for c in l] != chave]
    if len(sem_repetidos) != len(dados):
        avisos.append(f"{caminho.name}: removi {len(dados) - len(sem_repetidos)} linha(s) que repetiam o "
                      "cabeçalho (paginação do relatório do ERP).")
    dados = sem_repetidos

    # CPF: coluna cpf com 11 digitos e CPF pontuado em qualquer trecho de texto
    mascarados = 0
    for l in dados:
        for i, c in enumerate(l):
            l[i], n = _mascarar_celula(c, originais[i])
            mascarados += n
    if mascarados:
        avisos.append(f"{caminho.name}: mascarei {mascarados} CPF ao carregar (ficam só os dígitos do meio).")
    for i in range(largura):
        preenchidos = [l[i] for l in dados if l[i]]
        if ("cpf" not in _sem_acento(originais[i]).lower() and preenchidos
                and sum(1 for v in preenchidos if re.fullmatch(r"\d{11}", v)) * 2 > len(preenchidos)):
            avisos.append(f"{caminho.name}: a coluna \"{originais[i]}\" tem valores de 11 dígitos que podem ser "
                          "CPF e não foram mascarados. Confirme com a pessoa e não repita esses números.")

    totais = [l for l in dados if e_linha_total(l)]
    principais = [l for l in dados if not e_linha_total(l)]

    tipos, conversores, colunas_perfil = [], [], []
    for i in range(largura):
        valores = [l[i] for l in principais if l[i] not in ("", "-")]
        tipo, conv = _inferir_coluna(originais[i], valores, avisos, caminho.name)
        tipos.append(tipo)
        conversores.append(conv)

    def converter(l, manter_texto=False):
        saida = []
        for i, c in enumerate(l):
            if c in ("", "-"):
                saida.append(None)
            elif conversores[i] is None:
                saida.append(c)
            else:
                v = conversores[i](c)
                numerico = tipos[i] in ("inteiro", "real")
                saida.append(c if v is None and (manter_texto or not numerico) else v)
        return saida

    sql_tipo = {"inteiro": "INTEGER", "real": "REAL", "data": "TEXT", "texto": "TEXT"}
    defs = ", ".join(f"{_aspas(n)} {sql_tipo[t]}" for n, t in zip(nomes, tipos))
    marcas = ", ".join("?" for _ in nomes)
    convertidas = [converter(l) for l in principais]
    con.execute(f"CREATE TABLE {_aspas(tabela)} ({defs})")
    con.executemany(f"INSERT INTO {_aspas(tabela)} VALUES ({marcas})", convertidas)
    if totais:
        con.execute(f"CREATE TABLE {_aspas(tabela + '__totais')} ({defs})")
        con.executemany(f"INSERT INTO {_aspas(tabela + '__totais')} VALUES ({marcas})", [converter(l, True) for l in totais])
        avisos.append(f"{caminho.name}: separei {len(totais)} linha(s) de total ou subtotal na tabela "
                      f"{tabela}__totais. Elas não entram nas somas de {tabela}.")

    for i in range(largura):
        col = [r[i] for r in convertidas]
        preenchidos = [v for v in col if v is not None]
        minimo, maximo, distintos = _estatisticas(tipos[i], preenchidos)
        vazios = 100.0 * (len(col) - len(preenchidos)) / len(col) if col else 0.0
        colunas_perfil.append({"nome": nomes[i], "original": originais[i], "tipo": tipos[i],
                               "vazios_pct": round(vazios, 1), "min": minimo, "max": maximo,
                               "distintos": distintos})
    if not principais:
        avisos.append(f"{caminho.name} tem só o cabeçalho, sem linhas de dados.")
    perfil = {"tabela": tabela, "arquivo": caminho.name, "linhas": len(principais),
              "linhas_total": len(totais), "colunas": colunas_perfil}
    if totais:
        perfil["tabela_totais"] = tabela + "__totais"
    return perfil


def carregar(arquivos: list[Path], base: Path) -> dict:
    """Carrega os arquivos numa base SQLite nova e devolve o perfil."""
    arquivos = [Path(a) for a in arquivos]
    if not arquivos:
        raise ErroDados("Informe pelo menos um arquivo para carregar.")
    base = Path(base)
    if any(a.resolve() == base.resolve() for a in arquivos):
        raise ErroDados("A base não pode ser o mesmo arquivo que você está carregando. Use outro caminho em --base.")
    apagar(base)
    avisos: list[str] = []
    if sqlite3.sqlite_version_info < (3, 25, 0):
        avisos.append(f"O SQLite desta máquina é o {sqlite3.sqlite_version}, anterior ao 3.25: "
                      "funções de janela (OVER) não funcionam. Use subconsultas.")
    sucesso = False
    con = None
    try:
        con = sqlite3.connect(str(base))
        usados: set[str] = set()
        tabelas = []
        for arq in arquivos:
            tabela = nome_seguro(arq.stem, usados)
            tabelas.append(_carregar_um(con, arq, tabela, avisos))
        con.commit()
        sucesso = True
    finally:
        if con is not None:
            con.close()
        if not sucesso:
            _remover_base(base)
    return {"sqlite": sqlite3.sqlite_version, "tabelas": tabelas, "avisos": avisos}


# --- consulta -------------------------------------------------------------------------------------------

_PERMITIDOS = {20, 21, 31, 33}  # READ, SELECT, FUNCTION, RECURSIVE


def _so_leitura(codigo, *_):
    return sqlite3.SQLITE_OK if codigo in _PERMITIDOS else sqlite3.SQLITE_DENY


def _esquema(con) -> dict[str, list[str]]:
    tabelas = [r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY rowid")]
    return {t: [c[1] for c in con.execute(f"PRAGMA table_info({_aspas(t)})")] for t in tabelas}


def _resumo_esquema(esquema: dict[str, list[str]]) -> str:
    return "; ".join(f"{t}({', '.join(cols)})" for t, cols in esquema.items())


def consultar(base: Path, sql: str, limite: int = LIMITE_LINHAS_PADRAO) -> dict:
    """Roda um SELECT na base, so leitura. Devolve colunas, linhas e se truncou."""
    base = Path(base)
    if not base.is_file():
        raise ErroDados("Não achei a base carregada. Rode o comando carregar antes de consultar.")
    if not str(sql).strip():
        raise ErroDados("Informe a consulta SQL.")
    con = None
    try:
        con = sqlite3.connect(f"file:{urllib.parse.quote(base.resolve().as_posix(), safe='/')}?mode=ro", uri=True)
        esquema = _esquema(con)
        con.execute("PRAGMA query_only=ON")
        con.set_authorizer(_so_leitura)
        try:
            cur = con.execute(sql)
            colunas = [d[0] for d in cur.description] if cur.description else []
            linhas = [list(r) for r in cur.fetchmany(limite + 1)]
        except (sqlite3.Error, sqlite3.Warning) as e:
            raise ErroDados(_traduzir_erro(str(e), esquema))
    except sqlite3.Error as e:
        raise ErroDados(f"Não consegui abrir a base: {e}")
    finally:
        if con is not None:
            con.close()
    truncado = len(linhas) > limite
    resultado = {"colunas": colunas, "linhas": linhas[:limite], "truncado": truncado}
    if truncado:
        resultado["avisos"] = [f"O resultado tem mais de {limite} linhas e foi cortado. "
                               "Agregue na consulta (GROUP BY) ou filtre para ver tudo."]
    return resultado


def _traduzir_erro(msg: str, esquema: dict[str, list[str]]) -> str:
    disponiveis = _resumo_esquema(esquema)
    m = re.match(r"no such column: (.+)", msg)
    if m:
        return f"A coluna {m.group(1)} não existe. Colunas disponíveis: {disponiveis}."
    m = re.match(r"no such table: (.+)", msg)
    if m:
        return f"A tabela {m.group(1)} não existe. Tabelas e colunas disponíveis: {disponiveis}."
    if "not authorized" in msg or "readonly" in msg or "read-only" in msg:
        return "Só consulta de leitura (SELECT ou WITH) é permitida na base carregada."
    if "one statement" in msg:
        return "Envie uma instrução SQL por vez."
    return f"Erro na consulta: {msg}"


def _e_base_sqlite(caminho: Path) -> bool:
    """Arquivo vazio (recem criado) ou com a assinatura do SQLite."""
    with caminho.open("rb") as f:
        inicio = f.read(len(ASSINATURA_SQLITE))
    return inicio == b"" or inicio == ASSINATURA_SQLITE


def _remover_base(base: Path) -> bool:
    apagou = False
    for sufixo in ("", "-wal", "-shm", "-journal"):
        arq = Path(str(base) + sufixo)
        if arq.is_file():
            arq.unlink()
            apagou = apagou or arq == base
    return apagou


def apagar(base: Path) -> dict:
    """Apaga a base e seus arquivos auxiliares. Recusa arquivo que nao seja uma base SQLite."""
    base = Path(base)
    if base.is_file() and not _e_base_sqlite(base):
        raise ErroDados(f"{base.name} não é uma base SQLite criada por este leitor. Não apaguei nada.")
    return {"apagado": _remover_base(base), "base": str(base)}


# --- linha de comando -----------------------------------------------------------------------------------

class _Parser(argparse.ArgumentParser):
    def error(self, message):
        raise ErroDados(f"Argumento inválido: {message}")


def _parser() -> argparse.ArgumentParser:
    p = _Parser(description="Leitor de arquivo exportado do ERP em SQLite temporário.")
    sub = p.add_subparsers(dest="comando", required=True, parser_class=_Parser)
    c = sub.add_parser("carregar")
    c.add_argument("--base", required=True)
    c.add_argument("arquivos", nargs="+")
    q = sub.add_parser("consultar")
    q.add_argument("--base", required=True)
    q.add_argument("--sql", required=True)
    q.add_argument("--limite", type=int, default=LIMITE_LINHAS_PADRAO)
    a = sub.add_parser("apagar")
    a.add_argument("--base", required=True)
    return p


def main(argv=None) -> int:
    try:
        args = _parser().parse_args(argv)
        if args.comando == "carregar":
            saida = carregar([Path(a) for a in args.arquivos], Path(args.base))
        elif args.comando == "consultar":
            if args.limite < 1:
                raise ErroDados("O limite precisa ser um número maior que zero.")
            saida = consultar(Path(args.base), args.sql, args.limite)
        else:
            saida = apagar(Path(args.base))
    except ErroDados as e:
        print(json.dumps({"errors": e.erros}, ensure_ascii=False))
        return 2
    except (sqlite3.Error, OSError) as e:
        print(json.dumps({"errors": [f"Não consegui concluir: {e}"]}, ensure_ascii=False))
        return 2
    print(json.dumps(saida, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
