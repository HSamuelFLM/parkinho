"""
Parkinho — Estacionamento com jeito de playground
Tecnologias: Python + Flask + SQLite + HTML/CSS
"""

from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from datetime import datetime, timedelta
import sqlite3
import os

app = Flask(__name__)
app.secret_key = "estacionamento-simples-2024"
DATABASE = os.path.join(os.path.dirname(__file__), "estacionamento.db")


# ============================================================
# BANCO DE DADOS
# ============================================================

def get_db():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    conn = get_db()
    cur = conn.cursor()

    # Clientes
    cur.execute("""
        CREATE TABLE IF NOT EXISTS clientes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT NOT NULL,
            documento TEXT,
            telefone TEXT,
            email TEXT,
            criado_em TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Veículos
    cur.execute("""
        CREATE TABLE IF NOT EXISTS veiculos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            cliente_id INTEGER,
            placa TEXT NOT NULL UNIQUE,
            marca TEXT,
            modelo TEXT,
            cor TEXT,
            tipo TEXT DEFAULT 'carro',      -- carro, moto, caminhao, van
            tamanho TEXT DEFAULT 'medio',   -- pequeno, medio, grande
            ano INTEGER,
            FOREIGN KEY (cliente_id) REFERENCES clientes(id)
        )
    """)

    # Vagas
    cur.execute("""
        CREATE TABLE IF NOT EXISTS vagas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            codigo TEXT NOT NULL UNIQUE,
            tipo TEXT NOT NULL DEFAULT 'normal',  -- normal, preferencial, pcd, eletrica
            status TEXT NOT NULL DEFAULT 'livre'  -- livre, ocupada
        )
    """)

    # Preços
    cur.execute("""
        CREATE TABLE IF NOT EXISTS precos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            descricao TEXT NOT NULL,
            tipo_cobranca TEXT NOT NULL,   -- hora, diaria, mensal, anual
            valor REAL NOT NULL,
            tipo_veiculo TEXT DEFAULT 'todos'  -- todos, carro, moto, etc
        )
    """)

    # Estacionamentos (entradas/saídas)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS estacionamentos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            veiculo_id INTEGER NOT NULL,
            vaga_id INTEGER NOT NULL,
            entrada TEXT NOT NULL,
            saida TEXT,
            valor_total REAL DEFAULT 0,
            status TEXT DEFAULT 'ativo',   -- ativo, finalizado
            observacao TEXT,
            FOREIGN KEY (veiculo_id) REFERENCES veiculos(id),
            FOREIGN KEY (vaga_id) REFERENCES vagas(id)
        )
    """)

    # Dados iniciais se estiver vazio
    cur.execute("SELECT COUNT(*) FROM vagas")
    if cur.fetchone()[0] == 0:
        vagas = []
        # Vagas normais
        for i in range(1, 21):
            vagas.append((f"N{i:02d}", "normal", "livre"))
        # Preferenciais
        for i in range(1, 6):
            vagas.append((f"P{i:02d}", "preferencial", "livre"))
        # PCD
        for i in range(1, 4):
            vagas.append((f"D{i:02d}", "pcd", "livre"))
        # Elétricas
        for i in range(1, 4):
            vagas.append((f"E{i:02d}", "eletrica", "livre"))
        cur.executemany("INSERT INTO vagas (codigo, tipo, status) VALUES (?, ?, ?)", vagas)

    # Preços: não cria padrões — o administrador gerencia pelo painel

    conn.commit()
    conn.close()


# ============================================================
# FUNÇÕES AUXILIARES
# ============================================================

