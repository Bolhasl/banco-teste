import sqlite3
import tkinter as tk
from tkinter import ttk, messagebox
from datetime import datetime, timedelta
import pandas as pd
import shutil
import os
import hashlib
from reportlab.pdfgen import canvas

# ----------------------------
# Configurações Globais
# ----------------------------
DB_NAME = 'estoque.db'
BACKUP_DIR = 'backups/'

# ----------------------------
# Banco de Dados
# ----------------------------
class BancoDados:
    def __init__(self):
        self.conn = sqlite3.connect(DB_NAME)
        self.criar_tabelas()
        self.criar_usuario_admin()
        self.criar_backup_dir()

    def criar_backup_dir(self):
        if not os.path.exists(BACKUP_DIR):
            os.makedirs(BACKUP_DIR)

    def criar_tabelas(self):
        queries = [
            """CREATE TABLE IF NOT EXISTS categorias (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nome TEXT UNIQUE NOT NULL)""",
                
            """CREATE TABLE IF NOT EXISTS produtos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nome TEXT UNIQUE NOT NULL,
                quantidade INTEGER NOT NULL,
                preco REAL NOT NULL,
                categoria_id INTEGER,
                data_atualizacao TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(categoria_id) REFERENCES categorias(id))""",
                
            """CREATE TABLE IF NOT EXISTS vendas (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                produto_id INTEGER NOT NULL,
                quantidade INTEGER NOT NULL,
                preco_venda REAL NOT NULL,
                data_venda TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(produto_id) REFERENCES produtos(id))""",
                
            """CREATE TABLE IF NOT EXISTS usuarios (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                usuario TEXT UNIQUE NOT NULL,
                senha TEXT NOT NULL,
                papel TEXT NOT NULL DEFAULT 'user')"""
        ]
        
        for query in queries:
            self.conn.execute(query)
        self.conn.commit()

    def criar_usuario_admin(self):
        senha_hash = self.hash_password('admin123')
        query = """INSERT OR IGNORE INTO usuarios (usuario, senha, papel) 
                   VALUES (?, ?, ?)"""
        self.conn.execute(query, ('admin', senha_hash, 'admin'))
        self.conn.commit()

    @staticmethod
    def hash_password(password):
        return hashlib.sha256(password.encode()).hexdigest()

    def backup(self):
        data = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_file = os.path.join(BACKUP_DIR, f'backup_{data}.db')
        shutil.copyfile(DB_NAME, backup_file)

# ----------------------------
# Modelos
# ----------------------------
class Produto:
    def __init__(self, id, nome, quantidade, preco, categoria=None):
        self.id = id
        self.nome = nome
        self.quantidade = quantidade
        self.preco = preco
        self.categoria = categoria

class Categoria:
    def __init__(self, id, nome):
        self.id = id
        self.nome = nome

class Venda:
    def __init__(self, id, produto_id, quantidade, preco, data):
        self.id = id
        self.produto_id = produto_id
        self.quantidade = quantidade
        self.preco = preco
        self.data = data

