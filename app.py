from flask import Flask, render_template, request, redirect, url_for, session, jsonify
import json
import random
import os
import hashlib 
import requests 
import stripe 
from typing import Dict, Any
from random import choice 

# Chaves de Teste do Stripe
stripe.api_key = os.environ.get('STRIPE_SECRET_KEY', 'sk_teste_fallback')
STRIPE_PUBLISHABLE_KEY = os.environ.get('STRIPE_PUBLIC_KEY', 'pk_teste_fallback')
PRECO_ASSINATURA = 5000 

# Chaves de Teste do reCAPTCHA
RECAPTCHA_SITE_KEY = "6Leh9u4rAAAAAAxlfmXnziGXU2pZl8xNVKKwBNDk" 
RECAPTCHA_SECRET_KEY = os.environ.get('RECAPTCHA_SECRET_KEY', 'recap_teste_fallback')

# Configuracao do CAPTCHA de Caracteres
A = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
a = "abcdefghijklmnopqrstuvwxyz"
Num = "0123456789"

app = Flask(__name__)
app.secret_key = 'f15p06a78' 
USUARIOS_FILE = 'usuarios.json'

#FUNÇOES DE PERSISTENCIA E SEGURANÇA 

def carregar_usuarios() -> Dict[str, Any]:
    if not os.path.exists(USUARIOS_FILE):
        return {}
    try:
        with open(USUARIOS_FILE, 'r') as f:
            return json.load(f)
    except json.JSONDecodeError:
        return {}

def salvar_usuarios(usuarios: Dict[str, Any]):
    with open(USUARIOS_FILE, 'w') as f:
        json.dump(usuarios, f, indent=4)

def hash_senha(senha: str) -> str:
    return hashlib.sha256(senha.encode()).hexdigest()

def verificar_captcha_soma(resposta_usuario: str, valor_esperado: str) -> bool:
    return resposta_usuario == valor_esperado 

# FUNÇÕES CAPTCHA 

def gerar_captcha_na_sessao():
    captcha_string = ""
    for _ in range(2): 
        captcha_string += choice(A) + choice(a) + choice(Num)
    
    session['captcha_valor'] = captcha_string 

def get_captcha_soma() -> str:
    return session.get('captcha_valor', 'Erro: Recarregue')

def verificar_recaptcha_google(token_captcha: str) -> bool:
    GOOGLE_URL = "https://www.google.com/recaptcha/api/siteverify"
    
    dados = {
        'secret': RECAPTCHA_SECRET_KEY,
        'response': token_captcha
    }
    try:
        resposta = requests.post(GOOGLE_URL, data=dados)
        resultado = resposta.json()
        return resultado.get('success', False)
    except requests.exceptions.RequestException as e:
        print(f"Erro na requisição reCAPTCHA: {e}")
        return False

@app.route('/')
def index():
    if session.get('logado'):
        return redirect(url_for('home'))
    return render_template('site.html', pagina_ativa='index', site_key=RECAPTCHA_SITE_KEY, stripe_pk=STRIPE_PUBLISHABLE_KEY, preco=PRECO_ASSINATURA) 

@app.route('/login', methods=['GET'])
def exibir_login():
    gerar_captcha_na_sessao()
    return render_template('site.html', pagina_ativa='login', captcha=get_captcha_soma(), sucesso=request.args.get('sucesso'), site_key=RECAPTCHA_SITE_KEY, preco=PRECO_ASSINATURA)

@app.route('/cadastro', methods=['GET'])
def exibir_cadastro():
    gerar_captcha_na_sessao()
    return render_template('site.html', pagina_ativa='cadastro', site_key=RECAPTCHA_SITE_KEY, preco=PRECO_ASSINATURA)


@app.route('/login', methods=['POST'])
def processar_login():
    login = request.form.get('username')
    senha = request.form.get('password')
    
    if not login or not senha:
        gerar_captcha_na_sessao() 
        return render_template('site.html', pagina_ativa='login', erro="Por favor, preencha Usuário e Senha.", captcha=get_captcha_soma(), site_key=RECAPTCHA_SITE_KEY, preco=PRECO_ASSINATURA)

    usuarios = carregar_usuarios()
    hashed_senha_input = hash_senha(senha)

    if login in usuarios and usuarios[login]['senha'] == hashed_senha_input:
        session['logado'] = True
        session['username'] = login
        return redirect(url_for('home'))
    else:
        gerar_captcha_na_sessao()
        return render_template('site.html', pagina_ativa='login', erro="Usuário ou senha inválidos.", captcha=get_captcha_soma(), site_key=RECAPTCHA_SITE_KEY, preco=PRECO_ASSINATURA)


