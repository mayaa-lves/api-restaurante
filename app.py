from flask import Flask, jsonify, request
import firebase_admin
from firebase_admin import credentials, firestore
from auth import token_obrigatorio, gerar_token
from flask_cors import CORS
import os
from dotenv import load_dotenv
import json
from flasgger import Swagger

load_dotenv()

app = Flask(__name__)

# Configuração do OpenAPI (Swagger)
app.config['SWAGGER'] = {
    'openapi': '3.0.0'
}
swagger = Swagger(app, template_file='openapi.yaml')

app.config['SECRET_KEY'] = os.getenv("SECRET_KEY")
CORS(app, origins="*")
ADM_USUARIO = os.getenv("ADM_USUARIO")
ADM_SENHA = os.getenv("ADM_SENHA")

# Configuração do Firebase
if os.getenv("VERCEL"):
    # ONLINE NA VERCEL
    cred = credentials.Certificate(json.loads(os.getenv("FIREBASE_CREDENTIALS")))
else:
    # LOCALHOST
    cred = credentials.Certificate("firebase.json")

firebase_admin.initialize_app(cred)
db = firestore.client()

# ==========================================
# ROTA RAIZ E LOGIN
# ==========================================
@app.route('/', methods=['GET'])
def root():
    return jsonify({
        "api": "artesanato_store",
        "version": "1.0",
        "author": "guilherme"
    }), 200

@app.route("/login", methods=["POST"])
def login():
    dados = request.get_json()

    if not dados:
        return jsonify({"Error": "Envie os dados para login"}), 400
    
    usuario = dados.get('usuario')
    senha = dados.get('senha')

    if not usuario or not senha:
        return jsonify({"Error": "Usuário e senha são obrigatórios!"}), 400
    
    if usuario == ADM_USUARIO and senha == ADM_SENHA:
        token = gerar_token(usuario)
        return jsonify({"message": "Login realizado com sucesso!", "token": token}), 200
    
    return jsonify({"Error": "Usuário ou senha inválidos"}), 401


# ==========================================
# ROTAS PÚBLICAS (Leitura)
# ==========================================

# 1. Listar todos os produtos
@app.route("/produtos", methods=['GET'])
def get_produtos():
    produtos = []
    lista = db.collection('produto').stream()

    for item in lista:
        produtos.append(item.to_dict())

    return jsonify(produtos), 200

# 2. Buscar produto por ID
@app.route("/produtos/<int:id>", methods=['GET'])
def get_produtos_by_id(id):
    docs = db.collection('produto').where('id', '==', id).limit(1).stream()

    for doc in docs:
        return jsonify(doc.to_dict()), 200
    
    return jsonify({"Error": "Produto não encontrado!"}), 404


# ==========================================
# ROTAS PRIVADAS (Requerem Token)
# ==========================================

# 3. Cadastrar novo produto
@app.route("/produtos", methods=['POST'])
@token_obrigatorio
def post_produtos():
    dados = request.get_json()
    
    campos_obrigatorios = ["nome", "estoque", "categoria", "ativo", "preco"]
    if not dados or not all(campo in dados for campo in campos_obrigatorios):
        return jsonify({"error": "Dados inválidos ou incompletos"}), 400
    
    try:
        # Busca o último ID no contador (Exatamente como no seu print do Firebase)
        contador_ref = db.collection("contador").document("controle_id")
        contador_doc = contador_ref.get()
        ultimo_id = contador_doc.to_dict().get("ultimo_id", 0)

        novo_id = ultimo_id + 1
        
        # Atualiza o contador
        contador_ref.update({"ultimo_id": novo_id})

        # Cadastra o produto
        db.collection("produto").add({
            "id": novo_id,
            "nome": dados["nome"],
            "categoria": dados["categoria"],
            "estoque": dados["estoque"],
            "preco": dados["preco"],
            "ativo": dados["ativo"]
        })

        return jsonify({"message": "Produto adicionado com sucesso!", "id": novo_id}), 201
    except Exception as e:
        return jsonify({"error": f"Falha na criação do produto: {str(e)}"}), 500

# 4. Alterar produto TOTALMENTE (PUT)
@app.route("/produtos/<int:id>", methods=['PUT'])
@token_obrigatorio
def produtos_put(id):
    dados = request.get_json()

    campos_obrigatorios = ["nome", "estoque", "categoria", "ativo", "preco"]
    if not dados or not all(campo in dados for campo in campos_obrigatorios):
        return jsonify({"error": "Dados inválidos ou incompletos"}), 400
    
    try:
        docs = db.collection("produto").where("id", "==", id).limit(1).get()
        if not docs:
            return jsonify({"error": "Produto não encontrado!"}), 404
        
        doc_ref = db.collection("produto").document(docs[0].id)
        doc_ref.update({
            "nome": dados["nome"],
            "categoria": dados["categoria"],
            "estoque": dados["estoque"],
            "preco": dados["preco"],
            "ativo": dados["ativo"]
        })

        return jsonify({"message": "Produto alterado com sucesso!"}), 200
    except Exception as e:   
        return jsonify({"error": f"Falha ao atualizar o produto: {str(e)}"}), 500

# 5. Alterar produto PONTUALMENTE (PATCH)
@app.route("/produtos/<int:id>", methods=['PATCH'])
@token_obrigatorio
def produtos_patch(id):
    dados = request.get_json()

    if not dados:
        return jsonify({"error": "Nenhum dado enviado para atualização"}), 400
    
    try:
        docs = db.collection("produto").where("id", "==", id).limit(1).get()
        if not docs:
            return jsonify({"error": "Produto não encontrado!"}), 404
        
        doc_ref = db.collection("produto").document(docs[0].id)
        
        # Filtra apenas os campos permitidos que vieram na requisição
        campos_permitidos = ["nome", "categoria", "estoque", "preco", "ativo"]
        update_data = {key: dados[key] for key in dados if key in campos_permitidos}

        if not update_data:
             return jsonify({"error": "Nenhum campo válido para atualizar"}), 400

        doc_ref.update(update_data)

        return jsonify({"message": "Produto atualizado com sucesso!"}), 200
    except Exception as e:   
        return jsonify({"error": f"Falha ao atualizar o produto: {str(e)}"}), 500

# 6. Excluir produto (DELETE)
@app.route("/produtos/<int:id>", methods=['DELETE'])
@token_obrigatorio
def produtos_delete(id):
    try:
        docs = db.collection("produto").where("id", "==", id).limit(1).get()

        if not docs:
            return jsonify({"erro": "Produto não encontrado!"}), 404
        
        doc_ref = db.collection("produto").document(docs[0].id)
        doc_ref.delete()
        
        return jsonify({"message": "Produto excluído com sucesso!"}), 200
    except Exception as e:
        return jsonify({"error": f"Falha ao excluir o produto: {str(e)}"}), 500


# ==========================================
# TRATAMENTO DE ERROS
# ==========================================
@app.errorhandler(404)
def error404(error):
    return jsonify({"error": "URL não encontrada!"}), 404

@app.errorhandler(500)
def error500(error):
    return jsonify({"error": "Servidor interno com falhas. Tente novamente mais tarde!"}), 500

if __name__ == "__main__":
    app.run(debug=True)