def calcular_valor(entrada_str, saida_str, tipo_veiculo="carro"):
    """Calcula valor com base no tempo de permanência."""
    entrada = datetime.fromisoformat(entrada_str)
    saida = datetime.fromisoformat(saida_str)
    duracao = saida - entrada
    horas = max(1, int(duracao.total_seconds() // 3600) + (1 if duracao.total_seconds() % 3600 > 0 else 0))

    conn = get_db()
    # Busca preço por hora do tipo de veículo
    preco = conn.execute(
        "SELECT valor FROM precos WHERE tipo_cobranca = 'hora' AND (tipo_veiculo = ? OR tipo_veiculo = 'todos') LIMIT 1",
        (tipo_veiculo,)
    ).fetchone()
    conn.close()

    valor_hora = preco["valor"] if preco else 12.0

    # Se ficar mais de 8 horas, considera diária
    if horas >= 8:
        conn = get_db()
        preco_dia = conn.execute(
            "SELECT valor FROM precos WHERE tipo_cobranca = 'diaria' AND (tipo_veiculo = ? OR tipo_veiculo = 'todos') LIMIT 1",
            (tipo_veiculo,)
        ).fetchone()
        conn.close()
        valor_dia = preco_dia["valor"] if preco_dia else 60.0
        dias = max(1, horas // 24 + (1 if horas % 24 > 0 else 0))
        return round(dias * valor_dia, 2)

    return round(horas * valor_hora, 2)


# ============================================================
# ROTAS PRINCIPAIS
# ============================================================

@app.route("/")
def index():
    conn = get_db()
    stats = {
        "vagas_livres": conn.execute("SELECT COUNT(*) FROM vagas WHERE status = 'livre'").fetchone()[0],
        "vagas_ocupadas": conn.execute("SELECT COUNT(*) FROM vagas WHERE status = 'ocupada'").fetchone()[0],
        "total_vagas": conn.execute("SELECT COUNT(*) FROM vagas").fetchone()[0],
        "ativos": conn.execute("SELECT COUNT(*) FROM estacionamentos WHERE status = 'ativo'").fetchone()[0],
        "clientes": conn.execute("SELECT COUNT(*) FROM clientes").fetchone()[0],
        "veiculos": conn.execute("SELECT COUNT(*) FROM veiculos").fetchone()[0],
    }

    # Ocupações ativas
    ativos = conn.execute("""
        SELECT e.*, v.placa, v.marca, v.modelo, v.cor, v.tipo as tipo_veiculo,
               vg.codigo as vaga_codigo, vg.tipo as vaga_tipo,
               c.nome as cliente_nome
        FROM estacionamentos e
        JOIN veiculos v ON e.veiculo_id = v.id
        JOIN vagas vg ON e.vaga_id = vg.id
        LEFT JOIN clientes c ON v.cliente_id = c.id
        WHERE e.status = 'ativo'
        ORDER BY e.entrada DESC
    """).fetchall()

    # Resumo de vagas por tipo
    vagas_resumo = conn.execute("""
        SELECT tipo,
               SUM(CASE WHEN status = 'livre' THEN 1 ELSE 0 END) as livres,
               SUM(CASE WHEN status = 'ocupada' THEN 1 ELSE 0 END) as ocupadas,
               COUNT(*) as total
        FROM vagas
        GROUP BY tipo
    """).fetchall()

    conn.close()
    return render_template("index.html", stats=stats, ativos=ativos, vagas_resumo=vagas_resumo)


# -------------------- CLIENTES --------------------

@app.route("/clientes")
def listar_clientes():
    conn = get_db()
    clientes = conn.execute("SELECT * FROM clientes ORDER BY nome").fetchall()
    conn.close()
    return render_template("clientes.html", clientes=clientes)


@app.route("/clientes/novo", methods=["GET", "POST"])
def novo_cliente():
    if request.method == "POST":
        nome = request.form.get("nome", "").strip()
        documento = request.form.get("documento", "").strip()
        telefone = request.form.get("telefone", "").strip()
        email = request.form.get("email", "").strip()

        if not nome:
            flash("Nome é obrigatório.", "erro")
            return redirect(url_for("novo_cliente"))

        conn = get_db()
        conn.execute(
            "INSERT INTO clientes (nome, documento, telefone, email) VALUES (?, ?, ?, ?)",
            (nome, documento, telefone, email)
        )
        conn.commit()
        conn.close()
        flash("Cliente cadastrado com sucesso!", "sucesso")
        return redirect(url_for("listar_clientes"))

    return render_template("form_cliente.html", cliente=None)


@app.route("/clientes/editar/<int:id>", methods=["GET", "POST"])
def editar_cliente(id):
    conn = get_db()
    cliente = conn.execute("SELECT * FROM clientes WHERE id = ?", (id,)).fetchone()
    if not cliente:
        flash("Cliente não encontrado.", "erro")
        return redirect(url_for("listar_clientes"))

    if request.method == "POST":
        nome = request.form.get("nome", "").strip()
        documento = request.form.get("documento", "").strip()
        telefone = request.form.get("telefone", "").strip()
        email = request.form.get("email", "").strip()

        conn.execute(
            "UPDATE clientes SET nome=?, documento=?, telefone=?, email=? WHERE id=?",
            (nome, documento, telefone, email, id)
        )
        conn.commit()
        conn.close()
        flash("Cliente atualizado!", "sucesso")
        return redirect(url_for("listar_clientes"))

    conn.close()
    return render_template("form_cliente.html", cliente=cliente)


@app.route("/clientes/excluir/<int:id>", methods=["POST"])
def excluir_cliente(id):
    conn = get_db()
    cliente = conn.execute("SELECT * FROM clientes WHERE id = ?", (id,)).fetchone()
    if not cliente:
        flash("Cliente não encontrado.", "erro")
        conn.close()
        return redirect(url_for("listar_clientes"))

    # Desvincula veículos deste cliente (não apaga os veículos)
    conn.execute("UPDATE veiculos SET cliente_id = NULL WHERE cliente_id = ?", (id,))
    conn.execute("DELETE FROM clientes WHERE id = ?", (id,))
    conn.commit()
    conn.close()
    flash(f"Cliente \"{cliente['nome']}\" excluído com sucesso.", "sucesso")
    return redirect(url_for("listar_clientes"))



# -------------------- VEÍCULOS --------------------

@app.route("/veiculos")
def listar_veiculos():
    conn = get_db()
    busca = request.args.get("q", "").strip().upper().replace(" ", "").replace("-", "")

    if busca:
        veiculos = conn.execute("""
            SELECT v.*, c.nome as cliente_nome,
                   (SELECT COUNT(*) FROM estacionamentos e
                    WHERE e.veiculo_id = v.id AND e.status = 'ativo') as no_patio
            FROM veiculos v
            LEFT JOIN clientes c ON v.cliente_id = c.id
            WHERE v.placa LIKE ? OR v.marca LIKE ? OR v.modelo LIKE ?
            ORDER BY v.placa
        """, (f"%{busca}%", f"%{busca}%", f"%{busca}%")).fetchall()
    else:
        veiculos = conn.execute("""
            SELECT v.*, c.nome as cliente_nome,
                   (SELECT COUNT(*) FROM estacionamentos e
                    WHERE e.veiculo_id = v.id AND e.status = 'ativo') as no_patio
            FROM veiculos v
            LEFT JOIN clientes c ON v.cliente_id = c.id
            ORDER BY v.placa
        """).fetchall()

    conn.close()
    return render_template("veiculos.html", veiculos=veiculos, busca=busca)



@app.route("/veiculos/novo", methods=["GET", "POST"])
def novo_veiculo():
    conn = get_db()
    clientes = conn.execute("SELECT id, nome FROM clientes ORDER BY nome").fetchall()

    if request.method == "POST":
        placa = request.form.get("placa", "").strip().upper().replace(" ", "").replace("-", "")
        cliente_id = request.form.get("cliente_id") or None
        marca = request.form.get("marca", "").strip()
        modelo = request.form.get("modelo", "").strip()
        cor = request.form.get("cor", "").strip()
        tipo = request.form.get("tipo", "carro")
        tamanho = request.form.get("tamanho", "medio")
        ano = request.form.get("ano") or None

        if not placa:
            flash("Placa é obrigatória.", "erro")
            conn.close()
            return redirect(url_for("novo_veiculo"))

        try:
            conn.execute(
                """INSERT INTO veiculos (cliente_id, placa, marca, modelo, cor, tipo, tamanho, ano)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (cliente_id, placa, marca, modelo, cor, tipo, tamanho, ano)
            )
            conn.commit()
            flash("Veículo cadastrado com sucesso!", "sucesso")
            conn.close()
            return redirect(url_for("listar_veiculos"))
        except sqlite3.IntegrityError:
            flash("Placa já cadastrada.", "erro")
            conn.close()
            return redirect(url_for("novo_veiculo"))

    conn.close()
    return render_template("form_veiculo.html", veiculo=None, clientes=clientes)


@app.route("/veiculos/editar/<int:id>", methods=["GET", "POST"])
def editar_veiculo(id):
    conn = get_db()
    veiculo = conn.execute("SELECT * FROM veiculos WHERE id = ?", (id,)).fetchone()
    clientes = conn.execute("SELECT id, nome FROM clientes ORDER BY nome").fetchall()

    if not veiculo:
        flash("Veículo não encontrado.", "erro")
        conn.close()
        return redirect(url_for("listar_veiculos"))

    if request.method == "POST":
        placa = request.form.get("placa", "").strip().upper().replace(" ", "").replace("-", "")
        cliente_id = request.form.get("cliente_id") or None
        marca = request.form.get("marca", "").strip()
        modelo = request.form.get("modelo", "").strip()
        cor = request.form.get("cor", "").strip()
        tipo = request.form.get("tipo", "carro")
        tamanho = request.form.get("tamanho", "medio")
        ano = request.form.get("ano") or None

        try:
            conn.execute(
                """UPDATE veiculos SET cliente_id=?, placa=?, marca=?, modelo=?, cor=?, tipo=?, tamanho=?, ano=?
                   WHERE id=?""",
                (cliente_id, placa, marca, modelo, cor, tipo, tamanho, ano, id)
            )
            conn.commit()
            flash("Veículo atualizado!", "sucesso")
            conn.close()
            return redirect(url_for("listar_veiculos"))
        except sqlite3.IntegrityError:
            flash("Placa já cadastrada em outro veículo.", "erro")

    conn.close()
    return render_template("form_veiculo.html", veiculo=veiculo, clientes=clientes)


@app.route("/veiculos/excluir/<int:id>", methods=["POST"])
def excluir_veiculo(id):
    conn = get_db()
    veiculo = conn.execute("SELECT * FROM veiculos WHERE id = ?", (id,)).fetchone()
    if not veiculo:
        flash("Veículo não encontrado.", "erro")
        conn.close()
        return redirect(url_for("listar_veiculos"))

    # Não permite excluir se estiver no pátio
    ativo = conn.execute(
        "SELECT id FROM estacionamentos WHERE veiculo_id = ? AND status = 'ativo'",
        (id,)
    ).fetchone()
    if ativo:
        flash(f"O veículo {veiculo['placa']} está no pátio. Registre a saída antes de excluir.", "erro")
        conn.close()
        return redirect(url_for("listar_veiculos"))

    # Remove histórico de estacionamentos deste veículo para permitir exclusão
    # (ou bloqueia se tiver histórico — aqui optamos por manter histórico e bloquear)
    historico = conn.execute(
        "SELECT COUNT(*) FROM estacionamentos WHERE veiculo_id = ?", (id,)
    ).fetchone()[0]

    if historico > 0:
        flash(
            f"O veículo {veiculo['placa']} possui histórico de estacionamento e não pode ser excluído. "
            "Você pode editar os dados.",
            "erro"
        )
        conn.close()
        return redirect(url_for("listar_veiculos"))

    conn.execute("DELETE FROM veiculos WHERE id = ?", (id,))
    conn.commit()
    conn.close()
    flash(f"Veículo {veiculo['placa']} excluído.", "sucesso")
    return redirect(url_for("listar_veiculos"))


# -------------------- VAGAS --------------------

@app.route("/vagas")
def listar_vagas():
    conn = get_db()
    filtro = request.args.get("filtro", "todas")  # todas, livres, ocupadas
    vagas = conn.execute("SELECT * FROM vagas ORDER BY tipo, codigo").fetchall()

    # Agrupa por tipo
    grupos = {}
    for v in vagas:
        if filtro == "livres" and v["status"] != "livre":
            continue
        if filtro == "ocupadas" and v["status"] != "ocupada":
            continue
        grupos.setdefault(v["tipo"], []).append(v)

    resumo = {
        "total": len(vagas),
        "livres": sum(1 for v in vagas if v["status"] == "livre"),
        "ocupadas": sum(1 for v in vagas if v["status"] == "ocupada"),
    }
    por_tipo = conn.execute("""
        SELECT tipo,
               COUNT(*) as total,
               SUM(CASE WHEN status = 'livre' THEN 1 ELSE 0 END) as livres,
               SUM(CASE WHEN status = 'ocupada' THEN 1 ELSE 0 END) as ocupadas
        FROM vagas
        GROUP BY tipo
        ORDER BY tipo
    """).fetchall()

    conn.close()
    return render_template(
        "vagas.html",
        grupos=grupos,
        resumo=resumo,
        por_tipo=por_tipo,
        filtro=filtro,
    )



@app.route("/vagas/nova", methods=["GET", "POST"])
def nova_vaga():
    if request.method == "POST":
        codigo = request.form.get("codigo", "").strip().upper()
        tipo = request.form.get("tipo", "normal")

        if not codigo:
            flash("Código da vaga é obrigatório.", "erro")
            return redirect(url_for("nova_vaga"))

        conn = get_db()
        try:
            conn.execute("INSERT INTO vagas (codigo, tipo, status) VALUES (?, ?, 'livre')", (codigo, tipo))
            conn.commit()
            flash("Vaga criada com sucesso!", "sucesso")
        except sqlite3.IntegrityError:
            flash("Código de vaga já existe.", "erro")
        conn.close()
        return redirect(url_for("listar_vagas"))

    return render_template("form_vaga.html", vaga=None)


@app.route("/vagas/editar/<int:id>", methods=["GET", "POST"])
def editar_vaga(id):
    conn = get_db()
    vaga = conn.execute("SELECT * FROM vagas WHERE id = ?", (id,)).fetchone()
    if not vaga:
        flash("Vaga não encontrada.", "erro")
        conn.close()
        return redirect(url_for("listar_vagas"))

    if request.method == "POST":
        codigo = request.form.get("codigo", "").strip().upper()
        tipo = request.form.get("tipo", "normal")

        if not codigo:
            flash("Código da vaga é obrigatório.", "erro")
            conn.close()
            return redirect(url_for("editar_vaga", id=id))

        try:
            conn.execute("UPDATE vagas SET codigo=?, tipo=? WHERE id=?", (codigo, tipo, id))
            conn.commit()
            flash("Vaga atualizada!", "sucesso")
        except sqlite3.IntegrityError:
            flash("Código de vaga já existe.", "erro")
            conn.close()
            return redirect(url_for("editar_vaga", id=id))

        conn.close()
        return redirect(url_for("listar_vagas"))

    conn.close()
    return render_template("form_vaga.html", vaga=vaga)


@app.route("/vagas/excluir/<int:id>", methods=["POST"])
def excluir_vaga(id):
    conn = get_db()
    vaga = conn.execute("SELECT * FROM vagas WHERE id = ?", (id,)).fetchone()
    if not vaga:
        flash("Vaga não encontrada.", "erro")
        conn.close()
        return redirect(url_for("listar_vagas"))

    if vaga["status"] == "ocupada":
        flash("Não é possível excluir uma vaga ocupada. Finalize a saída primeiro.", "erro")
        conn.close()
        return redirect(url_for("listar_vagas"))

    # Verifica histórico
    uso = conn.execute(
        "SELECT COUNT(*) FROM estacionamentos WHERE vaga_id = ?", (id,)
    ).fetchone()[0]
    if uso > 0:
        flash("Esta vaga possui histórico e não pode ser excluída. Você pode apenas editá-la.", "erro")
        conn.close()
        return redirect(url_for("listar_vagas"))

    conn.execute("DELETE FROM vagas WHERE id = ?", (id,))
    conn.commit()
    conn.close()
    flash(f"Vaga {vaga['codigo']} excluída.", "sucesso")
    return redirect(url_for("listar_vagas"))


# -------------------- PREÇOS --------------------

@app.route("/precos")
def listar_precos():
    conn = get_db()
    precos = conn.execute("SELECT * FROM precos ORDER BY tipo_cobranca, tipo_veiculo").fetchall()
    conn.close()
    return render_template("precos.html", precos=precos)


@app.route("/precos/novo", methods=["GET", "POST"])
def novo_preco():
    if request.method == "POST":
        descricao = request.form.get("descricao", "").strip()
        tipo_cobranca = request.form.get("tipo_cobranca", "hora")
        valor = request.form.get("valor", "0").replace(",", ".")
        tipo_veiculo = request.form.get("tipo_veiculo", "todos")

        if not descricao:
            flash("Descrição é obrigatória.", "erro")
            return redirect(url_for("novo_preco"))

        try:
            valor = float(valor)
            if valor < 0:
                raise ValueError()
        except ValueError:
            flash("Valor inválido.", "erro")
            return redirect(url_for("novo_preco"))

        conn = get_db()
        conn.execute(
            "INSERT INTO precos (descricao, tipo_cobranca, valor, tipo_veiculo) VALUES (?, ?, ?, ?)",
            (descricao, tipo_cobranca, valor, tipo_veiculo)
        )
        conn.commit()
        conn.close()
        flash("Preço cadastrado!", "sucesso")
        return redirect(url_for("listar_precos"))

    return render_template("form_preco.html", preco=None)


@app.route("/precos/editar/<int:id>", methods=["GET", "POST"])
def editar_preco(id):
    conn = get_db()
    preco = conn.execute("SELECT * FROM precos WHERE id = ?", (id,)).fetchone()
    if not preco:
        flash("Preço não encontrado.", "erro")
        conn.close()
        return redirect(url_for("listar_precos"))

    if request.method == "POST":
        descricao = request.form.get("descricao", "").strip()
        tipo_cobranca = request.form.get("tipo_cobranca", "hora")
        valor = request.form.get("valor", "0").replace(",", ".")
        tipo_veiculo = request.form.get("tipo_veiculo", "todos")

        if not descricao:
            flash("Descrição é obrigatória.", "erro")
            conn.close()
            return redirect(url_for("editar_preco", id=id))

        try:
            valor = float(valor)
            if valor < 0:
                raise ValueError()
        except ValueError:
            flash("Valor inválido.", "erro")
            conn.close()
            return redirect(url_for("editar_preco", id=id))

        conn.execute(
            "UPDATE precos SET descricao=?, tipo_cobranca=?, valor=?, tipo_veiculo=? WHERE id=?",
            (descricao, tipo_cobranca, valor, tipo_veiculo, id)
        )
        conn.commit()
        conn.close()
        flash("Preço atualizado!", "sucesso")
        return redirect(url_for("listar_precos"))

    conn.close()
    return render_template("form_preco.html", preco=preco)


@app.route("/precos/excluir/<int:id>", methods=["POST"])
def excluir_preco(id):
    conn = get_db()
    preco = conn.execute("SELECT * FROM precos WHERE id = ?", (id,)).fetchone()
    if not preco:
        flash("Preço não encontrado.", "erro")
        conn.close()
        return redirect(url_for("listar_precos"))

    conn.execute("DELETE FROM precos WHERE id = ?", (id,))
    conn.commit()
    conn.close()
    flash(f"Preço \"{preco['descricao']}\" excluído.", "sucesso")
    return redirect(url_for("listar_precos"))


# -------------------- ENTRADA / SAÍDA --------------------

@app.route("/entrada", methods=["GET", "POST"])
def entrada():
    conn = get_db()
    veiculos = conn.execute("SELECT id, placa, marca, modelo FROM veiculos ORDER BY placa").fetchall()
    vagas_livres = conn.execute("SELECT id, codigo, tipo FROM vagas WHERE status = 'livre' ORDER BY tipo, codigo").fetchall()

    if request.method == "POST":
        veiculo_id = request.form.get("veiculo_id")
        vaga_id = request.form.get("vaga_id")
        placa_avulsa = request.form.get("placa_avulsa", "").strip().upper().replace(" ", "").replace("-", "")

        # Se veio placa avulsa, cadastra veículo rápido
        if placa_avulsa and not veiculo_id:
            try:
                cur = conn.execute(
                    "INSERT INTO veiculos (placa, tipo) VALUES (?, 'carro')",
                    (placa_avulsa,)
                )
                veiculo_id = cur.lastrowid
            except sqlite3.IntegrityError:
                # Já existe
                row = conn.execute("SELECT id FROM veiculos WHERE placa = ?", (placa_avulsa,)).fetchone()
                veiculo_id = row["id"]

        if not veiculo_id or not vaga_id:
            flash("Selecione veículo e vaga.", "erro")
            conn.close()
            return redirect(url_for("entrada"))

        # Verifica se veículo já está estacionado
        ativo = conn.execute(
            "SELECT id FROM estacionamentos WHERE veiculo_id = ? AND status = 'ativo'",
            (veiculo_id,)
        ).fetchone()
        if ativo:
            flash("Este veículo já está estacionado!", "erro")
            conn.close()
            return redirect(url_for("entrada"))

        # Verifica se vaga está livre
        vaga = conn.execute("SELECT status FROM vagas WHERE id = ?", (vaga_id,)).fetchone()
        if not vaga or vaga["status"] != "livre":
            flash("Vaga não está disponível.", "erro")
            conn.close()
            return redirect(url_for("entrada"))

        agora = datetime.now().isoformat(timespec="seconds")
        conn.execute(
            "INSERT INTO estacionamentos (veiculo_id, vaga_id, entrada, status) VALUES (?, ?, ?, 'ativo')",
            (veiculo_id, vaga_id, agora)
        )
        conn.execute("UPDATE vagas SET status = 'ocupada' WHERE id = ?", (vaga_id,))
        conn.commit()
        conn.close()
        flash("Entrada registrada com sucesso!", "sucesso")
        return redirect(url_for("index"))

    conn.close()
    return render_template("entrada.html", veiculos=veiculos, vagas_livres=vagas_livres)


@app.route("/saida", methods=["GET", "POST"])
def buscar_saida():
    """Busca veículo no pátio pela placa para registrar saída."""
    resultado = None
    placa_busca = ""

    if request.method == "POST":
        placa_busca = request.form.get("placa", "").strip().upper().replace(" ", "").replace("-", "")
        if placa_busca:
            conn = get_db()
            resultado = conn.execute("""
                SELECT e.id, e.entrada, v.placa, v.marca, v.modelo, v.cor,
                       vg.codigo as vaga_codigo, vg.tipo as vaga_tipo
                FROM estacionamentos e
                JOIN veiculos v ON e.veiculo_id = v.id
                JOIN vagas vg ON e.vaga_id = vg.id
                WHERE e.status = 'ativo' AND v.placa = ?
            """, (placa_busca,)).fetchone()
            conn.close()

            if resultado:
                return redirect(url_for("saida", id=resultado["id"]))
            flash(f"Nenhum veículo com a placa {placa_busca} está no pátio.", "erro")

    # Lista ativos para seleção rápida
    conn = get_db()
    ativos = conn.execute("""
        SELECT e.id, v.placa, v.marca, v.modelo, vg.codigo as vaga_codigo, e.entrada
        FROM estacionamentos e
        JOIN veiculos v ON e.veiculo_id = v.id
        JOIN vagas vg ON e.vaga_id = vg.id
        WHERE e.status = 'ativo'
        ORDER BY e.entrada DESC
    """).fetchall()
    conn.close()
    return render_template("buscar_saida.html", ativos=ativos, placa_busca=placa_busca)


@app.route("/saida/<int:id>", methods=["GET", "POST"])
def saida(id):
    conn = get_db()
    est = conn.execute("""
        SELECT e.*, v.placa, v.marca, v.modelo, v.tipo as tipo_veiculo, v.cor,
               vg.codigo as vaga_codigo, vg.tipo as vaga_tipo
        FROM estacionamentos e
        JOIN veiculos v ON e.veiculo_id = v.id
        JOIN vagas vg ON e.vaga_id = vg.id
        WHERE e.id = ? AND e.status = 'ativo'
    """, (id,)).fetchone()

    if not est:
        flash("Estacionamento não encontrado ou já finalizado.", "erro")
        conn.close()
        return redirect(url_for("buscar_saida"))

    agora = datetime.now().isoformat(timespec="seconds")
    valor_calculado = calcular_valor(est["entrada"], agora, est["tipo_veiculo"] or "carro")
    entrada_dt = datetime.fromisoformat(est["entrada"])
    tempo = datetime.now() - entrada_dt
    horas = tempo.days * 24 + tempo.seconds // 3600
    minutos = (tempo.seconds % 3600) // 60

    if request.method == "POST":
        # Valor flexível: usa o informado ou o calculado
        valor_str = request.form.get("valor", "").replace(",", ".").strip()
        desconto_str = request.form.get("desconto", "0").replace(",", ".").strip()
        observacao = request.form.get("observacao", "").strip()
        forma_pagamento = request.form.get("forma_pagamento", "dinheiro")

        try:
            valor = float(valor_str) if valor_str else valor_calculado
            if valor < 0:
                raise ValueError()
        except ValueError:
            flash("Valor inválido.", "erro")
            conn.close()
            return redirect(url_for("saida", id=id))

        try:
            desconto = float(desconto_str) if desconto_str else 0
            if desconto < 0:
                desconto = 0
            if desconto > 100:
                desconto = 100
        except ValueError:
            desconto = 0

        valor_final = round(valor * (1 - desconto / 100), 2)

        obs_parts = []
        if observacao:
            obs_parts.append(observacao)
        if desconto > 0:
            obs_parts.append(f"Desconto: {desconto:.0f}%")
        if forma_pagamento:
            obs_parts.append(f"Pagamento: {forma_pagamento}")
        obs_final = " | ".join(obs_parts) if obs_parts else None

        conn.execute(
            "UPDATE estacionamentos SET saida=?, valor_total=?, status='finalizado', observacao=? WHERE id=?",
            (agora, valor_final, obs_final, id)
        )
        conn.execute("UPDATE vagas SET status = 'livre' WHERE id = ?", (est["vaga_id"],))
        conn.commit()
        conn.close()
        flash(f"Saída registrada! Placa {est['placa']} — Valor: R$ {valor_final:.2f}", "sucesso")
        return redirect(url_for("index"))

    conn.close()
    return render_template(
        "saida.html",
        est=est,
        valor_atual=valor_calculado,
        tempo=tempo,
        horas=horas,
        minutos=minutos,
    )



# -------------------- RELATÓRIOS --------------------

@app.route("/relatorios")
def relatorios():
    periodo = request.args.get("periodo", "hoje")
    data_ini = request.args.get("data_ini", "")
    data_fim = request.args.get("data_fim", "")

    # Monta filtro de data
    filtro_sql = "e.status = 'finalizado'"
    params = []

    if periodo == "hoje":
        filtro_sql += " AND date(e.saida) = date('now')"
        periodo_label = "Hoje"
    elif periodo == "7dias":
        filtro_sql += " AND date(e.saida) >= date('now', '-6 days')"
        periodo_label = "Últimos 7 dias"
    elif periodo == "30dias":
        filtro_sql += " AND date(e.saida) >= date('now', '-29 days')"
        periodo_label = "Últimos 30 dias"
    elif periodo == "mes":
        filtro_sql += " AND strftime('%Y-%m', e.saida) = strftime('%Y-%m', 'now')"
        periodo_label = "Este mês"
    elif periodo == "tudo":
        periodo_label = "Todo o período"
    elif periodo == "custom" and data_ini and data_fim:
        filtro_sql += " AND date(e.saida) BETWEEN ? AND ?"
        params.extend([data_ini, data_fim])
        periodo_label = f"{data_ini} a {data_fim}"
    else:
        filtro_sql += " AND date(e.saida) = date('now')"
        periodo = "hoje"
        periodo_label = "Hoje"

    conn = get_db()

    # KPIs do período
    kpis = conn.execute(f"""
        SELECT
            COUNT(*) as qtd_saidas,
            COALESCE(SUM(e.valor_total), 0) as receita,
            COALESCE(AVG(e.valor_total), 0) as ticket_medio,
            COALESCE(MAX(e.valor_total), 0) as maior_ticket
        FROM estacionamentos e
        WHERE {filtro_sql}
    """, params).fetchone()

    # Ativos agora (não depende do período)
    no_patio = conn.execute(
        "SELECT COUNT(*) FROM estacionamentos WHERE status = 'ativo'"
    ).fetchone()[0]

    total_vagas = conn.execute("SELECT COUNT(*) FROM vagas").fetchone()[0]
    ocupacao = round((no_patio / total_vagas * 100), 1) if total_vagas else 0

    # Por tipo de vaga
    por_tipo = conn.execute(f"""
        SELECT vg.tipo, COUNT(*) as qtd, COALESCE(SUM(e.valor_total), 0) as total
        FROM estacionamentos e
        JOIN vagas vg ON e.vaga_id = vg.id
        WHERE {filtro_sql}
        GROUP BY vg.tipo
        ORDER BY total DESC
    """, params).fetchall()

    # Por tipo de veículo
    por_veiculo = conn.execute(f"""
        SELECT COALESCE(v.tipo, 'outro') as tipo, COUNT(*) as qtd,
               COALESCE(SUM(e.valor_total), 0) as total
        FROM estacionamentos e
        JOIN veiculos v ON e.veiculo_id = v.id
        WHERE {filtro_sql}
        GROUP BY v.tipo
        ORDER BY total DESC
    """, params).fetchall()

    # Receita por dia (para gráfico simples)
    por_dia = conn.execute(f"""
        SELECT date(e.saida) as dia, COUNT(*) as qtd,
               COALESCE(SUM(e.valor_total), 0) as total
        FROM estacionamentos e
        WHERE {filtro_sql}
        GROUP BY date(e.saida)
        ORDER BY dia
    """, params).fetchall()

    max_dia = max((r["total"] for r in por_dia), default=1) or 1

    # Histórico
    historico = conn.execute(f"""
        SELECT e.*, v.placa, v.marca, v.modelo, v.tipo as tipo_veiculo,
               vg.codigo as vaga_codigo, vg.tipo as vaga_tipo
        FROM estacionamentos e
        JOIN veiculos v ON e.veiculo_id = v.id
        JOIN vagas vg ON e.vaga_id = vg.id
        WHERE {filtro_sql}
        ORDER BY e.saida DESC
        LIMIT 100
    """, params).fetchall()

    conn.close()
    return render_template(
        "relatorios.html",
        periodo=periodo,
        periodo_label=periodo_label,
        data_ini=data_ini,
        data_fim=data_fim,
        kpis=kpis,
        no_patio=no_patio,
        ocupacao=ocupacao,
        total_vagas=total_vagas,
        por_tipo=por_tipo,
        por_veiculo=por_veiculo,
        por_dia=por_dia,
        max_dia=max_dia,
        historico=historico,
    )



# ============================================================
# INICIALIZAÇÃO
# ============================================================

if __name__ == "__main__":
    init_db()
    print("=" * 50)
    print("  Parkinho")
    print("  Acesse: http://127.0.0.1:5000")
    print("=" * 50)
    app.run(debug=True, host="0.0.0.0", port=5000)