# ----------------------------
# Sistema Principal
# ----------------------------
class SistemaEstoque:
    def __init__(self):
        self.db = BancoDados()
        self.usuario_logado = None

    # Operações de Produtos
    def adicionar_produto(self, nome, quantidade, preco, categoria_id):
        query = """INSERT INTO produtos (nome, quantidade, preco, categoria_id)
                   VALUES (?, ?, ?, ?)"""
        try:
            self.db.conn.execute(query, (nome, quantidade, preco, categoria_id))
            self.db.conn.commit()
            return True
        except sqlite3.IntegrityError:
            return False

    def registrar_venda(self, produto_id, quantidade):
        with self.db.conn:
            # Verifica estoque
            produto = self.db.conn.execute(
                "SELECT quantidade, preco FROM produtos WHERE id = ?",
                (produto_id,)
            ).fetchone()
            
            if produto and produto[0] >= quantidade:
                # Atualiza estoque
                self.db.conn.execute(
                    "UPDATE produtos SET quantidade = quantidade - ? WHERE id = ?",
                    (quantidade, produto_id)
                )
                # Registra venda
                self.db.conn.execute(
                    "INSERT INTO vendas (produto_id, quantidade, preco_venda) VALUES (?, ?, ?)",
                    (produto_id, quantidade, produto[1])
                )
                return True
        return False

    # Categorias
    def adicionar_categoria(self, nome):
        query = "INSERT INTO categorias (nome) VALUES (?)"
        try:
            self.db.conn.execute(query, (nome,))
            self.db.conn.commit()
            return True
        except sqlite3.IntegrityError:
            return False

    # Relatórios
    def gerar_relatorio_vendas(self, data_inicio, data_fim):
        query = """SELECT v.data_venda, p.nome, v.quantidade, v.preco_venda 
                   FROM vendas v
                   JOIN produtos p ON v.produto_id = p.id
                   WHERE v.data_venda BETWEEN ? AND ?"""
        return self.db.conn.execute(query, (data_inicio, data_fim)).fetchall()

    # Exportação
    def exportar_excel(self, dados, nome_arquivo):
        df = pd.DataFrame(dados)
        df.to_excel(nome_arquivo, index=False)

    def exportar_pdf(self, dados, nome_arquivo):
        pdf = canvas.Canvas(nome_arquivo)
        y = 800
        for linha in dados:
            pdf.drawString(50, y, str(linha))
            y -= 20
        pdf.save()

    # Autenticação
    def login(self, usuario, senha):
        query = "SELECT senha, papel FROM usuarios WHERE usuario = ?"
        resultado = self.db.conn.execute(query, (usuario,)).fetchone()
        if resultado and resultado[0] == self.db.hash_password(senha):
            self.usuario_logado = {'usuario': usuario, 'papel': resultado[1]}
            return True
        return False

# ----------------------------
# Interface Gráfica
# ----------------------------
class Aplicacao(tk.Tk):
    def __init__(self, sistema):
        super().__init__()
        self.sistema = sistema
        self.title("Sistema de Estoque")
        self.geometry("800x600")
        
        self.criar_widgets_login()
        
    def criar_widgets_login(self):
        self.frame_login = ttk.Frame(self)
        
        ttk.Label(self.frame_login, text="Usuário:").grid(row=0, column=0)
        self.usuario_entry = ttk.Entry(self.frame_login)
        self.usuario_entry.grid(row=0, column=1)
        
        ttk.Label(self.frame_login, text="Senha:").grid(row=1, column=0)
        self.senha_entry = ttk.Entry(self.frame_login, show="*")
        self.senha_entry.grid(row=1, column=1)
        
        ttk.Button(self.frame_login, text="Login", 
                  command=self.efetuar_login).grid(row=2, columnspan=2)
        
        self.frame_login.pack(expand=True)

    def efetuar_login(self):
        if self.sistema.login(
            self.usuario_entry.get(),
            self.senha_entry.get()
        ):
            self.frame_login.destroy()
            self.criar_menu_principal()
        else:
            messagebox.showerror("Erro", "Credenciais inválidas")

    def criar_menu_principal(self):
        # Implementar interface completa com abas para:
        # - Gestão de Produtos
        # - Vendas
        # - Categorias
        # - Relatórios
        # - Backup
        # - Usuários (para admin)
        pass

# ----------------------------
# Rotina de Backup Automático
# ----------------------------
def realizar_backup():
    sistema = SistemaEstoque()
    sistema.db.backup()

# Agendar backup diário
if __name__ == '__main__':
    # Iniciar aplicação
    sistema = SistemaEstoque()
    app = Aplicacao(sistema)
    app.mainloop()
    
    # Agendar backup (executar em thread separada)
    realizar_backup()