@app.route('/cadastro', methods=['POST'])
def processar_cadastro():
    login = request.form.get('username')
    senha = request.form.get('password')
    email = request.form.get('email')
    
    # Obter o token do reCAPTCHA do Google
    token_captcha = request.form.get('g-recaptcha-response')

    if not login or not senha or not email or not token_captcha:
        return render_template('site.html', pagina_ativa='cadastro', erro="Por favor, preencha todos os campos e marque o reCAPTCHA.", site_key=RECAPTCHA_SITE_KEY, preco=PRECO_ASSINATURA)

    # 1. Parte de validacao google
    if not verificar_recaptcha_google(token_captcha):
        return render_template('site.html', pagina_ativa='cadastro', erro="Falha na verificação de robô (reCAPTCHA). Tente novamente.", site_key=RECAPTCHA_SITE_KEY, preco=PRECO_ASSINATURA)

    # 2. verificacao de duplicidade e Save
    usuarios = carregar_usuarios()
    if login in usuarios:
        return render_template('site.html', pagina_ativa='cadastro', erro="Usuário já existe. Tente outro nome.", site_key=RECAPTCHA_SITE_KEY, preco=PRECO_ASSINATURA)
    
    usuarios[login] = {'senha': hash_senha(senha), 'status_assinatura': 'inativo', 'email': email}
    salvar_usuarios(usuarios)
    
    return redirect(url_for('exibir_login', sucesso="Cadastro realizado com sucesso! Faça login."))


@app.route('/pagamento/processar', methods=['POST'])
def processar_pagamento():
    if not session.get('logado'):
        #Se não estiver logado, volta para o login.
        return redirect(url_for('exibir_login')) 
    
    token_pagamento = request.form.get('stripeToken') 
    
    if not token_pagamento:
        return redirect(url_for('exibir_cobranca', erro="Erro: Token de pagamento não recebido."))

    try:
        # criacao da cobranca na stripe
        charge = stripe.Charge.create(
            amount=PRECO_ASSINATURA,
            currency="brl",
            description=f"Assinatura Premium - Usuário: {session['username']}",
            source=token_pagamento, 
        )

        # 2. sucesso = atulizar json
        if charge.paid:
            usuarios = carregar_usuarios()
            login = session['username']
            
            if login in usuarios:
                usuarios[login]['status_assinatura'] = 'ativo'
                salvar_usuarios(usuarios)
            
            # Redirecionar para a home
            
            return redirect(url_for('home', sucesso_pagamento='Assinatura ativada com sucesso!'))
        else:
            return redirect(url_for('exibir_cobranca', erro='Pagamento não autorizado. Tente outro cartão.'))

    except stripe.error.CardError as e:
        erro_msg = e.json_body.get('error', {}).get('message', 'Erro desconhecido no cartão.')
        return redirect(url_for('exibir_cobranca', erro=erro_msg))
        
    except Exception as e:
        print(f"ERRO CRÍTICO NO PAGAMENTO: {e}")
        return redirect(url_for('exibir_cobranca', erro='Erro interno no processamento.'))
    
@app.route('/home')
def home():
    if not session.get('logado'):
        return redirect(url_for('exibir_login'))
    
    usuarios = carregar_usuarios()
    usuario_atual = usuarios.get(session.get('username'), {}) 
    
    sucesso_pagamento = request.args.get('sucesso_pagamento')
    
    return render_template('site.html', pagina_ativa='dashboard', username=session.get('username'), status_assinatura=usuario_atual.get('status_assinatura', 'inativo'), stripe_pk=STRIPE_PUBLISHABLE_KEY, preco=PRECO_ASSINATURA, sucesso_pagamento=sucesso_pagamento)

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('exibir_login', sucesso="Sessão encerrada."))

@app.route('/assinatura')
def exibir_assinatura():
    if not session.get('logado'):
        return redirect(url_for('exibir_login'))
    return render_template('site.html', pagina_ativa='assinatura', stripe_pk=STRIPE_PUBLISHABLE_KEY, preco=PRECO_ASSINATURA)

@app.route('/cobranca')
def exibir_cobranca():
    if not session.get('logado'):
        return redirect(url_for('exibir_login'))
    
    erro = request.args.get('erro')
    sucesso = request.args.get('sucesso_pagamento')
    
    return render_template('site.html', pagina_ativa='cobranca', erro=erro, sucesso=sucesso, stripe_pk=STRIPE_PUBLISHABLE_KEY, preco=PRECO_ASSINATURA)


if __name__ == '__main__':
    if not os.path.exists(USUARIOS_FILE):
        salvar_usuarios({})
        
    app.run(debug=True)